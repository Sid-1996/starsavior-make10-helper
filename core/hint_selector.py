"""Hint Selector：從 Solver 的全部候選中選出前 N 個提示。

排序策略（面積優先＋固定掃描順序）：
1. 第一優先：最小矩形面積（area）。
2. 相同面積：deterministic 掃描順序 row1 → col1 → row2 → col2
   （左上優先；同一棋盤狀態永遠產生一致的提示，不用 random）。

第 1 個是首選（照著打），第 2..N 個是備選（一次全顯示，輔助力道才夠）。
注意：
- 输入可以是任何順序；選擇結果與輸入順序無關（key 內含完整排序鍵）。
- 候選本身不可能含 UNKNOWN（Solver 已排除）；「整盤有 UNKNOWN 就不產生
  新提示」是監控迴圈的政策，不在這裡處理。
- 純函式，不依賴 GUI / OpenCV / 螢幕，可獨立測試。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from core.solver import Rectangle

DEFAULT_HINT_COUNT = 5
MAX_HINT_COUNT = 10


@dataclass(frozen=True)
class Hint:
    """單一推薦提示（首選或備選）。"""

    rectangle: Rectangle
    candidate_count: int  # 參與選擇的候選總數（除錯/狀態顯示用）


def select_hints(candidates: Sequence[Rectangle], limit: int = DEFAULT_HINT_COUNT) -> list[Hint]:
    """選出前 limit 個 Hint（面積排序）；無候選回傳空串列。"""
    if limit <= 0:
        return []
    ranked = sorted(
        candidates,
        key=lambda rect: (rect.area, rect.row1, rect.col1, rect.row2, rect.col2),
    )
    total = len(ranked)
    return [Hint(rectangle=rect, candidate_count=total) for rect in ranked[:limit]]


def select_hint(candidates: Sequence[Rectangle]) -> Hint | None:
    """選出唯一 Hint（首選）；無候選時回傳 None（呼叫端維持無提示狀態）。"""
    hints = select_hints(candidates, limit=1)
    return hints[0] if hints else None
