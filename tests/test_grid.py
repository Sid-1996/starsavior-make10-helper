"""Grid 固定切割單元測試。"""

import pytest

from core.grid import build_grid
from core.roi_model import GRID_COLS, GRID_ROWS, Roi


class TestBuildGrid:
    def test_total_150_cells(self):
        cells = build_grid(Roi(x=0, y=0, width=150, height=100))
        assert len(cells) == GRID_ROWS * GRID_COLS == 150

    def test_row_major_order(self):
        cells = build_grid(Roi(x=0, y=0, width=150, height=100))
        assert (cells[0].row, cells[0].column) == (0, 0)
        assert (cells[14].row, cells[14].column) == (0, 14)
        assert (cells[15].row, cells[15].column) == (1, 0)
        assert (cells[149].row, cells[149].column) == (9, 14)

    def test_origin_and_cell_size(self):
        cells = build_grid(Roi(x=100, y=200, width=150, height=100))
        first = cells[0]
        assert first.x == 100
        assert first.y == 200
        assert first.width == pytest.approx(10.0)
        assert first.height == pytest.approx(10.0)

    def test_last_cell_reaches_roi_edge(self):
        # 最後一格右下邊界必須等於 ROI 右下（浮點精度內）
        roi = Roi(x=494, y=265, width=934, height=620)
        cells = build_grid(roi)
        last = cells[-1]
        assert last.x1 == pytest.approx(roi.x + roi.width)
        assert last.y1 == pytest.approx(roi.y + roi.height)

    def test_cells_are_contiguous(self):
        # 相鄰 cell 邊界連續：不重疊也不留縫（浮點精度內）
        roi = Roi(x=0, y=0, width=934, height=621)
        cells = build_grid(roi)
        for row in range(GRID_ROWS):
            for column in range(GRID_COLS - 1):
                left = cells[row * GRID_COLS + column]
                right = cells[row * GRID_COLS + column + 1]
                assert left.x1 == pytest.approx(right.x)
        for row in range(GRID_ROWS - 1):
            for column in range(GRID_COLS):
                top = cells[row * GRID_COLS + column]
                bottom = cells[(row + 1) * GRID_COLS + column]
                assert top.y1 == pytest.approx(bottom.y)

    def test_center_is_middle(self):
        cells = build_grid(Roi(x=0, y=0, width=150, height=100))
        first = cells[0]
        assert first.center_x == pytest.approx(5.0)
        assert first.center_y == pytest.approx(5.0)

    def test_crop_box_covers_roi_without_gap(self):
        # 取整後的 crop 框：同列相鄰 x1 == x0，同行相鄰 y1 == y0
        roi = Roi(x=494, y=265, width=934, height=620)
        cells = build_grid(roi)
        for row in range(GRID_ROWS):
            for column in range(GRID_COLS - 1):
                left = cells[row * GRID_COLS + column].crop_box()
                right = cells[row * GRID_COLS + column + 1].crop_box()
                assert left[2] == right[0]
        for row in range(GRID_ROWS - 1):
            for column in range(GRID_COLS):
                top = cells[row * GRID_COLS + column].crop_box()
                bottom = cells[(row + 1) * GRID_COLS + column].crop_box()
                assert top[3] == bottom[1]

    def test_crop_box_positive_size(self):
        roi = Roi(x=0, y=0, width=934, height=620)
        for cell in build_grid(roi):
            x0, y0, x1, y1 = cell.crop_box()
            assert x1 > x0
            assert y1 > y0
