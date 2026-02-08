import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie

@ensure_csrf_cookie
def index(request):
    return render(request, 'game/board.html')

def make_move(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        move = data.get('move')
        
        print(f"🔥 Move Received: {move}")
        
        return JsonResponse({'status': 'success', 'move': move})
    
    return JsonResponse({'status': 'error'})