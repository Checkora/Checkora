from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/move/', views.make_move, name='make_move'),
    path('api/valid-moves/', views.valid_moves, name='valid_moves'),
    path('api/new-game/', views.new_game, name='new_game'),
    path('api/check-promotion/', views.check_promotion, name='check_promotion'),
    path('api/state/', views.get_state, name='get_state'),
    path('api/pause/', views.set_pause),
    path('api/resign/', views.resign_game, name='resign_game'),
    path('api/ai-move/', views.ai_move, name='ai_move'),
    path('api/draw/', views.offer_draw, name='offer_draw'),
]