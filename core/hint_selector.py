"""Hint Selector：從 Solver 的全部候選中選出唯一提示。

選擇策略（§十二，唯一確定的主要策略）：
1. 第一優先：最小矩形面積（area）。
2. 相同面積：deterministic 掃描順序 row1 → col1 → row2 → col2
   （左上優先；同一棋盤狀態永遠產生一致的提示，不用 random）。

注意：
- 输入可以是任何順序；選擇結果與輸入順序無關（key 內含完整排序鍵）。
- 候選本身不可能含 UNKNOWN（Solver 已排除）；「整盤有 UNKNOWN 就不產生
  新提示」是監控迴圈（Phase 6）的政策，不在這裡處理。
- 純函式，不依賴 GUI / OpenCV / 螢幕，可獨立測試。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from core.solver import Rectangle


@dataclass(frozen=True)
class Hint:
    """唯一推薦提示。"""

    rectangle: Rectangle
    candidate_count: int  # 參與選擇的候選總數（除錯/狀態顯示用）


def select_hint(candidates: Sequence[Rectangle]) -> Hint | None:
    """選出唯一 Hint；無候選時回傳 None（呼叫端維持無提示狀態）。"""
    if not candidates:
        return None
    best = min(
        candidates,
        key=lambda rect: (rect.area, rect.row1, rect.col1, rect.row2, rect.col2),
    )
    return Hint(rectangle=best, candidate_count=len(candidates))
