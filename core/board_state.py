"""Board State：10x15 棋盤狀態資料模型。

CellState 必須清楚分離三種語意（不要用 0 / -1 混淆）：
- DIGIT：該格有數字，另外保存 digit = 1~9
- EMPTY：該格確實沒有數字（已消除的空格）
- UNKNOWN：程式目前無法可靠判斷

BoardState 不依賴 GUI、不讀螢幕，Solver 只吃 BoardState。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.roi_model import GRID_COLS, GRID_ROWS


class CellState(Enum):
    """Cell 的辨識狀態（三態分離）。"""

    DIGIT = "digit"
    EMPTY = "empty"
    UNKNOWN = "unknown"


@dataclass
class Cell:
    """單一格子的辨識結果。"""

    row: int
    column: int
    state: CellState
    digit: int | None = None  # state == DIGIT 時為 1~9
    confidence: float = 0.0  # Template Matching 信心分數

    def __post_init__(self) -> None:
        if self.state == CellState.DIGIT:
            if self.digit is None or not 1 <= self.digit <= 9:
                raise ValueError("DIGIT 狀態必須帶有 1~9 的 digit")
        elif self.digit is not None:
            raise ValueError("只有 DIGIT 狀態可以帶 digit")


@dataclass
class BoardState:
    """10x15 棋盤狀態，cells 為 row-major 共 150 格。"""

    cells: list[Cell]

    def __post_init__(self) -> None:
        if len(self.cells) != GRID_ROWS * GRID_COLS:
            raise ValueError(f"BoardState 必須有 {GRID_ROWS * GRID_COLS} 格")
        for index, cell in enumerate(self.cells):
            want_row, want_col = divmod(index, GRID_COLS)
            if cell.row != want_row or cell.column != want_col:
                raise ValueError(f"第 {index} 格座標錯誤，應為 ({want_row}, {want_col})")

    @classmethod
    def all_unknown(cls) -> "BoardState":
        """建立 150 格全 UNKNOWN 的初始棋盤。"""
        cells = [
            Cell(row=row, column=column, state=CellState.UNKNOWN)
            for row in range(GRID_ROWS)
            for column in range(GRID_COLS)
        ]
        return cls(cells=cells)

    def at(self, row: int, column: int) -> Cell:
        """取得指定座標的 Cell，越界丟 IndexError。"""
        if not 0 <= row < GRID_ROWS or not 0 <= column < GRID_COLS:
            raise IndexError(f"座標超出 10x15：({row}, {column})")
        return self.cells[row * GRID_COLS + column]

    def digit_grid(self) -> list[list[int | None]]:
        """回傳 10x15 數字矩陣；DIGIT 放 digit，EMPTY/UNKNOWN 放 None。"""
        return [
            [
                cell.digit if cell.state == CellState.DIGIT else None
                for cell in self.cells[row * GRID_COLS : (row + 1) * GRID_COLS]
            ]
            for row in range(GRID_ROWS)
        ]

    def counts(self) -> dict[CellState, int]:
        """回傳三態各自的格數。"""
        result = {state: 0 for state in CellState}
        for cell in self.cells:
            result[cell.state] += 1
        return result

    def has_unknown(self) -> bool:
        """是否有 UNKNOWN（第一版：有 UNKNOWN 就不產生新的提示）。"""
        return any(cell.state == CellState.UNKNOWN for cell in self.cells)
