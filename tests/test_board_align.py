"""board_align 自動對齊單元測試（合成棋盤影像）。"""

import cv2
import numpy as np
import pytest

from core.board_align import align_to_board

pytest.importorskip("cv2")


def _draw_board(
    img: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    bg: int = 70,
    outer: int = 20,
    empty_ratio: float = 0.1,
    seed: int = 7,
) -> None:
    """在 img 上畫一個 10x15 合成棋盤（置中數字 glyph，含部分空格）。"""
    if outer is not None:
        img[:] = outer
    cv2.rectangle(img, (x, y), (x + w - 1, y + h - 1), bg, -1)
    rng = np.random.default_rng(seed)
    cw, ch = w / 15, h / 10
    for r in range(10):
        for c in range(15):
            if rng.random() < empty_ratio:
                continue
            cx = int(x + (c + 0.5) * cw)
            cy = int(y + (r + 0.5) * ch)
            text = str(int(rng.integers(1, 10)))
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1.1, 2)
            # putText 錨點為 baseline 左端；計算讓 glyph 置中於格子中心
            org = (cx - tw // 2, cy + th // 2)
            cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 1.1, 235, 2)


class TestAlignToBoard:
    def test_larger_selection_snaps_to_board(self):
        """框選範圍比棋盤大 → 應吸附回實際棋盤位置。"""
        img = np.full((800, 1000), 20, np.uint8)
        bx, by, bw, bh = 120, 90, 450, 300  # cell 30px
        _draw_board(img, bx, by, bw, bh)
        roi = (bx - 80, by - 70, bw + 200, bh + 180)
        result = align_to_board(img, roi)
        assert result is not None
        ax, ay, aw, ah = result
        assert abs(ax - bx) <= 6
        assert abs(ay - by) <= 6
        assert abs(aw - bw) <= 8
        assert abs(ah - bh) <= 8
        # 吸附結果應接近 15:10 比例
        assert abs(aw / ah - 1.5) < 0.1

    def test_digits_only_without_cell_background(self):
        """棋盤底色與外部相同（只有數字有邊緣）→ 仍應對齊，誤差小於一格。"""
        img = np.full((800, 1000), 20, np.uint8)
        bx, by, bw, bh = 100, 100, 600, 400  # cell 40px
        _draw_board(img, bx, by, bw, bh, bg=20)
        roi = (bx - 50, by - 50, bw + 150, bh + 120)
        result = align_to_board(img, roi)
        assert result is not None
        ax, ay, aw, ah = result
        assert abs(ax - bx) <= 25
        assert abs(ay - by) <= 25
        assert abs(aw - bw) <= 30
        assert abs(ah - bh) <= 30

    def test_fractional_cell_size(self):
        """cell 尺寸非整數（如 30.2px）也應正確對齊。"""
        img = np.full((800, 1000), 20, np.uint8)
        bx, by, bw, bh = 137, 63, 453, 297
        _draw_board(img, bx, by, bw, bh, seed=11)
        roi = (bx - 40, by - 40, bw + 90, bh + 80)
        result = align_to_board(img, roi)
        assert result is not None
        ax, ay, aw, ah = result
        assert abs(ax - bx) <= 8
        assert abs(ay - by) <= 8
        assert abs(aw - bw) <= 10
        assert abs(ah - bh) <= 10

    def test_selection_inside_board_expands(self):
        """選取範圍略小於棋盤、完整落在棋盤內 → 應外擴吸附到整個棋盤。"""
        img = np.full((800, 1000), 20, np.uint8)
        bx, by, bw, bh = 150, 120, 450, 300
        _draw_board(img, bx, by, bw, bh, seed=3)
        # 選取棋盤中央約 80% 區域
        roi = (bx + 40, by + 30, bw - 80, bh - 60)
        result = align_to_board(img, roi)
        assert result is not None
        ax, ay, aw, ah = result
        assert abs(ax - bx) <= 6
        assert abs(ay - by) <= 6
        assert abs(aw - bw) <= 8
        assert abs(ah - bh) <= 8

    def test_flat_image_returns_none(self):
        """完全沒有內容 → 不應猜測，回傳 None。"""
        img = np.full((600, 800), 30, np.uint8)
        assert align_to_board(img, (100, 100, 400, 300)) is None

    def test_tiny_content_returns_none(self):
        """只有極少量雜訊邊緣 → 回傳 None。"""
        img = np.full((600, 800), 30, np.uint8)
        img[200:206, 300:306] = 240
        assert align_to_board(img, (150, 150, 400, 300)) is None

    def test_invalid_rect_returns_none(self):
        img = np.full((600, 800), 30, np.uint8)
        assert align_to_board(img, (10, 10, 0, 100)) is None
        assert align_to_board(img, (10, 10, 100, -5)) is None

    def test_result_within_screen_bounds(self):
        """選取框貼近影像邊界時，對齊結果不得超出影像。"""
        img = np.full((800, 1000), 20, np.uint8)
        bx, by, bw, bh = 20, 15, 450, 300
        _draw_board(img, bx, by, bw, bh, seed=5)
        roi = (0, 0, 700, 500)
        result = align_to_board(img, roi)
        if result is not None:
            ax, ay, aw, ah = result
            assert ax >= 0 and ay >= 0
            assert ax + aw <= 1000 and ay + ah <= 800
