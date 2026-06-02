def detect_opening(moves: list[str]) -> str | None:
    """
    Detect the opening played based on the move sequence.
    Replicates and enhances the existing frontend logic.
    Returns None if no specific opening is matched.
    """
    if not moves or len(moves) == 0:
        return None

    m1 = moves[0] if len(moves) > 0 else None
    m2 = moves[1] if len(moves) > 1 else None
    m3 = moves[2] if len(moves) > 2 else None
    m4 = moves[3] if len(moves) > 3 else None
    m5 = moves[4] if len(moves) > 4 else None

    # Sanitize inputs to remove checks, mates, etc., if needed,
    # though usually opening moves don't involve checks/captures initially,
    # it's safe to use exact matches for standard openings.
    
    if m1 == 'e4':
        if m2 == 'c5': return 'Sicilian Defense'
        if m2 == 'e5':
            if m3 == 'Nf3':
                if m4 == 'Nc6':
                    if m5 == 'Bb5': return 'Ruy Lopez'
                    if m5 == 'Bc4': return 'Italian Game'
                    if m5 == 'd4': return 'Scotch Game'
                if m4 == 'Nf6': return 'Petrov Defense'
            return "King's Pawn Game"
        if m2 == 'e6': return 'French Defense'
        if m2 == 'c6': return 'Caro-Kann Defense'
        if m2 == 'd6': return 'Pirc Defense'
        return "King's Pawn Game"
        
    if m1 == 'd4':
        if m2 == 'd5':
            if m3 == 'c4': return "Queen's Gambit"
            return "Queen's Pawn Game"
        if m2 == 'Nf6':
            if m3 == 'c4':
                if m4 == 'e6': return 'Nimzo-Indian Defense'
                if m4 == 'g6': return "King's Indian Defense"
            return 'Indian Defense'
        return "Queen's Pawn Game"
        
    if m1 == 'Nf3': return 'Réti Opening'
    if m1 == 'c4': return 'English Opening'
    if m1 == 'f4': return "Bird's Opening"
    
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
