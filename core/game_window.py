"""目標遊戲視窗綁定（Win32，標題精確比對）。

- 啟動／重連時以精確標題找遊戲視窗：可見＋面積最大者（啟動器等標題不同者天然排除）。
- 之後一律使用「客戶區」座標（無邊框全螢幕下等於視窗矩形；視窗模式自動扣除邊框標題列）。
- 非 Windows 平台：find 系列一律回傳 None（呼叫端走 mss 前景備援）。

需實際 HWND 的單元測試只在 Windows 跑；選擇規則（pick_best）與座標換算是純函式，
任何平台可測。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

DEFAULT_GAME_TITLE = "StarSavior"


@dataclass(frozen=True)
class WindowInfo:
    """遊戲客戶區（螢幕座標，實體像素）。"""

    hwnd: int
    left: int
    top: int
    width: int
    height: int

    def is_valid(self) -> bool:
        return self.hwnd != 0 and self.width > 0 and self.height > 0


@dataclass(frozen=True)
class WindowCandidate:
    """列舉到的頂層視窗（選擇規則的輸入）。"""

    hwnd: int
    title: str
    visible: bool
    left: int
    top: int
    right: int
    bottom: int

    def area(self) -> int:
        return max(0, self.right - self.left) * max(0, self.bottom - self.top)


def pick_best(candidates: list[WindowCandidate], title: str) -> WindowCandidate | None:
    """精確標題＋可見＋面積最大；沒有命中回傳 None。"""
    matches = [c for c in candidates if c.visible and c.title == title and c.area() > 0]
    if not matches:
        return None
    return max(matches, key=lambda c: c.area())


def _user32():
    import ctypes

    return ctypes.windll.user32


def _enumerate_windows() -> list[WindowCandidate]:
    """列舉所有可見頂層視窗（Windows only）。"""
    import ctypes
    from ctypes import wintypes

    user32 = _user32()
    found: list[WindowCandidate] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            found.append(
                WindowCandidate(
                    hwnd=int(hwnd),
                    title=buffer.value,
                    visible=True,
                    left=rect.left,
                    top=rect.top,
                    right=rect.right,
                    bottom=rect.bottom,
                )
            )
        return True

    user32.EnumWindows(callback, 0)
    return found


def client_info(hwnd: int) -> WindowInfo | None:
    """取該 HWND 的客戶區資訊；視窗已死／失敗回傳 None。"""
    if sys.platform != "win32" or not hwnd:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = _user32()
        if not user32.IsWindow(hwnd):
            return None
        client = wintypes.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(client)):
            return None
        point = wintypes.POINT(client.left, client.top)
        if not user32.ClientToScreen(hwnd, ctypes.byref(point)):
            return None
        width = client.right - client.left
        height = client.bottom - client.top
        if width <= 0 or height <= 0:
            return None
        return WindowInfo(hwnd=hwnd, left=point.x, top=point.y, width=width, height=height)
    except (AttributeError, OSError):
        return None


def find_game_window(title: str = DEFAULT_GAME_TITLE) -> WindowInfo | None:
    """綁定遊戲視窗；找不到／非 Windows 回傳 None。"""
    if sys.platform != "win32":
        return None
    try:
        candidates = _enumerate_windows()
    except (AttributeError, OSError):
        return None
    best = pick_best(candidates, title)
    if best is None:
        return None
    return client_info(best.hwnd)


def refresh_window(hwnd: int) -> WindowInfo | None:
    """每 tick 刷新客戶區位置（視窗移動跟著走）；死了回傳 None。"""
    return client_info(hwnd)


def is_minimized(hwnd: int) -> bool:
    """是否最小化（最小化時後台幀凍結，監控應顯示等待而不報錯）。"""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        return bool(_user32().IsIconic(hwnd))
    except (AttributeError, OSError):
        return False


def bring_to_front(hwnd: int) -> bool:
    """把遊戲帶到前景（框選備援路徑用，盡力而為）。"""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        user32 = _user32()
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        return bool(user32.SetForegroundWindow(hwnd))
    except (AttributeError, OSError):
        return False
