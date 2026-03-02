"""
bt_dp_ai.py — Checkers AI using Alpha-Beta Pruning + Backtracking + DP.

This module implements a game-tree search combining three techniques:

1. **Backtracking**
   The board is mutated in place via ``engine.apply_move()`` /
   ``engine.undo_move()``.  This avoids copying the entire board dict
   at every node, saving O(n) memory per recursion level.

2. **Dynamic Programming (Transposition Table)**
   Identical board states reached via different move orderings share
   cached evaluations.  The ``memo`` dictionary maps ``board_key``
   values to previously computed scores, eliminating redundant
   subtree exploration.

3. **Alpha-Beta Pruning**
   Branches that provably cannot influence the final decision are
   pruned.  In the best case this reduces the effective branching
   factor from O(b^d) to O(b^(d/2)), allowing deeper searches in
   the same wall-clock time.

Transposition-Table Flags:
    The memo stores ``(score, flag, depth)`` entries where *flag* is
    one of ``EXACT``, ``LOWER_BOUND``, or ``UPPER_BOUND``.  This
    allows cached values from pruned subtrees to still be used to
    narrow the α-β window on future lookups — the standard technique
    used in professional game engines.
"""

from __future__ import annotations

import math
from typing import Optional

from engine import CheckersEngine, MovePath
from utils import opponent

# =========================================================================
# Transposition-table flag constants
# =========================================================================

EXACT: int = 0
"""The stored score is exact (no pruning occurred)."""

LOWER_BOUND: int = 1
"""The stored score is a lower bound (beta cut-off, maximiser can do at least this well)."""

UPPER_BOUND: int = 2
"""The stored score is an upper bound (alpha cut-off, minimiser can hold score this low)."""

# =========================================================================
# Module-level state
# =========================================================================

memo: dict[tuple, dict] = {}
"""Global transposition table (DP memo).  Keys are ``(board_key, depth, maximising)``."""

nodes_searched: int = 0
"""Counter reset and incremented per ``ai_move`` call — useful for profiling."""


# =========================================================================
# Alpha-Beta Search
# =========================================================================

def alphabeta_bt_dp(
    engine: CheckersEngine,
    depth: int,
    alpha: float,
    beta: float,
    maximizing: bool,
    player: str,
) -> float:
    """Alpha-Beta Minimax with in-place backtracking and DP memoisation.

    Algorithm steps at each node
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    1. **DP lookup** — check the transposition table.  If a cache entry
       exists with sufficient depth, use its flag to return early or
       narrow the window.
    2. **Terminal / depth-0 check** — return a heuristic score.
    3. **Recursive expansion** — for each legal move:
       a. ``apply_move``   ← *Backtracking Step 1*
       b. Recurse with updated α-β window
       c. ``undo_move``    ← *Backtracking Step 3*
       d. If α ≥ β → prune remaining siblings
    4. **DP store** — cache the result with the appropriate flag.

    Args:
        engine:     Game engine instance (mutated in place).
        depth:      Remaining plies to search.
        alpha:      Lower bound of acceptable scores (maximiser).
        beta:       Upper bound of acceptable scores (minimiser).
        maximizing: ``True`` if this is the maximiser's turn.
        player:     The AI's colour — stays fixed for scoring.

    Returns:
        The evaluated score from *player*'s perspective.
    """
    global nodes_searched
    nodes_searched += 1

    # ── DP Lookup (Transposition Table) ────────────────────────────
    key: tuple = (engine.board_key(), depth, maximizing)

    if key in memo:
        entry: dict = memo[key]
        if entry['depth'] >= depth:
            if entry['flag'] == EXACT:
                return entry['score']
            elif entry['flag'] == LOWER_BOUND:
                alpha = max(alpha, entry['score'])
            elif entry['flag'] == UPPER_BOUND:
                beta = min(beta, entry['score'])
            if alpha >= beta:
                return entry['score']

    # ── Terminal state ─────────────────────────────────────────────
    if engine.game_over():
        winner: Optional[str] = engine.get_winner()
        if winner == player:
            return 1000 + depth       # Win sooner → higher score
        elif winner is None:
            return 0
        else:
            return -1000 - depth      # Lose later → less negative

    # ── Depth limit → static evaluation ────────────────────────────
    if depth == 0:
        return engine.evaluate(player)

    # ── Recursive search ───────────────────────────────────────────
    current_player: str = player if maximizing else opponent(player)
    moves: list[MovePath] = engine.generate_moves(current_player)

    if not moves:
        # No legal moves = loss for current_player
        if current_player == player:
            return -1000 - depth
        else:
            return 1000 + depth

    original_alpha: float = alpha
    best: float = -math.inf if maximizing else math.inf

    for move in moves:
        # BACKTRACKING STEP 1: mutate board
        info = engine.apply_move(move)

        # BACKTRACKING STEP 2: recurse
        val: float = alphabeta_bt_dp(
            engine, depth - 1, alpha, beta, not maximizing, player
        )

        # BACKTRACKING STEP 3: restore board
        engine.undo_move(move, info)

        if maximizing:
            best = max(best, val)
            alpha = max(alpha, val)
        else:
            best = min(best, val)
            beta = min(beta, val)

        # ── ALPHA-BETA PRUNE ──────────────────────────────────────
        if alpha >= beta:
            break   # Remaining siblings cannot improve the outcome

    # ── Store in transposition table ────────────────────────────────
    if best <= original_alpha:
        flag: int = UPPER_BOUND
    elif best >= beta:
        flag = LOWER_BOUND
    else:
        flag = EXACT

    memo[key] = {'score': best, 'flag': flag, 'depth': depth}

    return best


# =========================================================================
# Public API
# =========================================================================

def ai_move(
    engine: CheckersEngine,
    player: str,
    depth: int = 6,
) -> Optional[MovePath]:
    """Choose the best move for *player* using Alpha-Beta + BT + DP.

    The root call iterates over all legal moves, calling
    ``alphabeta_bt_dp`` for each, and returns the move with the
    highest score.

    Args:
        engine: Game engine instance.
        player: AI's colour (``'r'`` or ``'b'``).
        depth:  Search depth in plies (default 6).

    Returns:
        The best move-path, or ``None`` if no legal moves exist.
    """
    global nodes_searched
    nodes_searched = 0

    best_score: float = -math.inf
    best_move: Optional[MovePath] = None
    alpha: float = -math.inf
    beta: float = math.inf

    moves: list[MovePath] = engine.generate_moves(player)

    for move in moves:
        info = engine.apply_move(move)
        score: float = alphabeta_bt_dp(
            engine, depth - 1, alpha, beta, False, player
        )
        engine.undo_move(move, info)

        if score > best_score:
            best_score = score
            best_move = move

        # Tighten alpha at root for earlier pruning
        alpha = max(alpha, score)

    print(
        f"[AI] Depth {depth} | Nodes searched: {nodes_searched} "
        f"| Best score: {best_score}"
    )

    return best_move