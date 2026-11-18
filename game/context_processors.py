from . import google_auth


def google_sign_in(request):
    # Forks and local setups without a Google client simply get no button.
    return {'google_login_enabled': google_auth.is_configured()}
