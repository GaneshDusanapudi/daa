"""
engine.py — Checkers Game Engine (Production-Ready).

This module encapsulates the complete game state and rule enforcement
for an 8×8 Checkers (Draughts) game.  It is designed to work with an
AI search algorithm that relies on **Backtracking** (in-place
``apply_move`` / ``undo_move``) and **Dynamic Programming** (via
``board_key`` for transposition-table memoisation).

Implemented Rules:
    1. Men move diagonally forward by one square.
    2. Kings (promoted men) move diagonally in all four directions.
    3. **Mandatory forced captures** — when a capture is available,
       the player *must* capture (simple moves are suppressed).
    4. **Multi-jump / chain captures** — after one capture, if the
       same piece can capture again from its new position, it *must*
       continue jumping.
    5. **Promotion** — a man reaching the opponent's back row becomes
       a King.

Key Design Decisions:
    • The board is a ``dict[(int,int), str|None]`` mapping dark
      squares to piece characters (``'r'``, ``'b'``, ``'R'``, ``'B'``
      or ``None``).  Only dark squares are stored.
    • Moves are represented as **position tuples** (paths), e.g.
      ``((6,1), (4,3), (2,5))`` for a double-jump.
    • ``apply_move`` returns an *info* dict that ``undo_move`` uses to
      restore the board, avoiding expensive board copies.
"""

from __future__ import annotations

from typing import Optional

from utils import BOARD_SIZE, in_bounds, opponent

# =========================================================================
# Direction tables
# =========================================================================

NORMAL_DIRECTIONS: dict[str, list[tuple[int, int]]] = {
    'r': [(-1, -1), (-1, 1)],   # Red advances upward  (row decreases)
    'b': [(1, -1), (1, 1)],     # Black advances downward (row increases)
}

KING_DIRECTIONS: list[tuple[int, int]] = [
    (-1, -1), (-1, 1),
    (1, -1), (1, 1),
]

# =========================================================================
# Positional-weight tables used by the evaluation heuristic
# =========================================================================

# Advancement bonus indexed by number of rows pushed toward promotion.
_ADVANCE_BONUS: list[float] = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]

_EDGE_COLS: set[int] = {0, 7}
_CENTER_ROWS: set[int] = {3, 4}
_CENTER_COLS: set[int] = {2, 3, 4, 5}

# Type aliases for readability
Position = tuple[int, int]
MovePath = tuple[Position, ...]
BoardDict = dict[Position, Optional[str]]
MoveInfo = dict


