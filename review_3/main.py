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
    if piece is None:
        return
    color = CLR_RED if piece.lower() == 'r' else CLR_BLUE
    radius: int = SQUARE // 2 - 8
    is_king: bool = piece.isupper()

    # Track which squares to hide during animation (start + already-jumped intermediates)
    hidden_positions: set[Position] = {start}

    for i in range(len(move_path) - 1):
        sr, sc = move_path[i]
        er, ec = move_path[i + 1]
        sx, sy = _sq_center(sr, sc)
        ex, ey = _sq_center(er, ec)

        dx: int = ex - sx
        dy: int = ey - sy
        dist: int = max(abs(dx), abs(dy))
        steps: int = max(1, dist // ANIMATION_SPEED)

        # If this is a jump, find the captured mid piece and hide it too
        if abs(er - sr) == 2:
            mid_pos: Position = ((sr + er) // 2, (sc + ec) // 2)
            hidden_positions.add(mid_pos)

        for step in range(steps + 1):
            t: float = step / steps
            cx: float = sx + dx * t
            cy: float = sy + dy * t

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

            draw_board(win)
            # Skip all hidden positions (start, captured midpoints)
            for (pr, pc), p in engine.board.items():
                if p is None or (pr, pc) in hidden_positions:
                    continue
                p_color = CLR_RED if p.lower() == 'r' else CLR_BLUE
                pcx, pcy = _sq_center(pr, pc)
                pygame.draw.circle(win, (40, 40, 40), (pcx + 2, pcy + 3), radius)
                pygame.draw.circle(win, p_color, (pcx, pcy), radius)
                pygame.draw.circle(win, CLR_WHITE, (pcx, pcy), radius, 2)
                if p.isupper():
                    cr = FONT_CROWN.render("K", True, CLR_GOLD)
                    win.blit(cr, cr.get_rect(center=(pcx, pcy)))

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

def _draw_mini_board(win: pygame.Surface, x: int, y: int, size: int) -> None:
    """Draw a decorative 4×4 mini checkerboard with pieces at (x, y)."""
    cell = size // 4
    for r in range(4):
        for c in range(4):
            is_dark = (r + c) % 2 == 1
            clr = CLR_DARK_SQ if is_dark else CLR_LIGHT_SQ
            pygame.draw.rect(win, clr, (x + c * cell, y + r * cell, cell, cell))

    piece_r = cell // 2 - 3
    pieces = [
        (0, 1, CLR_BLUE), (0, 3, CLR_BLUE),
        (1, 0, CLR_BLUE), (1, 2, CLR_BLUE),
        (2, 1, CLR_RED),  (2, 3, CLR_RED),
        (3, 0, CLR_RED),  (3, 2, CLR_RED),
    ]
    for pr, pc, clr in pieces:
        cx = x + pc * cell + cell // 2
        cy = y + pr * cell + cell // 2
        pygame.draw.circle(win, (20, 20, 20), (cx + 1, cy + 2), piece_r)
        pygame.draw.circle(win, clr, (cx, cy), piece_r)
        pygame.draw.circle(win, CLR_WHITE, (cx, cy), piece_r, 1)
    pygame.draw.rect(win, CLR_GOLD, (x - 1, y - 1, size + 2, size + 2), 2, border_radius=2)


def _draw_rule_row(
    win: pygame.Surface, x: int, y: int, w: int,
    icon_color: tuple, heading: str, heading_clr: tuple,
    lines: list[str], body_font: pygame.font.Font,
    heading_font: pygame.font.Font,
) -> int:
    """Draw a compact rule row with a colored dot icon. Returns new y."""
    # Background strip
    strip = pygame.Surface((w, 14 + len(lines) * 15 + 8), pygame.SRCALPHA)
    strip.fill((255, 255, 255, 12))
    win.blit(strip, (x, y))
    pygame.draw.rect(win, icon_color, (x, y, 3, strip.get_height()))

    # Colored dot icon
    pygame.draw.circle(win, icon_color, (x + 16, y + 11), 5)

    # Heading
    h_surf = heading_font.render(heading, True, heading_clr)
    win.blit(h_surf, (x + 28, y + 3))

    # Body lines
    for i, line in enumerate(lines):
        s = body_font.render(line, True, (200, 200, 210))
        win.blit(s, (x + 16, y + 20 + i * 15))

    return y + strip.get_height() + 6


def draw_intro_screen(win: pygame.Surface, mouse_pos: tuple[int, int]) -> pygame.Rect:
    """Render a polished intro screen that fits cleanly in 600×600."""
    win.fill((18, 20, 26))

    # ── Top gradient glow ──
    for i in range(80):
        a = max(0, 50 - i)
        gs = pygame.Surface((WIDTH, 1), pygame.SRCALPHA)
        gs.fill((255, 200, 50, a))
        win.blit(gs, (0, i))

    # ── Centred header area ──
    # Mini board
    board_size = 80
    bx = WIDTH // 2 - 170
    _draw_mini_board(win, bx, 20, board_size)

    # Title
    title_font = pygame.font.SysFont("segoeui", 46, bold=True)
    title = title_font.render("CHECKERS", True, CLR_GOLD)
    win.blit(title, title.get_rect(midleft=(bx + board_size + 20, 42)))

    # Subtitle — algorithm pills
    pill_font = pygame.font.SysFont("segoeui", 11, bold=True)
    pills = [
        ("Backtracking", (180, 130, 255)),
        ("Dynamic Programming", (100, 200, 160)),
        ("Alpha-Beta", (255, 180, 80)),
    ]
    px = bx + board_size + 22
    for label, clr in pills:
        ps = pill_font.render(label, True, clr)
        pw = ps.get_width() + 12
        pill_bg = pygame.Surface((pw, 18), pygame.SRCALPHA)
        pygame.draw.rect(pill_bg, (*clr, 30), (0, 0, pw, 18), border_radius=9)
        pygame.draw.rect(pill_bg, (*clr, 90), (0, 0, pw, 18), 1, border_radius=9)
        win.blit(pill_bg, (px, 72))
        win.blit(ps, (px + 6, 73))
        px += pw + 6

    # ── Divider ──
    pygame.draw.line(win, (60, 60, 70), (30, 108), (WIDTH - 30, 108), 1)

    # ── Player badges ──
    y = 116
    # Red
    pygame.draw.circle(win, CLR_RED, (60, y + 9), 8)
    pygame.draw.circle(win, CLR_WHITE, (60, y + 9), 8, 1)
    p_font = pygame.font.SysFont("segoeui", 16, bold=True)
    win.blit(p_font.render("You play RED", True, (240, 140, 140)), (75, y + 1))

    # Blue
    pygame.draw.circle(win, CLR_BLUE, (WIDTH // 2 + 40, y + 9), 8)
    pygame.draw.circle(win, CLR_WHITE, (WIDTH // 2 + 40, y + 9), 8, 1)
    win.blit(p_font.render("AI plays BLUE (Depth 6)", True, (140, 180, 240)),
             (WIDTH // 2 + 55, y + 1))

    # ── Rule sections ──
    heading_font = pygame.font.SysFont("segoeui", 14, bold=True)
    body_font = pygame.font.SysFont("segoeui", 13)
    rx = 30
    rw = WIDTH - 60
    y = 146

    y = _draw_rule_row(win, rx, y, rw, CLR_ACCENT,
        "HOW TO PLAY", CLR_ACCENT, [
            "Click a piece to select it (yellow highlight).",
            "Valid moves shown as dots — click one to move.",
            "Capture all opponent pieces or block their moves to win!",
        ], body_font, heading_font)

    y = _draw_rule_row(win, rx, y, rw, CLR_GOLD,
        "MOVEMENT", CLR_GOLD, [
            "Men move diagonally forward by one square.",
            "Kings (K) move diagonally in all four directions.",
            "Reach the back row to promote a man to King.",
        ], body_font, heading_font)

    y = _draw_rule_row(win, rx, y, rw, (255, 90, 90),
        "CAPTURES (MANDATORY)", (255, 120, 120), [
            "Jump over an opponent diagonally to capture them.",
            "If a capture exists, you MUST take it.",
            "Chain jumps: keep capturing if more are available.",
        ], body_font, heading_font)

    y = _draw_rule_row(win, rx, y, rw, CLR_BLUE,
        "AI ENGINE", (120, 170, 240), [
            "Alpha-Beta Pruning + DP memoization at depth 6.",
            "Searches thousands of positions per move.",
        ], body_font, heading_font)

    # ── Decorative vs divider ──
    vy = y + 2
    pygame.draw.line(win, (50, 50, 60), (80, vy), (WIDTH - 80, vy), 1)
    vs_font = pygame.font.SysFont("segoeui", 11, bold=True)
    vs_bg = pygame.Surface((60, 16), pygame.SRCALPHA)
    vs_bg.fill((18, 20, 26, 255))
    win.blit(vs_bg, (WIDTH // 2 - 30, vy - 8))
    # Red vs Blue icons
    pygame.draw.circle(win, CLR_RED, (WIDTH // 2 - 18, vy), 6)
    vs_t = vs_font.render("VS", True, (150, 150, 160))
    win.blit(vs_t, vs_t.get_rect(center=(WIDTH // 2, vy)))
    pygame.draw.circle(win, CLR_BLUE, (WIDTH // 2 + 18, vy), 6)

    # ── START button ──
    btn_w, btn_h = 240, 48
    btn_y = vy + 16
    btn_rect = pygame.Rect(WIDTH // 2 - btn_w // 2, btn_y, btn_w, btn_h)
    hovered = btn_rect.collidepoint(mouse_pos)

    if hovered:
        glow = pygame.Surface((btn_w + 30, btn_h + 30), pygame.SRCALPHA)
        pygame.draw.rect(glow, (70, 200, 140, 35),
                         (0, 0, btn_w + 30, btn_h + 30), border_radius=20)
        win.blit(glow, (btn_rect.x - 15, btn_rect.y - 15))

    fill = CLR_ACCENT_HOV if hovered else CLR_ACCENT
    pygame.draw.rect(win, fill, btn_rect, border_radius=14)
    pygame.draw.rect(win, CLR_WHITE, btn_rect, width=2, border_radius=14)
    btn_font = pygame.font.SysFont("segoeui", 24, bold=True)
    bl = btn_font.render("START GAME", True, CLR_WHITE)
    win.blit(bl, bl.get_rect(center=btn_rect.center))

    # ── Footer ──
    ft_font = pygame.font.SysFont("segoeui", 11)
    ft = ft_font.render("DAA Review 3  |  Backtracking + DP + Alpha-Beta Pruning",
                         True, (70, 70, 80))
    win.blit(ft, ft.get_rect(center=(WIDTH // 2, WIDTH - 10)))

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
    title = FONT_BIG.render(f"{winner_name} Wins!", True, winner_color)
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