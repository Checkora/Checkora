from django.contrib import admin

from .models import GameResult, UserProfile


@admin.register(GameResult)
class GameResultAdmin(admin.ModelAdmin):
    list_display = ('mode', 'winner', 'end_reason', 'played_at')
    list_filter = ('mode', 'winner', 'end_reason')
    ordering = ('-played_at',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'avatar')
    search_fields = ('user__username', 'user__email')
