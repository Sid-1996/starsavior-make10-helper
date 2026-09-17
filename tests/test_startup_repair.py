"""啟動 ROI 自動修復測試（offscreen；擷取與對齊皆以假函式替換）。"""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtGui import QImage  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import core.screen_capture  # noqa: E402
from core import board_align  # noqa: E402
from core.roi_model import Roi  # noqa: E402
from core.settings_store import SettingsStore  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _dummy_image() -> QImage:
    return QImage(100, 100, QImage.Format.Format_RGB888)


def _make_window(tmp_path, roi: Roi | None, monkeypatch, align_results):
    """建 MainWindow（啟動修復開著）；align 依序回傳 align_results。"""
    from gui.main_window import MainWindow

    store = SettingsStore(tmp_path / "settings.json")
    if roi is not None:
        store.save_roi(roi)
    monkeypatch.setattr(
        core.screen_capture, "get_virtual_screen_geometry", lambda: (0, 0, 1920, 1080)
    )
    monkeypatch.setattr(core.screen_capture, "capture_region", lambda *args: _dummy_image())
    monkeypatch.setattr(core.screen_capture, "capture_virtual_screen", lambda: _dummy_image())
    calls = {"n": 0}

    def fake_align(gray, rect, expand_ratio=0.0):
        result = align_results[min(calls["n"], len(align_results) - 1)]
        calls["n"] += 1
        return result

    monkeypatch.setattr(board_align, "align_to_board", fake_align)
    return MainWindow(store=store, log_dir=tmp_path)


class TestAutoRepair:
    def test_no_roi_skips_capture(self, qapp, tmp_path, monkeypatch):
        def fail_capture(*args):
            raise AssertionError("無 ROI 時不該擷取")

        monkeypatch.setattr(core.screen_capture, "capture_virtual_screen", fail_capture)
        from gui.main_window import MainWindow

        win = MainWindow(store=SettingsStore(tmp_path / "settings.json"), log_dir=tmp_path)
        assert win._roi is None
        win.close()

    def test_neighborhood_hit_adopts_and_saves(self, qapp, tmp_path, monkeypatch):
        saved = Roi(x=100, y=100, width=300, height=200)
        # 附近找到 (5,5,300,200)（影像座標）→ 螢幕座標 (15,45,300,200)
        win = _make_window(tmp_path, saved, monkeypatch, [(5, 5, 300, 200)])
        assert win._roi == Roi(x=15, y=45, width=300, height=200)
        data = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
        assert data["roi"] == {"x": 15, "y": 45, "width": 300, "height": 200}
        assert "自動對齊" in win.lbl_roi_status.text()
        win.close()

    def test_same_position_is_quiet(self, qapp, tmp_path, monkeypatch):
        saved = Roi(x=100, y=100, width=300, height=200)
        # left=10, top=40；回傳 (90,60,300,200) → 剛好等於 saved
        win = _make_window(tmp_path, saved, monkeypatch, [(90, 60, 300, 200)])
        assert win._roi == saved
        assert "自動對齊" not in win.lbl_roi_status.text()
        win.close()

    def test_fallback_fullscreen_hit(self, qapp, tmp_path, monkeypatch):
        from gui.main_window import MainWindow

        saved = Roi(x=100, y=100, width=300, height=200)
        # 附近 miss，全螢幕找到同尺寸 → 辨識驗證通過 → 採用
        monkeypatch.setattr(MainWindow, "_looks_like_board", lambda self, roi: True)
        win = _make_window(tmp_path, saved, monkeypatch, [None, (500, 400, 300, 200)])
        assert win._roi == Roi(x=500, y=400, width=300, height=200)
        assert "自動對齊" in win.lbl_roi_status.text()
        win.close()

    def test_fallback_rejects_bad_size(self, qapp, tmp_path, monkeypatch):
        from gui.main_window import MainWindow

        saved = Roi(x=100, y=100, width=300, height=200)
        monkeypatch.setattr(MainWindow, "_looks_like_board", lambda self, roi: True)
        # 全螢幕找到尺寸差太多的 → 不敢認，沿用
        win = _make_window(tmp_path, saved, monkeypatch, [None, (500, 400, 600, 200)])
        assert win._roi == saved
        win.close()

    def test_fallback_rejects_failed_verification(self, qapp, tmp_path, monkeypatch):
        from gui.main_window import MainWindow

        saved = Roi(x=100, y=100, width=300, height=200)
        monkeypatch.setattr(MainWindow, "_looks_like_board", lambda self, roi: False)
        win = _make_window(tmp_path, saved, monkeypatch, [None, (500, 400, 300, 200)])
        assert win._roi == saved
        assert "未找到棋盤" in win.lbl_roi_status.text()
        win.close()

    def test_fallback_keeps_when_rejected(self, qapp, tmp_path, monkeypatch):
        saved = Roi(x=100, y=100, width=300, height=200)
        win = _make_window(tmp_path, saved, monkeypatch, [None, None])
        assert win._roi == saved
        assert "未找到棋盤" in win.lbl_roi_status.text()
        win.close()

    def test_capture_failure_keeps_roi(self, qapp, tmp_path, monkeypatch):
        saved = Roi(x=100, y=100, width=300, height=200)
        store = SettingsStore(tmp_path / "settings.json")
        store.save_roi(saved)
        monkeypatch.setattr(
            core.screen_capture,
            "capture_region",
            lambda *args: (_ for _ in ()).throw(OSError("no screen")),
        )
        monkeypatch.setattr(
            core.screen_capture,
            "capture_virtual_screen",
            lambda: (_ for _ in ()).throw(OSError("no screen")),
        )
        from gui.main_window import MainWindow

        win = MainWindow(store=store, log_dir=tmp_path)
        assert win._roi == saved
        win.close()


class TestLooksLikeBoard:
    def _window(self, tmp_path):
        from gui.main_window import MainWindow

        return MainWindow(
            auto_repair=False,
            store=SettingsStore(tmp_path / "settings.json"),
            log_dir=tmp_path,
        )

    def test_real_board_passes(self, qapp, tmp_path, monkeypatch):
        from test_monitor_gui import _compose_board

        win = self._window(tmp_path)
        board_image = _compose_board({(0, 0): 4, (0, 1): 6})
        monkeypatch.setattr(core.screen_capture, "capture_region", lambda *args: board_image)
        assert win._looks_like_board(Roi(x=0, y=0, width=930, height=620)) is True
        win.close()

    def test_non_board_fails(self, qapp, tmp_path, monkeypatch):
        import numpy as np

        win = self._window(tmp_path)
        noise = np.random.default_rng(42).integers(0, 256, size=(620, 930, 3), dtype=np.uint8)
        height, width, _ = noise.shape
        noisy = QImage(noise.data, width, height, width * 3, QImage.Format.Format_RGB888).copy()
        monkeypatch.setattr(core.screen_capture, "capture_region", lambda *args: noisy)
        assert win._looks_like_board(Roi(x=0, y=0, width=930, height=620)) is False
        win.close()
