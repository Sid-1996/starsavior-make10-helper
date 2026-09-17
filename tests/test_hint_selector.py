"""Hint Selector 單元測試（純函式，不碰螢幕/GUI）。"""

from core.board_state import BoardState, Cell, CellState
from core.hint_selector import Hint, select_hint, select_hints
from core.solver import Rectangle, find_rectangles


def _rect(row1, col1, row2, col2) -> Rectangle:
    area = (row2 - row1 + 1) * (col2 - col1 + 1)
    return Rectangle(row1, col1, row2, col2, 10, 2, area - 2, area)


class TestSelectHint:
    def test_empty_gives_none(self):
        assert select_hint([]) is None

    def test_single_candidate(self):
        only = _rect(2, 3, 2, 4)
        assert select_hint([only]) == Hint(rectangle=only, candidate_count=1)

    def test_min_area_wins(self):
        # 4+6（area=2）優先於 8□□2（area=4）；不要禁止遠距離候選
        small = _rect(0, 0, 0, 1)
        large = Rectangle(5, 5, 5, 8, 10, 2, 2, 4)
        assert select_hint([large, small]) == Hint(rectangle=small, candidate_count=2)

    def test_far_candidate_still_selectable(self):
        # 沒有較小矩形時，遠距離候選仍可被選中
        far = Rectangle(0, 0, 0, 5, 10, 2, 4, 6)
        assert select_hint([far]) == Hint(rectangle=far, candidate_count=1)

    def test_tie_breaks_by_scan_order(self):
        # 相同 area：row1 → col1 → row2 → col2，左上優先
        lower = _rect(3, 0, 3, 1)
        upper = _rect(0, 5, 0, 6)
        assert select_hint([lower, upper]).rectangle == upper
        assert select_hint([upper, lower]).rectangle == upper

    def test_tie_breaks_by_end_corner(self):
        first = _rect(0, 0, 0, 1)
        second = _rect(0, 0, 1, 1)
        assert select_hint([second, first]).rectangle == first

    def test_result_independent_of_input_order(self):
        candidates = [_rect(5, 5, 5, 6), _rect(0, 0, 0, 1), _rect(2, 2, 4, 4)]
        assert select_hint(candidates) == select_hint(list(reversed(candidates)))

    def test_does_not_mutate_input(self):
        candidates = [_rect(5, 5, 5, 6), _rect(0, 0, 0, 1)]
        snapshot = list(candidates)
        select_hint(candidates)
        assert candidates == snapshot


class TestSelectHints:
    def test_empty_gives_empty_list(self):
        assert select_hints([]) == []
        assert select_hints([], limit=3) == []

    def test_limit_truncates_by_area_order(self):
        areas = [_rect(0, 0, 0, 5), _rect(0, 0, 0, 1), _rect(2, 2, 4, 4), _rect(0, 5, 0, 6)]
        hints = select_hints(areas, limit=2)
        assert [h.rectangle.area for h in hints] == [2, 2]
        assert (hints[0].rectangle.row1, hints[0].rectangle.col1) == (0, 0)
        assert (hints[1].rectangle.row1, hints[1].rectangle.col1) == (0, 5)
        assert all(h.candidate_count == 4 for h in hints)

    def test_limit_larger_than_candidates(self):
        only = _rect(2, 3, 2, 4)
        assert select_hints([only], limit=5) == [Hint(rectangle=only, candidate_count=1)]

    def test_nonpositive_limit(self):
        assert select_hints([_rect(0, 0, 0, 1)], limit=0) == []

    def test_single_wrapper_matches_first(self):
        candidates = [_rect(5, 5, 5, 6), _rect(0, 0, 0, 1)]
        assert select_hint(candidates) == select_hints(candidates, limit=5)[0]


class TestSelectorWithSolver:
    def _board(self, digits: dict[tuple[int, int], int]) -> BoardState:
        cells = []
        for row in range(10):
            for column in range(15):
                if (row, column) in digits:
                    cells.append(
                        Cell(
                            row=row,
                            column=column,
                            state=CellState.DIGIT,
                            digit=digits[(row, column)],
                        )
                    )
                else:
                    cells.append(Cell(row=row, column=column, state=CellState.EMPTY))
        return BoardState(cells=cells)

    def test_solver_to_hint_picks_min_area(self):
        # §二十二-12：小矩形 4+6（area=2）勝過遠距離 8□□2（area=4）
        board = self._board({(0, 0): 4, (0, 1): 6, (5, 5): 8, (5, 8): 2})
        hint = select_hint(find_rectangles(board))
        assert hint is not None
        assert (hint.rectangle.row1, hint.rectangle.col1) == (0, 0)
        assert hint.rectangle.area == 2
        assert hint.candidate_count == len(find_rectangles(board))

    def test_solver_to_hint_none_when_no_candidate(self):
        board = self._board({(0, 0): 5})
        assert select_hint(find_rectangles(board)) is None
