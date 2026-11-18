from django.test import TestCase, Client
from django.urls import reverse
from game.engine import ChessGame
from unittest.mock import patch

class Issue1630PredictionTest(TestCase):
    def setUp(self):
        self.client = Client()
        session = self.client.session
        self.game = ChessGame()
        # The engine plays White here, so it is its turn at the start.
        self.game.player_color = 'black'
        session['game'] = self.game.to_dict()
        session.save()

    @patch('game.engine.ChessGame.get_ai_move')
    def test_no_prediction_in_pvp_or_normal_ai_mode(self, mock_get_ai_move):
        for mode in ['ai', 'pvp']:
            self.game.mode = mode
            session = self.client.session
            session['game'] = self.game.to_dict()
            session.save()

            mock_get_ai_move.return_value = {'from_row': 6, 'from_col': 4, 'to_row': 4, 'to_col': 4, 'eval': 40, 'alts': []}
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

    @patch('game.engine.ChessGame.get_ai_move')
    def test_analysis_mode_is_not_served(self, mock_get_ai_move):
        # No view can start an "analysis" game, so ai_move does not take one.
        self.game.mode = 'analysis'
        session = self.client.session
        session['game'] = self.game.to_dict()
        session.save()

        response = self.client.post(reverse('ai_move'), content_type='application/json')

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
