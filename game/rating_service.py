def calculate_rating_change(result):
    if result == "win":
        return 20

    if result == "draw":
        return 5

    if result == "loss":
        return -10

    raise ValueError(
        f"Invalid result: {result}"
    )

