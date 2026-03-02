# prepare.md — Line-by-Line Study Guide for DAA Review 3 Panel

Each person must study their section thoroughly. For each code block you will find:
**What** → What this code does  
**Why** → Why we need it / why this approach  
**Output** → What it produces  
**Complexity** → Time & space  
**Justification** → Why only this method, not alternatives  

---

# ═══════════════════════════════════════════════════════════════════
# PERSON 1 — Game Engine, Rules & Backtracking in Move Generation
# ═══════════════════════════════════════════════════════════════════

## Files to Study
- `utils.py` — Lines 1–17 (full file)
- `engine.py` — Lines 1–245 (board init, directions, move generation, capture chains)

---

## 1.1 Board Representation (`engine.py` Lines 69–102)

### Code
```python
class CheckersEngine:
    def __init__(self):
        self.board: BoardDict = {}
        self.turn: str = 'r'
        self._init_board()

    def _init_board(self):
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if (r + c) % 2 == 1:           # Only dark squares
                    if r < 3:
                        self.board[(r, c)] = 'b'   # Black pieces rows 0-2
                    elif r > 4:
                        self.board[(r, c)] = 'r'   # Red pieces rows 5-7
                    else:
                        self.board[(r, c)] = None   # Empty middle rows
```

### What
Creates the game board as a **dictionary** where keys are `(row, col)` tuples and values are piece characters (`'r'`, `'b'`, `'R'`, `'B'`, or `None`).

### Why
- Only 32 of 64 squares are dark (playable). A 2D list wastes 50% of its space.
- Dictionary lookup `self.board[(3,4)]` is **O(1)** — same speed as array indexing.
- Keys are `(row, col)` tuples — intuitive and hashable.

### Output
```
{(0,1): 'b', (0,3): 'b', (0,5): 'b', (0,7): 'b',
 (1,0): 'b', (1,2): 'b', (1,4): 'b', (1,6): 'b',
 (2,1): 'b', (2,3): 'b', (2,5): 'b', (2,7): 'b',
 (3,0): None, (3,2): None, (3,4): None, (3,6): None,
 (4,1): None, (4,3): None, (4,5): None, (4,7): None,
 (5,0): 'r', (5,2): 'r', (5,4): 'r', (5,6): 'r',
 (6,1): 'r', (6,3): 'r', (6,5): 'r', (6,7): 'r',
 (7,0): 'r', (7,2): 'r', (7,4): 'r', (7,6): 'r'}
```

### Complexity
- **Time**: O(n) to initialise, n = 32 dark squares
- **Space**: O(n) — one dict entry per dark square

### Justification
> **Why not a 2D list?** A `board[8][8]` array stores 64 entries, but only 32 are used. The dict avoids wasting memory and makes iteration over pieces faster (skip empties with `if piece`). Also, dict keys are directly hashable for the DP `board_key`.

---

## 1.2 Direction Tables (`engine.py` Lines 41–49)

### Code
```python
NORMAL_DIRECTIONS = {
    'r': [(-1, -1), (-1, 1)],    # Red moves UPWARD (row decreases)
    'b': [(1, -1), (1, 1)],      # Black moves DOWNWARD (row increases)
}

KING_DIRECTIONS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]  # All 4 diagonals
```

### What
Defines which diagonal directions each piece type can move in.

