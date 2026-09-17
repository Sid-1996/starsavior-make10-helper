"""數字辨識：EMPTY 判斷 + Template Matching，保留 confidence。

流程（先 EMPTY、再 Template Matching；不用 OCR 猜空白）：
1. cell 畫面縮放到 TEMPLATE_SIZE
2. 先判斷是否為 EMPTY（白 tile 缺席 → EMPTY，見 _is_empty）
3. 有內容 → 對 1~9 模板做 normalized cross-correlation
4. 最高分 < threshold → UNKNOWN（不要硬猜）
5. 缺模板 → UNKNOWN

EMPTY 判定原理（實機量測）：
- 有數字 = 白 tile（亮部占比 ~0.5，黑字對比 std ~70）
- 已消除 = 深色 tile 洞（均值 ~97）或面板花紋（均值 ~120），亮部占比 = 0
- 因此「亮部占比低 + 對比不高」即 EMPTY；不再用面板均值推估
  （舊法在滿盤時把面板均值估成白 tile 亮度，導致消除格永遠判 UNKNOWN）。
- 輕微變暗的數字（std 仍高）不會被判 EMPTY，會進入 Template Matching
  （歸一化相關對線性亮度變化不敏感）；假設螢幕亮度恆定（與模板同機擷取）。

回傳 RecognitionResult，呼叫端（BoardBuilder）負責寫入 BoardState。
辨識器不讀螢幕、不碰 GUI。
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from core.templates import DIGITS, TEMPLATE_SIZE, TemplateSet

DEFAULT_MATCH_THRESHOLD = 0.75  # 最高分低於此 → UNKNOWN
DEFAULT_BRIGHT_LEVEL = 200.0  # 高於此亮度視為白 tile 像素
DEFAULT_BRIGHT_FRACTION = 0.15  # 亮部占比低於此 → 可能 EMPTY（數字格約 0.5）
DEFAULT_CONTENT_STD = 20.0  # 標準差高於此 → 有內容（數字格約 65+），不判 EMPTY


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
        bright_level: float = DEFAULT_BRIGHT_LEVEL,
        bright_fraction: float = DEFAULT_BRIGHT_FRACTION,
        content_std: float = DEFAULT_CONTENT_STD,
    ) -> None:
        self.templates = templates
        self.match_threshold = match_threshold
        self.bright_level = bright_level
        self.bright_fraction = bright_fraction
        self.content_std = content_std

    def recognize(self, cell_image: np.ndarray) -> RecognitionResult:
        """辨識單一 cell（灰階 uint8，任意尺寸）。"""
        if cell_image.ndim != 2 or cell_image.dtype != np.uint8:
            raise ValueError("cell_image 必須是 2D uint8 灰階影像")
        if cell_image.size == 0:
            return RecognitionResult(state="unknown", digit=None, confidence=0.0, scores={})
        normalized = self._normalize(cell_image)

        if self._is_empty(normalized):
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

    def _is_empty(self, normalized: np.ndarray) -> bool:
        # 沒有白 tile（亮部占比低）且對比不高 → 已消除的空格。
        # 對比高的一律視為有內容（交給 Template Matching 判斷，避免把變暗的數字判 EMPTY）。
        if float((normalized >= self.bright_level).mean()) >= self.bright_fraction:
            return False
        return float(normalized.std()) < self.content_std

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
