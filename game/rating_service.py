def calculate_rating_change(result, player_rating, opponent_rating, k=32, games_played=None):
    """Compute Elo rating change with optional provisional K-factor."""
    if result not in ("win", "draw", "loss"):
        raise ValueError(
            f"Invalid result: {result}"
        )
    
    # If games_played is provided, apply dynamic K-factor:
    # 32 for provisional ratings (under 30 games) to keep it responsive for new players,
    # 16 for established ratings (30+ games) to keep it stable.
    if games_played is not None:
        k = 32 if games_played < 30 else 16
        
    score = {"win": 1.0, "draw": 0.5, "loss": 0.0}[result]
    expected = 1 / (1 + 10 ** ((opponent_rating - player_rating) / 400))
    change = round(k * (score - expected))
    return change


