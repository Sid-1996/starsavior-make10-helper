"""BoardBuilder：Screen Capture → Grid 切圖 → 辨識 → BoardState。

正確架構（Board 不讀螢幕、Solver 不讀螢幕）：
    QImage（呼叫端擷取）
      ↓ image_utils.qimage_to_gray
    灰階全 ROI
      ↓ grid.build_grid + CellGeometry.crop_box 切 150 格
    150 張 cell 小圖
      ↓ recognition.DigitRecognizer（先 EMPTY、再 Template Matching）
    BoardState（DIGIT / EMPTY / UNKNOWN 三態分離）

Builder 自己不擷取螢幕：呼叫端傳入灰階 ROI 畫面即可，
方便測試用固定截圖重現。
面板底色（panel_mean）從「所有 cell 中位數亮度」估計：
已消除的空格占多數時，中位數接近面板底色。
"""

from __future__ import annotations

import numpy as np

from core.board_state import BoardState, Cell, CellState
from core.grid import build_grid
from core.recognition import DigitRecognizer
from core.roi_model import Roi


def estimate_panel_mean(cell_images: list[np.ndarray]) -> float:
    """用所有 cell 中央小塊亮度的中位數估計面板底色。

    已消除的空格通常是多數（或至少接近一半）時，中位數會落在面板底色；
    若棋盤幾乎全滿（中位數落在數字上），呼叫端不該把 EMPTY 當成確定答案——
    DigitRecognizer 會因為平均亮度偏離 panel_mean 而回 UNKNOWN，這是刻意設計。
    """
    means: list[float] = []
    for image in cell_images:
        height, width = image.shape[:2]
        # 取中央 1/2 區域，避開 tile 圓角與格線
        x0, x1 = width // 4, width * 3 // 4
        y0, y1 = height // 4, height * 3 // 4
        center = image[y0:y1, x0:x1]
        if center.size:
            means.append(float(center.mean()))
    if not means:
        return 0.0
    return float(np.median(means))


def cut_cells(roi_image: np.ndarray, roi: Roi) -> list[np.ndarray]:
    """把灰階 ROI 畫面按固定 Grid 切成 150 張 cell 小圖（row-major）。"""
    if roi_image.ndim != 2 or roi_image.dtype != np.uint8:
        raise ValueError("roi_image 必須是 2D uint8 灰階影像")
    height, width = roi_image.shape[:2]
    cells: list[np.ndarray] = []
    for geometry in build_grid(roi):
        # CellGeometry 是全螢幕座標；roi_image 以 ROI 左上為原點，先平移
        x0, y0, x1, y1 = geometry.crop_box()
        x0 -= roi.x
        y0 -= roi.y
        x1 -= roi.x
        y1 -= roi.y
        x0 = max(0, min(x0, width))
        y0 = max(0, min(y0, height))
        x1 = max(0, min(x1, width))
        y1 = max(0, min(y1, height))
        if x1 <= x0 or y1 <= y0:
            cells.append(np.zeros((1, 1), dtype=np.uint8))
        else:
            cells.append(roi_image[y0:y1, x0:x1].copy())
    return cells


def build_board_state(
    roi_image: np.ndarray,
    roi: Roi,
    recognizer: DigitRecognizer,
) -> BoardState:
    """從灰階 ROI 畫面建立 BoardState。"""
    images = cut_cells(roi_image, roi)
    panel_mean = estimate_panel_mean(images)
    board = BoardState.all_unknown()
    for index, image in enumerate(images):
        row, column = divmod(index, 15)
        result = recognizer.recognize(image, panel_mean=panel_mean)
        if result.state == "digit":
            assert result.digit is not None
            board.cells[index] = Cell(
                row=row,
                column=column,
                state=CellState.DIGIT,
                digit=result.digit,
                confidence=result.confidence,
            )
        elif result.state == "empty":
            board.cells[index] = Cell(row=row, column=column, state=CellState.EMPTY)
        else:
            board.cells[index] = Cell(
                row=row, column=column, state=CellState.UNKNOWN, confidence=result.confidence
            )
    return board
