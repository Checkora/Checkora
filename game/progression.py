from .models import UserProgress

LEVEL_THRESHOLDS = {
    1: 0,
    2: 100,
    3: 250,
    4: 500,
    5: 1000,
    6: 1500,
    7: 2200,
    8: 3000,
}


def calculate_level(xp: int) -> int:
    if xp < 0:
        raise ValueError(
            f"xp must be non-negative, got {xp}"
        )
        
    level = 1

    for lvl, threshold in LEVEL_THRESHOLDS.items():
        if xp >= threshold:
            level = lvl

    return level


def award_xp(user, amount: int) -> UserProgress:
    if amount <= 0:
        raise ValueError(
            f"amount must be positive, got {amount}"
        )
        
    progress, _ = UserProgress.objects.get_or_create(
        user=user
    )

    progress.xp += amount
    progress.level = calculate_level(
        progress.xp
    )
    
    progress.save()

    return progress
