"""Rectangle Solver 單元測試（純 BoardState，不碰螢幕/GUI/OpenCV）。"""

import random

from core.board_state import BoardState, Cell, CellState
from core.solver import Rectangle, find_rectangles


def make_board(
    digits: dict[tuple[int, int], int] | None = None,
    unknowns: set[tuple[int, int]] | None = None,
) -> BoardState:
    """稀疏建盤：digits 是 (row, col) -> 1~9；其餘為 EMPTY；unknowns 為 UNKNOWN。"""
    digits = digits or {}
    unknowns = unknowns or set()
    cells = []
    for row in range(10):
        for column in range(15):
            if (row, column) in unknowns:
                cells.append(Cell(row=row, column=column, state=CellState.UNKNOWN))
            elif (row, column) in digits:
                digit = digits[(row, column)]
                cells.append(Cell(row=row, column=column, state=CellState.DIGIT, digit=digit))
            else:
                cells.append(Cell(row=row, column=column, state=CellState.EMPTY))
    return BoardState(cells=cells)


def rect_of(board: BoardState, rectangle: Rectangle) -> list[Cell]:
    """取出矩形涵蓋的 cells（驗證用：重算總和必須為 10）。"""
    return [
        board.at(row, column)
        for row in range(rectangle.row1, rectangle.row2 + 1)
        for column in range(rectangle.col1, rectangle.col2 + 1)
    ]


def brute_force(board: BoardState) -> set[Rectangle]:
    """獨立參考實作：四重迴圈直接加總，無 prefix sum、無剪枝。"""
    expected: set[Rectangle] = set()
    for row1 in range(10):
        for col1 in range(15):
            for row2 in range(row1, 10):
                for col2 in range(col1, 15):
                    cells = [
                        board.at(row, column)
                        for row in range(row1, row2 + 1)
                        for column in range(col1, col2 + 1)
                    ]
                    if any(cell.state == CellState.UNKNOWN for cell in cells):
                        continue
                    digits = [cell.digit for cell in cells if cell.state == CellState.DIGIT]
                    if not digits or sum(digits) != 10:
                        continue
                    area = (row2 - row1 + 1) * (col2 - col1 + 1)
                    expected.add(
                        Rectangle(row1, col1, row2, col2, 10, len(digits), area - len(digits), area)
                    )
    return expected


def assert_solver_matches_brute_force(board: BoardState) -> list[Rectangle]:
    """Solver 回傳必須與參考實作完全一致（集合相等）。"""
    found = find_rectangles(board)
    assert set(found) == brute_force(board)
    return found


class TestBasicPairs:
    def test_4_plus_6(self):
        board = make_board({(0, 0): 4, (0, 1): 6})
        found = assert_solver_matches_brute_force(board)
        assert Rectangle(0, 0, 0, 1, total=10, number_count=2, empty_count=0, area=2) in found

    def test_8_plus_2(self):
        board = make_board({(3, 3): 8, (3, 4): 2})
        found = assert_solver_matches_brute_force(board)
        assert Rectangle(3, 3, 3, 4, total=10, number_count=2, empty_count=0, area=2) in found

    def test_empty_crossing(self):
        # 8 □ □ 2：EMPTY 視為 0，可以被跨越
        board = make_board({(0, 0): 8, (0, 3): 2})
        found = assert_solver_matches_brute_force(board)
        assert Rectangle(0, 0, 0, 3, total=10, number_count=2, empty_count=2, area=4) in found

    def test_2x2(self):
        board = make_board({(0, 0): 1, (0, 1): 2, (1, 0): 3, (1, 1): 4})
        found = assert_solver_matches_brute_force(board)
        assert Rectangle(0, 0, 1, 1, total=10, number_count=4, empty_count=0, area=4) in found

    def test_1xn_row(self):
        board = make_board({(2, 5): 1, (2, 6): 2, (2, 7): 3, (2, 8): 4})
        found = assert_solver_matches_brute_force(board)
        assert Rectangle(2, 5, 2, 8, total=10, number_count=4, empty_count=0, area=4) in found

    def test_nx1_column(self):
        board = make_board({(0, 7): 1, (1, 7): 2, (2, 7): 3, (3, 7): 4})
        found = assert_solver_matches_brute_force(board)
        assert Rectangle(0, 7, 3, 7, total=10, number_count=4, empty_count=0, area=4) in found

    def test_interior_empty_2d(self):
        # 3 □ 2 / 2 □ 3：中間整欄是 EMPTY，2x3 全框總和 10
        board = make_board({(0, 0): 3, (0, 2): 2, (1, 0): 2, (1, 2): 3})
        found = assert_solver_matches_brute_force(board)
        assert Rectangle(0, 0, 1, 2, total=10, number_count=4, empty_count=2, area=6) in found


