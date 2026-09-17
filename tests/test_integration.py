"""端到端整合測試：用真實模板拼出合成棋盤，走完整鏈。

ROI 畫面 → 切格 → 辨識 → BoardState → Solver → Hint Selector → Overlay 幾何，
再加 monitor 穩定→提交→切盤 的全鏈。模板來自 repo 內 templates/（真實遊戲擷取）。
"""

import cv2
import numpy as np

from core.board_builder import build_board_state
from core.board_state import CellState
from core.grid import build_grid
from core.hint_selector import select_hint
from core.monitor import BoardMonitor
from core.recognition import DigitRecognizer
from core.roi_model import Roi
from core.solver import find_rectangles
from core.templates import TemplateStore
from gui.hint_overlay import hint_shapes

ROI = Roi(x=0, y=0, width=930, height=620)  # 每格恰好 62x62
CELL = 62
PANEL = 128


def _compose(plant: dict[tuple[int, int], int]) -> np.ndarray:
    """拼合成 ROI 灰階圖：數字格放模板（48→62），其餘填面板底色。"""
    templates = TemplateStore().load_all()
    assert templates.is_complete()
    image = np.full((ROI.height, ROI.width), PANEL, dtype=np.uint8)
    for (row, column), digit in plant.items():
        tile = cv2.resize(templates.templates[digit], (CELL, CELL), interpolation=cv2.INTER_AREA)
        image[row * CELL : (row + 1) * CELL, column * CELL : (column + 1) * CELL] = tile
    return image


def _recognize(image: np.ndarray):
    recognizer = DigitRecognizer(TemplateStore().load_all())
    return build_board_state(image, ROI, recognizer)


def _recognize_at(image: np.ndarray, roi: Roi, cell: int):
    """任意 cell 尺寸的辨識（解析度無關性驗證用）。"""
    recognizer = DigitRecognizer(TemplateStore().load_all())
    return build_board_state(image, roi, recognizer)


class TestResolutionIndependence:
    def test_different_cell_size_still_recognized(self):
        """換解析度（80px 格）＋比例 ROI：同一模板照樣辨識（resize 到 48 比對）。"""
        from core.roi_model import RoiFrac

        cell = 80
        roi = Roi(x=0, y=0, width=15 * cell, height=10 * cell)
        templates = TemplateStore().load_all()
        image = np.full((roi.height, roi.width), PANEL, dtype=np.uint8)
        plant = {(0, 0): 4, (0, 1): 6, (9, 13): 5, (9, 14): 5}
        for (row, column), digit in plant.items():
            tile = cv2.resize(
                templates.templates[digit], (cell, cell), interpolation=cv2.INTER_AREA
            )
            image[row * cell : (row + 1) * cell, column * cell : (column + 1) * cell] = tile
        board = _recognize_at(image, roi, cell)
        assert not board.has_unknown()
        for (row, column), digit in plant.items():
            assert board.at(row, column).digit == digit
        # 比例 ROI 在此尺寸下換算回同一絕對座標
        frac = RoiFrac.from_absolute(roi, 0, 0, roi.width, roi.height)
        assert frac.to_absolute(0, 0, roi.width, roi.height) == roi


class TestFullPipeline:
    def test_recognize_solve_select_shapes(self):
        plant = {(0, 0): 4, (0, 1): 6, (5, 5): 8, (5, 8): 2}
        board = _recognize(_compose(plant))
        assert not board.has_unknown()
        for (row, column), digit in plant.items():
            cell = board.at(row, column)
            assert cell.state == CellState.DIGIT
            assert cell.digit == digit
        assert board.at(0, 2).state == CellState.EMPTY
        assert board.at(9, 14).state == CellState.EMPTY

        hint = select_hint(find_rectangles(board))
        assert hint is not None
        # 最小 area 優先：4+6（area=2）勝過 8□□2（area=4）
        assert (hint.rectangle.row1, hint.rectangle.col1) == (0, 0)
        assert hint.rectangle.area == 2

        shapes = hint_shapes(hint.rectangle, build_grid(ROI))
        assert shapes.start == (31.0, 31.0)
        assert shapes.end == (31.0 + CELL, 31.0)
        assert shapes.border == (0, 0, 2 * CELL, CELL)

    def test_monitor_chain_across_board_change(self):
        plant_a = {(0, 0): 4, (0, 1): 6}
        plant_b = {(9, 13): 5, (9, 14): 5}  # A 配對被消除，遠處開新局
        frame_a = _compose(plant_a)
        frame_b = _compose(plant_b)

        monitor = BoardMonitor()
        for _ in range(2):
            assert monitor.note_frame(frame_a) is False
        assert monitor.note_frame(frame_a) is True
        snapshot = monitor.commit_board(_recognize(frame_a))
        assert snapshot.changed is True
        assert (snapshot.hint.rectangle.row1, snapshot.hint.rectangle.col1) == (0, 0)
        monitor.rebaseline(frame_a)

        for _ in range(2):
            assert monitor.note_frame(frame_b) is False
        assert monitor.note_frame(frame_b) is True
        snapshot = monitor.commit_board(_recognize(frame_b))
        assert snapshot.changed is True
        assert (snapshot.hint.rectangle.row1, snapshot.hint.rectangle.col1) == (9, 13)
        monitor.rebaseline(frame_b)
        assert monitor.note_frame(frame_b) is False
