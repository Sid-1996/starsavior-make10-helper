"""Rectangle Solver：純 Python 演算法，只吃 BoardState。

合法矩形（完整矩形，含兩端；1xN / Nx1 / 正方形皆可）：
1. 矩形內所有數字總和 == 10（EMPTY 視為 0，可以被跨越）
2. 至少含有一個 DIGIT（全 EMPTY 不是候選）
3. 含有 UNKNOWN 的矩形一律排除（不可靠，不硬猜）

注意：「整盤有 UNKNOWN 就不產生新提示」是監控迴圈（Phase 6）的政策；
Solver 只保證回傳的候選本身不含 UNKNOWN。

實作：2D Prefix Sum（數值表 + UNKNOWN 計數表 + DIGIT 計數表），
每個矩形 O(1) 查詢；列舉時沿 col2 方向累加，總和 > 10 提早剪枝
（數字皆非負：EMPTY 以 0 計，UNKNOWN 也以 0 計入累加——真實總和只會
更大，所以剪枝安全；UNKNOWN 矩形另行排除）。

輸出為 deterministic 掃描順序：row1 → col1 → row2 → col2。
Solver 不負責選提示（最小 area 優先是 Phase 4 Hint Selector 的事）。
不依賴 OpenCV / GUI / 螢幕，可獨立測試。
"""

from __future__ import annotations

from dataclasses import dataclass

from core.board_state import BoardState, CellState
from core.roi_model import GRID_COLS, GRID_ROWS

TARGET_SUM = 10


@dataclass(frozen=True)
class Rectangle:
    """合法消除矩形（包含兩端）；total 恆為 10，留著供除錯/顯示。"""

    row1: int
    col1: int
    row2: int
    col2: int
    total: int
    number_count: int  # DIGIT 格數
    empty_count: int  # EMPTY 格數（UNKNOWN 必為 0，否則不會回傳）
    area: int  # (row2-row1+1) * (col2-col1+1)，供 Phase 4 排序


def _prefix_sums(board: BoardState) -> tuple[list[list[int]], list[list[int]], list[list[int]]]:
    """回傳 (數值, unknown計數, digit計數) 三張 (ROWS+1)x(COLS+1) prefix sum 表。"""
    values = [[0] * (GRID_COLS + 1) for _ in range(GRID_ROWS + 1)]
    unknowns = [[0] * (GRID_COLS + 1) for _ in range(GRID_ROWS + 1)]
    digits = [[0] * (GRID_COLS + 1) for _ in range(GRID_ROWS + 1)]
    for row in range(GRID_ROWS):
        value_row, unknown_row, digit_row = values[row + 1], unknowns[row + 1], digits[row + 1]
        for column in range(GRID_COLS):
            cell = board.at(row, column)
            value = cell.digit if cell.state == CellState.DIGIT else 0
            unknown = 1 if cell.state == CellState.UNKNOWN else 0
            digit = 1 if cell.state == CellState.DIGIT else 0
            value_row[column + 1] = (
                value_row[column] + values[row][column + 1] - values[row][column] + value
            )
            unknown_row[column + 1] = (
                unknown_row[column] + unknowns[row][column + 1] - unknowns[row][column] + unknown
            )
            digit_row[column + 1] = (
                digit_row[column] + digits[row][column + 1] - digits[row][column] + digit
            )
    return values, unknowns, digits


def _rect_query(table: list[list[int]], row1: int, col1: int, row2: int, col2: int) -> int:
    """左閉右閉矩形查詢（O(1)）。"""
    return (
        table[row2 + 1][col2 + 1]
        - table[row1][col2 + 1]
        - table[row2 + 1][col1]
        + table[row1][col1]
    )


def find_rectangles(board: BoardState) -> list[Rectangle]:
    """找出棋盤上所有合法矩形（deterministic 掃描順序）。"""
    values, unknowns, digits = _prefix_sums(board)
    found: list[Rectangle] = []
    for row1 in range(GRID_ROWS):
        for col1 in range(GRID_COLS):
            for row2 in range(row1, GRID_ROWS):
                total = 0
                for col2 in range(col1, GRID_COLS):
                    # 加上 (row1..row2, col2) 這一條 column strip
                    total += _rect_query(values, row1, col2, row2, col2)
                    if total > TARGET_SUM:
                        break  # 數字非負，繼續右擴只會更大
                    if _rect_query(unknowns, row1, col1, row2, col2) > 0:
                        continue
                    number_count = _rect_query(digits, row1, col1, row2, col2)
                    if number_count == 0 or total != TARGET_SUM:
                        continue
                    area = (row2 - row1 + 1) * (col2 - col1 + 1)
                    found.append(
                        Rectangle(
                            row1=row1,
                            col1=col1,
                            row2=row2,
                            col2=col2,
                            total=total,
                            number_count=number_count,
                            empty_count=area - number_count,
                            area=area,
                        )
                    )
    return found
