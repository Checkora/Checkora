import json
import os


class OpeningDetector:
    def __init__(self):
        base_dir = os.path.dirname(__file__)
        file_path = os.path.join(base_dir, "openings.json")

        with open(file_path, "r", encoding="utf-8") as f:
            self.openings = json.load(f)

    def detect(self, move_history):
        move_tokens = [move["notation"] for move in move_history]

        best_match = None
        best_length = 0

        for opening_moves, opening_name in self.openings.items():
            opening_tokens = opening_moves.split()

            if move_tokens[:len(opening_tokens)] != opening_tokens:
                continue

            length = len(opening_tokens)

            if length > best_length:
                best_length = length
                best_match = {
                    "name": opening_name,
                    "moves": opening_moves,
                }

        return best_match