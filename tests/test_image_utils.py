"""qimage_to_gray 回歸測試（防止 sip.voidptr buffer 問題復發）。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtGui")

import numpy as np  # noqa: E402
from PyQt6.QtGui import QColor, QImage  # noqa: E402

from gui.image_utils import qimage_to_gray  # noqa: E402


def test_qimage_to_gray_shape_and_values():
    img = QImage(64, 48, QImage.Format.Format_RGB888)
    img.fill(QColor(100, 150, 200))
    gray = qimage_to_gray(img)
    assert gray.shape == (48, 64)
    assert gray.dtype == np.uint8
    # (100, 150, 200) 的 luma ≈ 141
    assert 130 <= int(gray.mean()) <= 150


def test_qimage_to_gray_empty():
    img = QImage(0, 0, QImage.Format.Format_RGB888)
    gray = qimage_to_gray(img)
    assert gray.size == 0


def test_qimage_to_gray_4k_like():
    # 模擬大圖（跨 stride 對齊邊界）
    img = QImage(1921, 100, QImage.Format.Format_RGB32)
    img.fill(QColor(255, 255, 255))
    gray = qimage_to_gray(img)
    assert gray.shape == (100, 1921)
    assert int(gray.mean()) == 255
