def in_bounds(r, c):
    return 0 <= r < 8 and 0 <= c < 8


def opponent(player):
    return 'b' if player == 'r' else 'r'