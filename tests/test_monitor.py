"""畫面變化偵測 + Hint Lock 單元測試（合成灰階幀 / 合成棋盤，不碰螢幕）。"""

import numpy as np
import pytest

from core.board_state import BoardState, Cell, CellState
from core.monitor import BoardMonitor, MonitorConfig, StabilityTracker, board_key, mean_abs_diff


def _frame(mark: tuple[int, int] | None = None) -> np.ndarray:
    """20x30 灰階幀；mark 在指定位置放一塊亮斑（模擬數字出現/消失）。"""
    image = np.full((20, 30), 60, dtype=np.uint8)
    if mark is not None:
        image[mark[0] : mark[0] + 4, mark[1] : mark[1] + 6] = 200
    return image


def _config() -> MonitorConfig:
    return MonitorConfig(diff_threshold=5.0, stable_required=3)


def make_board(
    digits: dict[tuple[int, int], int] | None = None,
    unknowns: set[tuple[int, int]] | None = None,
) -> BoardState:
    digits = digits or {}
    unknowns = unknowns or set()
    cells = []
    for row in range(10):
        for column in range(15):
            if (row, column) in unknowns:
                cells.append(Cell(row=row, column=column, state=CellState.UNKNOWN))
            elif (row, column) in digits:
                cells.append(
                    Cell(row=row, column=column, state=CellState.DIGIT, digit=digits[(row, column)])
                )
            else:
                cells.append(Cell(row=row, column=column, state=CellState.EMPTY))
    return BoardState(cells=cells)


class TestMeanAbsDiff:
    def test_identical_is_zero(self):
        assert mean_abs_diff(_frame(), _frame()) == 0.0

    def test_shape_mismatch_is_infinite(self):
        assert mean_abs_diff(_frame(), np.zeros((5, 5), dtype=np.uint8)) == float("inf")

    def test_rejects_non_grayscale(self):
        tracker = StabilityTracker(_config())
        with pytest.raises(ValueError):
            tracker.note_frame(np.zeros((10, 10, 3), dtype=np.uint8))


class TestStabilityTracker:
    def test_stable_run_emits_once(self):
        tracker = StabilityTracker(_config())
        assert tracker.note_frame(_frame()) is False
        assert tracker.note_frame(_frame()) is False
        assert tracker.note_frame(_frame()) is True  # 連續 3 幀穩定
        assert tracker.note_frame(_frame()) is False  # 同一段不再重複回報

    def test_change_resets_run(self):
        tracker = StabilityTracker(_config())
        tracker.note_frame(_frame())
        tracker.note_frame(_frame())
        assert tracker.note_frame(_frame((0, 0))) is False  # 變化打斷連續計數
        assert tracker.note_frame(_frame((0, 0))) is False
        assert tracker.note_frame(_frame((0, 0))) is True  # 新畫面重新穩定

    def test_flicker_never_stabilizes(self):
        # 消除動畫中間幀來回跳動：永不觸發重辨識
        tracker = StabilityTracker(_config())
        results = [tracker.note_frame(_frame((0, 0) if i % 2 else None)) for i in range(10)]
        assert results == [False] * 10

    def test_small_noise_stays_stable(self):
        tracker = StabilityTracker(_config())
        base = _frame()
        noisy = base.astype(np.int16) + 1  # 全圖 +1：平均差 1 < 門檻
        noisy = np.clip(noisy, 0, 255).astype(np.uint8)
        assert tracker.note_frame(base) is False
        assert tracker.note_frame(noisy) is False
        assert tracker.note_frame(base) is True

    def test_rebaseline_absorbs_current_frame(self):
        tracker = StabilityTracker(_config())
        tracker.note_frame(_frame())
        tracker.note_frame(_frame())
        assert tracker.note_frame(_frame()) is True
        tracker.rebaseline(_frame((0, 0)))  # 如 Overlay 更新後的像素變化
        assert tracker.note_frame(_frame((0, 0))) is False
        assert tracker.note_frame(_frame((0, 0))) is False


class TestBoardMonitor:
    def test_first_commit_establishes_hint(self):
        monitor = BoardMonitor(_config())
        snapshot = monitor.commit_board(make_board({(0, 0): 4, (0, 1): 6}))
        assert snapshot.rebuilt is True
        assert snapshot.changed is True
        assert snapshot.hint is not None
        assert snapshot.hint.rectangle.area == 2

    def test_hint_lock_keeps_same_object(self):
        monitor = BoardMonitor(_config())
        first = monitor.commit_board(make_board({(0, 0): 4, (0, 1): 6}))
        # confidence 不同但語意相同 → 不算變化，Hint 物件保持同一
        twin = make_board({(0, 0): 4, (0, 1): 6})
        twin.cells[0].confidence = 0.99
        second = monitor.commit_board(twin)
        assert second.rebuilt is False
        assert second.changed is False
        assert second.hint is first.hint

    def test_unknown_keeps_old_hint(self):
        monitor = BoardMonitor(_config())
        monitor.commit_board(make_board({(0, 0): 4, (0, 1): 6}))
        snapshot = monitor.commit_board(make_board({(0, 0): 4}, unknowns={(0, 1), (5, 5)}))
        assert snapshot.rebuilt is False
        assert snapshot.changed is False
        assert snapshot.hint is monitor.hint
        assert (snapshot.hint.rectangle.row1, snapshot.hint.rectangle.col1) == (0, 0)

    def test_real_change_updates_hint(self):
        monitor = BoardMonitor(_config())
        monitor.commit_board(make_board({(0, 0): 4, (0, 1): 6}))
        # 消除後：原配對清空，遠處出現 9+1
        snapshot = monitor.commit_board(make_board({(7, 7): 9, (7, 8): 1}))
        assert snapshot.rebuilt is True
        assert snapshot.changed is True
        assert (snapshot.hint.rectangle.row1, snapshot.hint.rectangle.col1) == (7, 7)

    def test_no_candidate_clears_hint(self):
        monitor = BoardMonitor(_config())
        monitor.commit_board(make_board({(0, 0): 4, (0, 1): 6}))
        snapshot = monitor.commit_board(make_board({(0, 0): 5}))
        assert snapshot.changed is True
        assert snapshot.hint is None

    def test_full_flow_stable_commit_rebaseline_quiet(self):
        monitor = BoardMonitor(_config())
        frame = _frame()
        assert monitor.note_frame(frame) is False
        assert monitor.note_frame(frame) is False
        assert monitor.note_frame(frame) is True
        snapshot = monitor.commit_board(make_board({(0, 0): 4, (0, 1): 6}))
        assert snapshot.changed is True
        monitor.rebaseline(frame)  # 提示顯示後吸收當前畫面
        assert monitor.note_frame(frame) is False
        assert monitor.note_frame(frame) is False

    def test_board_key_ignores_confidence(self):
        left = make_board({(0, 0): 4})
        right = make_board({(0, 0): 4})
        right.cells[0].confidence = 0.5
        assert board_key(left) == board_key(right)
