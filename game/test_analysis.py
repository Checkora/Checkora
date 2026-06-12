import json
from django.test import TestCase, override_settings
from game.analysis import (
    detect_opening,
    count_captures,
    count_checks,
    count_checkmates,
    count_promotions,
    build_summary
)

@override_settings(SECURE_SSL_REDIRECT=False)
class AnalysisTest(TestCase):
    def test_detect_opening(self):
        self.assertEqual(detect_opening(['e4', 'e5', 'Nf3', 'Nc6', 'Bc4']), 'Italian Game')
        self.assertEqual(detect_opening(['e4', 'c5']), 'Sicilian Defense')
        self.assertEqual(detect_opening(['d4', 'd5', 'c4']), "Queen's Gambit")
        self.assertIsNone(detect_opening(['a3', 'a6']))
        self.assertIsNone(detect_opening([]))
        self.assertEqual(detect_opening(['e4', 'e5', 'Nf3']), "King's Pawn Game")
        self.assertEqual(detect_opening(['d4', 'Nf6', 'c4', 'e6']), 'Nimzo-Indian Defense')
        self.assertEqual(detect_opening(['d4', 'Nf6', 'c4', 'd5']), 'Indian Defense')
        self.assertEqual(detect_opening(['f4', 'd5']), "Bird's Opening")

    def test_count_captures(self):
        self.assertEqual(count_captures(['e4', 'e5', 'exd5']), 1)
        self.assertEqual(count_captures(['Nxe4', 'Qxd4']), 2)
        self.assertEqual(count_captures(['e4', 'e5']), 0)

    def test_count_checks(self):
        self.assertEqual(count_checks(['e4', 'e5', 'Bb5+']), 1)
        self.assertEqual(count_checks(['e4', 'e5']), 0)

    def test_count_checkmates(self):
        self.assertEqual(count_checkmates(['e4', 'e5', 'Qh5#']), 1)
        self.assertEqual(count_checkmates(['e4', 'e5']), 0)

    def test_count_promotions(self):
        self.assertEqual(count_promotions(['e8=Q', 'd1=N']), 2)
        self.assertEqual(count_promotions(['e4', 'e5']), 0)

    def test_build_summary(self):
        moves = ['e4', 'e5', 'Nf3', 'Nc6', 'Bc4', 'exd4', 'Bb5+']
        summary = build_summary(moves, 'Win', 'Checkmate')
        self.assertEqual(summary['opening'], 'Italian Game')
        self.assertEqual(summary['result'], 'Win')
        self.assertEqual(summary['total_moves'], 4) # 7 moves -> 4 total full moves
        self.assertEqual(summary['captures'], 1)
        self.assertEqual(summary['checks'], 1)
        self.assertEqual(summary['checkmates'], 0)
        self.assertEqual(summary['promotions'], 0)
        self.assertEqual(summary['end_reason'], 'Checkmate')

    def test_api_endpoint(self):
        payload = {
            "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4"],
            "result": "Win",
            "reason": "Checkmate"
        }
        response = self.client.post(
            '/api/analyze-game/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['opening'], 'Italian Game')
        self.assertEqual(data['result'], 'Win')
        self.assertEqual(data['total_moves'], 3)
        self.assertEqual(data['captures'], 0)
        self.assertEqual(data['checks'], 0)
        self.assertEqual(data['checkmates'], 0)
        self.assertEqual(data['promotions'], 0)
        self.assertEqual(data['end_reason'], 'Checkmate')

