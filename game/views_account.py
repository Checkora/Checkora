"""The player's own pages: profile, picture, settings and account deletion."""

import hashlib
import logging
import secrets
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.auth.views import redirect_to_login
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import accounts, avatars, google_auth
from .forms import AvatarUploadForm, EmailChangeForm, EmailCodeForm, UsernameForm
from .models import GoogleAccount, UserProfile
from .progression import player_summary

logger = logging.getLogger(__name__)


def _profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _notify(address, subject, body):
    """A security notice. Failing to send one never blocks the change it reports."""
    if not address:
        return
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [address], fail_silently=False)
    except Exception:
        logger.warning('Could not send "%s" to a player', subject, exc_info=True)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@login_required
def profile_view(request):
    return render(request, 'game/profile.html', player_summary(request.user))


# ---------------------------------------------------------------------------
# Picture
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(['GET', 'POST'])
def upload_avatar(request):
    """GET shows the picture page. POST takes an uploaded file."""
    profile = _profile(request.user)

    if request.method == 'POST':
        form = AvatarUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                profile.use_upload(avatars.encode_upload(form.cleaned_data['avatar']))
            except avatars.AvatarError as exc:
                logger.info('Avatar upload refused for user %s: %s', request.user.pk, exc)
                messages.error(request, str(exc))
            else:
                messages.success(request, 'Your picture has been updated.')
        else:
            for field_errors in form.errors.values():
                for error in field_errors:
                    messages.error(request, error)
        return redirect('upload_avatar')

    return render(request, 'game/avatar.html', {
        'form': AvatarUploadForm(),
        'profile': profile,
        'presets': [
            {'key': key, 'label': label, 'url': avatars.preset_url(key)}
            for key, label in avatars.PRESETS
        ],
    })


@login_required
@require_POST
def select_avatar_preset(request):
    key = request.POST.get('preset', '')
    if key not in dict(avatars.PRESETS):
        messages.error(request, 'Pick one of the pieces.')
    else:
        _profile(request.user).use_preset(key)
        messages.success(request, f'Your picture is now the {dict(avatars.PRESETS)[key].lower()}.')
    return redirect('upload_avatar')


@login_required
@require_POST
def remove_avatar(request):
    _profile(request.user).clear_avatar()
    messages.success(request, 'Picture removed.')
    return redirect('upload_avatar')


@login_required
@require_GET
def get_avatar(request):
    """The signed-in player's picture URL, "" when they have none."""
    profile = UserProfile.objects.defer('avatar').filter(user=request.user).first()
    return JsonResponse({'avatar': profile.avatar_url if profile else ''})


