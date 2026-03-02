"""
utils.py — Shared Constants and Helper Functions for the Checkers Game.

This module provides board-level constants and pure utility functions
used across the engine, AI, and UI layers.  Keeping them in a single
place avoids circular imports and ensures consistency.

Algorithmic Relevance:
    • ``in_bounds`` is called inside every move-generation loop — its
      O(1) check is a hot-path micro-optimisation.
    • ``opponent`` is used by both the engine and the Alpha-Beta search
      to toggle between maximising and minimising players.
"""

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BOARD_SIZE: int = 8
"""Side length of the Checkers board (standard = 8)."""


# ---------------------------------------------------------------------------
# Pure Helper Functions
# ---------------------------------------------------------------------------

def in_bounds(row: int, col: int) -> bool:
    """Return ``True`` if *(row, col)* lies within the 8×8 board.

    Args:
        row: Zero-indexed row (0 = top, 7 = bottom).
        col: Zero-indexed column (0 = left, 7 = right).

    Returns:
        ``True`` when both coordinates are in [0, BOARD_SIZE).
    """
    return 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE


def opponent(player: str) -> str:
    """Return the opposing player character.

    Args:
        player: ``'r'`` (red / human) or ``'b'`` (black / AI).

    Returns:
        ``'b'`` if *player* is ``'r'``, otherwise ``'r'``.
    """
    return 'b' if player == 'r' else 'r'