### Why
- Men can only move **forward** (toward the opponent's side).
- Kings can move in **all 4 diagonals** — this is what makes promotion powerful.
- Stored as `(row_delta, col_delta)` pairs for easy arithmetic.

### Example
```
Red piece at (5, 2):
  Directions: (-1, -1) and (-1, 1)
  → Can move to (4, 1) or (4, 3)

King at (3, 4):
  Directions: (-1,-1), (-1,1), (1,-1), (1,1)
  → Can move to (2, 3), (2, 5), (4, 3), (4, 5)
```

---

## 1.3 Forced Capture — `generate_moves` (`engine.py` Lines 216–245)

### Code
```python
def generate_moves(self, player):
    # Step 1: Find ALL capture chains using backtracking
    all_captures = []
    for (row, col), piece in self.board.items():
        if piece and piece.lower() == player:
            self._build_capture_chain(row, col, piece, [(row,col)], set(), all_captures)

    # Step 2: FORCED CAPTURE — if any captures exist, ONLY return captures
    if all_captures:
        max_len = max(len(m) for m in all_captures)
        return [m for m in all_captures if len(m) == max_len]   # Longest only

    # Step 3: No captures available → return simple (non-capture) moves
    return self._get_simple_moves(player)
```

### What
Generates all legal moves for a player. If any capture is possible, **only** captures are returned (the player is forced to capture).

### Why — The Forced Capture Rule
In official Checkers rules (WCDF), if you can capture, you **must**. This prevents players from avoiding captures to keep their pieces safe.

### Output Example
```
# If Red has a capture available:
generate_moves('r') → [((5,0), (3,2))]        # Only the capture, no simple moves

# If no captures:
generate_moves('r') → [((5,0),(4,1)), ((5,2),(4,1)), ((5,2),(4,3)), ...]
```

### Complexity
- **Time**: O(p × 4 × chain_depth) where p = number of player's pieces
- **Space**: O(number of valid chains)

### Justification
> **Why filter to longest chains?** Tournament Checkers requires taking the **maximum** capture. If you can double-jump, you can't choose to single-jump instead.

---

## 1.4 ⭐ BACKTRACKING in Move Generation — `_build_capture_chain` (`engine.py` Lines 136–214)

**This is the most important function for Person 1.**

### Code (line by line)
```python
def _build_capture_chain(self, row, col, piece, path, captured_set, results):
```
- `row, col` — current position of the jumping piece
- `piece` — the piece character (`'r'`, `'b'`, `'R'`, `'B'`)
- `path` — list of positions visited so far, e.g., `[(6,1), (4,3)]`
- `captured_set` — set of already-captured positions (prevents re-capture)
- `results` — accumulator list where completed chains are stored

```python
    found_jump = False

    for d_row, d_col in self._get_directions(piece):
        mid_row, mid_col = row + d_row, col + d_col         # Adjacent square
        jump_row, jump_col = row + 2*d_row, col + 2*d_col   # Landing square
```
- We check each diagonal direction
- `mid` = the square being jumped over (must have an opponent)
- `jump` = the landing square (must be empty)

```python
        if not in_bounds(jump_row, jump_col):
            continue
```
- Skip if landing is off the board

```python
        if (mid_piece is not None
                and mid_piece.lower() == opponent(piece.lower())
                and (mid_row, mid_col) not in captured_set
                and dest_piece is None):
```
- Valid jump requires: (1) mid has an opponent, (2) not already captured, (3) landing is empty

```python
            found_jump = True

            # ── BACKTRACKING STEP 1: APPLY (mutate the board) ──
            self.board[(row, col)] = None
            saved_mid = self.board[(mid_row, mid_col)]
            self.board[(mid_row, mid_col)] = None
            self.board[(jump_row, jump_col)] = piece
```
- **APPLY**: Temporarily move the piece and remove the captured opponent
- `saved_mid` is stored so we can restore it later

```python
            # Check mid-chain promotion
            if piece == 'r' and jump_row == 0:
                self.board[(jump_row, jump_col)] = 'R'
                promoted = True
```
- If the piece reaches the back row mid-chain, it promotes

```python
            captured_set.add((mid_row, mid_col))
            path.append((jump_row, jump_col))

            # ── BACKTRACKING STEP 2: RECURSE ──
            self._build_capture_chain(jump_row, jump_col, new_piece, path, captured_set, results)
```
- Add this jump to the path and captured set
- **RECURSE**: Try to find more jumps from the new position

```python
            # ── BACKTRACKING STEP 3: UNDO (restore the board) ──
            path.pop()
            captured_set.discard((mid_row, mid_col))
            self.board[(jump_row, jump_col)] = None
            self.board[(mid_row, mid_col)] = saved_mid
            self.board[(row, col)] = piece
```
- **UNDO**: Reverse every mutation — board is identical to before Step 1

```python
    if not found_jump:
        if len(path) > 1:
            results.append(tuple(path))   # This chain is complete
```
- If no more jumps possible and we've made at least one jump → save the chain

### Example — Double Jump
```
Initial board:                    After chain discovery:
  . b . .                          Path: ((6,1), (4,3), (2,5))
  . . . .                          Captured: {(5,2), (3,4)}
  . . . b .
  . . . . .
  . r . . .                        The board is UNCHANGED after discovery!
```

### Diagram
```
    (6,1)  ──jump──>  (4,3)  ──jump──>  (2,5)
              ↑                  ↑
         captures (5,2)     captures (3,4)

    Backtracking ensures the board returns to its original state
    after exploring each candidate chain.
```

### Complexity
- **Time**: O(4^k) per piece, where k = max chain length (usually ≤ 4)
- **Space**: O(k) recursion stack depth

### Justification
> **Why mutate the board instead of cloning?** If we copied the board at each recursive step, generating chains for all pieces would need O(n × 4^k) copies. By mutating and undoing, we use O(1) extra memory per recursion level, with just one board instance.

---

# ═══════════════════════════════════════════════════════════════════
# PERSON 2 — Backtracking in AI Search
# ═══════════════════════════════════════════════════════════════════

## Files to Study
- `engine.py` — Lines 251–329 (`apply_move`, `undo_move`)
- `bt_dp_ai.py` — Lines 147–157 (the BT loop inside `alphabeta_bt_dp`)

---

## 2.1 The Problem: Why Backtracking?

The AI needs to explore **thousands** of possible future board states to decide the best move. There are two approaches:

### Approach A: Clone the board (NAIVE)
```python
import copy
for move in moves:
    new_board = copy.deepcopy(board)     # O(n) per copy
    new_board.make_move(move)
    score = search(new_board, depth - 1)
```
- Creates a new board at **every** node
- At depth 6 with branching factor 10: 10^6 = 1,000,000 copies
- Each copy is O(32) → **32 million operations** just for copying

### Approach B: Backtracking (OUR APPROACH)
```python
for move in moves:
    info = engine.apply_move(move)       # O(1) mutate
    score = search(engine, depth - 1)    # Same board object
    engine.undo_move(move, info)         # O(1) restore
```
- **ONE** board for the entire search
- apply = O(1), undo = O(1)
- Total: ~2,800 apply+undo pairs (not 1 million copies)

### Memory Comparison Table

| Approach | Memory | Operations at d=6, b=10 |
|----------|--------|------------------------|
| Cloning | O(n × b^d) = 32 × 10^6 entries | 1,000,000 deep copies |
| **Backtracking** | **O(n + d)** = 32 + 6 = **38** | 2,800 apply+undo pairs |

---

## 2.2 `apply_move` — BT Step 1: APPLY (`engine.py` Lines 251–305)

### Code (line by line)
```python
def apply_move(self, move: MovePath) -> MoveInfo:
    start = move[0]                        # Line 266: First position in path
    piece = self.board[start]              # Line 267: What piece is moving
    captured_list = []                     # Line 268: Track captures for UNDO
    promoted = False                       # Line 269: Track promotion for UNDO
```
- **What**: Extract the piece and prepare the change log

```python
    self.board[start] = None               # Line 271: Remove piece from origin
```
- **What**: The starting square is now empty
- **Why**: The piece is "picked up" from the board

```python
    for i in range(1, len(move)):          # Line 274: Process each leg
        prev_row, prev_col = move[i - 1]   # Where we came from
        dest_row, dest_col = move[i]        # Where we're going
```
- **What**: Walk through each leg of a multi-jump path
- **Example**: For `((6,1), (4,3), (2,5))` — leg 1: (6,1)→(4,3), leg 2: (4,3)→(2,5)

```python
        if abs(dest_row - prev_row) == 2:   # Line 279: Is this a jump?
            mid = ((prev_row + dest_row) // 2,  # Line 280-282: Midpoint
                   (prev_col + dest_col) // 2)
            captured_list.append((mid, self.board[mid]))  # Line 284: SAVE for undo
            self.board[mid] = None                        # Line 285: REMOVE captured
```
- **What**: If moving 2 squares diagonally, it's a capture. Find the midpoint, save the captured piece, then remove it.
- **Why save?**: The `captured_list` is the **change log** — without it, `undo_move` couldn't restore the captured pieces.

```python
    final = move[-1]                       # Line 288: Last position
    self.board[final] = piece              # Line 289: Place piece at destination
```

```python
    if piece == 'r' and final[0] == 0:     # Line 292: Red reaches row 0?
        self.board[final] = 'R'            # Line 293: PROMOTE to King
        promoted = True
    elif piece == 'b' and final[0] == 7:   # Line 295: Black reaches row 7?
        self.board[final] = 'B'            # Line 296: PROMOTE to King
```

```python
    self.turn = opponent(self.turn)         # Line 299: Switch turns

    return {                               # Line 301-305: THE CHANGE LOG
        'piece': piece,                    # Original piece character
        'captured': captured_list,         # List of (position, piece) tuples
        'promoted': promoted,              # Whether promotion occurred
    }
```

### What does `info` look like?
```python
# Simple move: ((5,0), (4,1))
info = {'piece': 'r', 'captured': [], 'promoted': False}

# Single capture: ((5,0), (3,2))
info = {'piece': 'r', 'captured': [((4,1), 'b')], 'promoted': False}

# Double jump with promotion: ((6,1), (4,3), (2,5))  and piece reaches row 0
info = {'piece': 'r', 'captured': [((5,2), 'b'), ((3,4), 'B')], 'promoted': True}
```

---

## 2.3 `undo_move` — BT Step 3: UNDO (`engine.py` Lines 307–329)

### Code (line by line)
```python
def undo_move(self, move: MovePath, info: MoveInfo) -> None:
    start = move[0]                         # Line 318: Original start position
    final = move[-1]                        # Line 319: Where the piece ended up

    original_piece = info['piece']          # Line 321: BEFORE any promotion
    self.board[final] = None                # Line 322: Clear destination
    self.board[start] = original_piece      # Line 323: Put piece BACK at origin
```
- **What**: Reverse the piece movement
- **Key**: We use `info['piece']` (the original character), NOT whatever is currently at `final`. This correctly un-promotes Kings.

```python
    for pos, captured_piece in info['captured']:   # Line 326
        self.board[pos] = captured_piece           # Line 327: Restore captured
```
- **What**: Put every captured piece back on the board

```python
    self.turn = opponent(self.turn)          # Line 329: Reverse turn switch
```

### Correctness Proof
Every mutation in `apply_move` has an exact reverse in `undo_move`:

| `apply_move` Mutation | `undo_move` Reversal |
|-----------------------|---------------------|
| `board[start] = None` | `board[start] = info['piece']` |
| `board[mid] = None` (capture) | `board[mid] = captured_piece` (from info) |
| `board[final] = piece` | `board[final] = None` |
| `piece → King` (promotion) | Restored from `info['piece']` (original) |
| `turn = opponent(turn)` | `turn = opponent(turn)` (reverses) |

> After `undo_move`, the board is **byte-for-byte identical** to its state before `apply_move` was called.

---

## 2.4 BT in the AI Search Loop (`bt_dp_ai.py` Lines 147–157)

```python
    for move in moves:                               # Line 147
        info = engine.apply_move(move)               # Line 149: BT STEP 1 — APPLY
        val = alphabeta_bt_dp(                       # Line 152: BT STEP 2 — RECURSE
            engine, depth - 1, alpha, beta,
            not maximizing, player
        )
        engine.undo_move(move, info)                 # Line 157: BT STEP 3 — UNDO
```

### Diagram — How backtracking flows through the tree
```
    search(depth=3, board=B₀)
    │
    ├── apply(move_A) → board=B₁
    │   ├── search(depth=2, board=B₁)
    │   │   ├── apply(move_X) → board=B₂
    │   │   │   └── search(depth=1, board=B₂) → score = 7
    │   │   ├── undo(move_X)  → board=B₁        ← RESTORED
    │   │   │
    │   │   ├── apply(move_Y) → board=B₃
    │   │   │   └── search(depth=1, board=B₃) → score = 3
    │   │   └── undo(move_Y)  → board=B₁        ← RESTORED
    │   │
    │   └── return max(7, 3) = 7
    │
    ├── undo(move_A) → board=B₀                  ← RESTORED TO ORIGINAL
    │
    ├── apply(move_B) → board=B₄
    │   └── search(depth=2, board=B₄) → score = 5
    ├── undo(move_B) → board=B₀                  ← RESTORED TO ORIGINAL
    │
    └── return max(7, 5) = 7
```

### Complexity
- **Time**: O(1) per apply_move + O(1) per undo_move = O(1) per node
- **Space**: O(d) stack frames, d = 6. Each frame holds one `info` dict with ≤ 4 captured pieces.
- **Total BT overhead**: O(d) — **constant** regardless of tree size

---

# ═══════════════════════════════════════════════════════════════════
# PERSON 3 — Dynamic Programming (Memoization)
# ═══════════════════════════════════════════════════════════════════

## Files to Study
- `engine.py` — Lines 368–380 (`board_key`) + Lines 386–444 (`evaluate`)
- `bt_dp_ai.py` — Lines 40–65 (flags, memo dict) + Lines 104–117 (DP lookup) + Line 178 (DP store)

---

## 3.1 The Problem: Overlapping Subproblems

### What are overlapping subproblems?
The same board position can be reached through **different** move sequences:

```
Sequence A:  Red(5,0)→(4,1)  then  Red(5,2)→(4,3)
Sequence B:  Red(5,2)→(4,3)  then  Red(5,0)→(4,1)
                      ↓                    ↓
              SAME BOARD STATE          SAME BOARD STATE
```

Without DP, the AI evaluates the subtree below this state **once for each path** that reaches it. This is exponential waste.

### This is why it's DP
The two requirements for Dynamic Programming are:
1. **Optimal substructure** ✅ — the best move from state X doesn't depend on how we reached X
2. **Overlapping subproblems** ✅ — state X can be reached via multiple paths

---

## 3.2 `board_key` — Generating the DP Key (`engine.py` Lines 368–380)

### Code (line by line)
```python
def board_key(self) -> frozenset:
    return frozenset(
        (pos, piece) for pos, piece in self.board.items() if piece
    )
```

### What
Creates a **unique, hashable fingerprint** for the current board state. Only occupied squares are included.

### Output Example
```python
# Board with 3 pieces:
board_key() → frozenset({
    ((0,1), 'b'),
    ((5,0), 'r'),
    ((3,4), 'R'),
})
```

### Why `frozenset`?
| Alternative | Problem |
|-------------|---------|
| `tuple(sorted(board.items()))` | Sorting is O(n log n); includes empty squares |
| `str(board)` | String creation is slow; not order-independent |
| **`frozenset`** | ✅ O(n), order-independent, hashable, skips empties |

### Why skip `None` entries?
- Only ~12 pieces mid-game vs 32 total squares
- Fewer items → faster hashing → faster dict lookups
- Two boards are identical if they have the same pieces in the same positions — empties don't matter

### Complexity
- **Time**: O(k) where k = number of occupied squares (≤ 24)
- **Space**: O(k) for the frozenset

---

## 3.3 The Transposition Table (`bt_dp_ai.py` Lines 53–63)

### Code
```python
memo: dict = {}          # Line 61: The DP dictionary (transposition table)
nodes_searched: int = 0  # Line 63: Counter for profiling

# Each entry looks like:
# memo[(board_key, depth, maximizing)] = {
#     'score': 7.5,         # The evaluated score
#     'flag': EXACT,         # Type of result (see 3.5)
#     'depth': 6,            # Depth at which this was computed
# }
```

### What
A Python dictionary that maps `(board_state, depth, maximizing)` → evaluation result.

### Why include `depth` and `maximizing` in the key?
- Same board at depth 6 has a **more accurate** score than at depth 2
- A maximizing node and minimizing node at the same board have **different** scores

### Diagram
```
   memo = {
     (frozenset({...}), 6, True):  {'score': 7.5, 'flag': EXACT, 'depth': 6},
     (frozenset({...}), 4, False): {'score': -2.0, 'flag': LOWER_BOUND, 'depth': 4},
     ...
   }
```

---

## 3.4 DP Lookup (`bt_dp_ai.py` Lines 104–117)

### Code (line by line)
```python
    key = (engine.board_key(), depth, maximizing)    # Line 105: Create lookup key
```

```python
    if key in memo:                                   # Line 107: Cache hit?
        entry = memo[key]
        if entry['depth'] >= depth:                   # Line 109: Sufficient depth?
```
- Only use cached result if it was computed at **equal or greater** depth (more accurate)

```python
            if entry['flag'] == EXACT:
                return entry['score']                 # Line 111: Perfect match → done!
```
- EXACT means no pruning occurred — the score is reliable. **Skip entire subtree!**

```python
            elif entry['flag'] == LOWER_BOUND:
                alpha = max(alpha, entry['score'])    # Line 113: Raise the floor
            elif entry['flag'] == UPPER_BOUND:
                beta = min(beta, entry['score'])      # Line 115: Lower the ceiling
            if alpha >= beta:
                return entry['score']                 # Line 117: Window collapsed
```
- LOWER/UPPER bounds **narrow** the α-β window, enabling more pruning downstream

### Example
```
State X was evaluated at depth 6 → score = 5.0, flag = EXACT
Later, State X is reached again at depth 4:
  → entry['depth']=6 >= depth=4 ✅
  → flag is EXACT → return 5.0 immediately
  → SAVED: an entire depth-4 subtree (~10,000 nodes) is SKIPPED
```

---

## 3.5 DP Store & Flags (`bt_dp_ai.py` Lines 170–178)

### Code
```python
    if best <= original_alpha:           # Line 171
        flag = UPPER_BOUND               # We know score ≤ best (pruned low)
    elif best >= beta:                   # Line 173
        flag = LOWER_BOUND               # We know score ≥ best (pruned high)
    else:                                # Line 175
        flag = EXACT                     # No pruning — score is exact

    memo[key] = {'score': best, 'flag': flag, 'depth': depth}  # Line 178
```

### What each flag means

| Flag | Meaning | When does it happen? |
|------|---------|---------------------|
| `EXACT` | Score IS exactly `best` | All children were explored, no pruning |
| `LOWER_BOUND` | True score is **≥** `best` | Beta cutoff — we stopped early because maximizer already has enough |
| `UPPER_BOUND` | True score is **≤** `best` | Alpha cutoff — we stopped early because minimizer already has enough |

### Why do we need flags?
Without flags, we might use a pruned result as if it were exact. Example:
```
Node X was pruned at score 5 (beta cutoff, LOWER_BOUND)
True score might be 5, 7, or 100 — we don't know exactly.
If we stored it as EXACT=5 and later queried it:
  We might miss a score of 100 → BAD DECISION
With LOWER_BOUND flag:
  We know score ≥ 5 → we use it to raise alpha, not as final answer
```

---

## 3.6 The Evaluation Heuristic (`engine.py` Lines 386–444)

### Code (simplified)
```python
def evaluate(self, player):
    score = 0.0
    for (row, col), piece in self.board.items():
        if piece is None:
            continue
        
        value = 3.0 if piece.isupper() else 1.0    # King=3, Man=1
        
        # Positional bonuses:
        if col in {0, 7}:       value += 0.5        # Edge safety
        if row in {3, 4}:       value += 0.3        # Centre control
        if close_to_promotion:  value += 0.1 * rows  # Advancement
        if on_home_row:         value += 0.2         # Back-row defence
        
        if own_piece:
            score += value
        else:
            score -= value
    return score
```

### Why each factor matters

| Factor | Bonus | Strategic reason |
|--------|-------|-----------------|
| King material | +3.0 | Kings move in 4 directions — 2× more powerful than men |
| Man material | +1.0 | Basic piece value |
| Edge column | +0.5 | Pieces on col 0 or 7 cannot be captured from one side |
| Centre | +0.3 | Centre pieces influence more diagonals |
| Advancement | +0.1×rows | Pieces near promotion are more threatening |
| Back-row | +0.2 | Guards against opponent promotion |

---

# ═══════════════════════════════════════════════════════════════════
# PERSON 4 — Alpha-Beta Pruning + DP Interaction
# ═══════════════════════════════════════════════════════════════════

## Files to Study
- `bt_dp_ai.py` — Lines 67–180 (`alphabeta_bt_dp`) + Lines 187–235 (`ai_move`)

---

## 4.1 What is Minimax?

Minimax is a decision algorithm for 2-player games. It alternates between:
- **Maximizer** (AI): picks the move with the **highest** score
- **Minimizer** (opponent): picks the move with the **lowest** score

```
         MAX (picks highest)
        / | \
      5   3   7          ← MAX picks 7
     /|  /|  /|
    MIN  MIN  MIN        ← each MIN picks lowest
```

### Why it works
The opponent is assumed to play **perfectly**. By assuming the worst case at each opponent's turn, the AI finds the best move that's guaranteed regardless of what the opponent does.

---

## 4.2 Alpha-Beta Pruning — The Key Optimisation

### What are α and β?
- **α (alpha)** = the **best** score the maximizer can guarantee so far (starts at -∞)
- **β (beta)** = the **best** score the minimizer can guarantee so far (starts at +∞)

### The Pruning Rule
> **If α ≥ β at any node → PRUNE (skip remaining children)**

### Code (line by line) (`bt_dp_ai.py` Lines 159–168)
```python
        if maximizing:
            best = max(best, val)          # Line 160: Track best for MAX
            alpha = max(alpha, val)        # Line 161: Raise floor
        else:
            best = min(best, val)          # Line 163: Track best for MIN
            beta = min(beta, val)          # Line 164: Lower ceiling

        if alpha >= beta:                  # Line 167: PRUNE CONDITION
            break                          # Line 168: Skip remaining moves
```

### Why pruning is correct — Example

```
           MAX
          / | \
        5   ?   ?

 MAX already has α=5 from left child.
 
           MAX (α=5)
          / | \
        5  MIN  ?
          / \
         3   ?

 MIN found 3 → β=3
 α=5 ≥ β=3 → PRUNE!

 WHY? MIN will pick ≤ 3. MAX already has 5.
 MAX will NEVER choose this branch. So skip "?".
```

### Detailed Pruning Diagram
```
                    MAX  α=-∞, β=+∞
                   / | \
                  /  |  \
               MIN  MIN  MIN
              α=-∞  ...  (pruned!)
              β=+∞
              /  \
            5    3
            ↑
     After 5: α=5, β=+∞ → continue
     After 3: best=3 → return 3 to MAX
     
     MAX: after left MIN returns 3 → α=3
     MAX: middle MIN starts with α=3, β=+∞
              /  \
            2     ?
            ↑
     After 2: best=2, β=min(+∞,2)=2
     α=3 ≥ β=2 → PRUNE! Don't evaluate "?"
     
     WHY? This MIN will give ≤ 2. MAX has 3. Skip.
```

---

## 4.3 Depth-Adjusted Terminal Scores (`bt_dp_ai.py` Lines 119–127)

### Code
```python
    if engine.game_over():
        winner = engine.get_winner()
        if winner == player:
            return 1000 + depth        # Win sooner → HIGHER score
        elif winner is None:
            return 0                   # Draw
        else:
            return -1000 - depth       # Lose later → LESS negative
```

### Why `+ depth`?
- A win at depth 6 (sooner) scores 1006
- A win at depth 2 (later) scores 1002
- The AI prefers **faster** wins and **slower** losses

---

## 4.4 How BT + DP + Alpha-Beta Work Together

### The Complete Flow
```
ai_move(engine, 'b', depth=6)
│
├─ For each legal move:
│   │
│   ├─ apply_move(move)                        ← BACKTRACKING
│   │
│   ├─ alphabeta_bt_dp(depth=5, α=-∞, β=+∞)
│   │   │
│   │   ├─ DP LOOKUP: board_key in memo?       ← DYNAMIC PROGRAMMING
│   │   │   ├─ EXACT hit → return cached score (SKIP SUBTREE)
│   │   │   └─ BOUND hit → narrow α-β window
│   │   │
│   │   ├─ For each child move:
│   │   │   ├─ apply_move()                    ← BACKTRACKING
│   │   │   ├─ recurse(depth-1, α, β)         ← ALPHA-BETA
│   │   │   ├─ undo_move()                     ← BACKTRACKING
│   │   │   └─ if α ≥ β → PRUNE               ← ALPHA-BETA
│   │   │
│   │   └─ DP STORE: memo[key] = {score, flag} ← DYNAMIC PROGRAMMING
│   │
│   ├─ undo_move(move)                         ← BACKTRACKING
│   └─ Track best_move
│
└─ Return best_move
```

---

## 4.5 Complexity Summary

### Time Complexity

| Algorithm | Nodes | At d=6, b=10 |
|-----------|-------|---------------|
| Brute-force (all game) | O(b^50) | 10^50 — IMPOSSIBLE |
| Minimax (depth-limited) | O(b^d) | 10^6 = 1,000,000 |
| Alpha-Beta | O(b^(d/2)) | 10^3 = 1,000 |
| **Alpha-Beta + DP** | < O(b^(d/2)) | **~2,800 actual** |

### Proof: Alpha-Beta is O(b^(d/2))

In the **best case** (moves sorted by quality):
- At MAX nodes: the best move is tried first → all other branches are pruned
- At MIN nodes: same — best response is tried first
- Result: only √(b^d) = b^(d/2) nodes are expanded

### Evidence from our game:
```
[AI] Depth 6 | Nodes searched: 2810
vs. plain Minimax at depth 6: ~1,000,000 nodes
Reduction: 99.7%
```

### Space Complexity

| Component | Space | Why |
|-----------|-------|-----|
| Board | O(n) = O(32) | Single board (thanks to BT) |
| Recursion stack | O(d) = O(6) | One frame per depth |
| `info` dicts on stack | O(d × c) | c = captures per move (≤ 4) |
| Transposition table | O(\|S\|) | \|S\| = unique states seen |
| **Total** | **O(n + d + \|S\|)** | |

Without BT: O(n × b^d) = 32 million for board copies alone. With BT: O(38). **That's the power of backtracking.**
