"""window_capture 測試（WGC 以假模組替換，不碰真實視窗/遊戲）。"""

import sys
import types

import numpy as np
import pytest

from core import window_capture
from core.window_capture import WindowCaptureSession, grab_one, to_grayscale, wgc_available


@pytest.fixture()
def fake_wgc(monkeypatch):
    """往 sys.modules 塞假 windows_capture；回傳 FakeCapture 類別以供操控。"""
    created = []

    class FakeCapture:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.handlers = {}
            self.stopped = False
            created.append(self)

        def event(self, fn):
            self.handlers[fn.__name__] = fn

        def start_free_threaded(self):
            pass

        def stop(self):
            self.stopped = True

    module = types.ModuleType("windows_capture")
    module.WindowsCapture = FakeCapture
    monkeypatch.setitem(sys.modules, "windows_capture", module)
    monkeypatch.setattr(window_capture, "_available", True)
    return FakeCapture, created


def _bgra_frame(value: int = 128, width: int = 64, height: int = 48):
    frame = types.SimpleNamespace()
    frame.frame_buffer = np.full((height, width, 4), value, dtype=np.uint8)
    frame.width = width
    frame.height = height
    return frame


class TestWgcAvailable:
    def test_returns_bool(self):
        assert isinstance(wgc_available(), bool)


class TestSession:
    def test_start_registers_handlers(self, fake_wgc):
        _, created = fake_wgc
        session = WindowCaptureSession(hwnd=1234)
        assert session.start() is True
        assert set(created[0].handlers) == {"_on_frame_arrived", "_on_closed"}

    def test_start_rejects_bad_hwnd(self, fake_wgc):
        assert WindowCaptureSession(hwnd=0).start() is False

    def test_latest_caches_bgr_copy(self, fake_wgc):
        _, created = fake_wgc
        session = WindowCaptureSession(hwnd=1234)
        assert session.latest() is None
        assert session.start() is True
        created[0].handlers["_on_frame_arrived"](_bgra_frame(200), None)
        latest, _stamp = session.latest()
        assert latest.shape == (48, 64, 3)  # 去 alpha
        assert latest.dtype == np.uint8
        assert int(latest.mean()) == 200
        session.stop()
        assert created[0].stopped is True

    def test_closed_flag(self, fake_wgc):
        _, created = fake_wgc
        session = WindowCaptureSession(hwnd=1234)
        session.start()
        assert session.closed is False
        created[0].handlers["_on_closed"]()
        assert session.closed is True

    def test_to_grayscale(self):
        bgr = np.zeros((4, 4, 3), dtype=np.uint8)
        bgr[:, :] = (255, 255, 255)
        gray = to_grayscale(bgr)
        assert gray.shape == (4, 4) and gray.dtype == np.uint8
        assert int(gray.mean()) > 200


class TestGrabOne:
    def test_returns_frame(self, fake_wgc, monkeypatch):
        fake_cls, created = fake_wgc
        frame = _bgra_frame(100)

        def instant_start(self):
            self.handlers["_on_frame_arrived"](frame, None)

        monkeypatch.setattr(fake_cls, "start_free_threaded", instant_start)
        result = grab_one(hwnd=1234, timeout_sec=1.0)
        assert result is not None
        assert result.shape == (48, 64, 3)
        assert created[0].stopped is True  # 用完即停

    def test_timeout_returns_none(self, fake_wgc):
        assert grab_one(hwnd=1234, timeout_sec=0.05) is None
