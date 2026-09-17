"""Hint Selector：從 Solver 的全部候選中選出前 N 個提示。

排序策略（面積優先＋固定掃描順序）：
1. 第一優先：最小矩形面積（area）。
2. 相同面積：deterministic 掃描順序 row1 → col1 → row2 → col2
   （左上優先；同一棋盤狀態永遠產生一致的提示，不用 random）。

第 1 個是首選（照著打），第 2..N 個是備選（一次全顯示，輔助力道才夠）。

同組數字去重（需傳 board）：後期棋盤空格多，同一組數字會被多個
大小不同的矩形框住（多的只是 EMPTY 留白，消下去結果完全一樣）。
greedy 依排名順序收：某候選的數字格集合已被已選提示覆蓋 → 跳過、
往後補滿 limit。只共享部分數字（走法真的不同）的不受影響，照常保留。
注意：
- 输入可以是任何順序；選擇結果與輸入順序無關（key 內含完整排序鍵）。
- 候選本身不可能含 UNKNOWN（Solver 已排除）；「整盤有 UNKNOWN 就不產生
  新提示」是監控迴圈的政策，不在這裡處理。
- 不傳 board 時退化為純面積截斷（舊行為，供不需要去重的呼叫端與測試）。
- 純函式，不依賴 GUI / OpenCV / 螢幕，可獨立測試。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from core.board_state import BoardState, CellState
from core.solver import Rectangle

DEFAULT_HINT_COUNT = 5
MAX_HINT_COUNT = 10


@dataclass(frozen=True)
class Hint:
    """單一推薦提示（首選或備選）。"""

    rectangle: Rectangle
    candidate_count: int  # 參與選擇的候選總數（除錯/狀態顯示用）


def _digit_cells(rectangle: Rectangle, board: BoardState) -> set[tuple[int, int]]:
    """矩形內 DIGIT 格的座標集合（EMPTY 留白不計；同組判斷只看數字）。"""
    cells = set()
    for row in range(rectangle.row1, rectangle.row2 + 1):
        for column in range(rectangle.col1, rectangle.col2 + 1):
            if board.at(row, column).state == CellState.DIGIT:
                cells.add((row, column))
    return cells


def select_hints(
    candidates: Sequence[Rectangle],
    limit: int = DEFAULT_HINT_COUNT,
    board: BoardState | None = None,
) -> list[Hint]:
    """選出前 limit 個 Hint（面積排序＋同組數字去重）；無候選回傳空串列。"""
    if limit <= 0:
        return []
    ranked = sorted(
        candidates,
        key=lambda rect: (rect.area, rect.row1, rect.col1, rect.row2, rect.col2),
    )
    total = len(ranked)
    if board is None:
        return [Hint(rectangle=rect, candidate_count=total) for rect in ranked[:limit]]
    picked: list[Hint] = []
    covered: set[tuple[int, int]] = set()
    for rect in ranked:
        digits = _digit_cells(rect, board)
        if digits and digits <= covered:
            continue  # 同組數字已有更小的框：跳過，往後補
        covered |= digits
        picked.append(Hint(rectangle=rect, candidate_count=total))
        if len(picked) >= limit:
            break
    return picked


def select_hint(candidates: Sequence[Rectangle]) -> Hint | None:
    """選出唯一 Hint（首選）；無候選時回傳 None（呼叫端維持無提示狀態）。"""
    hints = select_hints(candidates, limit=1)
    return hints[0] if hints else None
