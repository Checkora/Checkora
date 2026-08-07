from .models import UserProgress
from django.db.models import F

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

    # Use F() expressions for an atomic increment to avoid lost updates
    # when concurrent requests award XP to the same user.
    UserProgress.objects.get_or_create(user=user)
    UserProgress.objects.filter(user=user).update(
        xp=F("xp") + amount,
    )

    # Re-fetch to compute level from the now-updated xp value.
    progress = UserProgress.objects.get(user=user)
    new_level = calculate_level(progress.xp)
    if new_level != progress.level:
        progress.level = new_level
        progress.save(update_fields=["level"])

    return progress
