"""QImage 與 numpy 陣列轉換工具。"""

from __future__ import annotations

import numpy as np
from PyQt6.QtGui import QImage


def qimage_to_gray(img: QImage) -> np.ndarray:
    """將 QImage 轉為 2D uint8 灰階陣列（供 core.board_align 使用）。"""
    gray_img = img.convertToFormat(QImage.Format.Format_Grayscale8)
    w, h = gray_img.width(), gray_img.height()
    if w == 0 or h == 0:
        return np.empty((0, 0), dtype=np.uint8)
    stride = gray_img.bytesPerLine()
    bits = gray_img.constBits()
    # PyQt6 的 sip.voidptr 預設沒有大小資訊，np.frombuffer 會拋錯，需明確設定
    bits.setsize(stride * h)
    arr = np.frombuffer(bits, dtype=np.uint8, count=stride * h)
    return arr.reshape(h, stride)[:, :w].copy()
