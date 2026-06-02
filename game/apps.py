import os
import logging

from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_migrate

logger = logging.getLogger(__name__)


class GameConfig(AppConfig):
    name = 'game'

    def ready(self):
        if 'allauth.socialaccount' not in settings.INSTALLED_APPS:
            return

        post_migrate.connect(
            self._bootstrap_google_oauth,
            dispatch_uid='game_bootstrap_google_oauth',
        )

    def _bootstrap_google_oauth(self, sender, **kwargs):
        try:
            from django.contrib.sites.models import Site
            from allauth.socialaccount.models import SocialApp

            site, _ = Site.objects.get_or_create(
                id=settings.SITE_ID,
                defaults={
                    'domain': os.getenv('SITE_DOMAIN', 'localhost'),
                    'name': 'Checkora',
                }
            )

            client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
            secret = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')
            if not (client_id and secret):
                return

            app, created = SocialApp.objects.get_or_create(
                provider='google',
                name='Google',
                defaults={
                    'client_id': client_id,
                    'secret': secret,
                }
            )
            if not created and (
                app.client_id != client_id or app.secret != secret
            ):
                app.client_id = client_id
                app.secret = secret
                app.save()
            app.sites.add(site)
        except Exception as exc:
            logger.debug('Google OAuth bootstrap skipped: %s', exc)
