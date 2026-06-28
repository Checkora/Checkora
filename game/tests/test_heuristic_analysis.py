import json
from django.test import TestCase, Client
from django.urls import reverse
from game.analysis import compute_material, classify_moves, build_summary

class HeuristicAnalysisTest(TestCase):
    def test_compute_material(self):
        # Starting position
        fen_start = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        mat = compute_material(fen_start)
        self.assertEqual(mat['white'], 39)
        self.assertEqual(mat['black'], 39)

        # White loses a queen
        fen_no_q = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR b KQkq - 0 1"
        mat = compute_material(fen_no_q)
        self.assertEqual(mat['white'], 30)
        self.assertEqual(mat['black'], 39)

    def test_classify_moves_blunder(self):
        # E.g. White loses a queen without compensation
        moves = ["e4"]
        fen_history = [
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNB1KBNR w KQkq - 0 2" # Artificially removing white queen on move 2 for test
        ]
        
        heuristics = classify_moves(moves, fen_history)
        self.assertEqual(heuristics['blunders'], 1)
        self.assertEqual(heuristics['accuracy'], 95)
        self.assertEqual(heuristics['move_analysis'][0], 'Blunder Candidate')

    def test_classify_moves_mistake(self):
        # E.g. White loses a pawn
        moves = ["e4"]
        fen_history = [
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            "rnbqkbnr/pppppppp/8/8/8/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2" # Artificially removing white pawn
        ]
        
        heuristics = classify_moves(moves, fen_history)
        self.assertEqual(heuristics['mistakes'], 1)
        self.assertEqual(heuristics['accuracy'], 98)
        self.assertEqual(heuristics['move_analysis'][0], 'Mistake')

    def test_classify_moves_regained(self):
        # White loses a queen, but regains it immediately
        moves = ["e4", "e5"]
        fen_history = [
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", # Start
            "rnbqkbnr/pppppppp/8/8/8/8/PPPP1PPP/RNB1KBNR b KQkq - 0 1", # White loses queen
            "rnb1kbnr/pppppppp/8/8/8/8/PPPP1PPP/RNB1KBNR w KQkq - 0 2", # Black loses queen
            "rnb1kbnr/pppppppp/8/8/8/8/PPPP1PPP/RNB1KBNR b KQkq - 0 2"
        ]
        
        heuristics = classify_moves(moves, fen_history)
        self.assertEqual(heuristics['blunders'], 0) # Regained compensation
        self.assertEqual(heuristics['accuracy'], 100)

    def test_build_summary_with_heuristics(self):
        moves = ["e4"]
        fen_history = [
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        ]
        summary = build_summary(moves, fen_history=fen_history)
        self.assertIn("accuracy", summary)
        self.assertIn("blunders", summary)
        self.assertEqual(summary['total_moves'], 1)

    def test_api_backwards_compatibility(self):
        # Ensure API doesn't fail if fen_history is absent
        from django.contrib.auth.models import User
        user = User.objects.create_user(username='test_heuristics', password='password123')
        
        client = Client()
        client.force_login(user)
        response = client.post(
            reverse('analyze_game'),
            json.dumps({"moves": ["e4", "e5"]}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertIn("opening", response_data)
