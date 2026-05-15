"""Opening detection service for the Checkora chess platform.

Provides a thin, testable interface between the view layer and the
``Opening`` model.  The service is stateless — every call is a single
indexed DB lookup.
"""

from game.models import Opening


def detect_opening(fen: str) -> dict | None:
    """Look up the deepest matching opening for a FEN position.

    Args:
        fen: A 3-field FEN key (board / side / castling).

    Returns:
        A dict ``{"eco": "B20", "name": "Sicilian Defense", "moves": "..."}``
        or ``None`` when no matching opening exists.
    """
    if not fen or not isinstance(fen, str):
        return None

    fen = fen.strip()
    try:
        opening = Opening.objects.get(fen=fen)
    except Opening.DoesNotExist:
        return None

    return {
        'eco': opening.eco,
        'name': opening.name,
        'moves': opening.moves,
    }
