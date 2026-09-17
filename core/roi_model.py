"""ROI（Region of Interest）資料模型與驗證。

兩種座標系：
- Roi：螢幕絕對座標（實體像素），管線（Grid / Overlay / mss 擷取）使用。
- RoiFrac：目標視窗客戶區「相對比例」（0~1），設定檔儲存用；
  視窗移動 / 換解析度後自動跟著走，啟動時換算成 Roi。
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


@dataclass(frozen=True)
class RoiFrac:
    """目標視窗客戶區內的相對辨識區域（比例 0~1）。

    視窗移動 / 換解析度後比例不變，啟動時以當下視窗尺寸換算成 Roi。
    """

    x: float
    y: float
    width: float
    height: float

    def is_valid(self) -> bool:
        return (
            self.width > 0
            and self.height > 0
            and 0 <= self.x < 1
            and 0 <= self.y < 1
            and self.x + self.width <= 1
            and self.y + self.height <= 1
        )

    def to_absolute(self, origin_x: int, origin_y: int, width: int, height: int) -> Roi:
        """以客戶區原點與尺寸換算成螢幕絕對 Roi（四捨五入）。"""
        return Roi(
            x=origin_x + round(self.x * width),
            y=origin_y + round(self.y * height),
            width=round(self.width * width),
            height=round(self.height * height),
        )

    @classmethod
    def from_absolute(
        cls, roi: Roi, origin_x: int, origin_y: int, width: int, height: int
    ) -> "RoiFrac":
        """由螢幕絕對 Roi 反推比例（框選後儲存用）；視窗尺寸無效時丟 ValueError。"""
        if width <= 0 or height <= 0:
            raise ValueError("視窗尺寸無效，無法換算比例")
        return cls(
            x=(roi.x - origin_x) / width,
            y=(roi.y - origin_y) / height,
            width=roi.width / width,
            height=roi.height / height,
        )


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


def rect_iou(first: Roi, second: Roi) -> float:
    """兩矩形的交併比（0~1）；任一無效回傳 0。"""
    if not first.is_valid() or not second.is_valid():
        return 0.0
    inter_left = max(first.x, second.x)
    inter_top = max(first.y, second.y)
    inter_right = min(first.x + first.width, second.x + second.width)
    inter_bottom = min(first.y + first.height, second.y + second.height)
    inter = max(0, inter_right - inter_left) * max(0, inter_bottom - inter_top)
    union = first.width * first.height + second.width * second.height - inter
    return inter / union if union > 0 else 0.0
