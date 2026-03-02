import pygame
import sys
from engine import CheckersEngine
from bt_dp_ai import ai_move

WIDTH = 600
ROWS = 8
SQUARE = WIDTH // ROWS

WHITE = (240, 240, 240)
BLACK = (40, 40, 40)

RED = (200, 0, 0)
LIGHT_BLUE = (173, 216, 230)

pygame.init()
WIN = pygame.display.set_mode((WIDTH, WIDTH))
pygame.display.set_caption("Checkers - Backtracking + DP")

FONT = pygame.font.SysFont(None, 40)


def draw_board(win):
    win.fill(WHITE)
    for r in range(ROWS):
        for c in range(ROWS):
            if (r + c) % 2 == 1:
                pygame.draw.rect(win, BLACK,
                                 (c * SQUARE, r * SQUARE, SQUARE, SQUARE))


def draw_pieces(win, board):
    for (r, c), piece in board.items():

        if piece is None:
            continue

        color = RED if piece.lower() == 'r' else LIGHT_BLUE

        pygame.draw.circle(
            win,
            color,
            (c * SQUARE + SQUARE // 2,
             r * SQUARE + SQUARE // 2),
            SQUARE // 2 - 10
        )

        if piece.isupper():
            crown = FONT.render("K", True, (255, 215, 0))
            win.blit(
                crown,
                (c * SQUARE + SQUARE // 2 - 10,
                 r * SQUARE + SQUARE // 2 - 15)
            )


def main():
    engine = CheckersEngine()
    selected = None

    HUMAN = 'r'
    AI = 'b'
    depth = 4

    run = True

    while run:

        draw_board(WIN)
        draw_pieces(WIN, engine.board)
        pygame.display.update()

        if engine.game_over():
            print("Winner:", engine.get_winner())
            pygame.time.delay(3000)
            break

        # AI TURN
        if engine.turn == AI:
            pygame.time.delay(1000)  # 1 second delay
            move = ai_move(engine, AI, depth)
            if move:
                engine.apply_move(move)
            continue

        # HUMAN TURN
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                run = False

            if event.type == pygame.MOUSEBUTTONDOWN:
                x, y = pygame.mouse.get_pos()
                row = y // SQUARE
                col = x // SQUARE

                if selected is None:
                    if engine.board.get((row, col)) and \
                       engine.board[(row, col)].lower() == HUMAN:
                        selected = (row, col)
                else:
                    move = (selected, (row, col))
                    if move in engine.generate_moves(HUMAN):
                        engine.apply_move(move)
                    selected = None

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()