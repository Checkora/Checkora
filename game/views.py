from django.shortcuts import render

# Create your views here.

def index(request):
    return render(request, 'game/board.html', {'range': range(8)})