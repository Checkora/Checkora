from django.urls import path
from . import views

urlpatterns = [
    path('', views.preloader, name='preloader'),
    path('home/', views.landing, name='landing'),
    path('play/', views.index, name='index'),
    
    # Game API Endpoints
    path('api/move/', views.make_move, name='make_move'),
    path('api/valid-moves/', views.valid_moves, name='valid_moves'),
    path('api/new-game/', views.new_game, name='new_game'),
    path('api/resume/', views.resume_game, name='resume_game'),
    path('api/check-promotion/', views.check_promotion, name='check_promotion'),
    path('api/state/', views.get_state, name='get_state'),
    path('api/pause/', views.set_pause),
    path('api/resign/', views.resign_game, name='resign_game'),
    path('api/ai-move/', views.ai_move, name='ai_move'),
    path('api/draw/', views.offer_draw, name='offer_draw'),
    path('stats/', views.stats_view, name='stats'),
    path('api/analyze-game/', views.analyze_game_view, name='analyze_game'),
    path('api/cron/cleanup-stale-games/', views.cleanup_cron, name='cleanup_cron'),

    # Authentication
    path('api/check-username/', views.check_username, name='check_username'),
    path('register/', views.register_view, name='register'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    path('login/', views.login_view, name='login'),
    path('rules/', views.rules, name='rules'),
    path('logout/', views.logout_view, name='logout'),
    
    # Account Settings & Recovery
    path('delete-account/', views.delete_account, name='delete_account'),
    path('confirm-delete/<uidb64>/<token>/', views.confirm_delete_account, name='confirm_delete_account'),
    path(
        'password-reset-account-selection/',
        views.password_reset_account_selection,
        name='password_reset_account_selection'
    ),
    
    # Features & Progressions
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    path("lessons/", views.lesson_map_view, name="lessons"),
    path('lessons/<str:lesson_name>/', views.lesson_detail_view, name='lesson_detail'),
    path('lessons/<str:lesson_name>/complete/', views.complete_lesson, name='complete_lesson'),
    
    # Opening Trainer
    path("openings/", views.opening_trainer, name="opening_trainer"),
    path("openings/<slug:slug>/", views.opening_detail, name="opening_detail"),

    path("api/puzzle-stats/", views.puzzle_stats_view, name="puzzle_stats"),
    path("api/puzzles/daily/", views.get_daily_puzzle, name="daily_puzzle"),
    
    # Badges & Achievements
    path("achievements/", views.achievements_view, name="achievements"),
    path("achievement/<int:achievement_id>/download/", views.download_badge, name="download_badge",),
    path("feature-badge/<int:achievement_id>/", views.feature_badge, name="feature_badge"),
    path("remove-featured-badge/<int:badge_id>/", views.remove_featured_badge, name="remove_featured_badge"),

    # Community Forum
    path("forum/", views.forum_list, name="forum"),
    path("forum/new/", views.forum_new, name="forum_new"),
    path("forum/<int:discussion_id>/", views.forum_detail, name="forum_detail"),
    path("forum/<int:discussion_id>/reply/", views.forum_reply, name="forum_reply"),

    # Reply actions
    path(
        "forum/reply/<int:reply_id>/edit/",
        views.forum_reply_edit,
        name="forum_reply_edit",
    ),

    path(
        "forum/reply/<int:reply_id>/delete/",
        views.forum_reply_delete,
        name="forum_reply_delete",
    ),
]