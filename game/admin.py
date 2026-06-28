from django.contrib import admin
from .models import ChessPuzzle, UserProfile
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
