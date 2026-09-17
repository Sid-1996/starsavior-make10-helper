"""螢幕擷取（Phase 1）。

座標一律使用「實體螢幕像素」。
main.py 會設定 Process DPI awareness 並關閉 Qt High-DPI 縮放，
確保 Qt 座標與 mss 擷取座標完全一致。

Phase 1 只需要：
- 全虛擬桌面擷取（供全螢幕框選器當背景）
- ROI 區域擷取（供主視窗預覽）
"""

from __future__ import annotations

import mss
from PyQt6.QtGui import QImage

from core.roi_model import Roi


class ScreenCaptureError(RuntimeError):
    """螢幕擷取失敗。"""


def get_virtual_screen_geometry() -> tuple[int, int, int, int]:
    """回傳虛擬桌面 (left, top, width, height)，多螢幕時涵蓋所有螢幕。"""
    with mss.MSS() as sct:
        mon = sct.monitors[0]
        return int(mon["left"]), int(mon["top"]), int(mon["width"]), int(mon["height"])


def _grab(left: int, top: int, width: int, height: int) -> QImage:
    if width <= 0 or height <= 0:
        raise ScreenCaptureError(f"無效的擷取尺寸: {width}x{height}")
    try:
        with mss.MSS() as sct:
            img = sct.grab({"left": left, "top": top, "width": width, "height": height})
    except mss.exception.ScreenShotError as exc:
        raise ScreenCaptureError(f"螢幕擷取失敗: {exc}") from exc
    qimage = QImage(img.rgb, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
    if qimage.isNull():
        raise ScreenCaptureError("擷取畫面轉換為 QImage 失敗")
    # 複製資料，讓 QImage 擁有自己的 buffer（img.rgb 離開 with 後仍有效）
    return qimage.copy()


def capture_virtual_screen() -> QImage:
    """擷取整個虛擬桌面畫面。"""
    left, top, width, height = get_virtual_screen_geometry()
    return _grab(left, top, width, height)


def capture_region(left: int, top: int, width: int, height: int) -> QImage:
    """擷取任意螢幕區域。"""
    return _grab(left, top, width, height)


def capture_roi(roi: Roi) -> QImage:
    """擷取指定 ROI 區域畫面。"""
    return _grab(roi.x, roi.y, roi.width, roi.height)
