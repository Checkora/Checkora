import time
from django.contrib.sessions.models import Session
from django.db import transaction
from django.contrib.auth import get_user_model
from game.models import GameResult

User = get_user_model()

def cleanup_stale_games():
    """
    Automated cleanup task for abandoned games.
    Iterates over all django_session records and applies rules to stale active games:
    Rule A (Low Engagement): < 5 moves -> hard deletion (remove game from session).
    Rule B (High Engagement): >= 5 moves -> auto-resign inactive player.
    """
    # 48 hours in seconds
    stale_threshold = time.time() - (48 * 3600)
    
    deleted_count = 0
    resigned_count = 0
    
    # Iterate over all sessions
    for session in Session.objects.all():
        try:
            session_data = session.get_decoded()
        except Exception:
            continue
            
        game_data = session_data.get('game')
        if not game_data or game_data.get('game_status') != 'active':
            continue
            
        last_ts = game_data.get('last_ts', 0)
        if last_ts > stale_threshold:
            continue
            
        moves_count = len(game_data.get('move_history', []))
        
        with transaction.atomic():
            if moves_count < 5:
                # Rule A: Hard deletion
                del session_data['game']
                session.session_data = Session.objects.encode(session_data)
                session.save()
                deleted_count += 1
            else:
                # Rule B: Auto-resignation
                current_turn = game_data.get('current_turn', 'white')
                player_color = game_data.get('player_color', 'white')
                mode = game_data.get('mode', 'pvp')
                
                # In AI mode, the human (player_color) is the inactive one
                # In PvP mode, the player whose turn it is is inactive
                if mode == 'ai':
                    winner = 'black' if player_color == 'white' else 'white'
                else:
                    winner = 'black' if current_turn == 'white' else 'white'
                
                game_data['game_status'] = 'resignation'
                session_data['game'] = game_data
                session.session_data = Session.objects.encode(session_data)
                session.save()
                
                # Create a GameResult historically linking to the user if auth is known
                user_id = session_data.get('_auth_user_id')
                user = User.objects.filter(pk=user_id).first() if user_id else None
                
                result = GameResult(
                    user=user,
                    mode=mode,
                    winner=winner,
                    end_reason='resign',
                    player_color=player_color
                )
                result.full_clean()
                result.save()
                
                resigned_count += 1
                
    return deleted_count, resigned_count
