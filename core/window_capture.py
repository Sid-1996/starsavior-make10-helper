"""遊戲視窗後台擷取（Windows.Graphics.Capture，簡稱 WGC）。

- 直接抓目標視窗的合成表面：被其他視窗蓋住也能抓到遊戲畫面，
  且永遠不含本工具自己的 Overlay（不同視窗）。
- WGC 不可用時（非 Windows / 套件缺失 / 啟動失敗）回傳 None，
  呼叫端退回 mss 前景擷取。
- 本模組 import 時不碰 windows-capture（延遲載入），任何平台可 import；
  回呼只做 numpy 複製，不碰 Qt（執行緒安全，GUI 執行緒用 latest() 輪詢）。

幀格式：BGR uint8 numpy（已去 alpha）；轉灰階請用 to_grayscale()。
"""

from __future__ import annotations

import sys
import threading
import time

import numpy as np

_available: bool | None = None


def wgc_available() -> bool:
    """windows-capture 是否可用（結果快取）。"""
    global _available
    if _available is None:
        if sys.platform != "win32":
            _available = False
        else:
            try:
                import windows_capture  # noqa: F401

                _available = True
            except ImportError:
                _available = False
    return _available


def to_grayscale(bgr: np.ndarray) -> np.ndarray:
    """BGR 轉灰階（BT.601，與 Qt 轉換一致性足夠模板比對）。"""
    import cv2

    return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)


class WindowCaptureSession:
    """綁定 HWND 的常駐 WGC 會話；最新幀以背景執行緒更新，主執行緒輪詢。"""

    def __init__(self, hwnd: int) -> None:
        self._hwnd = hwnd
        self._lock = threading.Lock()
        self._latest: tuple[np.ndarray, float] | None = None
        self._closed = False
        self._capture = None
        self._running = False

    @property
    def closed(self) -> bool:
        """遊戲視窗關閉（WGC 斷線）時為 True，呼叫端應停止監控。"""
        with self._lock:
            return self._closed

    def start(self) -> bool:
        """啟動擷取執行緒；失敗回傳 False（不丟例外）。"""
        if self._running or not wgc_available() or not self._hwnd:
            return False
        try:
            from windows_capture import WindowsCapture

            capture = WindowsCapture(
                cursor_capture=False, draw_border=False, window_hwnd=self._hwnd
            )
            capture.event(self._on_frame_arrived)
            capture.event(self._on_closed)
            capture.start_free_threaded()
        except Exception:
            return False
        self._capture = capture
        self._running = True
        return True

    def stop(self) -> None:
        """停止擷取（重複呼叫無害）。"""
        self._running = False
        capture, self._capture = self._capture, None
        if capture is not None:
            try:
                capture.stop()
            except Exception:
                pass

    def latest(self) -> tuple[np.ndarray, float] | None:
        """最新 (BGR, timestamp)；尚無幀回傳 None。回傳陣列僅供讀取。"""
        with self._lock:
            return self._latest

    # -- 回呼（WGC 執行緒） ------------------------------------------------ #
    def _on_frame_arrived(self, frame, _control) -> None:
        try:
            bgr = np.asarray(frame.frame_buffer)[..., :3].copy()
            stamp = time.monotonic()
        except Exception:
            return
        with self._lock:
            self._latest = (bgr, stamp)

    def _on_closed(self) -> None:
        with self._lock:
            self._closed = True


def grab_one(hwnd: int, timeout_sec: float = 3.0) -> np.ndarray | None:
    """抓單幀 BGR（框選／預覽／驗證用）；逾時或不可用回傳 None。"""
    session = WindowCaptureSession(hwnd)
    if not session.start():
        return None
    try:
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            latest = session.latest()
            if latest is not None:
                return latest[0]
            time.sleep(0.05)
        return None
    finally:
        session.stop()
