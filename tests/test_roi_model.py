"""Roi 資料模型單元測試。"""

from core.roi_model import GRID_COLS, GRID_ROWS, Roi, clamp_roi_to_bounds


class TestRoiFromDrag:
    def test_left_top_to_right_bottom(self):
        roi = Roi.from_drag(100, 50, 400, 250)
        assert (roi.x, roi.y, roi.width, roi.height) == (100, 50, 300, 200)

    def test_right_bottom_to_left_top(self):
        roi = Roi.from_drag(400, 250, 100, 50)
        assert (roi.x, roi.y, roi.width, roi.height) == (100, 50, 300, 200)

    def test_left_bottom_to_right_top(self):
        roi = Roi.from_drag(100, 250, 400, 50)
        assert (roi.x, roi.y, roi.width, roi.height) == (100, 50, 300, 200)

    def test_right_top_to_left_bottom(self):
        roi = Roi.from_drag(400, 50, 100, 250)
        assert (roi.x, roi.y, roi.width, roi.height) == (100, 50, 300, 200)

    def test_negative_screen_coords_allowed(self):
        # 多螢幕時虛擬桌面原點可為負
        roi = Roi.from_drag(-1920, -100, -100, 200)
        assert (roi.x, roi.y, roi.width, roi.height) == (-1920, -100, 1820, 300)


class TestRoiValidation:
    def test_valid_roi(self):
        assert Roi(x=0, y=0, width=150, height=100).is_valid()

    def test_zero_width_invalid(self):
        assert not Roi(x=0, y=0, width=0, height=100).is_valid()

    def test_zero_height_invalid(self):
        assert not Roi(x=0, y=0, width=150, height=0).is_valid()

    def test_negative_size_invalid(self):
        assert not Roi(x=0, y=0, width=-5, height=100).is_valid()

    def test_cell_size(self):
        cell = Roi(x=0, y=0, width=150, height=100).cell_size()
        assert cell is not None
        cw, ch = cell
        assert cw == 150 / GRID_COLS
        assert ch == 100 / GRID_ROWS

    def test_cell_size_invalid_returns_none(self):
        assert Roi(x=0, y=0, width=0, height=0).cell_size() is None


class TestClampRoiToBounds:
    def test_inside_bounds_unchanged(self):
        roi = Roi(x=10, y=10, width=100, height=50)
        clamped = clamp_roi_to_bounds(roi, 0, 0, 1000, 800)
        assert clamped == roi

    def test_crossing_left_edge_clamped(self):
        roi = Roi(x=-50, y=10, width=200, height=50)
        clamped = clamp_roi_to_bounds(roi, 0, 0, 1000, 800)
        assert (clamped.x, clamped.width) == (0, 150)
        assert clamped.is_valid()

    def test_crossing_right_edge_clamped(self):
        roi = Roi(x=950, y=10, width=200, height=50)
        clamped = clamp_roi_to_bounds(roi, 0, 0, 1000, 800)
        assert (clamped.x, clamped.width) == (950, 50)

    def test_crossing_top_edge_clamped(self):
        roi = Roi(x=10, y=-100, width=200, height=300)
        clamped = clamp_roi_to_bounds(roi, 0, 0, 1000, 800)
        assert (clamped.y, clamped.height) == (0, 200)

    def test_no_overlap_returns_invalid(self):
        roi = Roi(x=2000, y=10, width=100, height=50)
        clamped = clamp_roi_to_bounds(roi, 0, 0, 1000, 800)
        assert clamped.width == 0
        assert not clamped.is_valid()
