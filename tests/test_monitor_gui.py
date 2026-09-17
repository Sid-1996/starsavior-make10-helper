"""監控迴圈 GUI 接線測試（offscreen；擷取函式以假圖替換，不碰真螢幕）。"""

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtGui import QColor, QImage  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import core.screen_capture  # noqa: E402
from core.roi_model import Roi  # noqa: E402
from core.settings_store import SettingsStore  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _solid(width: int, height: int, gray: int) -> QImage:
    image = QImage(width, height, QImage.Format.Format_RGB888)
    image.fill(QColor(gray, gray, gray))
    return image


@pytest.fixture()
def fast_settle(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda seconds: None)


@pytest.fixture()
def fake_capture(monkeypatch):
    """capture_roi 永遠回傳 150x100 素灰圖（全 EMPTY 盤）。"""
    monkeypatch.setattr(core.screen_capture, "capture_roi", lambda roi: _solid(150, 100, 60))


def _window(tmp_path):
    from gui.main_window import MainWindow

    win = MainWindow(store=SettingsStore(tmp_path / "settings.json"), log_dir=tmp_path)
    win._apply_roi(Roi(x=0, y=0, width=150, height=100))
    return win


class TestMonitorButtons:
    def test_start_stop_lifecycle(self, qapp, tmp_path):
        win = _window(tmp_path)
        assert win.btn_start.isEnabled() is True
        assert win.btn_stop.isEnabled() is False
        win.btn_start.click()
        assert win._monitor_timer.isActive()
        assert "監控中" in win.lbl_monitor.text()
        assert win.btn_start.isEnabled() is False
        assert win.btn_stop.isEnabled() is True
        win.btn_stop.click()
        assert not win._monitor_timer.isActive()
        assert "停止" in win.lbl_monitor.text()
        assert win._monitor is None
        win.close()

    def test_start_without_roi_stays_stopped(self, qapp, tmp_path):
        from gui.main_window import MainWindow

        win = MainWindow(store=SettingsStore(tmp_path / "settings.json"), log_dir=tmp_path)
        assert win.btn_start.isEnabled() is False
        win.close()


class TestMonitorTicks:
    def test_stable_frames_build_board_once(self, qapp, tmp_path, fake_capture, fast_settle):
        win = _window(tmp_path)
        win.btn_start.click()
        for _ in range(3):
            win._on_monitor_tick()  # 連續 3 幀穩定 → 建盤一次
        assert win._monitor is not None
        assert win._monitor.board is not None
        assert len(win._monitor.board.cells) == 150
        assert win._monitor.hint is None  # 全 EMPTY：無候選
        assert "停止" not in win.lbl_monitor.text()
        # 之後相同幀不再重建（Hint Lock：board 物件保持同一）
        board_before = win._monitor.board
        win._on_monitor_tick()
        assert win._monitor.board is board_before
        win.close()

    def test_pixel_change_same_board_stays_locked(self, qapp, tmp_path, fast_settle, monkeypatch):
        frames = [_solid(150, 100, 60)] * 3 + [_solid(150, 100, 100)] * 3
        monkeypatch.setattr(
            core.screen_capture,
            "capture_roi",
            lambda roi: frames.pop(0) if frames else _solid(150, 100, 100),
        )
        win = _window(tmp_path)
        win.btn_start.click()
        for _ in range(6):
            win._on_monitor_tick()
        # 亮度整體改變但語意同為全 EMPTY → hint 維持 None，不報變化
        assert win._monitor is not None
        assert win._monitor.board is not None
        assert win._monitor.hint is None
        win.close()


class TestCleanCaptureRetry:
    def _pair_window(self, qapp, tmp_path):
        from core.board_state import BoardState, Cell, CellState

        win = _window(tmp_path)
        cells = []
        for row in range(10):
            for column in range(15):
                if (row, column) == (0, 0):
                    cells.append(Cell(row, column, CellState.DIGIT, digit=4))
                elif (row, column) == (0, 1):
                    cells.append(Cell(row, column, CellState.DIGIT, digit=6))
                else:
                    cells.append(Cell(row, column, CellState.EMPTY))
        win._show_board_hint(BoardState(cells=cells))
        return win

    def _polluted(self, shapes):
        from PyQt6.QtGui import QPainter

        from gui.hint_overlay import paint_hint

        image = _solid(150, 100, 60)
        painter = QPainter(image)
        paint_hint(painter, shapes.border, shapes.start, shapes.end)
        painter.end()
        return image

    def test_retries_until_clean(self, qapp, tmp_path, fast_settle, monkeypatch):
        win = self._pair_window(qapp, tmp_path)
        win.btn_start.click()
        shapes = win._overlay.current_shapes
        assert shapes is not None
        calls: list = []
        sequence = [self._polluted(shapes), self._polluted(shapes), _solid(150, 100, 60)]

        def fake_capture(roi):
            calls.append(roi)
            return sequence.pop(0)

        monkeypatch.setattr(core.screen_capture, "capture_roi", fake_capture)
        result = win._capture_clean(shapes)
        assert len(calls) == 3
        assert len(sequence) == 0
        assert result.width() == 150
        log_text = (tmp_path / "monitor.log").read_text(encoding="utf-8")
        assert "overlay residue detected" in log_text
        win.close()

    def test_no_overlay_skips_check(self, qapp, tmp_path, fast_settle, monkeypatch):
        win = _window(tmp_path)
        win.btn_start.click()
        calls: list = []

        def fake_capture(roi):
            calls.append(roi)
            return _solid(150, 100, 60)

        monkeypatch.setattr(core.screen_capture, "capture_roi", fake_capture)
        win._capture_clean(None)
        assert len(calls) == 1
        win.close()

    def test_status_and_log_trace_ticks(self, qapp, tmp_path, fake_capture, fast_settle):
        win = _window(tmp_path)
        win.btn_start.click()
        assert "監控中 #0" in win.lbl_monitor.text()
        win._on_monitor_tick()
        assert "監控中 #1" in win.lbl_monitor.text()
        log_text = (tmp_path / "monitor.log").read_text(encoding="utf-8")
        assert "start roi=" in log_text
        win.close()
