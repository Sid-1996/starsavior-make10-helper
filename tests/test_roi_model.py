"""Roi 資料模型單元測試。"""

from core.roi_model import GRID_COLS, GRID_ROWS, Roi, RoiFrac, clamp_roi_to_bounds, rect_iou


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


class TestRoiFrac:
    def test_roundtrip_absolute(self):
        frac = RoiFrac(x=0.25, y=0.25, width=0.5, height=0.5)
        absolute = frac.to_absolute(100, 50, 1000, 800)
        assert absolute == Roi(x=350, y=250, width=500, height=400)
        back = RoiFrac.from_absolute(absolute, 100, 50, 1000, 800)
        assert back == frac

    def test_move_and_resize_follow_fractions(self):
        # 視窗從 1920x1080@(0,0) 搬到 2560x1440@(2560,0)：比例不變，絕對座標跟著走
        frac = RoiFrac.from_absolute(Roi(x=493, y=263, width=933, height=622), 0, 0, 1920, 1080)
        moved = frac.to_absolute(2560, 0, 2560, 1440)
        assert moved == Roi(x=2560 + 657, y=351, width=1244, height=829)

    def test_invalid_fraction(self):
        assert not RoiFrac(x=0.5, y=0.5, width=0.6, height=0.6).is_valid()  # 超出右下
        assert not RoiFrac(x=0.5, y=0.5, width=0, height=0.5).is_valid()
        assert RoiFrac(x=0, y=0, width=1, height=1).is_valid()

    def test_from_absolute_rejects_bad_window(self):
        import pytest

        with pytest.raises(ValueError):
            RoiFrac.from_absolute(Roi(x=0, y=0, width=10, height=10), 0, 0, 0, 1080)


class TestRectIou:
    def test_identical_is_one(self):
        roi = Roi(x=10, y=10, width=100, height=50)
        assert rect_iou(roi, roi) == 1.0

    def test_disjoint_is_zero(self):
        first = Roi(x=0, y=0, width=10, height=10)
        second = Roi(x=20, y=20, width=10, height=10)
        assert rect_iou(first, second) == 0.0

    def test_half_overlap(self):
        import pytest

        first = Roi(x=0, y=0, width=10, height=10)
        second = Roi(x=5, y=0, width=10, height=10)
        assert rect_iou(first, second) == pytest.approx(1 / 3)

    def test_invalid_is_zero(self):
        assert (
            rect_iou(Roi(x=0, y=0, width=0, height=10), Roi(x=0, y=0, width=10, height=10)) == 0.0
        )
