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
from core.i18n import t

_DIGIT_STYLE = "font-family: Consolas, monospace; font-size: 13px;"
_UNKNOWN_STYLE = "font-family: Consolas, monospace; font-size: 13px; color: #e0a030;"
_EMPTY_STYLE = "font-family: Consolas, monospace; font-size: 13px; color: #808080;"


class RecognitionPanel(QWidget):
    """10x15 辨識結果矩陣 + 三態統計。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._matrix_label = QLabel(t("panel.initial"))
        self._matrix_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._matrix_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._matrix_label.setStyleSheet(_DIGIT_STYLE)
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._last_board: BoardState | None = None
        self._last_missing: list[int] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._matrix_label)
        layout.addWidget(self._status_label)

    def retranslate(self) -> None:
        """語言切換時用最後的資料重繪（無資料回到初始文字）。"""
        if self._last_board is not None:
            self.show_board(self._last_board, self._last_missing)
        else:
            self._matrix_label.setText(t("panel.initial"))
            self._status_label.setText("")

    def show_board(self, board: BoardState, missing_templates: list[int]) -> None:
        """顯示 BoardState；missing_templates 為缺失的模板 digit 清單。"""
        self._last_board = board
        self._last_missing = list(missing_templates)
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
        status = t(
            "panel.stats",
            digit=counts[CellState.DIGIT],
            empty=counts[CellState.EMPTY],
            unknown=counts[CellState.UNKNOWN],
        )
        if missing_templates:
            missing = "、".join(str(digit) for digit in missing_templates)
            status += t("panel.missing", missing=missing)
        self._status_label.setText(status)

    def show_message(self, message: str) -> None:
        """顯示純文字訊息（例如尚未辨識、辨識失敗）。"""
        self._matrix_label.setText(message)
        self._status_label.setText("")


def make_group_box(panel: RecognitionPanel) -> QGroupBox:
    """包一層 GroupBox，方便主視窗排版。標題由呼叫端在切語言時重設。"""
    group = QGroupBox(t("panel.group"))
    layout = QVBoxLayout(group)
    layout.addWidget(panel)
    return group