@require_GET
def user_avatar(request, user_id):
    """The bytes of an uploaded picture. Public, like the leaderboard it appears on."""
    data_uri = UserProfile.objects.filter(user_id=user_id).values_list('avatar', flat=True).first()
    decoded = avatars.decode(data_uri) if data_uri else None
    if decoded is None:
        raise Http404
    mime, body = decoded
    response = HttpResponse(body, content_type=mime)
    # The URL changes whenever the picture does (?v=), so it never goes stale.
    response['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

EMAIL_CODE_MAX_AGE_SECONDS = 600
EMAIL_CODE_MAX_ATTEMPTS = 5
EMAIL_CODE_COOLDOWN_SECONDS = 60


def _password_form_class(user):
    return PasswordChangeForm if user.has_usable_password() else SetPasswordForm


def _render_settings(request, status=200, **forms):
    user = request.user
    context = {
        'username_form': forms.get('username_form') or UsernameForm(initial={'username': user.username}),
        'email_form': forms.get('email_form') or EmailChangeForm(),
        'password_form': forms.get('password_form') or _password_form_class(user)(user),
        'has_password': user.has_usable_password(),
        'next_username_change': accounts.next_username_change(user),
        'username_change_days': accounts.USERNAME_CHANGE_INTERVAL.days,
        'google_account': GoogleAccount.objects.filter(user=user).first(),
        'google_login_enabled': google_auth.is_configured(),
        'email_change_pending': request.session.get('email_change', {}).get('email'),
    }
    return render(request, 'game/account.html', context, status=status)


@login_required
@require_GET
def account_settings(request):
    return _render_settings(request)


@login_required
@require_POST
def change_username(request):
    form = UsernameForm(request.POST)
    if form.is_valid():
        new_username = form.cleaned_data['username']
        if new_username == request.user.username:
            return redirect('account_settings')
        try:
            accounts.change_username(request.user, new_username)
        except accounts.UsernameTaken:
            form.add_error('username', 'That username is taken. Try another one.')
        except accounts.UsernameChangeTooSoon as exc:
            form.add_error('username', f'You can change your username again on {exc.available_at:%d %b %Y}.')
        else:
            messages.success(request, f'You are now {new_username}.')
            return redirect('account_settings')
    return _render_settings(request, status=400, username_form=form)


def _code_hash(code):
    return hashlib.sha256(f'{code}:{settings.SECRET_KEY}'.encode()).hexdigest()


@login_required
@require_POST
def change_email(request):
    form = EmailChangeForm(request.POST)
    if not form.is_valid():
        return _render_settings(request, status=400, email_form=form)

    new_email = form.cleaned_data['email']
    if new_email.lower() == (request.user.email or '').lower():
        form.add_error('email', 'That is already your email.')
        return _render_settings(request, status=400, email_form=form)

    cooldown_key = 'email_change_cooldown_' + hashlib.sha256(new_email.lower().encode()).hexdigest()
    if not cache.add(cooldown_key, 1, timeout=EMAIL_CODE_COOLDOWN_SECONDS):
        form.add_error('email', 'A code went to that address a moment ago. Wait a minute and try again.')
        return _render_settings(request, status=429, email_form=form)

    code = f'{secrets.randbelow(1_000_000):06d}'
    request.session['email_change'] = {
        'email': new_email,
        'hash': _code_hash(code),
        'sent_at': time.time(),
        'attempts': 0,
    }
    # As on /register/, an address that belongs to someone else gets the same
    # answer and no mail, so this page can't be used to look accounts up.
    if not accounts.email_taken(new_email, exclude=request.user):
        try:
            send_mail(
                'Your Checkora email code',
                f'Your code is {code}. Enter it on Checkora to start using this address. '
                'It expires in 10 minutes.\n\nIf you did not ask for this, ignore this email.',
                settings.DEFAULT_FROM_EMAIL,
                [new_email],
                fail_silently=False,
            )
        except Exception:
            logger.warning('Email change code could not be sent', exc_info=True)
            request.session.pop('email_change', None)
            cache.delete(cooldown_key)
            form.add_error('email', 'The code could not be sent. Check the address and try again.')
            return _render_settings(request, status=502, email_form=form)
    messages.success(request, f'We sent a six-digit code to {new_email}.')
    return redirect('verify_email_change')


@login_required
@require_http_methods(['GET', 'POST'])
def verify_email_change(request):
    pending = request.session.get('email_change')
    if not pending or time.time() - pending['sent_at'] > EMAIL_CODE_MAX_AGE_SECONDS:
        request.session.pop('email_change', None)
        messages.error(request, 'That code has expired. Ask for a new one.')
        return redirect('account_settings')

    form = EmailCodeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        pending['attempts'] += 1
        request.session['email_change'] = pending
        if pending['attempts'] > EMAIL_CODE_MAX_ATTEMPTS:
            request.session.pop('email_change', None)
            messages.error(request, 'Too many wrong codes. Ask for a new one.')
            return redirect('account_settings')

        if secrets.compare_digest(_code_hash(form.cleaned_data['code']), pending['hash']):
            user = request.user
            old_email = user.email
            with transaction.atomic():
                taken = accounts.email_taken(pending['email'], exclude=user)
                if not taken:
                    user.email = pending['email']
                    user.save(update_fields=['email'])
            request.session.pop('email_change', None)
            if taken:
                messages.error(request, 'That address can not be used. Try another one.')
                return redirect('account_settings')
            _notify(
                old_email,
                'Your Checkora email was changed',
                f'The email on the Checkora account {user.username} is now {user.email}.\n\n'
                'If you did not do this, reset your password and reply to this email.',
            )
            messages.success(request, f'Your email is now {user.email}.')
            return redirect('account_settings')
        form.add_error('code', 'That code is not right.')

    return render(request, 'game/verify_email_change.html', {
        'form': form,
        'email': pending['email'],
    })


@login_required
@require_POST
def change_password(request):
    had_password = request.user.has_usable_password()
    form = _password_form_class(request.user)(request.user, request.POST)
    if not form.is_valid():
        return _render_settings(request, status=400, password_form=form)

    user = form.save()
    # Without this the change would sign the player out of this browser.
    update_session_auth_hash(request, user)
    _notify(
        user.email,
        'Your Checkora password was changed' if had_password else 'Your Checkora account has a password',
        f'The password on the Checkora account {user.username} was just '
        f'{"changed" if had_password else "set"}.\n\n'
        'If you did not do this, reset your password straight away.',
    )
    messages.success(request, 'Password changed.' if had_password else 'Password set. You can now sign in with it too.')
    return redirect('account_settings')


@login_required
@require_POST
def unlink_google(request):
    if not request.user.has_usable_password():
        messages.error(request, 'Set a password first, or you would have no way to sign in.')
    else:
        deleted, _ = GoogleAccount.objects.filter(user=request.user).delete()
        if deleted:
            messages.success(request, 'Google account unlinked.')
    return redirect('account_settings')


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------

class AccountDeletionTokenGenerator(PasswordResetTokenGenerator):
    """Tokens for the account deletion link.

    The separate salt keeps them from working as password reset tokens,
    and password reset tokens from deleting accounts. The salt still names
    the module this class used to live in, so links already mailed work.
    """
    key_salt = "game.views.AccountDeletionTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        # Unlike a reset token this one must survive a login: the link may
        # be opened in a browser where the owner has to sign in first.
        return f"{user.pk}{user.password}{timestamp}{user.email}"


account_deletion_token = AccountDeletionTokenGenerator()


@login_required
@require_http_methods(['GET', 'POST'])
def delete_account(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        if request.user.has_usable_password():
            user = authenticate(request, username=username, password=request.POST.get('password'))
        else:
            # An account made with Google has no password to ask for, so the
            # typed username and the mailed confirmation link are the check.
            user = request.user if username == request.user.username else None

        if user is None or user != request.user:
            messages.error(request, 'Invalid username or password.')
            return render(request, 'game/delete_account.html', status=400)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        link = request.build_absolute_uri(reverse(
            'confirm_delete_account',
            kwargs={'uidb64': uid, 'token': account_deletion_token.make_token(user)},
        ))
        try:
            send_mail(
                subject='Confirm Account Deletion',
                message=(
                    f'Click the link below to permanently delete your account:\n\n{link}\n\n'
                    "If this wasn't you, ignore this email."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception:
            logger.warning('Account deletion link could not be sent', exc_info=True)
            messages.error(request, 'Failed to send confirmation email.')
            return render(request, 'game/delete_account.html', status=502)

        messages.success(request, 'Confirmation email sent to your registered email.')
        return redirect('account_settings')

    return render(request, 'game/delete_account.html')


@require_http_methods(['GET', 'POST'])
def confirm_delete_account(request, uidb64, token):
    """Ask for a last confirmation, then delete the account on POST.

    Opening the mailed link changes nothing, so a mail scanner or a link
    preview cannot delete an account. Only the logged-in owner can confirm.
    """
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())

    try:
        user_pk = int(force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError):
        user_pk = None

    if user_pk != request.user.pk or not account_deletion_token.check_token(request.user, token):
        messages.error(request, 'Invalid or expired deletion link.')
        return redirect('landing')

    if request.method != 'POST':
        return render(request, 'game/confirm_delete_account.html', {'uidb64': uidb64, 'token': token})

    user = request.user
    logout(request)
    user.delete()
    return render(request, 'game/delete_success.html')
