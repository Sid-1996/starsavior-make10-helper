"""數字辨識：EMPTY 判斷 + Template Matching，保留 confidence。

流程（先 EMPTY、再 Template Matching；不用 OCR 猜空白）：
1. cell 畫面縮放到 TEMPLATE_SIZE
2. 先判斷是否為 EMPTY（與面板底色的差異夠小 → EMPTY）
3. 有內容 → 對 1~9 模板做 normalized cross-correlation
4. 最高分 < threshold → UNKNOWN（不要硬猜）
5. 缺模板 → UNKNOWN

回傳 RecognitionResult，呼叫端（BoardBuilder）負責寫入 BoardState。
辨識器不讀螢幕、不碰 GUI。
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from core.templates import DIGITS, TEMPLATE_SIZE, TemplateSet

DEFAULT_MATCH_THRESHOLD = 0.75  # 最高分低於此 → UNKNOWN
DEFAULT_EMPTY_STD = 8.0  # cell 灰階標準差低於此 → EMPTY（接近素色面板）
DEFAULT_EMPTY_MEAN_MARGIN = 25.0  # 與面板底色平均值差異小於此 → EMPTY


@dataclass(frozen=True)
class RecognitionResult:
    """單一 cell 的辨識結果；state 只能是 DIGIT / EMPTY / UNKNOWN。"""

    state: str  # "digit" | "empty" | "unknown"
    digit: int | None  # state == "digit" 時為 1~9
    confidence: float  # 最高模板分數（0~1）；EMPTY/UNKNOWN 可為 0
    scores: dict[int, float]  # 每個 digit 的分數（除錯/測試用）


class DigitRecognizer:
    """Template Matching 數字辨識器（模板由外部 TemplateSet 注入）。"""

    def __init__(
        self,
        templates: TemplateSet,
        match_threshold: float = DEFAULT_MATCH_THRESHOLD,
        empty_std: float = DEFAULT_EMPTY_STD,
        empty_mean_margin: float = DEFAULT_EMPTY_MEAN_MARGIN,
    ) -> None:
        self.templates = templates
        self.match_threshold = match_threshold
        self.empty_std = empty_std
        self.empty_mean_margin = empty_mean_margin

    def recognize(
        self, cell_image: np.ndarray, panel_mean: float | None = None
    ) -> RecognitionResult:
        """辨識單一 cell（灰階 uint8，任意尺寸）。

        panel_mean: 面板底色的灰階平均值（EMPTY 參考）；沒給就只用標準差判斷。
        """
        if cell_image.ndim != 2 or cell_image.dtype != np.uint8:
            raise ValueError("cell_image 必須是 2D uint8 灰階影像")
        if cell_image.size == 0:
            return RecognitionResult(state="unknown", digit=None, confidence=0.0, scores={})
        normalized = self._normalize(cell_image)

        if self._is_empty(normalized, panel_mean):
            return RecognitionResult(state="empty", digit=None, confidence=0.0, scores={})
        if not self.templates.is_complete() and not self.templates.templates:
            # 完全沒有模板：不要硬猜，直接 UNKNOWN
            return RecognitionResult(state="unknown", digit=None, confidence=0.0, scores={})

        scores = self._match_all(normalized)
        if not scores:
            return RecognitionResult(state="unknown", digit=None, confidence=0.0, scores={})
        best_digit = max(scores, key=lambda digit: scores[digit])
        best_score = scores[best_digit]
        if best_score < self.match_threshold:
            return RecognitionResult(
                state="unknown", digit=None, confidence=best_score, scores=scores
            )
        return RecognitionResult(
            state="digit", digit=best_digit, confidence=best_score, scores=scores
        )

    def _normalize(self, cell_image: np.ndarray) -> np.ndarray:
        if cell_image.shape[1] == TEMPLATE_SIZE[0] and cell_image.shape[0] == TEMPLATE_SIZE[1]:
            return cell_image
        return cv2.resize(cell_image, TEMPLATE_SIZE, interpolation=cv2.INTER_AREA)

    def _is_empty(self, normalized: np.ndarray, panel_mean: float | None) -> bool:
        # 素色面板：標準差很小，且平均亮度接近面板底色
        if float(normalized.std()) >= self.empty_std:
            return False
        if panel_mean is None:
            # 沒有面板參考時：低對比可能是數字的一部分，不要硬判 EMPTY
            return False
        # 再確認平均亮度接近面板底色（避免把整片白/整片黑的異常當 EMPTY）
        return abs(float(normalized.mean()) - panel_mean) < self.empty_mean_margin

    def _match_all(self, normalized: np.ndarray) -> dict[int, float]:
        scores: dict[int, float] = {}
        needle = normalized.astype(np.float32)
        for digit in DIGITS:
            template = self.templates.templates.get(digit)
            if template is None:
                continue
            result = cv2.matchTemplate(needle, template.astype(np.float32), cv2.TM_CCOEFF_NORMED)
            scores[digit] = float(result[0][0])
        return scores
