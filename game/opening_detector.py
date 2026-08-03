import json
import os


class OpeningDetector:
    def __init__(self):
        base_dir = os.path.dirname(__file__)
        file_path = os.path.join(base_dir, "openings.json")

        with open(file_path, "r", encoding="utf-8") as f:
            self.openings = json.load(f)

    def detect(self, move_history):
        moves = []

        for move in move_history:
            moves.append(move["notation"])
        sequence = " ".join(moves)

        best_match = None
        best_length = 0

        for opening_moves, opening_name in self.openings.items():

            if sequence.startswith(opening_moves):

                length = len(opening_moves.split())

                if length > best_length:
                    best_length = length
                    best_match = {
                        "name": opening_name,
                        "moves": opening_moves
                    }

        return best_match