from utils import in_bounds, opponent

NORMAL_DIRECTIONS = {
    'r': [(-1, -1), (-1, 1)],
    'b': [(1, -1), (1, 1)]
}

KING_DIRECTIONS = [
    (-1, -1), (-1, 1),
    (1, -1), (1, 1)
]


class CheckersEngine:

    def __init__(self):
        self.board = {}
        self.turn = 'r'
        self.init_board()

    # ---------- INIT ---------- #

    def init_board(self):
        for r in range(8):
            for c in range(8):
                if (r + c) % 2 == 1:
                    if r < 3:
                        self.board[(r, c)] = 'b'
                    elif r > 4:
                        self.board[(r, c)] = 'r'
                    else:
                        self.board[(r, c)] = None

    # ---------- MOVE GENERATION ---------- #

    def generate_moves(self, player):
        moves = []

        for (r, c), piece in self.board.items():

            if piece is None:
                continue

            if piece.lower() != player:
                continue

            directions = KING_DIRECTIONS if piece.isupper() else NORMAL_DIRECTIONS[player]

            for dr, dc in directions:

                nr, nc = r + dr, c + dc
                jr, jc = r + 2 * dr, c + 2 * dc

                # Normal move
                if in_bounds(nr, nc) and self.board.get((nr, nc)) is None:
                    moves.append(((r, c), (nr, nc)))

                # Capture move
                if (in_bounds(jr, jc)
                        and self.board.get((nr, nc)) is not None
                        and self.board.get((nr, nc)).lower() == opponent(player)
                        and self.board.get((jr, jc)) is None):

                    moves.append(((r, c), (jr, jc)))

        return moves

    # ---------- APPLY MOVE (Backtracking Step 1) ---------- #

    def apply_move(self, move):
        start, end = move
        sr, sc = start
        er, ec = end

        captured = None
        promoted = False

        piece = self.board[start]

        # Capture
        if abs(er - sr) == 2:
            mid = ((sr + er) // 2, (sc + ec) // 2)
            captured = (mid, self.board[mid])
            self.board[mid] = None

        # Move
        self.board[end] = piece
        self.board[start] = None

        # Promotion
        if piece == 'r' and er == 0:
            self.board[end] = 'R'
            promoted = True
        elif piece == 'b' and er == 7:
            self.board[end] = 'B'
            promoted = True

        self.turn = opponent(self.turn)

        return captured, promoted

    # ---------- UNDO MOVE (Backtracking Step 3) ---------- #

    def undo_move(self, move, info):
        captured, promoted = info
        start, end = move

        piece = self.board[end]

        # Revert promotion
        if promoted:
            piece = piece.lower()

        self.board[start] = piece
        self.board[end] = None

        if captured:
            pos, val = captured
            self.board[pos] = val

        self.turn = opponent(self.turn)

    # ---------- GAME STATUS ---------- #

    def has_moves(self, player):
        return len(self.generate_moves(player)) > 0

    def game_over(self):
        return not self.has_moves('r') or not self.has_moves('b')

    def get_winner(self):
        reds = any(p and p.lower() == 'r' for p in self.board.values())
        blacks = any(p and p.lower() == 'b' for p in self.board.values())

        if not reds:
            return 'b'
        if not blacks:
            return 'r'
        if not self.has_moves('r'):
            return 'b'
        if not self.has_moves('b'):
            return 'r'
        return None

    # ---------- DP SUPPORT ---------- #

    def board_key(self):
        return tuple(sorted(self.board.items()))

    # ---------- EVALUATION ---------- #

    def evaluate(self, player):
        score = 0

        for piece in self.board.values():
            if piece is None:
                continue

            value = 1
            if piece.isupper():
                value = 3   # Kings more valuable

            if piece.lower() == player:
                score += value
            else:
                score -= value

        return score