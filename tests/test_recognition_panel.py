"""辨識結果面板單元測試（offscreen，不實際截圖）。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.board_state import BoardState, Cell, CellState  # noqa: E402
from gui.recognition_panel import RecognitionPanel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _board_with_states() -> BoardState:
    board = BoardState.all_unknown()
    board.cells[0] = Cell(row=0, column=0, state=CellState.DIGIT, digit=8, confidence=0.9)
    board.cells[1] = Cell(row=0, column=1, state=CellState.EMPTY)
    return board


class TestRecognitionPanel:
    def test_show_board_matrix(self, qapp):
        panel = RecognitionPanel()
        panel.show_board(_board_with_states(), [])
        lines = panel._matrix_label.text().split("\n")
        assert len(lines) == 10
        assert lines[0].split(" ")[:3] == ["8", "□", "?"]
        assert "數字 1 格" in panel._status_label.text()
        assert "空格 1 格" in panel._status_label.text()
        assert "未知 148 格" in panel._status_label.text()

    def test_show_missing_templates(self, qapp):
        panel = RecognitionPanel()
        panel.show_board(_board_with_states(), [4, 7])
        assert "缺少模板：4、7" in panel._status_label.text()

    def test_show_message(self, qapp):
        panel = RecognitionPanel()
        panel.show_message("尚未辨識")
        assert panel._matrix_label.text() == "尚未辨識"
        assert panel._status_label.text() == ""
