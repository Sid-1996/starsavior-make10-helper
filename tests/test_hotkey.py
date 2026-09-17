"""F8 全域快捷鍵測試（offscreen；註冊走真實 Win32 API，不模擬按鍵）。"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.roi_model import Roi  # noqa: E402
from core.settings_store import SettingsStore  # noqa: E402
from gui.global_hotkey import GlobalHotkey  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class TestGlobalHotkey:
    def test_start_stop_lifecycle(self, qapp):
        calls: list = []
        hotkey = GlobalHotkey(lambda: calls.append("hit"), hotkey_id=0x5B01)
        if sys.platform != "win32":
            assert hotkey.start() is False
            return
        assert hotkey.start() is True
        assert hotkey.is_active is True
        assert hotkey.start() is False  # 重複啟動拒絕
        hotkey.stop()
        assert hotkey.is_active is False
        hotkey.stop()  # 重複停止無害

    def test_handle_dispatches_by_id(self, qapp):
        calls: list = []
        hotkey = GlobalHotkey(lambda: calls.append("hit"), hotkey_id=0x5B02)
        assert hotkey._handle_hotkey(0x5B02) is True
        assert calls == ["hit"]
        assert hotkey._handle_hotkey(0x1234) is False
        assert calls == ["hit"]


class TestHotkeyToggleWiring:
    def _window_with_hint(self, qapp, tmp_path):
        from core.board_state import BoardState, Cell, CellState
        from gui.main_window import MainWindow

        win = MainWindow(store=SettingsStore(tmp_path / "settings.json"), log_dir=tmp_path)
        win._apply_roi(Roi(x=0, y=0, width=450, height=300))
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

    def test_f8_toggles_and_mutes(self, qapp, tmp_path):
        win = self._window_with_hint(qapp, tmp_path)
        assert win._overlay.isVisible()
        win._on_hotkey_toggle()  # 第一下：隱藏 + 靜音
        assert not win._overlay.isVisible()
        assert win._overlay_muted is True
        win._on_hotkey_toggle()  # 第二下：顯示回來 + 解除靜音
        assert win._overlay.isVisible()
        assert win._overlay_muted is False
        win.close()

    def test_f8_without_hint_is_noop(self, qapp, tmp_path):
        from gui.main_window import MainWindow

        win = MainWindow(store=SettingsStore(tmp_path / "settings.json"), log_dir=tmp_path)
        win._on_hotkey_toggle()
        assert win._overlay_muted is False
        assert not win._overlay.isVisible()
        win.close()

    def test_restore_respects_mute(self, qapp, tmp_path):
        from core.hint_selector import Hint
        from core.monitor import BoardMonitor
        from core.solver import Rectangle

        win = self._window_with_hint(qapp, tmp_path)
        win._monitor = BoardMonitor()
        win._monitor.hint = Hint(Rectangle(0, 0, 0, 1, 10, 2, 0, 2), 1)
        win._overlay_muted = True
        win._overlay.hide()
        win._restore_overlay()
        assert not win._overlay.isVisible()
        win.close()
