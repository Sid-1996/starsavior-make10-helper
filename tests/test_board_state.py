"""BoardState / Cell 三態分離單元測試。"""

import pytest

from core.board_state import BoardState, Cell, CellState


class TestCell:
    def test_digit_requires_valid_digit(self):
        cell = Cell(row=0, column=0, state=CellState.DIGIT, digit=5, confidence=0.9)
        assert cell.digit == 5

    @pytest.mark.parametrize("bad", [None, 0, 10, -1])
    def test_digit_rejects_invalid_digit(self, bad):
        with pytest.raises(ValueError):
            Cell(row=0, column=0, state=CellState.DIGIT, digit=bad)

    def test_empty_cannot_carry_digit(self):
        with pytest.raises(ValueError):
            Cell(row=0, column=0, state=CellState.EMPTY, digit=3)

    def test_unknown_cannot_carry_digit(self):
        with pytest.raises(ValueError):
            Cell(row=0, column=0, state=CellState.UNKNOWN, digit=3)

    def test_empty_and_unknown_default_no_digit(self):
        assert Cell(row=1, column=2, state=CellState.EMPTY).digit is None
        assert Cell(row=1, column=2, state=CellState.UNKNOWN).digit is None


class TestBoardState:
    def test_all_unknown_has_150_cells(self):
        board = BoardState.all_unknown()
        assert len(board.cells) == 150
        assert all(cell.state == CellState.UNKNOWN for cell in board.cells)

    def test_rejects_wrong_cell_count(self):
        with pytest.raises(ValueError):
            BoardState(cells=[])

    def test_rejects_misplaced_cell(self):
        board = BoardState.all_unknown()
        board.cells[0] = Cell(row=9, column=9, state=CellState.EMPTY)
        with pytest.raises(ValueError):
            BoardState(cells=board.cells)

    def test_at_returns_correct_cell(self):
        board = BoardState.all_unknown()
        board.cells[3 * 15 + 7] = Cell(row=3, column=7, state=CellState.DIGIT, digit=4)
        assert board.at(3, 7).digit == 4

    @pytest.mark.parametrize("pos", [(-1, 0), (0, -1), (10, 0), (0, 15)])
    def test_at_out_of_bounds(self, pos):
        board = BoardState.all_unknown()
        with pytest.raises(IndexError):
            board.at(*pos)

    def test_digit_grid(self):
        board = BoardState.all_unknown()
        board.cells[0] = Cell(row=0, column=0, state=CellState.DIGIT, digit=8)
        board.cells[1] = Cell(row=0, column=1, state=CellState.EMPTY)
        grid = board.digit_grid()
        assert len(grid) == 10
        assert len(grid[0]) == 15
        assert grid[0][0] == 8
        assert grid[0][1] is None  # EMPTY → None
        assert grid[9][14] is None  # UNKNOWN → None

    def test_counts(self):
        board = BoardState.all_unknown()
        board.cells[0] = Cell(row=0, column=0, state=CellState.DIGIT, digit=1)
        board.cells[1] = Cell(row=0, column=1, state=CellState.EMPTY)
        counts = board.counts()
        assert counts[CellState.DIGIT] == 1
        assert counts[CellState.EMPTY] == 1
        assert counts[CellState.UNKNOWN] == 148

    def test_has_unknown(self):
        board = BoardState.all_unknown()
        assert board.has_unknown() is True
        for index, cell in enumerate(board.cells):
            row, column = divmod(index, 15)
            board.cells[index] = Cell(row=row, column=column, state=CellState.EMPTY)
        assert board.has_unknown() is False
