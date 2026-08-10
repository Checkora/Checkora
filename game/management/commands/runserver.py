"""Local runserver with an explicit HTTP-only reminder for newcomers."""
import os
import sys
from datetime import datetime

from django.conf import settings
from django.core.management.commands.runserver import Command as RunserverCommand
from django.utils.version import get_docs_version


class Command(RunserverCommand):
    help = (
        'Starts a lightweight web server for development and reminds '
        'contributors to open the site over HTTP.'
    )

    def _display_host(self):
        if self._raw_ipv6:
            return f'[{self.addr}]'
        if self.addr == '0':
            return '127.0.0.1'
        return self.addr

    def on_bind(self, server_port):
        host = self._display_host()
        quit_command = 'CTRL-BREAK' if sys.platform == 'win32' else 'CONTROL-C'
        now = datetime.now().strftime('%B %d, %Y - %X')
        version = self.get_version()
        local_url = f'http://{host}:{server_port}/'

        self.stdout.write(
            f'{now}\n'
            f'Django version {version}, using settings {settings.SETTINGS_MODULE!r}\n'
            f'Starting development server at {local_url}\n'
            f'Quit the server with {quit_command}.'
        )
        docs_version = get_docs_version()
        if os.environ.get('DJANGO_RUNSERVER_HIDE_WARNING') != 'true':
            self.stdout.write(
                self.style.WARNING(
                    'WARNING: This is a development server. Do not use it in a '
                    'production setting. Use a production WSGI or ASGI server '
                    'instead.\nFor more information on production servers see: '
                    f'https://docs.djangoproject.com/en/{docs_version}/howto/'
                    'deployment/'
                )
            )
        self.stdout.write(
            self.style.WARNING(
                f'\nOpen this URL in your browser (HTTP only, not HTTPS):\n'
                f'  {local_url}\n'
                f'If the browser upgrades to https://, disable secure-connection '
                f'settings or clear cached HSTS for {host} '
                f'(Chrome/Brave: chrome://net-internals/#hsts).\n'
            )
        )
