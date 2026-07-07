import json
from django.test import TestCase, Client
from django.urls import reverse
from game.engine import ChessGame
from unittest.mock import patch
from django.contrib.sessions.middleware import SessionMiddleware

class Issue1630PredictionTest(TestCase):
    def setUp(self):
        self.client = Client()
        session = self.client.session
        self.game = ChessGame()
        self.game.mode = 'analysis'
        session['game'] = self.game.to_dict()
        session.save()

    @patch('game.engine.ChessGame.get_ai_move')
    def test_prediction_data_generated_in_analysis_mode(self, mock_get_ai_move):
        # mock_get_ai_move is called twice:
        # 1. By the main game instance to get the best move
        # 2. By the temp_game instance to predict opponent responses
        mock_get_ai_move.side_effect = [
            {'from_row': 6, 'from_col': 4, 'to_row': 4, 'to_col': 4, 'eval': 40, 'alts': []},
            {'from_row': 1, 'from_col': 4, 'to_row': 3, 'to_col': 4, 'eval': -30, 'alts': [
                {'from_row': 1, 'from_col': 2, 'to_row': 3, 'to_col': 2, 'eval': -40},
                {'from_row': 1, 'from_col': 3, 'to_row': 3, 'to_col': 3, 'eval': -50},
                {'from_row': 0, 'from_col': 6, 'to_row': 2, 'to_col': 5, 'eval': -60},
                {'from_row': 0, 'from_col': 1, 'to_row': 2, 'to_col': 2, 'eval': -70}
            ]}
        ]
        
        response = self.client.post(reverse('ai_move'), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data['valid'], True, data)
        ai_move = data['ai_move']
        self.assertIn('predicted_responses', ai_move)
        preds = ai_move['predicted_responses']
        
        # Verify it has at least one response and is limited to 3
        self.assertTrue(len(preds) > 0)
        self.assertEqual(len(preds), 3)
        self.assertEqual(preds[0]['eval'], -30)
        self.assertEqual(preds[1]['eval'], -40)
        self.assertEqual(preds[2]['eval'], -50)

    @patch('game.engine.ChessGame.get_ai_move')
    def test_no_prediction_in_pvp_or_normal_ai_mode(self, mock_get_ai_move):
        for mode in ['ai', 'pvp']:
            self.game.mode = mode
            session = self.client.session
            session['game'] = self.game.to_dict()
            session.save()

            mock_get_ai_move.return_value = {'from_row': 1, 'from_col': 4, 'to_row': 3, 'to_col': 4, 'eval': 40, 'alts': []}
            mock_get_ai_move.reset_mock()

            response = self.client.post(reverse('ai_move'), content_type='application/json')

            if mode == 'ai':
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertNotIn('predicted_responses', data.get('ai_move', {}))
                self.assertEqual(mock_get_ai_move.call_count, 1)
            else:
                self.assertEqual(response.status_code, 400)
                self.assertEqual(mock_get_ai_move.call_count, 0)

class Issue1630EngineParserTest(TestCase):
    @patch('game.engine.ChessGame._call_engine')
    def test_bestmove_parsing_backward_compatibility(self, mock_call):
        mock_call.return_value = "BESTMOVE 1 4 3 4\n"
        game = ChessGame()
        result = game.get_ai_move()
        self.assertEqual(result['from_row'], 1)
        self.assertEqual(result['to_row'], 3)
        self.assertIsNone(result.get('eval'))
        self.assertEqual(result.get('alts'), [])

    @patch('game.engine.ChessGame._call_engine')
    def test_eval_and_alts_parsing(self, mock_call):
        mock_call.return_value = "BESTMOVE 1 4 3 4 EVAL 45 ALTS 1 3 3 3 20 6 2 4 2 -10\n"
        game = ChessGame()
        result = game.get_ai_move()
        self.assertEqual(result['from_row'], 1)
        self.assertEqual(result['eval'], 45)
        self.assertEqual(len(result['alts']), 2)
        self.assertEqual(result['alts'][0]['from_row'], 1)
        self.assertEqual(result['alts'][0]['eval'], 20)
        self.assertEqual(result['alts'][1]['from_row'], 6)
        self.assertEqual(result['alts'][1]['eval'], -10)