class TestExclusions:
    def test_l_shape_not_returned(self):
        # L 型三格總和 10，但其外包矩形因多一格數字總和 11 → 不得回傳 L，也不得回傳該框
        board = make_board({(0, 0): 4, (1, 0): 4, (1, 1): 2, (0, 1): 1})
        assert assert_solver_matches_brute_force(board) == []

    def test_all_empty(self):
        assert find_rectangles(make_board()) == []

    def test_single_digit_no_pair(self):
        assert find_rectangles(make_board({(5, 5): 5})) == []

    def test_over_ten_not_returned(self):
        assert find_rectangles(make_board({(0, 0): 9, (0, 1): 9})) == []

    def test_unknown_not_treated_as_empty(self):
        # 若把 UNKNOWN 當 0，(0,0)-(0,2) 總和恰為 10；必須排除
        board = make_board({(0, 0): 7, (0, 2): 3}, unknowns={(0, 1)})
        assert assert_solver_matches_brute_force(board) == []

    def test_unknown_only_taints_its_rectangles(self):
        # 有效配對不受遠處 UNKNOWN 影響；回傳候選皆不含 UNKNOWN
        board = make_board({(0, 0): 4, (0, 1): 6}, unknowns={(5, 5), (9, 14)})
        found = assert_solver_matches_brute_force(board)
        assert Rectangle(0, 0, 0, 1, total=10, number_count=2, empty_count=0, area=2) in found
        for rectangle in found:
            assert all(cell.state != CellState.UNKNOWN for cell in rect_of(board, rectangle))


class TestMultipleAndOrder:
    def test_multiple_rectangles_all_found(self):
        board = make_board({(0, 0): 4, (0, 1): 6, (0, 5): 3, (0, 6): 7})
        found = find_rectangles(board)
        assert Rectangle(0, 0, 0, 1, 10, 2, 0, 2) in found
        assert Rectangle(0, 5, 0, 6, 10, 2, 0, 2) in found
        # 每個回傳都必須是真正的合法矩形（重算驗證）
        for rectangle in found:
            cells = rect_of(board, rectangle)
            assert sum(cell.digit for cell in cells if cell.state == CellState.DIGIT) == 10
            assert any(cell.state == CellState.DIGIT for cell in cells)
            assert all(cell.state != CellState.UNKNOWN for cell in cells)

    def test_deterministic_scan_order(self):
        board = make_board({(0, 0): 4, (0, 1): 6, (0, 5): 3, (0, 6): 7, (9, 13): 5, (9, 14): 5})
        first = find_rectangles(board)
        second = find_rectangles(board)
        assert first == second
        keys = [(r.row1, r.col1, r.row2, r.col2) for r in first]
        assert keys == sorted(keys)
        # 同一棋盤狀態永遠產生一致的提示順序：左上優先
        assert (first[0].row1, first[0].col1) == (0, 0)

    def test_bottom_right_corner(self):
        # 掃描需涵蓋整張 10x15，含右下角
        board = make_board({(9, 13): 5, (9, 14): 5})
        found = assert_solver_matches_brute_force(board)
        assert Rectangle(9, 13, 9, 14, total=10, number_count=2, empty_count=0, area=2) in found

    def test_post_elimination_board(self):
        # 消除後原位置變 EMPTY，棋盤仍是 10x15；剩餘數字仍可配對
        board = make_board({(4, 4): 8, (4, 7): 2})
        assert len(board.cells) == 150
        assert board.at(4, 5).state == CellState.EMPTY
        found = assert_solver_matches_brute_force(board)
        assert Rectangle(4, 4, 4, 7, total=10, number_count=2, empty_count=2, area=4) in found

    def test_random_boards_always_valid_and_ordered(self):
        rng = random.Random(20260917)
        for _ in range(30):
            digits = {}
            for _ in range(rng.randint(0, 25)):
                digits[(rng.randrange(10), rng.randrange(15))] = rng.randint(1, 9)
            unknowns = {
                (rng.randrange(10), rng.randrange(15)) for _ in range(rng.randint(0, 5))
            } - set(digits)
            board = make_board(digits, unknowns)
            found = find_rectangles(board)
            assert set(found) == brute_force(board)
            keys = [(r.row1, r.col1, r.row2, r.col2) for r in found]
            assert keys == sorted(keys)
            for rectangle in found:
                cells = rect_of(board, rectangle)
                assert rectangle.total == 10
                assert rectangle.area == (rectangle.row2 - rectangle.row1 + 1) * (
                    rectangle.col2 - rectangle.col1 + 1
                )
                assert rectangle.number_count >= 1
                assert rectangle.empty_count == rectangle.area - rectangle.number_count
                assert sum(cell.digit for cell in cells if cell.state == CellState.DIGIT) == 10
                assert all(cell.state != CellState.UNKNOWN for cell in cells)
