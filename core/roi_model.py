"""ROI（Region of Interest）資料模型與驗證。

ROI 代表使用者框選的 10x15 數字棋盤螢幕區域，
座標一律使用「實體螢幕像素」（與 mss 擷取座標一致）。
"""

from __future__ import annotations

from dataclasses import dataclass

GRID_ROWS = 10
GRID_COLS = 15


@dataclass(frozen=True)
class Roi:
    """螢幕上的矩形辨識區域（實體像素座標）。"""

    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_drag(cls, start_x: int, start_y: int, end_x: int, end_y: int) -> "Roi":
        """由任意方向拖曳的起訖兩點建立 ROI（自動正規化為左上原點）。"""
        return cls(
            x=min(start_x, end_x),
            y=min(start_y, end_y),
            width=abs(end_x - start_x),
            height=abs(end_y - start_y),
        )

    def is_valid(self) -> bool:
        """寬高皆需為正，且必須能切成 10x15 格。"""
        return self.width > 0 and self.height > 0

    def cell_size(self) -> tuple[float, float] | None:
        """回傳單一 cell 的 (寬, 高)，ROI 無效時回傳 None。"""
        if not self.is_valid():
            return None
        return self.width / GRID_COLS, self.height / GRID_ROWS


def clamp_roi_to_bounds(
    roi: Roi,
    bounds_left: int,
    bounds_top: int,
    bounds_width: int,
    bounds_height: int,
) -> Roi:
    """將 ROI 限制在螢幕（虛擬桌面）邊界內。

    若 ROI 與邊界完全沒有交集，回傳寬高為 0 的無效 ROI，
    由呼叫端透過 is_valid() 判斷。
    """
    right = min(roi.x + roi.width, bounds_left + bounds_width)
    bottom = min(roi.y + roi.height, bounds_top + bounds_height)
    left = max(roi.x, bounds_left)
    top = max(roi.y, bounds_top)
    width = max(0, right - left)
    height = max(0, bottom - top)
    return Roi(x=left, y=top, width=width, height=height)
