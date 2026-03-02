"""
main.py — Checkers Game UI (Pygame) with Intro, Gameplay & Game-Over Screens.

This module implements the complete graphical front-end for the Checkers
game, organised as a **state machine** with three screens:

    INTRO  →  PLAYING  →  GAME_OVER  →  (restart → INTRO)

Visual Features:
    • **Intro screen**: Title, game rules/instructions, "Start Game" button
    • **Gameplay**:  Wood-themed board, piece shadows, yellow selection
      highlight, valid-move indicators, smooth AI move animation
    • **Game-over screen**: Winner announcement, "Play Again" and "Quit"
      buttons

All rendering and event handling is performed in the ``main()`` function
at the bottom of this file.
"""

from __future__ import annotations

import sys
from typing import Optional

import pygame

from engine import CheckersEngine, MovePath, Position
from bt_dp_ai import ai_move, memo as ai_memo

# =========================================================================
# Display constants
# =========================================================================

WIDTH: int = 600
ROWS: int = 8
SQUARE: int = WIDTH // ROWS
FPS: int = 60
ANIMATION_SPEED: int = 8  # Pixels the piece moves per animation frame

# =========================================================================
# Colour palette — premium wood-and-classic aesthetic
# =========================================================================

CLR_BG         = (30, 30, 35)        # Dark background (behind board)
CLR_LIGHT_SQ   = (235, 220, 200)     # Light wood square
CLR_DARK_SQ    = (110, 70, 45)       # Dark wood square
CLR_RED        = (200, 40, 40)       # Red player pieces
CLR_BLUE       = (60, 130, 200)      # Blue / AI pieces
CLR_GOLD       = (255, 215, 0)       # Crown "K" label
CLR_SELECT     = (255, 230, 0)       # Yellow selection ring
CLR_VALID      = (255, 230, 0, 130)  # Semi-transparent valid-move dot
CLR_OVERLAY    = (0, 0, 0, 180)      # Dark translucent overlay
CLR_WHITE      = (255, 255, 255)
CLR_ACCENT     = (70, 180, 130)      # Accent green for buttons
CLR_ACCENT_HOV = (90, 210, 150)      # Button hover colour
CLR_BTN_QUIT   = (180, 60, 60)       # Quit button colour
CLR_BTN_QUIT_H = (210, 80, 80)       # Quit button hover
CLR_GREY       = (160, 160, 160)

# =========================================================================
# Game states
# =========================================================================

STATE_INTRO: int = 0
STATE_PLAYING: int = 1
STATE_GAME_OVER: int = 2

# =========================================================================
# Pygame initialisation
# =========================================================================

pygame.init()
WIN: pygame.Surface = pygame.display.set_mode((WIDTH, WIDTH))
pygame.display.set_caption("Checkers — Backtracking + DP + Alpha-Beta")
CLOCK: pygame.time.Clock = pygame.time.Clock()

FONT_TITLE  = pygame.font.SysFont("segoeui", 50, bold=True)
FONT_HEADING = pygame.font.SysFont("segoeui", 28, bold=True)
FONT_BODY   = pygame.font.SysFont("segoeui", 18)
FONT_BTN    = pygame.font.SysFont("segoeui", 26, bold=True)
FONT_BIG    = pygame.font.SysFont("segoeui", 52, bold=True)
FONT_SMALL  = pygame.font.SysFont("segoeui", 24)
FONT_CROWN  = pygame.font.SysFont("segoeui", 22, bold=True)


# =====================================================================
# Drawing helpers — Board & Pieces
# =====================================================================

def _sq_center(row: int, col: int) -> tuple[int, int]:
    """Return the pixel centre of board square *(row, col)*."""
    return col * SQUARE + SQUARE // 2, row * SQUARE + SQUARE // 2


def draw_board(win: pygame.Surface) -> None:
    """Draw the 8×8 chequered board with wood-tone colours."""
    win.fill(CLR_LIGHT_SQ)
    for r in range(ROWS):
        for c in range(ROWS):
            if (r + c) % 2 == 1:
                pygame.draw.rect(
                    win, CLR_DARK_SQ,
                    (c * SQUARE, r * SQUARE, SQUARE, SQUARE),
                )


