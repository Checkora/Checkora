from django.contrib import admin
from .models import ChessPuzzle


@admin.register(ChessPuzzle)
class ChessPuzzleAdmin(admin.ModelAdmin):
    list_display = ('title', 'difficulty', 'date')
    search_fields = ('title', 'fen')
    list_filter = ('difficulty', 'date')
