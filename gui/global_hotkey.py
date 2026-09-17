"""全域快捷鍵（目前僅 F8：顯示 / 隱藏 Overlay）。

遊戲進行時焦點在遊戲視窗，QShortcut 收不到按鍵，因此用 Win32
RegisterHotKey 註冊執行緒級熱鍵，再以 QAbstractNativeEventFilter 接收
WM_HOTKEY。只控制提示顯示，不操作遊戲。

非 Windows 平台：start() 直接回傳 False（無熱鍵，不影響其他功能）。
"""

from __future__ import annotations

import sys
from typing import Callable

from PyQt6.QtCore import QAbstractNativeEventFilter
from PyQt6.QtWidgets import QApplication

WM_HOTKEY = 0x0312
VK_F8 = 0x77
MOD_NOREPEAT = 0x4000  # 按住不連發，避免快速來回切換
_DEFAULT_ID = 0x5A10


class GlobalHotkey(QAbstractNativeEventFilter):
    """F8 全域熱鍵；觸發時呼叫 on_activated（例如切換 Overlay 顯示）。"""

    def __init__(
        self,
        on_activated: Callable[[], None],
        hotkey_id: int = _DEFAULT_ID,
        virtual_key: int = VK_F8,
    ) -> None:
        super().__init__()
        self._on_activated = on_activated
        self._id = hotkey_id
        self._vk = virtual_key
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def start(self) -> bool:
        """註冊熱鍵並安裝事件過濾器；失敗回傳 False（不丟例外）。"""
        if sys.platform != "win32" or self._active:
            return False
        try:
            import ctypes

            ok = ctypes.windll.user32.RegisterHotKey(None, self._id, MOD_NOREPEAT, self._vk)
            if not ok:
                return False
            app = QApplication.instance()
            if app is None:
                ctypes.windll.user32.UnregisterHotKey(None, self._id)
                return False
            app.installNativeEventFilter(self)
            self._active = True
            return True
        except (AttributeError, OSError):
            return False

    def stop(self) -> None:
        """取消註冊（重複呼叫無害）。"""
        if not self._active:
            return
        self._active = False
        try:
            app = QApplication.instance()
            if app is not None:
                app.removeNativeEventFilter(self)
            if sys.platform == "win32":
                import ctypes

                ctypes.windll.user32.UnregisterHotKey(None, self._id)
        except (AttributeError, OSError):
            pass

    def _handle_hotkey(self, wparam: int) -> bool:
        """WM_HOTKEY 的 wParam 是觸發的熱鍵 id；吻合才觸發回呼。"""
        if wparam == self._id:
            self._on_activated()
            return True
        return False

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            try:
                from ctypes import wintypes

                msg = wintypes.MSG.from_address(message.__int__())
                if msg.message == WM_HOTKEY and self._handle_hotkey(msg.wParam):
                    return True, 0
            except (ValueError, OSError):
                pass
        return False, 0
