"""Management command to import ECO opening data into the database.

Usage:
    python manage.py import_openings               # use bundled TSV
    python manage.py import_openings --file eco.tsv # custom file
    python manage.py import_openings --clear        # wipe before import
"""

import csv
import os

import chess

from django.core.management.base import BaseCommand, CommandError
from game.models import Opening


# Default bundled data file
DEFAULT_TSV = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    os.pardir, os.pardir, 'data', 'eco_openings.tsv',
)


def _fen_key(board: chess.Board) -> str:
    """Build a 3-field FEN key matching ChessGame.generate_fen_key().

    Format: ``<placement> <side> <castling>``
    """
    parts = board.fen().split()
    castling = parts[2] if len(parts) > 2 else '-'
    return f"{parts[0]} {parts[1]} {castling}"


def _pgn_at_ply(moves_san: list[str], ply: int) -> str:
    """Build a PGN string up to the given half-move index."""
    parts = []
    for i in range(ply + 1):
        if i % 2 == 0:
            parts.append(f"{i // 2 + 1}.")
        parts.append(moves_san[i])
    return ' '.join(parts)


class Command(BaseCommand):
    help = 'Import ECO chess openings from a TSV file into the database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file', type=str, default=DEFAULT_TSV,
            help='Path to TSV file (eco, name, moves columns).',
        )
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete all existing Opening rows before importing.',
        )

    def handle(self, *args, **options):
        tsv_path = os.path.normpath(options['file'])
        if not os.path.isfile(tsv_path):
            raise CommandError(f'File not found: {tsv_path}')

        if options['clear']:
            deleted, _ = Opening.objects.all().delete()
            self.stdout.write(f'Cleared {deleted} existing opening(s).')

        created = 0
        skipped = 0
        errors = 0

        with open(tsv_path, encoding='utf-8') as fh:
            reader = csv.DictReader(fh, delimiter='\t')
            for row_num, row in enumerate(reader, start=2):
                eco = row.get('eco', '').strip()
                name = row.get('name', '').strip()
                moves_raw = row.get('moves', '').strip()

                if not eco or not name or not moves_raw:
                    self.stderr.write(f'Row {row_num}: skipping (missing field)')
                    skipped += 1
                    continue

                try:
                    board = chess.Board()
                    # Strip move numbers: "1. e4 e5 2. Nf3" → ["e4","e5","Nf3"]
                    tokens = moves_raw.split()
                    san_moves = [t for t in tokens if not t.endswith('.')]

                    for i, san in enumerate(san_moves):
                        board.push_san(san)
                        fen = _fen_key(board)
                        pgn = _pgn_at_ply(san_moves, i)
                        half_moves = i + 1

                        try:
                            existing = Opening.objects.get(fen=fen)
                            # Only overwrite if this line reaches the
                            # position at a strictly deeper depth
                            # (= more specific opening name).
                            if half_moves > existing.move_count:
                                existing.eco = eco
                                existing.name = name
                                existing.moves = pgn
                                existing.move_count = half_moves
                                existing.save()
                        except Opening.DoesNotExist:
                            Opening.objects.create(
                                fen=fen, eco=eco, name=name,
                                moves=pgn, move_count=half_moves,
                            )
                            created += 1

                except Exception as exc:
                    self.stderr.write(f'Row {row_num} ({eco}): {exc}')
                    errors += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done. Created={created}  Skipped={skipped}  Errors={errors}'
        ))
