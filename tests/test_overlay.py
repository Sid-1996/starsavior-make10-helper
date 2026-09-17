"""Hint Overlay 測試（offscreen 平台；幾何純函式 + 視窗行為 + 渲染冒煙）。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

import numpy as np  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QImage  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.grid import build_grid  # noqa: E402
from core.roi_model import Roi  # noqa: E402
from core.solver import Rectangle  # noqa: E402
from gui.hint_overlay import HintOverlay, hint_shapes  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
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
        assert overlay.current_shapes is not None
        overlay.hide_hint()
        assert not overlay.isVisible()
        assert overlay.current_shapes is None
        overlay.close()


class TestMainWindowWiring:
    def _window_with_roi(self, qapp, tmp_path):
        from core.settings_store import SettingsStore
        from gui.main_window import MainWindow

        win = MainWindow(store=SettingsStore(tmp_path / "settings.json"))
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

    def test_overlay_created_and_hide_button(self, qapp, tmp_path):
        win = self._window_with_roi(qapp, tmp_path)
        assert isinstance(win._overlay, HintOverlay)
        assert win.btn_hide_hint.text() == "隱藏提示"
        win.close()

    def test_show_board_hint_displays_and_hides(self, qapp, tmp_path):
        win = self._window_with_roi(qapp, tmp_path)
        hint = win._show_board_hint(self._pair_board())
        assert hint is not None
        assert (hint.rectangle.row1, hint.rectangle.col1) == (0, 0)
        assert win._overlay.isVisible()
        # 每格 30x30：第一格中心 (15,15)
        assert win._overlay.current_shapes.start == (15, 15)
        win.btn_hide_hint.click()
        assert not win._overlay.isVisible()
        win.close()

    def test_show_board_hint_none_without_candidate(self, qapp, tmp_path):
        from core.board_state import BoardState

        win = self._window_with_roi(qapp, tmp_path)
        assert win._show_board_hint(BoardState.all_unknown()) is None
        assert not win._overlay.isVisible()
        win.close()

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
