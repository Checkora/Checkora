"""Management command to clean up unverified/inactive user accounts."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Clean up unverified (inactive) user accounts older than a specified retention window.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--retention-hours',
            type=float,
            default=24.0,
            help='Retention period in hours (default: 24.0 hours).'
        )

    def handle(self, *args, **options):
        retention_hours = options['retention_hours']
        threshold = timezone.now() - timedelta(hours=retention_hours)
        User = get_user_model()
        
        # Query inactive users created before the threshold
        inactive_users = User.objects.filter(is_active=False, date_joined__lt=threshold)
        count = inactive_users.count()
        
        if count > 0:
            self.stdout.write(self.style.WARNING(f"Found {count} inactive users older than {retention_hours} hours. Deleting..."))
            inactive_users.delete()
            self.stdout.write(self.style.SUCCESS(f"Successfully deleted {count} inactive user(s)."))
        else:
            self.stdout.write(self.style.SUCCESS("No inactive users found exceeding the retention window."))
