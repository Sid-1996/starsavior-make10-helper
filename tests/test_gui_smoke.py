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
    def test_constructor_without_saved_roi_guides(self, qapp, tmp_path):
        from gui.main_window import MainWindow

        win = MainWindow(
            auto_repair=False, auto_start=False, store=SettingsStore(tmp_path / "settings.json")
        )
        assert win.windowTitle()
        # 引導模式：開關隱藏，只留框選引導
        assert win._needs_setup is True
        assert win.btn_toggle.isHidden() is True
        assert win.btn_guide.isHidden() is False
        assert "框選" in win.lbl_status.text()
        assert "尚未辨識" in win.recognition_panel._matrix_label.text()
        win.close()

    def test_constructor_loads_saved_roi_ready(self, qapp, tmp_path):
        from gui.main_window import MainWindow

        store = SettingsStore(tmp_path / "settings.json")
        store.save_roi(Roi(x=11, y=22, width=450, height=300))
        win = MainWindow(auto_repair=False, auto_start=False, store=store)
        assert win._needs_setup is False
        assert win.btn_toggle.isHidden() is False
        assert win.btn_guide.isHidden() is True
        assert win._settings.spin_x.value() == 11
        assert win._settings.spin_y.value() == 22
        assert win._settings.spin_w.value() == 450
        assert win._settings.spin_h.value() == 300
        assert "就緒" in win.lbl_status.text() or "找不到" in win.lbl_status.text()
        win.close()

    def test_manual_spin_edit_saves_roi(self, qapp, tmp_path):
        from gui.main_window import MainWindow

        path = tmp_path / "settings.json"
        win = MainWindow(auto_repair=False, auto_start=False, store=SettingsStore(path))
        # 模擬使用者在設定對話框手動輸入 X / Y / W / H
        dlg = win._settings
        dlg.spin_x.setValue(10)
        dlg.spin_y.setValue(20)
        dlg.spin_w.setValue(450)
        dlg.spin_h.setValue(300)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["roi"] == {"x": 10, "y": 20, "width": 450, "height": 300}
        assert win._roi == Roi(x=10, y=20, width=450, height=300)
        assert win._needs_setup is False
        win.close()

    def test_invalid_size_returns_to_guide(self, qapp, tmp_path):
        from gui.main_window import MainWindow

        store = SettingsStore(tmp_path / "settings.json")
        win = MainWindow(auto_repair=False, auto_start=False, store=store)
        win._apply_roi(Roi(x=10, y=20, width=450, height=300))
        assert win._needs_setup is False
        # 寬度歸 0 → ROI 清空，回到引導模式
        win._settings.spin_w.setValue(0)
        assert win._roi is None
        assert win._needs_setup is True
        assert win.btn_guide.isHidden() is False
        win.close()

    def test_guide_resolves_after_roi_applied(self, qapp, tmp_path):
        from gui.main_window import MainWindow

        win = MainWindow(
            auto_repair=False, auto_start=False, store=SettingsStore(tmp_path / "settings.json")
        )
        assert win.btn_guide.isHidden() is False
        win._apply_roi(Roi(x=0, y=0, width=450, height=300))
        assert win._needs_setup is False
        assert win.btn_guide.isHidden() is True
        assert win.btn_toggle.isHidden() is False
        win.close()


class TestSettingsDialogSmoke:
    def test_dialog_contents_and_open(self, qapp, tmp_path):
        from gui.main_window import MainWindow

        win = MainWindow(
            auto_repair=False, auto_start=False, store=SettingsStore(tmp_path / "settings.json")
        )
        dlg = win._settings
        assert dlg.btn_select.text() == "框選辨識區域"
        assert dlg.btn_align.isEnabled() is True
        assert dlg.chk_topmost.isChecked() is True  # 預設置頂
        assert "尚未辨識" in dlg.recognition_panel._matrix_label.text()
        win.btn_settings.click()
        assert dlg.isVisible()
        dlg.close()
        win.close()

    def test_topmost_toggle_persists(self, qapp, tmp_path):
        from PyQt6.QtCore import Qt

        from gui.main_window import MainWindow

        store = SettingsStore(tmp_path / "settings.json")
        win = MainWindow(auto_repair=False, auto_start=False, store=store, log_dir=tmp_path)
        assert win._settings.chk_topmost.isChecked() is True
        assert bool(win.windowFlags() & Qt.WindowType.WindowStaysOnTopHint) is True
        win._settings.chk_topmost.setChecked(False)
        assert store.load_always_on_top() is False
        assert bool(win.windowFlags() & Qt.WindowType.WindowStaysOnTopHint) is False
        win.close()
