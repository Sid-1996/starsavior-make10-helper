"""畫面變化偵測 + Hint Lock（Phase 6，純邏輯，不碰 GUI / 螢幕擷取）。

流程（§十六）：
    固定間隔餵入 ROI 灰階幀
      ↓ StabilityTracker：連續 stable_required 幀無明顯變化才算穩定
      ↓ 穩定且與基準不同 → 呼叫端做一次乾淨重辨識（先隱藏 Overlay 再擷取）
      ↓ BoardMonitor.commit_board：UNKNOWN 維持舊提示；棋盤語意不變維持舊提示
      ↓ 真正變化 → 重新 Solver → 選新 Hint → 更新 Overlay

- 消除動畫中間幀不會連續穩定，因此不會觸發重辨識（動畫等待）。
- Hint Lock（§十七）：只要棋盤沒有有效變化，保持同一個 Hint 物件。
- 本模組不做辨識：build / solve / select 由呼叫端（主視窗監控迴圈）執行，
  commit 只收 BoardState，方便單元測試用合成棋盤驗證。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from core.board_state import BoardState
from core.hint_selector import DEFAULT_HINT_COUNT, Hint, select_hints
from core.solver import find_rectangles


@dataclass(frozen=True)
class MonitorConfig:
    """監控參數（呼叫端可調整；預設值針對 300ms 幀間隔調校）。"""

    frame_interval_ms: int = 300
    # 有明顯變化的像素比例（|亮度差| > 12 的像素占比）超過此值視為畫面變化。
    # 用比例而非全圖平均：消除 1~2 格只佔全 ROI 約 1%，平均值會被稀釋到看不見。
    diff_threshold: float = 0.002
    stable_required: int = 3  # 連續幾幀無明顯變化才算穩定（動畫等待）
    settle_delay_sec: float = 0.25  # 乾淨重辨識前，隱藏 Overlay 後的等待秒數
    max_clean_retries: int = 3  # 乾淨擷取仍殘留 Overlay 筆跡時的最大重試次數


PIXEL_DIFF_THRESHOLD = 12


def changed_pixel_ratio(first: np.ndarray, second: np.ndarray) -> float:
    """兩幀差異超過亮度門檻的像素比例（0~1）；形狀不同視為 1（ROI 變更）。"""
    if first.shape != second.shape:
        return 1.0
    delta = first.astype(np.int16) - second.astype(np.int16)
    return float(np.mean(np.abs(delta) > PIXEL_DIFF_THRESHOLD))


def board_key(board: BoardState) -> tuple[tuple[str, int | None], ...]:
    """棋盤語意指紋（只看 state + digit，忽略 confidence 浮點抖動）。"""
    return tuple((cell.state.value, cell.digit) for cell in board.cells)


class StabilityTracker:
    """幀穩定追蹤：回傳 True 表示「新的穩定畫面，與基準有有效差異」。"""

    def __init__(self, config: MonitorConfig = MonitorConfig()) -> None:
        self._config = config
        self._previous: np.ndarray | None = None
        self._baseline: np.ndarray | None = None
        self._run = 0
        self._emitted = False
        self._last_ratio = 0.0

    @property
    def run_length(self) -> int:
        """目前連續穩定計數（供狀態列顯示）。"""
        return self._run

    @property
    def last_ratio(self) -> float:
        """上一幀與前一幀的變化像素比例（供除錯日誌）。"""
        return self._last_ratio

    def note_frame(self, frame: np.ndarray) -> bool:
        """餵入一幀；需要乾淨重辨識時回傳 True（每個穩定段只回傳一次）。"""
        if frame.ndim != 2 or frame.dtype != np.uint8:
            raise ValueError("frame 必須是 2D uint8 灰階影像")
        ratio = 0.0 if self._previous is None else changed_pixel_ratio(frame, self._previous)
        self._last_ratio = ratio
        if self._previous is None or ratio > self._config.diff_threshold:
            self._run = 1
            self._emitted = False
        else:
            self._run += 1
        self._previous = frame.copy()
        if self._run >= self._config.stable_required and not self._emitted:
            self._emitted = True
            if (
                self._baseline is None
                or changed_pixel_ratio(frame, self._baseline) > self._config.diff_threshold
            ):
                self._baseline = frame.copy()
                return True
        return False

    def rebaseline(self, frame: np.ndarray) -> None:
        """把目前畫面設為新基準（提示更新後吸收 Overlay 像素差異，避免空轉）。"""
        self._baseline = frame.copy()
        self._previous = frame.copy()
        self._run = self._config.stable_required
        self._emitted = True


@dataclass
class MonitorSnapshot:
    """commit_board 的結果快照。"""

    rebuilt: bool  # 是否接受了新 board（UNKNOWN 不接受）
    changed: bool  # 棋盤是否有效變化（hints 是否已更新）
    board: BoardState | None
    hints: list[Hint]


@dataclass
class BoardMonitor:
    """持有穩定追蹤 + 目前棋盤 + 目前提示列（Hint Lock）。"""

    config: MonitorConfig = field(default_factory=MonitorConfig)
    tracker: StabilityTracker = field(init=False)
    board: BoardState | None = field(default=None, init=False)
    hints: list[Hint] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.tracker = StabilityTracker(self.config)

    def note_frame(self, frame: np.ndarray) -> bool:
        """稳定性追踪（見 StabilityTracker.note_frame）。"""
        return self.tracker.note_frame(frame)

    def rebaseline(self, frame: np.ndarray) -> None:
        """重設基準（見 StabilityTracker.rebaseline）。"""
        self.tracker.rebaseline(frame)

    def commit_board(
        self, board: BoardState, max_hints: int = DEFAULT_HINT_COUNT
    ) -> MonitorSnapshot:
        """提交乾淨重辨識的結果；回傳 hints 是否更新。

        - UNKNOWN：維持舊提示，等待下一次穩定畫面（§八）。
        - 語意不變：維持舊提示（Hint Lock，§十七）。
        - 有效變化：重新 Solver + 選前 max_hints 個 Hint（可能無候選 → 空串列）。
        """
        if board.has_unknown():
            return MonitorSnapshot(rebuilt=False, changed=False, board=self.board, hints=self.hints)
        if self.board is not None and board_key(board) == board_key(self.board):
            return MonitorSnapshot(rebuilt=False, changed=False, board=self.board, hints=self.hints)
        self.board = board
        self.hints = select_hints(find_rectangles(board), limit=max_hints, board=board)
        return MonitorSnapshot(rebuilt=True, changed=True, board=self.board, hints=self.hints)
