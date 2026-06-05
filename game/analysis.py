import json
import os

_openings_cache = None

def _load_openings() -> list[dict]:
    global _openings_cache
    if _openings_cache is None:
        path = os.path.join(os.path.dirname(__file__), 'opening_book_index.json')
        with open(path) as f:
            data = json.load(f)
        _openings_cache = sorted(data, key=lambda x: len(x["moves"]), reverse=True)
    return _openings_cache

def detect_opening(moves: list[str]) -> str | None:
    """
    Detect the opening played based on the move sequence.
    Replicates and enhances the existing frontend logic.
    Returns None if no specific opening is matched.
    """
    if not moves:
        return None

    openings = _load_openings()
    for opening in openings:
        op_moves = opening["moves"]
        if len(moves) >= len(op_moves) and moves[:len(op_moves)] == op_moves:
            return opening["name"]
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
