from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/move/', views.make_move, name='make_move'),
    path('api/valid-moves/', views.valid_moves, name='valid_moves'),
    path('api/new-game/', views.new_game, name='new_game'),
    path('api/state/', views.get_state, name='get_state'),
]