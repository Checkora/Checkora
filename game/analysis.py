import os
import json

# Load the opening book JSON once on startup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OPENINGS_JSON_PATH = os.path.join(BASE_DIR, 'openings.json')

try:
    with open(OPENINGS_JSON_PATH, 'r', encoding='utf-8') as f:
        OPENINGS = json.load(f)
except FileNotFoundError:
    OPENINGS = {}
    # TODO: replace with project logger
    print(f"warning: opening book not found at {OPENINGS_JSON_PATH}")
except json.JSONDecodeError as exc:
    raise RuntimeError(f"invalid openings.json: {exc}") from exc

def detect_opening(moves: list[str]) -> str | None:
    """
    Detect the opening played based on the move sequence.
    Replicates and enhances the existing frontend logic.
    Returns None if no specific opening is matched.
    """
    if not moves:
        return None

    # Search for the longest matching prefix sequence of moves in the opening dictionary.
    for i in range(len(moves), 0, -1):
        prefix_key = " ".join(moves[:i])
        if prefix_key in OPENINGS:
            return OPENINGS[prefix_key]

    return None

def count_captures(moves: list[str]) -> int:
    """Count total captures ('x') in the move history."""
    return sum(1 for move in moves if 'x' in move)

def count_checks(moves: list[str]) -> int:
    """Count total checks ('+') in the move history."""
    return sum(1 for move in moves if '+' in move)

def count_checkmates(moves: list[str]) -> int:
    """Count total checkmates ('#') in the move history."""
    return sum(1 for move in moves if '#' in move)

def count_promotions(moves: list[str]) -> int:
    """Count total promotions ('=') in the move history."""
    return sum(1 for move in moves if '=' in move)

def build_summary(moves: list[str], result: str, end_reason: str) -> dict:
    """
    Build a comprehensive summary of the game.
    """
    opening = detect_opening(moves) or 'Standard Game'
    
    return {
        "opening": opening,
        "result": result,
        "total_moves": (len(moves) + 1) // 2, # Total full moves
        "captures": count_captures(moves),
        "checks": count_checks(moves),
        "checkmates": count_checkmates(moves),
        "promotions": count_promotions(moves),
        "end_reason": end_reason
    }
