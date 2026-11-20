from django.conf import settings

from . import google_auth


def google_sign_in(request):
    # Forks and local setups without a Google client simply get no button.
    return {'google_login_enabled': google_auth.is_configured()}


def canonical_url(request):
    # Without the query string, so ?page=2 and the like don't count as pages of their own.
    return {'canonical_url': settings.SITE_URL + request.path}
