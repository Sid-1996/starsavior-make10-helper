"""GUI 冒煙測試（offscreen 平台，不實際截圖 / 不顯示視窗）。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

import json  # noqa: E402

from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.roi_model import Roi  # noqa: E402
from core.settings_store import SettingsStore  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class TestMainWindowSmoke:
    def test_constructor_without_saved_roi(self, qapp, tmp_path):
        from gui.main_window import MainWindow

        win = MainWindow(
            auto_repair=False, auto_start=False, store=SettingsStore(tmp_path / "settings.json")
        )
        assert win.windowTitle()
        assert "未設定" in win.lbl_roi_status.text()
        assert "棋盤尺寸：10 × 15" in win.lbl_board_size.text()
        assert "停止" in win.lbl_monitor.text()
        # 測試辨識可用（Phase 2），監控仍是 Phase 6+ 佔位
        assert win.btn_test.isEnabled() is False
        assert win.btn_start.isEnabled() is False
        assert win.btn_stop.isEnabled() is False
        assert "尚未辨識" in win.recognition_panel._matrix_label.text()
        win.close()

    def test_constructor_loads_saved_roi(self, qapp, tmp_path):
        from gui.main_window import MainWindow

        store = SettingsStore(tmp_path / "settings.json")
        store.save_roi(Roi(x=11, y=22, width=450, height=300))
        win = MainWindow(auto_repair=False, auto_start=False, store=store)
        assert win.spin_x.value() == 11
        assert win.spin_y.value() == 22
        assert win.spin_w.value() == 450
        assert win.spin_h.value() == 300
        assert "已設定" in win.lbl_roi_status.text()
        win.close()

    def test_manual_spin_edit_saves_roi(self, qapp, tmp_path):
        from gui.main_window import MainWindow

        path = tmp_path / "settings.json"
        win = MainWindow(auto_repair=False, auto_start=False, store=SettingsStore(path))
        # 模擬使用者手動輸入 X / Y / W / H
        win.spin_x.setValue(10)
        win.spin_y.setValue(20)
        win.spin_w.setValue(450)
        win.spin_h.setValue(300)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["roi"] == {"x": 10, "y": 20, "width": 450, "height": 300}
        assert win._roi == Roi(x=10, y=20, width=450, height=300)
        win.close()

    def test_invalid_size_clears_roi(self, qapp, tmp_path):
        from gui.main_window import MainWindow

        store = SettingsStore(tmp_path / "settings.json")
        win = MainWindow(auto_repair=False, auto_start=False, store=store)
        win._apply_roi(Roi(x=10, y=20, width=450, height=300))
        # 寬度歸 0 → ROI 應清空且狀態回到未設定
        win.spin_w.setValue(0)
        assert win._roi is None
        assert "未設定" in win.lbl_roi_status.text()
        win.close()
