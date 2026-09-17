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

    win = MainWindow(
        auto_repair=False, store=SettingsStore(tmp_path / "settings.json"), log_dir=tmp_path
    )
    win._apply_roi(Roi(x=0, y=0, width=150, height=100))
    return win


def _compose_board(plant: dict[tuple[int, int], int]) -> "QImage":
    """用真實模板拼 930x620 ROI 圖（每格 62x62），回傳彩色 QImage。"""
    import cv2
    import numpy as np

    from core.templates import TemplateStore

    templates = TemplateStore().load_all()
    assert templates.is_complete()
    gray = np.full((620, 930), 128, dtype=np.uint8)
    for (row, column), digit in plant.items():
        tile = cv2.resize(templates.templates[digit], (62, 62), interpolation=cv2.INTER_AREA)
        gray[row * 62 : (row + 1) * 62, column * 62 : (column + 1) * 62] = tile
    rgb = np.stack([gray, gray, gray], axis=-1)
    height, width, _ = rgb.shape
    return QImage(rgb.data, width, height, width * 3, QImage.Format.Format_RGB888).copy()


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

        win = MainWindow(
            auto_repair=False, store=SettingsStore(tmp_path / "settings.json"), log_dir=tmp_path
        )
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

    def test_exhausted_returns_none(self, qapp, tmp_path, fast_settle, monkeypatch):
        win = self._pair_window(qapp, tmp_path)
        win.btn_start.click()
        shapes = win._overlay.current_shapes
        assert shapes is not None
        polluted = self._polluted(shapes)
        monkeypatch.setattr(core.screen_capture, "capture_roi", lambda roi: polluted)
        assert win._capture_clean(shapes) is None
        log_text = (tmp_path / "monitor.log").read_text(encoding="utf-8")
        assert "skip rebuild" in log_text
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

    def test_rebuild_dumps_frames_and_board_summary(
        self, qapp, tmp_path, fake_capture, fast_settle
    ):
        win = _window(tmp_path)
        win.btn_start.click()
        for _ in range(3):  # 穩定觸發重建（全 EMPTY 盤 → hint None）
            win._on_monitor_tick()
        assert (tmp_path / "last_stable.png").is_file()
        assert (tmp_path / "last_clean.png").is_file()
        log_text = (tmp_path / "monitor.log").read_text(encoding="utf-8")
        assert "board digit=0 empty=150 unknown=0" in log_text
        win.close()


class TestFullSimulation:
    def test_board_change_switches_hint(self, qapp, tmp_path, fast_settle, monkeypatch):
        """全真模擬：A 盤穩定出提示 → 換 B 盤 → 提示必須跟著換（回歸：卡在第一次）。"""
        from gui.main_window import MainWindow

        board_a = _compose_board({(0, 0): 4, (0, 1): 6})
        board_b = _compose_board({(9, 13): 5, (9, 14): 5})
        # _apply_roi 的預覽先吃掉 1 張；每次穩定觸發吃 3 張（tick+乾淨+基準）
        frames = [board_a] * 6 + [board_b] * 6
        monkeypatch.setattr(core.screen_capture, "capture_roi", lambda roi: frames.pop(0))

        win = MainWindow(
            auto_repair=False, store=SettingsStore(tmp_path / "settings.json"), log_dir=tmp_path
        )
        win._apply_roi(Roi(x=0, y=0, width=930, height=620))
        win.btn_start.click()

        for _ in range(3):
            win._on_monitor_tick()
        hint_a = win._monitor.hint
        assert hint_a is not None
        assert (hint_a.rectangle.row1, hint_a.rectangle.col1) == (0, 0)
        assert win._overlay.isVisible()

        for _ in range(3):
            win._on_monitor_tick()
        hint_b = win._monitor.hint
        assert hint_b is not None
        assert (hint_b.rectangle.row1, hint_b.rectangle.col1) == (9, 13)
        assert win._overlay.current_shapes.start == (13 * 62 + 31, 9 * 62 + 31)

        win._on_monitor_tick()  # 之後同盤安靜：Hint 物件保持同一
        assert win._monitor.hint is hint_b
        win.close()
