"""BoardBuilder 流程單元測試（合成 ROI 畫面，不讀螢幕）。"""

import numpy as np

from core.board_builder import build_board_state, cut_cells
from core.board_state import CellState
from core.recognition import DigitRecognizer
from core.roi_model import Roi
from core.templates import TemplateSet


def _make_roi_image() -> tuple[np.ndarray, Roi]:
    # 150x100 的 ROI：前 100 格暗（模擬面板/空格），後 50 格亮（模擬數字）
    # 暗格占多數，中位數可正確估計為面板底色
    image = np.full((100, 150), 200, dtype=np.uint8)
    image[:, :100] = 60
    return image, Roi(x=0, y=0, width=150, height=100)


class TestCutCells:
    def test_cuts_150_cells(self):
        image, roi = _make_roi_image()
        cells = cut_cells(image, roi)
        assert len(cells) == 150
        assert all(cell.ndim == 2 for cell in cells)

    def test_cell_content_matches_roi(self):
        image, roi = _make_roi_image()
        cells = cut_cells(image, roi)
        # 第 0 格在暗區，最後一格在亮區
        assert float(cells[0].mean()) < 100
        assert float(cells[-1].mean()) > 150

    def test_rejects_non_grayscale(self):
        _, roi = _make_roi_image()
        bad = np.zeros((100, 150, 3), dtype=np.uint8)
        try:
            cut_cells(bad, roi)
        except ValueError:
            return
        raise AssertionError("應拒絕非灰階影像")


class TestBuildBoardState:
    def test_empty_templates_give_unknown_or_empty(self):
        image, roi = _make_roi_image()
        recognizer = DigitRecognizer(TemplateSet(templates={}))
        board = build_board_state(image, roi, recognizer)
        assert len(board.cells) == 150
        # 沒有模板時：亮格 → UNKNOWN（不硬猜），暗格 → EMPTY
        assert board.at(0, 0).state == CellState.EMPTY
        assert board.at(0, 14).state == CellState.UNKNOWN

    def test_matching_template_gives_digit(self):
        image, roi = _make_roi_image()
        # 模板直接取右上 cell 的內容，保證高分
        cells = cut_cells(image, roi)
        import cv2

        template = cv2.resize(cells[14], (48, 48), interpolation=cv2.INTER_AREA)
        recognizer = DigitRecognizer(TemplateSet(templates={7: template}))
        board = build_board_state(image, roi, recognizer)
        assert board.at(0, 14).state == CellState.DIGIT
        assert board.at(0, 14).digit == 7
        assert board.at(0, 14).confidence > 0.9
