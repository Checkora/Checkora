from django.core.management.base import BaseCommand
from game.models import Achievement

class Command(BaseCommand):
    help = 'Seed achievements for the platform'

    def handle(self, *args, **options):
        achievements = [
            {'name': 'First Steps', 'description': 'Play your first game', 'icon_name': 'footprints'},
            {'name': 'Winner', 'description': 'Win your first game', 'icon_name': 'trophy'},
            {'name': 'Veteran', 'description': 'Play 50 games', 'icon_name': 'award'},
            {'name': 'Centurion', 'description': 'Play 100 games', 'icon_name': 'shield-check'},
            {'name': 'Master', 'description': 'Reach 1500 rating', 'icon_name': 'crown'},
        ]
        
        for ach_data in achievements:
            ach, created = Achievement.objects.get_or_create(
                name=ach_data['name'],
                defaults={'description': ach_data['description'], 'icon_name': ach_data['icon_name']}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created achievement: {ach.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Achievement already exists: {ach.name}'))