class CheckersEngine:
    """Core game engine with backtracking-safe apply/undo support.

    Attributes:
        board:  Mapping of dark-square coordinates → piece character
                or ``None`` (empty).
        turn:   ``'r'`` or ``'b'`` — whose turn it is.
    """

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        """Create a new engine with the standard starting position."""
        self.board: BoardDict = {}
        self.turn: str = 'r'
        self._init_board()

    def _init_board(self) -> None:
        """Populate ``self.board`` with the standard 8×8 opening layout.

        Black pieces occupy rows 0-2; red pieces occupy rows 5-7.
        Only dark squares ``(r+c) % 2 == 1`` are used.
        """
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                if (row + col) % 2 == 1:
                    if row < 3:
                        self.board[(row, col)] = 'b'
                    elif row > 4:
                        self.board[(row, col)] = 'r'
                    else:
                        self.board[(row, col)] = None

    # ------------------------------------------------------------------
    # Direction helper
    # ------------------------------------------------------------------

    def _get_directions(self, piece: str) -> list[tuple[int, int]]:
        """Return the legal diagonal directions for *piece*.

        Kings use all four diagonals; men use only their forward two.
        """
        if piece.isupper():
            return KING_DIRECTIONS
        return NORMAL_DIRECTIONS[piece.lower()]

    # ------------------------------------------------------------------
    # Move generation
    # ------------------------------------------------------------------

    def _get_simple_moves(self, player: str) -> list[MovePath]:
        """Return all non-capture moves for *player*.

        Each move is a 2-element tuple ``((start_r, start_c), (end_r, end_c))``.
        """
        moves: list[MovePath] = []
        for (row, col), piece in self.board.items():
            if piece is None or piece.lower() != player:
                continue
            for d_row, d_col in self._get_directions(piece):
                new_row, new_col = row + d_row, col + d_col
                if in_bounds(new_row, new_col) and self.board.get((new_row, new_col)) is None:
                    moves.append(((row, col), (new_row, new_col)))
        return moves

    def _build_capture_chain(
        self,
        row: int,
        col: int,
        piece: str,
        path: list[Position],
        captured_set: set[Position],
        results: list[tuple[Position, ...]],
    ) -> None:
        """Recursively discover all multi-jump chains from *(row, col)*.

        This is the **Backtracking** core of move generation: the board
        is temporarily mutated for each candidate jump, then restored
        when the recursive call returns.

        Args:
            row, col:       Current position of the jumping piece.
            piece:          Piece character (may be uppercase for King).
            path:           Jump destinations accumulated so far.
            captured_set:   Positions of pieces already captured in
                            this chain (prevents re-capturing).
            results:        Accumulator — completed chains are appended.
        """
        found_jump: bool = False

        for d_row, d_col in self._get_directions(piece):
            mid_row, mid_col = row + d_row, col + d_col
            jump_row, jump_col = row + 2 * d_row, col + 2 * d_col

            if not in_bounds(jump_row, jump_col):
                continue

            mid_piece: Optional[str] = self.board.get((mid_row, mid_col))
            dest_piece: Optional[str] = self.board.get((jump_row, jump_col))

            # Valid jump: mid square has an opponent, dest square is empty,
            # and the mid piece hasn't already been captured in this chain.
            if (mid_piece is not None
                    and mid_piece.lower() == opponent(piece.lower())
                    and (mid_row, mid_col) not in captured_set
                    and dest_piece is None):

                found_jump = True

                # --- Temporarily apply the jump (mutate board) ---
                self.board[(row, col)] = None
                saved_mid: str = self.board[(mid_row, mid_col)]
                self.board[(mid_row, mid_col)] = None
                self.board[(jump_row, jump_col)] = piece

                # Check mid-chain promotion
                promoted: bool = False
                if piece == 'r' and jump_row == 0:
                    self.board[(jump_row, jump_col)] = 'R'
                    promoted = True
                elif piece == 'b' and jump_row == 7:
                    self.board[(jump_row, jump_col)] = 'B'
                    promoted = True

                new_piece: str = self.board[(jump_row, jump_col)]
                captured_set.add((mid_row, mid_col))
                path.append((jump_row, jump_col))

                # Recurse — keep looking for more jumps
                self._build_capture_chain(
                    jump_row, jump_col, new_piece, path, captured_set, results
                )

                # --- Undo the jump (backtrack) ---
                path.pop()
                captured_set.discard((mid_row, mid_col))
                self.board[(jump_row, jump_col)] = None
                self.board[(mid_row, mid_col)] = saved_mid
                self.board[(row, col)] = piece

        # If no further jumps were found and we have at least one jump
        # in the path, record the completed chain.
        if not found_jump and path:
            results.append(tuple(path))

    def generate_moves(self, player: str) -> list[MovePath]:
        """Generate all legal moves for *player*.

        **Forced-capture rule**: if *any* capture chain exists, only
        capture moves are returned.  Among captures, only the
        **longest** chains are kept (standard tournament rule).

        Args:
            player: ``'r'`` or ``'b'``.

        Returns:
            A list of move-paths (tuples of board positions).
        """
        # 1. Collect all capture chains
        chains: list[MovePath] = []
        for (row, col), piece in self.board.items():
            if piece is None or piece.lower() != player:
                continue
            partial: list[tuple[Position, ...]] = []
            self._build_capture_chain(row, col, piece, [], set(), partial)
            for chain in partial:
                full_path: MovePath = ((row, col),) + chain
                chains.append(full_path)

        if chains:
            max_length: int = max(len(ch) for ch in chains)
            return [ch for ch in chains if len(ch) == max_length]

        # 2. No captures available — return simple moves
        return self._get_simple_moves(player)

    # ------------------------------------------------------------------
    # Apply / Undo  (Backtracking interface)
    # ------------------------------------------------------------------

    def apply_move(self, move: MovePath) -> MoveInfo:
        """Apply a move-path to the board **in place**.

        This is **Backtracking Step 1** — the board is mutated so that
        the recursive AI search can explore the resulting subtree
        without copying the entire board.

        Args:
            move: Tuple of positions the piece travels through.
                  Length 2 → simple move; length ≥ 3 → multi-jump.

        Returns:
            An ``info`` dict consumed by ``undo_move`` to fully restore
            the board state.
        """
        start: Position = move[0]
        piece: str = self.board[start]
        captured_list: list[tuple[Position, str]] = []
        promoted: bool = False

        self.board[start] = None

        # Process each step in the path
        for i in range(1, len(move)):
            prev_row, prev_col = move[i - 1]
            dest_row, dest_col = move[i]

            # If this leg is a jump (distance = 2), capture the mid piece
            if abs(dest_row - prev_row) == 2:
                mid: Position = (
                    (prev_row + dest_row) // 2,
                    (prev_col + dest_col) // 2,
                )
                captured_list.append((mid, self.board[mid]))
                self.board[mid] = None

        # Place piece at final destination
        final: Position = move[-1]
        self.board[final] = piece

        # Promotion check
        if piece == 'r' and final[0] == 0:
            self.board[final] = 'R'
            promoted = True
        elif piece == 'b' and final[0] == 7:
            self.board[final] = 'B'
            promoted = True

        self.turn = opponent(self.turn)

        return {
            'piece': piece,
            'captured': captured_list,
            'promoted': promoted,
        }

    def undo_move(self, move: MovePath, info: MoveInfo) -> None:
        """Undo a previously applied move — **Backtracking Step 3**.

        Restores the board to the exact state it was in before
        ``apply_move`` was called, including all captured pieces
        and any promotion that occurred.

        Args:
            move: The same move-path passed to ``apply_move``.
            info: The dict returned by ``apply_move``.
        """
        start: Position = move[0]
        final: Position = move[-1]

        original_piece: str = info['piece']
        self.board[final] = None
        self.board[start] = original_piece

        # Restore every captured piece
        for pos, captured_piece in info['captured']:
            self.board[pos] = captured_piece

        self.turn = opponent(self.turn)

    # ------------------------------------------------------------------
    # Game status
    # ------------------------------------------------------------------

    def has_moves(self, player: str) -> bool:
        """Return ``True`` if *player* has at least one legal move."""
        return len(self.generate_moves(player)) > 0

    def game_over(self) -> bool:
        """Return ``True`` if the game has ended.

        The game ends when either player has no legal moves remaining.
        """
        return not self.has_moves('r') or not self.has_moves('b')

    def get_winner(self) -> Optional[str]:
        """Return ``'r'``, ``'b'``, or ``None`` (draw / ongoing).

        A player loses when they have no pieces or no legal moves.
        """
        reds_exist: bool = any(p and p.lower() == 'r' for p in self.board.values())
        blacks_exist: bool = any(p and p.lower() == 'b' for p in self.board.values())

        if not reds_exist:
            return 'b'
        if not blacks_exist:
            return 'r'
        if not self.has_moves('r'):
            return 'b'
        if not self.has_moves('b'):
            return 'r'
        return None

    # ------------------------------------------------------------------
    # DP Support — Board Key
    # ------------------------------------------------------------------

    def board_key(self) -> frozenset:
        """Return a hashable snapshot of the board for DP memoisation.

        Only *occupied* squares are included — this produces a smaller
        frozenset than sorting all 32 dark squares, resulting in faster
        hashing and dict lookups in the transposition table.

        Returns:
            A ``frozenset`` of ``(position, piece)`` pairs.
        """
        return frozenset(
            (pos, piece) for pos, piece in self.board.items() if piece
        )

    # ------------------------------------------------------------------
    # Evaluation Heuristic
    # ------------------------------------------------------------------

    def evaluate(self, player: str) -> float:
        """Score the board from *player*'s perspective.

        The heuristic combines multiple strategic factors:

        +------------+--------+-------------------------------------------+
        | Factor     | Bonus  | Rationale                                 |
        +============+========+===========================================+
        | Man        | +1.0   | Base material value                       |
        | King       | +3.0   | Kings are far more mobile                 |
        | Edge col   | +0.5   | Can't be captured from one side           |
        | Advance    | +0.1×n | Pieces closer to promotion are stronger   |
        | Centre     | +0.3   | Central pieces control more diagonals     |
        | Back row   | +0.2   | Guards the promotion lane                 |
        +------------+--------+-------------------------------------------+

        Args:
            player: The colour to evaluate for (``'r'`` or ``'b'``).

        Returns:
            A float score — positive means *player* is ahead.
        """
        score: float = 0.0

        for (row, col), piece in self.board.items():
            if piece is None:
                continue

            # Base material
            value: float = 3.0 if piece.isupper() else 1.0

            # Advancement (men only)
            if not piece.isupper():
                if piece.lower() == 'r':
                    value += _ADVANCE_BONUS[7 - row]
                else:
                    value += _ADVANCE_BONUS[row]

            # Edge safety
            if col in _EDGE_COLS:
                value += 0.5

            # Centre control
            if row in _CENTER_ROWS and col in _CENTER_COLS:
                value += 0.3

            # Back-row defence
            if piece.lower() == 'r' and row == 7:
                value += 0.2
            elif piece.lower() == 'b' and row == 0:
                value += 0.2

            # Ownership sign
            if piece.lower() == player:
                score += value
            else:
                score -= value

        return score