import json
import os
import subprocess
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie

@ensure_csrf_cookie
def index(request):
    return render(request, 'game/board.html')

def make_move(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            move = data.get('move')
            
            # Windows users ke liye '.exe' zaroori hai
            engine_path = os.path.join(settings.BASE_DIR, 'game', 'engine', 'main.exe')
            
            if not os.path.exists(engine_path):
                return JsonResponse({'status': 'error', 'message': 'Engine not found'})

            process = subprocess.Popen(
                [engine_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(input=move)
            
            print(f"♟️ C++ Says: {stdout.strip()}")
            
            if "VALID" in stdout:
                return JsonResponse({'status': 'success', 'move': move, 'engine_response': stdout.strip()})
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid Move'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'error'})