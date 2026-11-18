"""Template tags for showing a player: their picture and their rank badge.

    {% load players %}
    {% avatar some_user "avatar--soft" %}
    {% rank_badge rating games_played %}
"""

from django import template
from django.contrib.auth.models import User
from django.templatetags.static import static

from game import progression
from game.models import UserProfile

register = template.Library()


def _profile(user):
    """The user's profile without the picture data, which can be large."""
    if User.profile.is_cached(user):
        return getattr(user, 'profile', None)
    return UserProfile.objects.defer('avatar').filter(user_id=user.pk).first()


@register.inclusion_tag('game/includes/avatar.html')
def avatar(user, classes=''):
    """The player's picture, or the first letter of their name.

    Lists should load users with select_related('profile') and
    .defer('profile__avatar'); otherwise this fetches the profile without
    the picture data.
    """
    profile = _profile(user) if user.pk else None
    preset = profile.avatar_preset if profile else ''
    return {
        'url': profile.avatar_url if profile else '',
        # The first letter says which colour the piece is, for the background.
        'preset_side': preset[:1],
        'initial': user.username[:1],
        'classes': classes,
    }


@register.inclusion_tag('game/includes/rank_badge.html')
def rank_badge(rating, games_played=None):
    rank = progression.rank_for(rating)
    return {
        'rank': rank,
        'icon': static(f'game/pieces/staunton-single/w{rank.piece}.webp'),
        'provisional': games_played is not None and progression.is_provisional(games_played),
        'provisional_games': progression.PROVISIONAL_GAMES,
    }
