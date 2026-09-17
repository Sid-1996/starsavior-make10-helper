"""辨識結果預覽面板（Phase 2）。

顯示 10x15 辨識矩陣：
- 數字格：顯示 1~9
- EMPTY：顯示 □
- UNKNOWN：顯示 ?

同時顯示三態統計與模板缺失提示。純顯示，不做辨識。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGroupBox, QLabel, QVBoxLayout, QWidget

from core.board_state import BoardState, CellState

_DIGIT_STYLE = "font-family: Consolas, monospace; font-size: 13px;"
_UNKNOWN_STYLE = "font-family: Consolas, monospace; font-size: 13px; color: #e0a030;"
_EMPTY_STYLE = "font-family: Consolas, monospace; font-size: 13px; color: #808080;"


class RecognitionPanel(QWidget):
    """10x15 辨識結果矩陣 + 三態統計。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._matrix_label = QLabel("尚未辨識")
        self._matrix_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._matrix_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._matrix_label.setStyleSheet(_DIGIT_STYLE)
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._matrix_label)
        layout.addWidget(self._status_label)

    def show_board(self, board: BoardState, missing_templates: list[int]) -> None:
        """顯示 BoardState；missing_templates 為缺失的模板 digit 清單。"""
        lines: list[str] = []
        for row in range(10):
            parts: list[str] = []
            for column in range(15):
                cell = board.at(row, column)
                if cell.state == CellState.DIGIT:
                    assert cell.digit is not None
                    parts.append(str(cell.digit))
                elif cell.state == CellState.EMPTY:
                    parts.append("□")
                else:
                    parts.append("?")
            lines.append(" ".join(parts))
        self._matrix_label.setText("\n".join(lines))

        counts = board.counts()
        status = (
            f"數字 {counts[CellState.DIGIT]} 格 / "
            f"空格 {counts[CellState.EMPTY]} 格 / "
            f"未知 {counts[CellState.UNKNOWN]} 格"
        )
        if missing_templates:
            missing = "、".join(str(digit) for digit in missing_templates)
            status += f"\n缺少模板：{missing}（相關格子只能判為 UNKNOWN，請先建立模板）"
        self._status_label.setText(status)

    def show_message(self, message: str) -> None:
        """顯示純文字訊息（例如尚未辨識、辨識失敗）。"""
        self._matrix_label.setText(message)
        self._status_label.setText("")


def make_group_box(panel: RecognitionPanel) -> QGroupBox:
    """包一層 GroupBox，方便主視窗排版。"""
    group = QGroupBox("辨識結果預覽（10 × 15）")
    layout = QVBoxLayout(group)
    layout.addWidget(panel)
    return group
