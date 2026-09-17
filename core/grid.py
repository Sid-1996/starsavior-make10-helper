"""10x15 Grid 固定切割。

使用者框選的是完整的 10x15 數字棋盤區域，第一版採用固定切割：
ROI 的 width / 15、height / 10，直接建立 10 rows x 15 columns 共 150 cells。

邊界使用浮點數累加（roi.x + i * cell_w），避免 ROI 寬高無法整除時
（例如 934 / 15）的累積誤差；實際切圖時再取整。

產出的座標一律是實體螢幕像素，後續直接提供給 Overlay。
"""

from __future__ import annotations

from dataclasses import dataclass

from core.roi_model import GRID_COLS, GRID_ROWS, Roi


@dataclass(frozen=True)
class CellGeometry:
    """單一 cell 的螢幕幾何（實體像素，浮點邊界）。"""

    row: int
    column: int
    x: float  # 左緣
    y: float  # 上緣
    width: float
    height: float

    @property
    def x1(self) -> float:
        return self.x + self.width

    @property
    def y1(self) -> float:
        return self.y + self.height

    @property
    def center_x(self) -> float:
        """Overlay 建議的滑鼠操作點（起點/終點）。"""
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2

    def crop_box(self) -> tuple[int, int, int, int]:
        """取整後的 (x0, y0, x1, y1)，供 numpy 切片 [y0:y1, x0:x1] 使用。"""
        x0 = round(self.x)
        y0 = round(self.y)
        x1 = round(self.x1)
        y1 = round(self.y1)
        if x1 <= x0:
            x1 = x0 + 1
        if y1 <= y0:
            y1 = y0 + 1
        return (x0, y0, x1, y1)


def build_grid(roi: Roi) -> list[CellGeometry]:
    """將 ROI 固定切成 10x15 共 150 格，row-major 順序回傳。

    Row-major：第 0 格是左上 (row=0, col=0)，第 149 格是右下。
    """
    cell_w = roi.width / GRID_COLS
    cell_h = roi.height / GRID_ROWS
    cells: list[CellGeometry] = []
    for row in range(GRID_ROWS):
        for column in range(GRID_COLS):
            cells.append(
                CellGeometry(
                    row=row,
                    column=column,
                    x=roi.x + column * cell_w,
                    y=roi.y + row * cell_h,
                    width=cell_w,
                    height=cell_h,
                )
            )
    return cells
