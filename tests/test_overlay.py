"""Hint Overlay 測試（offscreen 平台；幾何純函式 + 視窗行為 + 渲染冒煙）。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

import numpy as np  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QColor, QImage  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.grid import build_grid  # noqa: E402
from core.roi_model import Roi  # noqa: E402
from core.solver import Rectangle  # noqa: E402
from gui.hint_overlay import HintOverlay, hint_shapes  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from core.i18n import set_language

    set_language("zh")  # UI 斷言以繁中為準，不隨系統語言浮動
    app = QApplication.instance() or QApplication([])
    yield app


def _grid() -> list:
    return build_grid(Roi(x=0, y=0, width=150, height=100))


def _alpha_sum(image: QImage) -> int:
    converted = image.convertToFormat(QImage.Format.Format_ARGB32)
    bits = converted.bits()
    bits.setsize(converted.width() * converted.height() * 4)
    array = np.frombuffer(bits, dtype=np.uint8).reshape(converted.height(), converted.width(), 4)
    return int(array[..., 3].sum())


class TestHintShapes:
    def test_border_and_endpoints(self):
        # 每格 10x10：(1,2) 外框 x=20~30,y=10~20，中心 (25,15)；
        # (3,4) 外框 x=40~50,y=30~40，中心 (45,35)
        shapes = hint_shapes(Rectangle(1, 2, 3, 4, 10, 2, 18, 20), _grid())
        assert shapes.border == (20, 10, 50, 40)
        assert shapes.start == (25, 15)
        assert shapes.end == (45, 35)

    def test_single_cell_hint(self):
        shapes = hint_shapes(Rectangle(0, 0, 0, 0, 10, 1, 0, 1), _grid())
        assert shapes.border == (0, 0, 10, 10)
        assert shapes.start == (5, 5)
        assert shapes.end == (5, 5)

    def test_missing_corner_rejected(self):
        with pytest.raises(ValueError):
            hint_shapes(Rectangle(0, 0, 9, 14, 10, 2, 138, 140), [])


class TestHintOverlayWindow:
    def test_click_through_and_focus_flags(self, qapp):
        overlay = HintOverlay(desktop=(0, 0, 300, 200))
        flags = overlay.windowFlags()
        assert bool(flags & Qt.WindowType.WindowTransparentForInput)
        assert bool(flags & Qt.WindowType.WindowDoesNotAcceptFocus)
        assert bool(flags & Qt.WindowType.WindowStaysOnTopHint)
        assert overlay.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        overlay.close()

    def test_local_mapping_subtracts_desktop_origin(self, qapp):
        overlay = HintOverlay(desktop=(-100, -50, 400, 300))
        shapes = hint_shapes(Rectangle(0, 0, 0, 1, 10, 2, 0, 2), _grid())
        border, start, end = overlay._to_local(shapes)
        assert border == (100, 50, 120, 60)
        assert start == (105, 55)
        assert end == (115, 55)
        overlay.close()

    def test_show_and_hide(self, qapp):
        overlay = HintOverlay(desktop=(0, 0, 300, 200))
        overlay.show_hint(Rectangle(0, 0, 0, 1, 10, 2, 0, 2), _grid())
        assert overlay.isVisibleTo(None) or overlay.isVisible()
        assert len(overlay.current_shapes) == 1
        overlay.hide_hint()
        assert not overlay.isVisible()
        assert overlay.current_shapes == []
        overlay.close()

    def test_show_multiple_secondary_last(self, qapp):
        overlay = HintOverlay(desktop=(0, 0, 300, 200))
        overlay.show_hints(
            [Rectangle(0, 0, 0, 1, 10, 2, 0, 2), Rectangle(0, 5, 0, 6, 10, 2, 0, 2)],
            _grid(),
        )
        assert len(overlay.current_shapes) == 2
        assert overlay.current_shapes[0].start == (5, 5)
        assert overlay.current_shapes[1].start == (55, 5)
        overlay.close()


class TestMainWindowWiring:
    def _window_with_roi(self, qapp, tmp_path):
        from core.settings_store import SettingsStore
        from gui.main_window import MainWindow

        win = MainWindow(
            auto_repair=False,
            auto_start=False,
            store=SettingsStore(tmp_path / "settings.json"),
            log_dir=tmp_path,
        )
        win._apply_roi(Roi(x=0, y=0, width=450, height=300))
        return win

    def _pair_board(self):
        from core.board_state import BoardState, Cell, CellState

        cells = []
        for row in range(10):
            for column in range(15):
                if (row, column) == (0, 0):
                    cells.append(Cell(row, column, CellState.DIGIT, digit=4))
                elif (row, column) == (0, 1):
                    cells.append(Cell(row, column, CellState.DIGIT, digit=6))
                else:
                    cells.append(Cell(row, column, CellState.EMPTY))
        return BoardState(cells=cells)

    def test_overlay_created_and_toggle(self, qapp, tmp_path):
        win = self._window_with_roi(qapp, tmp_path)
        assert isinstance(win._overlay, HintOverlay)
        assert win.btn_toggle.text() == "開始監控 (F8)"
        win.close()

    def test_show_board_hint_displays_and_hides(self, qapp, tmp_path):
        win = self._window_with_roi(qapp, tmp_path)
        hints = win._show_board_hints(self._pair_board())
        assert len(hints) >= 1
        assert (hints[0].rectangle.row1, hints[0].rectangle.col1) == (0, 0)
        assert win._overlay.isVisible()
        # 每格 30x30：第一格中心 (15,15)
        assert win._overlay.current_shapes[0].start == (15, 15)
        win._on_stop_monitor()  # 停止監控連帶隱藏提示
        assert not win._overlay.isVisible()
        win.close()

    def test_show_board_hint_none_without_candidate(self, qapp, tmp_path):
        from core.board_state import BoardState

        win = self._window_with_roi(qapp, tmp_path)
        assert win._show_board_hints(BoardState.all_unknown()) == []
        assert not win._overlay.isVisible()
        win.close()

    def test_hints_count_pref(self, qapp, tmp_path):
        from core.settings_store import SettingsStore
        from gui.main_window import MainWindow

        win = MainWindow(
            auto_repair=False,
            auto_start=False,
            store=SettingsStore(tmp_path / "settings.json"),
            log_dir=tmp_path,
        )
        assert win.spin_hints.value() == 5
        win.spin_hints.setValue(3)
        assert SettingsStore(tmp_path / "settings.json").load_max_hints() == 3
        win.close()

    def test_boxes_never_filled(self, qapp):
        """回歸：多框共用 painter 時 brush 不可洩漏，框內必須是背景（數字不能被蓋掉）。"""
        from PyQt6.QtGui import QPainter

        from gui.hint_overlay import paint_hint

        shapes_a = hint_shapes(Rectangle(0, 0, 2, 2, 10, 2, 7, 9), _grid())
        shapes_b = hint_shapes(Rectangle(5, 5, 7, 7, 10, 2, 7, 9), _grid())
        image = QImage(150, 100, QImage.Format.Format_RGB888)
        image.fill(QColor(128, 128, 128))
        painter = QPainter(image)
        paint_hint(painter, shapes_a.border, shapes_a.start, shapes_a.end, index=1)
        paint_hint(painter, shapes_b.border, shapes_b.start, shapes_b.end, index=0)
        painter.end()
        assert image.pixelColor(15, 5) == QColor(128, 128, 128)  # A 框內部：背景
        assert image.pixelColor(15, 0) != QColor(128, 128, 128)  # A 框上緣：有線
        assert image.pixelColor(65, 60) == QColor(128, 128, 128)  # B 框內部：背景

    def test_paint_hint_draws_to_image(self, qapp):
        # 不經 QWidget.render（offscreen 會崩潰）：直接把 paint_hint 打到 QImage 驗證
        from PyQt6.QtGui import QPainter

        from gui.hint_overlay import paint_hint

        shapes = hint_shapes(Rectangle(0, 0, 0, 1, 10, 2, 0, 2), _grid())
        image = QImage(300, 200, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        paint_hint(painter, shapes.border, shapes.start, shapes.end)
        painter.end()
        assert _alpha_sum(image) > 0

        blank = QImage(300, 200, QImage.Format.Format_ARGB32)
        blank.fill(Qt.GlobalColor.transparent)
        assert _alpha_sum(blank) == 0


class TestOverlayPresent:
    def _painted(self):
        from PyQt6.QtGui import QPainter

        from gui.hint_overlay import paint_hint

        shapes = hint_shapes(Rectangle(0, 0, 0, 1, 10, 2, 0, 2), _grid())
        image = QImage(150, 100, QImage.Format.Format_RGB888)
        image.fill(QColor(128, 128, 128))
        painter = QPainter(image)
        paint_hint(painter, shapes.border, shapes.start, shapes.end)
        painter.end()
        return shapes, image

    def test_detects_residue(self, qapp):
        from gui.hint_overlay import overlay_present

        shapes, image = self._painted()
        roi = Roi(x=0, y=0, width=150, height=100)
        assert overlay_present(image, shapes, roi, (0, 0)) is True

    def test_detects_secondary_color(self, qapp):
        from PyQt6.QtGui import QPainter

        from gui.hint_overlay import overlay_present, paint_hint

        shapes, _ = self._painted()
        image = QImage(150, 100, QImage.Format.Format_RGB888)
        image.fill(QColor(128, 128, 128))
        painter = QPainter(image)
        paint_hint(painter, shapes.border, shapes.start, shapes.end, index=1)
        painter.end()
        roi = Roi(x=0, y=0, width=150, height=100)
        assert overlay_present(image, shapes, roi, (0, 0)) is True

    def test_clean_frame_passes(self, qapp):
        from gui.hint_overlay import overlay_present

        shapes, _ = self._painted()
        clean = QImage(150, 100, QImage.Format.Format_RGB888)
        clean.fill(QColor(128, 128, 128))
        roi = Roi(x=0, y=0, width=150, height=100)
        assert overlay_present(clean, shapes, roi, (0, 0)) is False

    def test_null_and_out_of_bounds_safe(self, qapp):
        from gui.hint_overlay import overlay_present

        shapes, _ = self._painted()
        roi = Roi(x=5000, y=5000, width=150, height=100)  # 採樣點全落在圖外
        clean = QImage(150, 100, QImage.Format.Format_RGB888)
        clean.fill(QColor(128, 128, 128))
        assert overlay_present(clean, shapes, roi, (0, 0)) is False
        assert overlay_present(QImage(), shapes, roi, (0, 0)) is False


class TestHintPalette:
    """10 色調色盤：互不相同、亮＋高飽和（棋盤白/灰/黑永不命中）、全部可被檢出。"""

    def test_palette_covers_max_hints_and_unique(self):
        from core.hint_selector import MAX_HINT_COUNT
        from gui.hint_overlay import _HINT_PALETTE

        assert len(_HINT_PALETTE) == MAX_HINT_COUNT
        rgb = [(c.red(), c.green(), c.blue()) for c in _HINT_PALETTE]
        assert len(set(rgb)) == MAX_HINT_COUNT

    def test_board_colors_never_match(self):
        from gui.hint_overlay import _is_overlay_pixel

        for gray in (0, 60, 128, 200, 255):  # 黑→灰→白，棋盤會出現的色
            assert _is_overlay_pixel(QColor(gray, gray, gray)) is False

    def test_all_palette_colors_detected(self):
        from gui.hint_overlay import _HINT_PALETTE, _is_overlay_pixel

        for color in _HINT_PALETTE:
            assert _is_overlay_pixel(color) is True

    def test_every_index_paints_detectable_hint(self, qapp):
        from PyQt6.QtGui import QPainter

        from core.hint_selector import MAX_HINT_COUNT
        from gui.hint_overlay import overlay_present, paint_hint

        shapes = hint_shapes(Rectangle(0, 0, 0, 1, 10, 2, 0, 2), _grid())
        roi = Roi(x=0, y=0, width=150, height=100)
        for index in range(MAX_HINT_COUNT):
            image = QImage(150, 100, QImage.Format.Format_RGB888)
            image.fill(QColor(240, 240, 240))  # 近白 tile：最嚴苛的底
            painter = QPainter(image)
            paint_hint(painter, shapes.border, shapes.start, shapes.end, index=index)
            painter.end()
            assert overlay_present(image, shapes, roi, (0, 0)) is True
            assert _alpha_sum(image) > 0  # 含徽章也有筆跡
