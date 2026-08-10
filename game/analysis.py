import os
import json
import logging

logger = logging.getLogger(__name__)

# Load the opening book JSON once on startup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OPENINGS_JSON_PATH = os.path.join(BASE_DIR, 'openings.json')

try:
    with open(OPENINGS_JSON_PATH, 'r', encoding='utf-8') as f:
        OPENINGS = json.load(f)
except FileNotFoundError:
    OPENINGS = {}
    logger.warning("Opening book not found at %s", OPENINGS_JSON_PATH)
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

def compute_material(fen: str) -> dict:
    """Calculate material balance from a FEN string."""
    piece_values = {'p': 1, 'n': 3, 'b': 3, 'r': 5, 'q': 9}
    board_part = fen.split(' ')[0]
    
    white_mat = sum(piece_values.get(c.lower(), 0) for c in board_part if c.isupper())
    black_mat = sum(piece_values.get(c, 0) for c in board_part if c.islower() and c in piece_values)
    
    return {'white': white_mat, 'black': black_mat}

def classify_moves(moves: list[str], fen_history: list[str]) -> dict:
    """Classify moves based on material heuristics."""
    if not fen_history or len(fen_history) <= len(moves):
        # Fallback if fen_history is empty or not properly aligned
        return {
            'move_analysis': ['Unknown'] * len(moves),
            'mistakes': 0,
            'blunders': 0,
            'accuracy': 100,
            'material_summary': []
        }

    move_analysis = []
    mistakes = 0
    blunders = 0
    accuracy = 100
    material_summary = []

    for i in range(len(fen_history)):
        material_summary.append(compute_material(fen_history[i]))

    for i, move in enumerate(moves):
        # i is the index of the move. fen_history[i] is before the move, fen_history[i+1] is after.
        is_white_turn = (i % 2 == 0)
        
        mat_before = material_summary[i]
        mat_after = material_summary[i + 1]
        
        # Calculate material advantage from the perspective of the player who just moved
        if is_white_turn:
            adv_before = mat_before['white'] - mat_before['black']
            adv_after_immediate = mat_after['white'] - mat_after['black']
        else:
            adv_before = mat_before['black'] - mat_before['white']
            adv_after_immediate = mat_after['black'] - mat_after['white']
            
        diff = adv_after_immediate - adv_before
        
        # To detect if the move was punished, look at the advantage after the opponent's reply (i+2)
        if i + 2 < len(material_summary):
            mat_reply = material_summary[i + 2]
            if is_white_turn:
                adv_after_reply = mat_reply['white'] - mat_reply['black']
            else:
                adv_after_reply = mat_reply['black'] - mat_reply['white']
            
            # Use the worst outcome between immediate and after reply
            diff = min(diff, adv_after_reply - adv_before)

        # Look ahead up to 4 plies to see if material is regained (e.g., a delayed recapture)
        regained = False
        if diff < 0:
            for lookahead in range(1, 5):
                if i + lookahead < len(material_summary):
                    mat_future = material_summary[i + lookahead]
                    if is_white_turn:
                        adv_future = mat_future['white'] - mat_future['black']
                    else:
                        adv_future = mat_future['black'] - mat_future['white']
                    
                    if adv_future >= adv_before:
                        regained = True
                        break

        classification = 'Good Move'
        if diff <= -3 and not regained:
            classification = 'Blunder Candidate'
            blunders += 1
            accuracy -= 5
        elif diff <= -1 and not regained:
            classification = 'Mistake'
            mistakes += 1
            accuracy -= 2
            
        move_analysis.append(classification)

    accuracy = max(0, min(100, accuracy))

    return {
        'move_analysis': move_analysis,
        'mistakes': mistakes,
        'blunders': blunders,
        'accuracy': accuracy,
        'material_summary': material_summary
    }

def build_summary(moves: list[str], result: str = 'Unknown', end_reason: str = 'Unknown', fen_history: list[str] = None) -> dict:
    """
    Build a comprehensive summary of the game.
    """
    opening = detect_opening(moves) or 'Standard Game'
    
    summary = {
        "opening": opening,
        "result": result,
        "total_moves": (len(moves) + 1) // 2, # Total full moves
        "captures": count_captures(moves),
        "checks": count_checks(moves),
        "checkmates": count_checkmates(moves),
        "promotions": count_promotions(moves),
        "end_reason": end_reason
    }
    
    if fen_history:
        heuristics = classify_moves(moves, fen_history)
        summary.update(heuristics)
        
    return summary
