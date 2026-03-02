import math
from utils import opponent

memo = {}


def minimax_bt_dp(engine, depth, maximizing, player):

    key = (engine.board_key(), depth, maximizing)

    if key in memo:
        return memo[key]

    # Strong terminal scoring
    if engine.game_over():
        winner = engine.get_winner()
        if winner == player:
            return 1000
        elif winner is None:
            return 0
        else:
            return -1000

    if depth == 0:
        return engine.evaluate(player)

    current_player = player if maximizing else opponent(player)
    moves = engine.generate_moves(current_player)

    if maximizing:
        best = -math.inf
        for move in moves:
            info = engine.apply_move(move)
            val = minimax_bt_dp(engine, depth - 1, False, player)
            engine.undo_move(move, info)
            best = max(best, val)
    else:
        best = math.inf
        for move in moves:
            info = engine.apply_move(move)
            val = minimax_bt_dp(engine, depth - 1, True, player)
            engine.undo_move(move, info)
            best = min(best, val)

    memo[key] = best
    return best


def ai_move(engine, player, depth=4):

    best_score = -math.inf
    best_move = None

    moves = engine.generate_moves(player)

    for move in moves:
        info = engine.apply_move(move)
        score = minimax_bt_dp(engine, depth - 1, False, player)
        engine.undo_move(move, info)

        if score > best_score:
            best_score = score
            best_move = move

    return best_move