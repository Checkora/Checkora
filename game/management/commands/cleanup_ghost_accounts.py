"""Purge inactive user accounts from abandoned OTP registration sessions.

Users who begin registration but never complete OTP verification leave
behind ``is_active=False`` records that permanently lock their username
due to Django's unique constraint.  This command deletes those *ghost*
accounts once they exceed a configurable age threshold (default: 24 h).

Usage
-----
::

    # Preview which accounts would be deleted
    python manage.py cleanup_ghost_accounts --dry-run

    # Delete ghost accounts older than 24 hours (default)
    python manage.py cleanup_ghost_accounts

    # Custom threshold in hours
    python manage.py cleanup_ghost_accounts --hours 48
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    """Delete inactive user accounts from abandoned registrations."""

    help = (
        'Delete inactive (is_active=False) user accounts that were '
        'created more than --hours ago and never verified their OTP.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Delete ghost accounts older than this many hours '
                 '(default: 24).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without making changes.',
        )

    def handle(self, *args, **options):
        hours = options['hours']
        dry_run = options['dry_run']
        cutoff = timezone.now() - timedelta(hours=hours)

        ghosts = User.objects.filter(
            is_active=False,
            date_joined__lt=cutoff,
        )
        count = ghosts.count()

        if dry_run:
            self.stdout.write(
                f'[DRY RUN] Would delete {count} ghost account(s) '
                f'older than {hours}h.'
            )
            for user in ghosts[:20]:
                self.stdout.write(
                    f'  - {user.username} ({user.email}) '
                    f'joined {user.date_joined}'
                )
            return

        deleted, _ = ghosts.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f'Deleted {deleted} ghost account(s) older than {hours}h.'
            )
        )
