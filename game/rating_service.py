def calculate_rating_change(result, player_rating, opponent_rating, k=32):
    """Compute Elo rating change."""
    if result not in ("win", "draw", "loss"):
        raise ValueError(
            f"Invalid result: {result}"
        )
    score = {"win": 1.0, "draw": 0.5, "loss": 0.0}[result]
    expected = 1 / (1 + 10 ** ((opponent_rating - player_rating) / 400))
    change = round(k * (score - expected))
    return change


