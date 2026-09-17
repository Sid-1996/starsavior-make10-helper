"""啟動 ROI 自動修復測試（offscreen；後台幀與對齊皆以假函式替換）。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from core import window_capture  # noqa: E402
from core.game_window import WindowInfo  # noqa: E402
from core.roi_model import Roi, RoiFrac  # noqa: E402
from core.settings_store import SettingsStore  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _frame(width=1920, height=1080):
    return np.zeros((height, width, 3), dtype=np.uint8)


def _window_with_frac(tmp_path, frac, win, monkeypatch, align_results, grabbed=True):
    """建 MainWindow（不自動修復/啟動），手動塞視窗＋比例後跑修復。"""
    from gui.main_window import MainWindow

    store = SettingsStore(tmp_path / "settings.json")
    store.save_roi_frac(frac)
    monkeypatch.setattr(
        window_capture, "grab_one", lambda hwnd, timeout_sec=2.0: _frame() if grabbed else None
    )
    calls = {"n": 0}

    def fake_align(gray, rect, origin):
        raw = align_results[min(calls["n"], len(align_results) - 1)]
        calls["n"] += 1
        if raw is None:
            return None
        return Roi(x=origin[0] + raw[0], y=origin[1] + raw[1], width=raw[2], height=raw[3])

    monkeypatch.setattr(MainWindow, "_align_to_roi", staticmethod(fake_align))
    widget = MainWindow(auto_repair=False, auto_start=False, store=store, log_dir=tmp_path)
    widget._game = win
    widget._roi_frac = frac
    widget._auto_repair_roi()
    return widget


WIN = WindowInfo(hwnd=4242, left=0, top=0, width=1920, height=1080)
FRAC = RoiFrac(x=0.25, y=0.25, width=0.5, height=0.5)  # → (480,270,960,540)
BOX = (480, 270, 960, 540)


class TestAutoRepair:
    def test_no_frac_or_window_skips_grab(self, qapp, tmp_path, monkeypatch):
        from gui.main_window import MainWindow

        def fail_grab(hwnd, timeout_sec=2.0):
            raise AssertionError("無比例/無視窗時不該抓幀")

        monkeypatch.setattr(window_capture, "grab_one", fail_grab)
        widget = MainWindow(
            auto_repair=False,
            auto_start=False,
            store=SettingsStore(tmp_path / "settings.json"),
            log_dir=tmp_path,
        )
        widget._auto_repair_roi()  # 無比例 → 直接返回
        assert widget._roi is None
        widget.close()

    def test_aligned_box_is_quiet(self, qapp, tmp_path, monkeypatch):
        widget = _window_with_frac(tmp_path, FRAC, WIN, monkeypatch, [(480, 270, 960, 540)])
        # IoU=1 > 0.9：沿用，無字樣
        assert widget._roi is None  # 修復不碰 _roi（解析階段負責）
        assert "自動對齊" not in widget.lbl_status.text()
        widget.close()

    def test_misaligned_adopts_repair(self, qapp, tmp_path, monkeypatch):
        import json

        # 框內檢查 miss（None），放大找到 (500,300,960,540) → 尺寸合採用
        widget = _window_with_frac(tmp_path, FRAC, WIN, monkeypatch, [None, (500, 300, 960, 540)])
        assert widget._roi_frac == RoiFrac.from_absolute(
            Roi(x=500, y=300, width=960, height=540), 0, 0, 1920, 1080
        )
        data = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
        assert "roi_frac" in data
        assert "自動對齊" in widget.lbl_status.text()
        widget.close()

    def test_miss_keeps_and_notes(self, qapp, tmp_path, monkeypatch):
        widget = _window_with_frac(tmp_path, FRAC, WIN, monkeypatch, [None, None])
        assert widget._roi_frac == FRAC
        assert "未在畫面上找到棋盤" in widget.lbl_status.text()
        widget.close()

    def test_bad_size_rejected(self, qapp, tmp_path, monkeypatch):
        widget = _window_with_frac(tmp_path, FRAC, WIN, monkeypatch, [None, (500, 300, 300, 200)])
        assert widget._roi_frac == FRAC  # 尺寸差太多不敢認
        widget.close()

    def test_no_frame_keeps_quiet(self, qapp, tmp_path, monkeypatch):
        widget = _window_with_frac(tmp_path, FRAC, WIN, monkeypatch, [None], grabbed=False)
        assert widget._roi_frac == FRAC
        widget.close()


class TestBindingResolveAutostart:
    def _window(self, tmp_path, monkeypatch, game=None):
        from core import game_window as gw_mod
        from gui.main_window import MainWindow

        monkeypatch.setattr(gw_mod, "find_game_window", lambda title="StarSavior": game)
        return MainWindow(
            auto_repair=False,
            auto_start=False,
            store=SettingsStore(tmp_path / "settings.json"),
            log_dir=tmp_path,
        )

    def test_bind_missing_sets_note(self, qapp, tmp_path, monkeypatch):
        win = self._window(tmp_path, monkeypatch, game=None)
        assert win._bind_window() is False
        assert win._game is None
        win.close()

    def test_bind_success(self, qapp, tmp_path, monkeypatch):
        win = self._window(tmp_path, monkeypatch, game=WIN)
        assert win._bind_window() is True
        assert win._game == WIN
        win.close()

    def test_resolve_frac_to_absolute(self, qapp, tmp_path, monkeypatch):
        from core.roi_model import Roi

        win = self._window(tmp_path, monkeypatch, game=WIN)
        win._game = WIN
        win._roi_frac = FRAC
        assert win._resolve_roi() is True
        assert win._roi == Roi(x=480, y=270, width=960, height=540)
        win.close()

    def test_resolve_migrates_legacy(self, qapp, tmp_path, monkeypatch):
        import json

        from core.roi_model import Roi

        store = SettingsStore(tmp_path / "settings.json")
        store.save_roi(Roi(x=480, y=270, width=960, height=540))
        win = self._window(tmp_path, monkeypatch, game=WIN)
        win._game = WIN
        assert win._resolve_roi() is True
        assert win._roi == Roi(x=480, y=270, width=960, height=540)
        assert win._roi_frac is not None
        data = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
        assert "roi" not in data and "roi_frac" in data
        win.close()

    def test_resolve_without_roi_fails(self, qapp, tmp_path, monkeypatch):
        win = self._window(tmp_path, monkeypatch, game=WIN)
        win._game = WIN
        assert win._resolve_roi() is False
        assert "框選" in win.lbl_status.text()  # 引導模式請使用者框選
        win.close()

    def test_ready_not_monitoring_by_default(self, qapp, tmp_path, monkeypatch):
        from gui.main_window import MainWindow

        store = SettingsStore(tmp_path / "settings.json")
        store.save_roi_frac(FRAC)
        monkeypatch.setattr("core.game_window.find_game_window", lambda title="StarSavior": WIN)
        monkeypatch.setattr(MainWindow, "_start_wgc", lambda self: setattr(self, "_wgc", None))
        win = MainWindow(store=store, log_dir=tmp_path)  # 預設：就緒但不監控
        try:
            assert not win._monitor_timer.isActive()
            assert "就緒" in win.lbl_status.text()
        finally:
            win.close()

    def test_autostart_opt_in_still_works(self, qapp, tmp_path, monkeypatch):
        from gui.main_window import MainWindow

        store = SettingsStore(tmp_path / "settings.json")
        store.save_roi_frac(FRAC)
        monkeypatch.setattr("core.game_window.find_game_window", lambda title="StarSavior": WIN)
        monkeypatch.setattr(MainWindow, "_start_wgc", lambda self: setattr(self, "_wgc", None))
        win = MainWindow(auto_start=True, store=store, log_dir=tmp_path)
        try:
            assert win._monitor_timer.isActive()
            assert "監控中" in win.lbl_status.text()
        finally:
            win.close()

    def test_no_autostart_without_window(self, qapp, tmp_path, monkeypatch):
        from gui.main_window import MainWindow

        store = SettingsStore(tmp_path / "settings.json")
        store.save_roi_frac(FRAC)
        monkeypatch.setattr("core.game_window.find_game_window", lambda title="StarSavior": None)
        win = MainWindow(store=store, log_dir=tmp_path)
        try:
            assert not win._monitor_timer.isActive()
            assert "找不到" in win.lbl_status.text()
        finally:
            win.close()


class TestSelectorBackground:
    def test_background_from_window_frame(self, qapp, tmp_path, monkeypatch):
        import numpy as np

        from core import window_capture as wc_mod
        from gui.main_window import MainWindow

        win = MainWindow(
            auto_repair=False,
            auto_start=False,
            store=SettingsStore(tmp_path / "settings.json"),
            log_dir=tmp_path,
        )
        win._game = WIN
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        monkeypatch.setattr(wc_mod, "grab_one", lambda hwnd, timeout_sec=3.0: frame)
        background, origin = win._selector_background()
        assert (background.width(), background.height()) == (1920, 1080)
        assert origin == (0, 0)
        win.close()
