"""Account rules shared by signup, Google sign-in and the settings page.

Nothing here knows about requests or templates. Views call these functions
and turn the exceptions into form errors.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from .models import GoogleAccount, UserProfile

# How long a signup that was never verified keeps its username and email.
PENDING_REGISTRATION_MAX_AGE_SECONDS = 3600

# A player can rename themselves once in this window. Usernames are how
# people find each other on the leaderboard and in the forum, and a name that
# keeps changing makes impersonation easy.
USERNAME_CHANGE_INTERVAL = timedelta(days=30)


class UsernameTaken(Exception):
    pass


class UsernameChangeTooSoon(Exception):
    def __init__(self, available_at):
        super().__init__(available_at)
        self.available_at = available_at


def pending_registrations():
    """Signups that never finished email verification.

    verify_otp logs the user in, so a verified account always has a
    last_login. An inactive account that has one was switched off later, by
    an admin, and must not come back through the registration flow.
    """
    return User.objects.filter(is_active=False, last_login__isnull=True)


def established_accounts():
    """Every account except signups still waiting for their email code."""
    return User.objects.exclude(is_active=False, last_login__isnull=True)


def _stale_registrations():
    stale_before = timezone.now() - timedelta(seconds=PENDING_REGISTRATION_MAX_AGE_SECONDS)
    return pending_registrations().filter(date_joined__lt=stale_before)


def _release_stale_username(username):
    _stale_registrations().filter(username__iexact=username).delete()


def username_taken(username, *, exclude=None):
    """Whether someone else holds this name, compared without case.

    A signup that never verified holds its name for an hour, as on /register/.
    Call inside a transaction when the answer decides a write.
    """
    _release_stale_username(username)
    holders = User.objects.filter(username__iexact=username)
    if exclude is not None:
        holders = holders.exclude(pk=exclude.pk)
    return holders.exists()


def username_in_use(username):
    """What username_taken() would answer, for the live check on the forms.

    It only reads: a stale signup is left in place and simply not counted.
    """
    return (
        User.objects.filter(username__iexact=username)
        .exclude(pk__in=_stale_registrations().values('pk'))
        .exists()
    )


def email_taken(email, *, exclude=None):
    holders = established_accounts().filter(email__iexact=email)
    if exclude is not None:
        holders = holders.exclude(pk=exclude.pk)
    return holders.exists()


def create_google_user(username, *, sub, email):
    """Create the account for a new Google player, linked to their Google id."""
    with transaction.atomic():
        # A signup that never verified this address loses it: Google has just
        # shown who owns it.
        pending_registrations().filter(email__iexact=email).delete()
        if username_taken(username):
            raise UsernameTaken()

        user = User(username=username, email=email, is_active=True)
        # No password: this account signs in through Google until the player
        # sets one on the settings page. Django's password reset skips it.
        user.set_unusable_password()
        user.full_clean(validate_unique=False)
        user.save()
        GoogleAccount.objects.create(user=user, sub=sub, email=email)
    return user


def change_username(user, new_username):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    now = timezone.now()
    # Changing only the case of your own name is allowed at any time and
    # does not start the interval.
    case_only = new_username.lower() == user.username.lower()
    if (
        not case_only
        and profile.username_changed_at
        and now < profile.username_changed_at + USERNAME_CHANGE_INTERVAL
    ):
        raise UsernameChangeTooSoon(profile.username_changed_at + USERNAME_CHANGE_INTERVAL)

    with transaction.atomic():
        if username_taken(new_username, exclude=user):
            raise UsernameTaken()
        user.username = new_username
        user.full_clean(validate_unique=False)
        user.save(update_fields=['username'])
        if not case_only:
            UserProfile.objects.filter(pk=profile.pk).update(username_changed_at=now)
    return user


def next_username_change(user):
    """When this player may rename themselves again, or None if they may now."""
    changed_at = (
        UserProfile.objects.filter(user=user)
        .values_list('username_changed_at', flat=True).first()
    )
    if changed_at is None:
        return None
    available_at = changed_at + USERNAME_CHANGE_INTERVAL
    return available_at if available_at > timezone.now() else None


def accounts_with_email(email, limit=2):
    """Established accounts using this address. Two is enough to know it is ambiguous."""
    return list(established_accounts().filter(email__iexact=email)[:limit])