def draw_pieces(
    win: pygame.Surface,
    board: dict[Position, Optional[str]],
    skip_pos: Optional[Position] = None,
) -> None:
    """Draw all pieces, optionally skipping *skip_pos* (used by animation)."""
    for (r, c), piece in board.items():
        if piece is None:
            continue
        if skip_pos and (r, c) == skip_pos:
            continue

        color = CLR_RED if piece.lower() == 'r' else CLR_BLUE
        cx, cy = _sq_center(r, c)
        radius: int = SQUARE // 2 - 8

        # Shadow → piece → rim
        pygame.draw.circle(win, (40, 40, 40), (cx + 2, cy + 3), radius)
        pygame.draw.circle(win, color, (cx, cy), radius)
        pygame.draw.circle(win, CLR_WHITE, (cx, cy), radius, 2)

        if piece.isupper():
            crown = FONT_CROWN.render("K", True, CLR_GOLD)
            win.blit(crown, crown.get_rect(center=(cx, cy)))


def draw_selection(
    win: pygame.Surface,
    pos: Optional[Position],
    valid_destinations: list[Position],
) -> None:
    """Highlight the selected piece (yellow ring) and valid destinations."""
    if pos is None:
        return

    r, c = pos
    cx, cy = _sq_center(r, c)
    radius: int = SQUARE // 2 - 6

    pygame.draw.circle(win, CLR_SELECT, (cx, cy), radius, 4)

    for dest in valid_destinations:
        dr, dc = dest
        dot_surf = pygame.Surface((SQUARE, SQUARE), pygame.SRCALPHA)
        pygame.draw.circle(
            dot_surf, CLR_VALID, (SQUARE // 2, SQUARE // 2), 14,
        )
        win.blit(dot_surf, (dc * SQUARE, dr * SQUARE))


# =====================================================================
# Animation
# =====================================================================

def animate_move(win: pygame.Surface, engine: CheckersEngine, move_path: MovePath) -> None:
    """Smoothly glide a piece along *move_path* over several frames.

    Each leg of a multi-jump is animated sequentially so the player
    can follow the AI's reasoning.
    """
    if len(move_path) < 2:
        return

    start: Position = move_path[0]
    piece: str = engine.board[start]
    color = CLR_RED if piece.lower() == 'r' else CLR_BLUE
    radius: int = SQUARE // 2 - 8
    is_king: bool = piece.isupper()

    for i in range(len(move_path) - 1):
        sr, sc = move_path[i]
        er, ec = move_path[i + 1]
        sx, sy = _sq_center(sr, sc)
        ex, ey = _sq_center(er, ec)

        dx: int = ex - sx
        dy: int = ey - sy
        dist: int = max(abs(dx), abs(dy))
        steps: int = max(1, dist // ANIMATION_SPEED)

        for step in range(steps + 1):
            t: float = step / steps
            cx: float = sx + dx * t
            cy: float = sy + dy * t

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

            draw_board(win)
            draw_pieces(win, engine.board, skip_pos=move_path[0])

            # Draw animated piece at interpolated position
            pygame.draw.circle(win, (40, 40, 40), (int(cx) + 2, int(cy) + 3), radius)
            pygame.draw.circle(win, color, (int(cx), int(cy)), radius)
            pygame.draw.circle(win, CLR_WHITE, (int(cx), int(cy)), radius, 2)

            if is_king:
                crown = FONT_CROWN.render("K", True, CLR_GOLD)
                win.blit(crown, crown.get_rect(center=(int(cx), int(cy))))

            pygame.display.update()
            CLOCK.tick(FPS)


# =====================================================================
# UI Helper: rounded button
# =====================================================================

def _draw_button(
    win: pygame.Surface,
    rect: pygame.Rect,
    text: str,
    color: tuple,
    hover_color: tuple,
    mouse_pos: tuple[int, int],
) -> bool:
    """Draw a rounded button and return ``True`` if the mouse is hovering.

    Args:
        win:         Target surface.
        rect:        Button rectangle.
        text:        Label string.
        color:       Default fill colour.
        hover_color: Fill colour when mouse hovers.
        mouse_pos:   Current mouse position.

    Returns:
        ``True`` if the mouse is over the button.
    """
    hovered: bool = rect.collidepoint(mouse_pos)
    fill = hover_color if hovered else color
    pygame.draw.rect(win, fill, rect, border_radius=12)
    pygame.draw.rect(win, CLR_WHITE, rect, width=2, border_radius=12)
    label = FONT_BTN.render(text, True, CLR_WHITE)
    win.blit(label, label.get_rect(center=rect.center))
    return hovered


# =====================================================================
# Screens
# =====================================================================

def draw_intro_screen(win: pygame.Surface, mouse_pos: tuple[int, int]) -> pygame.Rect:
    """Render the intro/instructions screen and return the Start button rect."""
    win.fill(CLR_BG)

    # ── Title ──
    title = FONT_TITLE.render("♛  CHECKERS  ♛", True, CLR_GOLD)
    win.blit(title, title.get_rect(center=(WIDTH // 2, 55)))

    subtitle = FONT_SMALL.render(
        "Backtracking  +  Dynamic Programming  +  Alpha-Beta", True, CLR_GREY
    )
    win.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, 95)))

    # ── Separator line ──
    pygame.draw.line(win, CLR_GREY, (40, 120), (WIDTH - 40, 120), 1)

    # ── Instructions ──
    y: int = 140
    instructions: list[tuple[str, list[str]]] = [
        ("HOW TO PLAY", [
            "You are RED.  The AI plays BLUE.",
            "Click a piece to select it (yellow highlight).",
            "Click a highlighted square to move.",
        ]),
        ("MOVEMENT RULES", [
            "Men move diagonally forward by one square.",
            "Kings (marked K) move diagonally in any direction.",
            "A man reaching the opposite back row becomes a King.",
        ]),
        ("CAPTURE RULES", [
            "Jump over an opponent's piece diagonally to capture it.",
            "Captures are MANDATORY — if you can capture, you must.",
            "Multi-jumps: if another capture is available after a",
            "jump, the piece must keep jumping (chain capture).",
        ]),
        ("WINNING", [
            "Capture all opponent pieces, or leave them with no",
            "legal moves.  The AI uses Alpha-Beta Pruning at depth 6.",
        ]),
    ]

    for heading, lines in instructions:
        heading_surf = FONT_HEADING.render(heading, True, CLR_ACCENT)
        win.blit(heading_surf, (40, y))
        y += 30
        for line in lines:
            line_surf = FONT_BODY.render(line, True, CLR_WHITE)
            win.blit(line_surf, (55, y))
            y += 22
        y += 10

    # ── Start button ──
    btn_rect = pygame.Rect(WIDTH // 2 - 110, y + 10, 220, 50)
    _draw_button(win, btn_rect, "▶  START GAME", CLR_ACCENT, CLR_ACCENT_HOV, mouse_pos)

    pygame.display.update()
    return btn_rect


def draw_game_over_screen(
    win: pygame.Surface,
    winner: str,
    mouse_pos: tuple[int, int],
) -> tuple[pygame.Rect, pygame.Rect]:
    """Render the game-over overlay and return (play_again_rect, quit_rect)."""
    # Translucent overlay
    overlay = pygame.Surface((WIDTH, WIDTH), pygame.SRCALPHA)
    overlay.fill(CLR_OVERLAY)
    win.blit(overlay, (0, 0))

    winner_name: str = "Red" if winner == 'r' else "Blue"
    winner_color = CLR_RED if winner == 'r' else CLR_BLUE

    # Winner text
    title = FONT_BIG.render(f"🏆  {winner_name} Wins!", True, winner_color)
    win.blit(title, title.get_rect(center=(WIDTH // 2, WIDTH // 2 - 70)))

    msg = FONT_SMALL.render("Great game! What would you like to do?", True, CLR_WHITE)
    win.blit(msg, msg.get_rect(center=(WIDTH // 2, WIDTH // 2 - 20)))

    # Buttons
    btn_play = pygame.Rect(WIDTH // 2 - 200, WIDTH // 2 + 20, 180, 50)
    btn_quit = pygame.Rect(WIDTH // 2 + 20,  WIDTH // 2 + 20, 180, 50)

    _draw_button(win, btn_play, "▶  Play Again", CLR_ACCENT, CLR_ACCENT_HOV, mouse_pos)
    _draw_button(win, btn_quit, "✕  Quit",       CLR_BTN_QUIT, CLR_BTN_QUIT_H, mouse_pos)

    pygame.display.update()
    return btn_play, btn_quit


# =====================================================================
# Main game loop — state machine
# =====================================================================

def main() -> None:
    """Entry point: runs the INTRO → PLAYING → GAME_OVER state machine.

    The loop continues indefinitely; the player can restart from the
    game-over screen or quit at any time.
    """
    state: int = STATE_INTRO
    engine: CheckersEngine = CheckersEngine()
    selected: Optional[Position] = None
    valid_destinations: list[Position] = []
    winner: Optional[str] = None

    HUMAN: str = 'r'
    AI: str = 'b'
    depth: int = 6  # Alpha-Beta allows efficient deep search

    # Rects for buttons (initialised lazily)
    btn_start: Optional[pygame.Rect] = None
    btn_play_again: Optional[pygame.Rect] = None
    btn_quit: Optional[pygame.Rect] = None

    while True:
        CLOCK.tick(FPS)
        mouse_pos: tuple[int, int] = pygame.mouse.get_pos()

        # ── STATE: INTRO ──────────────────────────────────────────
        if state == STATE_INTRO:
            btn_start = draw_intro_screen(WIN, mouse_pos)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if btn_start and btn_start.collidepoint(event.pos):
                        state = STATE_PLAYING
            continue

        # ── STATE: PLAYING ────────────────────────────────────────
        if state == STATE_PLAYING:
            draw_board(WIN)
            draw_pieces(WIN, engine.board)
            draw_selection(WIN, selected, valid_destinations)
            pygame.display.update()

            # Check game over
            if engine.game_over():
                winner = engine.get_winner()
                state = STATE_GAME_OVER
                continue

            # AI turn
            if engine.turn == AI:
                pygame.time.delay(300)
                move: Optional[MovePath] = ai_move(engine, AI, depth)
                if move:
                    animate_move(WIN, engine, move)
                    engine.apply_move(move)
                continue

            # Human turn
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.MOUSEBUTTONDOWN:
                    x, y = event.pos
                    row: int = y // SQUARE
                    col: int = x // SQUARE

                    all_moves: list[MovePath] = engine.generate_moves(HUMAN)

                    if selected is None:
                        piece = engine.board.get((row, col))
                        if piece and piece.lower() == HUMAN:
                            piece_moves = [m for m in all_moves if m[0] == (row, col)]
                            if piece_moves:
                                selected = (row, col)
                                valid_destinations = [m[-1] for m in piece_moves]
                    else:
                        target: Position = (row, col)
                        matching = [
                            m for m in all_moves
                            if m[0] == selected and m[-1] == target
                        ]
                        if matching:
                            engine.apply_move(matching[0])
                        selected = None
                        valid_destinations = []

            continue

        # ── STATE: GAME_OVER ──────────────────────────────────────
        if state == STATE_GAME_OVER:
            # Redraw the board behind the overlay
            draw_board(WIN)
            draw_pieces(WIN, engine.board)
            btn_play_again, btn_quit = draw_game_over_screen(
                WIN, winner or 'r', mouse_pos
            )

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.MOUSEBUTTONDOWN:
                    if btn_play_again and btn_play_again.collidepoint(event.pos):
                        # ── RESTART ──
                        engine = CheckersEngine()
                        ai_memo.clear()  # Reset transposition table
                        selected = None
                        valid_destinations = []
                        winner = None
                        state = STATE_INTRO
                    elif btn_quit and btn_quit.collidepoint(event.pos):
                        pygame.quit()
                        sys.exit()

            continue


if __name__ == "__main__":
    main()