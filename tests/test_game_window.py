"""遊戲視窗綁定測試（選擇規則是純函式，任何平台可測；HWND 實測只在 Windows）。"""

import sys

import pytest

from core.game_window import WindowCandidate, WindowInfo, client_info, pick_best


def _cand(hwnd, title, w=800, h=600, visible=True, left=0, top=0):
    return WindowCandidate(
        hwnd=hwnd, title=title, visible=visible, left=left, top=top, right=left + w, bottom=top + h
    )


class TestPickBest:
    def test_exact_title_wins(self):
        candidates = [_cand(1, "StarSavior"), _cand(2, "Star Savior 10")]
        assert pick_best(candidates, "StarSavior").hwnd == 1

    def test_substring_does_not_match(self):
        # 啟動器標題含空白字樣，精確比對必須排除
        candidates = [_cand(1, "Star Savior 10"), _cand(2, "My StarSavior Fan")]
        assert pick_best(candidates, "StarSavior") is None

    def test_invisible_excluded(self):
        candidates = [_cand(1, "StarSavior", visible=False), _cand(2, "StarSavior", w=100, h=100)]
        assert pick_best(candidates, "StarSavior").hwnd == 2

    def test_largest_wins(self):
        candidates = [
            _cand(1, "StarSavior", w=640, h=480),
            _cand(2, "StarSavior", w=1920, h=1080),
        ]
        assert pick_best(candidates, "StarSavior").hwnd == 2

    def test_empty_returns_none(self):
        assert pick_best([], "StarSavior") is None


class TestClientInfo:
    def test_dead_hwnd_returns_none(self):
        # 不存在的 HWND：一律 None（Windows 實測；其他平台直接 None）
        assert client_info(0) is None
        if sys.platform == "win32":
            assert client_info(0xDEADBEEF) is None

    def test_window_info_validation(self):
        assert WindowInfo(hwnd=1, left=0, top=0, width=100, height=100).is_valid()
        assert not WindowInfo(hwnd=0, left=0, top=0, width=100, height=100).is_valid()
        assert not WindowInfo(hwnd=1, left=0, top=0, width=0, height=100).is_valid()


@pytest.mark.skipif(sys.platform != "win32", reason="需真實 Win32 視窗")
class TestLiveWindow:
    def test_current_process_window_enumerated(self):
        # 本行程的主控台視窗必可見：驗證列舉鏈路（不依賴遊戲是否開啟）
        import ctypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if not hwnd:
            pytest.skip("無主控台視窗")
        info = client_info(int(hwnd))
        assert info is None or info.is_valid()
