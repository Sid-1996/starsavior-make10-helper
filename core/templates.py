"""Template 系統：1~9 數字模板的儲存/載入，與辨識器分離。

設計原則：
- TemplateStore 只負責「模板檔案從哪裡來、長什麼樣子」：
  templates/1.png ... templates/9.png（灰階、大小一致）
- 它不做任何比對；比對交給 core/recognition.py
- 優先支援「從實際遊戲畫面建立/更新模板」：
  - save_template(digit, roi, cell) 會從最近一次擷取的 ROI 畫面
    切出該 cell 並存檔（需要呼叫端先提供畫面，Store 自己不讀螢幕）
- 一般使用者不需要每次啟動都重新設定模板：
  - 啟動時 load_all() 缺模板只會記錄缺失，不丟例外
  - 辨識器遇到缺模板就回 UNKNOWN，由呼叫端決定重試或等待

模板檔案格式：灰階 PNG。大小建議與實際 cell 接近（例如 62x62），
但不強制；讀入時會統一縮放到 TEMPLATE_SIZE 再比對。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from core.paths import resource_path

DIGITS = tuple(range(1, 10))
TEMPLATE_SIZE = (48, 48)  # (width, height)：所有模板統一比對尺寸

DEFAULT_TEMPLATES_DIR = resource_path("templates")


@dataclass
class TemplateSet:
    """一次載入的 1~9 模板集合；缺失的 digit 直接不存在。"""

    templates: dict[int, np.ndarray] = field(default_factory=dict)

    def has(self, digit: int) -> bool:
        return digit in self.templates

    def missing(self) -> list[int]:
        """回傳缺少的 digit 清單（例如 [4, 7]）。"""
        return [digit for digit in DIGITS if digit not in self.templates]

    def is_complete(self) -> bool:
        return not self.missing()


class TemplateStore:
    """模板檔案的讀寫；自己不擷取螢幕、不做比對。"""

    def __init__(self, templates_dir: Path | None = None) -> None:
        self.templates_dir = Path(templates_dir) if templates_dir else DEFAULT_TEMPLATES_DIR

    def template_path(self, digit: int) -> Path:
        if digit not in DIGITS:
            raise ValueError(f"模板只支援 1~9，收到 {digit}")
        return self.templates_dir / f"{digit}.png"

    def load_all(self) -> TemplateSet:
        """載入 templates/ 下所有可用模板；缺檔/壞檔一律跳過不丟例外。"""
        templates: dict[int, np.ndarray] = {}
        for digit in DIGITS:
            path = self.template_path(digit)
            if not path.is_file():
                continue
            image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if image is None or image.size == 0:
                continue
            templates[digit] = _normalize_template(image)
        return TemplateSet(templates=templates)

    def save_template(self, digit: int, cell_image: np.ndarray) -> Path:
        """從實際遊戲畫面切出的 cell 存成模板；回傳存檔路徑。

        cell_image: 單一 cell 的灰階畫面（任意尺寸，會統一縮放）。
        """
        if digit not in DIGITS:
            raise ValueError(f"模板只支援 1~9，收到 {digit}")
        if cell_image.ndim != 2 or cell_image.dtype != np.uint8:
            raise ValueError("模板必須是 2D uint8 灰階影像")
        if cell_image.size == 0:
            raise ValueError("模板影像不可為空")
        path = self.template_path(digit)
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized = _normalize_template(cell_image)
        if not cv2.imwrite(str(path), normalized):
            raise OSError(f"模板寫入失敗：{path}")
        return path


def _normalize_template(image: np.ndarray) -> np.ndarray:
    """統一縮放到 TEMPLATE_SIZE（灰階 uint8）。"""
    if image.shape[1] == TEMPLATE_SIZE[0] and image.shape[0] == TEMPLATE_SIZE[1]:
        return image.copy()
    return cv2.resize(image, TEMPLATE_SIZE, interpolation=cv2.INTER_AREA)
