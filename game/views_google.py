"""Views for "Continue with Google".

A Google account that is already linked signs straight in. A verified Google
address that matches one Checkora account gets linked to it. Anyone else is a
new player: the Google identity waits in the session and no account exists
until they pick a username. A signed-in player can also link Google from the
settings page.
"""

import logging
import secrets
import time

from django.contrib import messages
from django.contrib.auth import login
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from . import accounts, google_auth
from .forms import UsernameForm
from .models import GoogleAccount
from .views import _login_destination, send_welcome_email

logger = logging.getLogger(__name__)

MODEL_BACKEND = 'django.contrib.auth.backends.ModelBackend'

# A Google identity waiting for its username is kept this long.
GOOGLE_SIGNUP_MAX_AGE_SECONDS = 900

UNAVAILABLE = 'Google sign-in is not available right now.'
FAILED = 'Google sign-in did not work. Please try again.'
EXPIRED = 'That Google sign-in took too long. Please start again.'
DEACTIVATED = 'This account has been deactivated.'


def _redirect_uri(request):
    return request.build_absolute_uri(reverse('google_callback'))


def _give_up(request, message, to='login'):
    messages.error(request, message)
    return redirect(to)


def _sign_in(request, user, destination, greeting):
    login(request, user, backend=MODEL_BACKEND)
    request.session.cycle_key()  # Prevent session fixation
    messages.success(request, greeting)
    return redirect(destination)


@require_GET
def google_login(request):
    linking = request.user.is_authenticated
    if linking and not request.GET.get('link'):
        return redirect('landing')
    if not google_auth.is_configured():
        return _give_up(request, UNAVAILABLE, to='account_settings' if linking else 'login')

    attempt = google_auth.new_attempt()
    request.session['google_oauth'] = {
        **attempt,
        'next': _login_destination(request),
        # Linking is tied to the account that asked for it.
        'link_user_id': request.user.pk if linking else None,
    }
    return redirect(google_auth.authorization_url(_redirect_uri(request), attempt))


def _identity_from_callback(request, attempt):
    """Check Google's answer and return the identity, or None after a message."""
    if not secrets.compare_digest(
        request.GET.get('state', '').encode(), attempt['state'].encode()
    ):
        messages.error(request, EXPIRED)
        return None
    code = request.GET.get('code')
    if request.GET.get('error') or not code:
        # The player closed Google's window or said no.
        messages.error(request, 'Google sign-in was cancelled.')
        return None
    try:
        id_token = google_auth.exchange_code(code, _redirect_uri(request), attempt['verifier'])
        return google_auth.read_id_token(id_token, attempt['nonce'])
    except google_auth.GoogleAuthError as exc:
        logger.warning('Google sign-in failed: %s', exc)
        messages.error(request, FAILED)
        return None


@require_GET
def google_callback(request):
    # Each attempt is used once, whatever happens next.
    attempt = request.session.pop('google_oauth', None)
    linking = bool(attempt and attempt.get('link_user_id'))

    if linking and attempt['link_user_id'] != request.user.pk:
        # Signed out, or someone else signed in, since the link was started.
        return _give_up(request, EXPIRED)
    if request.user.is_authenticated and not linking:
        return redirect('landing')
    if not attempt or not google_auth.is_configured():
        return _give_up(request, EXPIRED)

    identity = _identity_from_callback(request, attempt)
    if identity is None:
        return redirect('account_settings' if linking else 'login')
    if linking:
        return _link_signed_in_player(request, identity)
    return _sign_in_or_start_signup(request, identity, attempt['next'])


def _link(user, identity):
    """Link a Google identity to an account. Returns an error message or None."""
    if GoogleAccount.objects.filter(user=user).exists():
        return ('This account is linked to another Google account. '
                'Sign in with that one, or with your username and password.')
    try:
        with transaction.atomic():
            GoogleAccount.objects.create(user=user, sub=identity['sub'], email=identity['email'])
    except IntegrityError:
        return 'That Google account is already linked to another Checkora account.'
    return None


def _link_signed_in_player(request, identity):
    existing = GoogleAccount.objects.filter(sub=identity['sub']).first()
    if existing and existing.user_id == request.user.pk:
        messages.info(request, 'That Google account is already linked.')
        return redirect('account_settings')
    if existing:
        return _give_up(request, 'That Google account is already linked to another Checkora account.',
                        to='account_settings')
    error = _link(request.user, identity)
    if error:
        return _give_up(request, error, to='account_settings')
    messages.success(request, f"Google account {identity['email']} is now linked.")
    return redirect('account_settings')


def _sign_in_or_start_signup(request, identity, destination):
    linked = GoogleAccount.objects.select_related('user').filter(sub=identity['sub']).first()
    if linked:
        if not linked.user.is_active:
            return _give_up(request, DEACTIVATED)
        return _sign_in(request, linked.user, destination, f'Welcome back, {linked.user.username}!')

    # Signups that never verified their email don't count: their owner has
    # not proved the address, and Google just has.
    existing = accounts.accounts_with_email(identity['email'])
    if len(existing) > 1:
        return _give_up(request, 'More than one account uses this email. '
                                 'Sign in with your username and password instead.')
    if existing:
        user = existing[0]
        if not user.is_active:
            return _give_up(request, DEACTIVATED)
        error = _link(user, identity)
        if error:
            return _give_up(request, error)
        return _sign_in(request, user, destination,
                        f'Welcome back, {user.username}! Your Google account is now linked.')

    request.session['google_signup'] = {
        'sub': identity['sub'],
        'email': identity['email'],
        'started_at': time.time(),
        'next': destination,
    }
    return redirect('google_username')


def _waiting_signup(request):
    pending = request.session.get('google_signup')
    if not pending:
        return None
    if time.time() - pending.get('started_at', 0) > GOOGLE_SIGNUP_MAX_AGE_SECONDS:
        request.session.pop('google_signup', None)
        return None
    return pending


@require_http_methods(['GET', 'POST'])
def google_username(request):
    if request.user.is_authenticated:
        return redirect('landing')

    pending = _waiting_signup(request)
    if not pending:
        return _give_up(request, EXPIRED)

    form = UsernameForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username']
        try:
            user = accounts.create_google_user(username, sub=pending['sub'], email=pending['email'])
        except accounts.UsernameTaken:
            form.add_error('username', 'That username is taken. Try another one.')
        except IntegrityError:
            # Two tabs finishing at once, or a name taken a moment ago.
            linked = GoogleAccount.objects.select_related('user').filter(sub=pending['sub']).first()
            if linked:
                request.session.pop('google_signup', None)
                return _sign_in(request, linked.user, pending['next'],
                                f'Welcome back, {linked.user.username}!')
            form.add_error('username', 'That username is taken. Try another one.')
        else:
            request.session.pop('google_signup', None)
            send_welcome_email(request, user)
            return _sign_in(request, user, pending['next'], f'Welcome to Checkora, {user.username}!')

    return render(request, 'game/google_username.html', {
        'form': form,
        'google_email': pending['email'],
    })
