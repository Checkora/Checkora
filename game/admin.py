from django.contrib import admin
from .models import (
    ChessPuzzle,
    UserProfile,
    GameResult,
    PlayerRating,
    RatingHistory,
    ActiveGame,
    Discussion,
    Reply,
    Achievement,
    UserAchievement,
    FeaturedBadge,
)
from django.contrib.auth.models import User
from django.db import DatabaseError
from .health_checks import (
    check_database,
    check_puzzles,
    check_achievements,
    check_lessons,
    check_openings,
)

@admin.register(ChessPuzzle)
class ChessPuzzleAdmin(admin.ModelAdmin):
    list_display = ('title', 'difficulty', 'date')
    search_fields = ('title', 'fen')
    list_filter = ('difficulty', 'date')
    

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'has_avatar')
    search_fields = ('user__username', 'user__email')

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('user',)
        return ()

    @admin.display(boolean=True, description='Has Avatar')
    def has_avatar(self, obj):
        return bool(obj.avatar)


@admin.register(GameResult)
class GameResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'mode', 'player_color', 'winner', 'end_reason', 'played_at')
    list_filter = ('mode', 'winner', 'end_reason', 'player_color', 'played_at')
    search_fields = ('user__username', 'user__email', 'end_reason')
    raw_id_fields = ('user', 'replay_record')


@admin.register(PlayerRating)
class PlayerRatingAdmin(admin.ModelAdmin):
    list_display = ('user', 'rating', 'games_played', 'wins', 'losses', 'draws', 'updated_at')
    list_filter = ('updated_at',)
    search_fields = ('user__username', 'user__email')
    raw_id_fields = ('user',)


@admin.register(RatingHistory)
class RatingHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'old_rating', 'new_rating', 'rating_change', 'result', 'created_at')
    list_filter = ('result', 'created_at')
    search_fields = ('user__username', 'user__email')
    raw_id_fields = ('user',)


@admin.register(ActiveGame)
class ActiveGameAdmin(admin.ModelAdmin):
    list_display = ('session_key', 'user', 'status', 'version', 'last_activity_at', 'created_at')
    list_filter = ('status', 'created_at', 'last_activity_at')
    search_fields = ('session_key', 'user__username', 'user__email')
    raw_id_fields = ('user',)


@admin.register(Discussion)
class DiscussionAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'category', 'created_at', 'updated_at')
    list_filter = ('category', 'created_at', 'updated_at')
    search_fields = ('title', 'content', 'user__username', 'user__email')
    raw_id_fields = ('user',)


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ('id', 'discussion', 'user', 'is_edited', 'is_deleted', 'created_at')
    list_filter = ('is_edited', 'is_deleted', 'created_at')
    search_fields = ('content', 'user__username', 'discussion__title')
    raw_id_fields = ('discussion', 'user', 'reply_to')


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'category', 'rarity', 'icon')
    list_filter = ('category', 'rarity')
    search_fields = ('code', 'title', 'description')


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ('user', 'achievement', 'unlocked_at')
    list_filter = ('unlocked_at', 'achievement__category', 'achievement__rarity')
    search_fields = ('user__username', 'user__email', 'achievement__title', 'achievement__code')
    raw_id_fields = ('user', 'achievement')


@admin.register(FeaturedBadge)
class FeaturedBadgeAdmin(admin.ModelAdmin):
    list_display = ('user', 'achievement')
    list_filter = ('achievement__category', 'achievement__rarity')
    search_fields = ('user__username', 'user__email', 'achievement__title', 'achievement__code')
    raw_id_fields = ('user', 'achievement')


original_each_context = admin.site.each_context

def custom_each_context(request):
    context = original_each_context(request)
    is_admin_index = (
        getattr(request, "resolver_match", None)
        and request.resolver_match.view_name == "admin:index"
    )
    if not is_admin_index:
        return context

    context["health_status"] = {
        "Database": check_database(),
        "Puzzle System": check_puzzles(),
        "Achievement System": check_achievements(),
        "Lesson System": check_lessons(),
        "Opening Trainer": check_openings(),
    }

    context["stats"] = {
        "users": 0,
        "puzzles": 0,
    }

    try:
        context["stats"] = {
            "users": User.objects.count(),
            "puzzles": ChessPuzzle.objects.count(),
        }
    except DatabaseError:
        context["stats"] = {"users": None, "puzzles": None}

    return context


admin.site.each_context = custom_each_context
