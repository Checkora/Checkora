from django.contrib.auth import get_user_model
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class CheckoraSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Link verified Google accounts to existing Checkora users."""

    def pre_social_login(self, request, sociallogin):
        if sociallogin.is_existing:
            return

        if sociallogin.account.provider != 'google':
            return

        email = sociallogin.account.extra_data.get('email')
        verified_email = sociallogin.account.extra_data.get(
            'email_verified',
            sociallogin.account.extra_data.get('verified_email'),
        )

        if not email or not verified_email:
            return

        User = get_user_model()
        try:
            existing_user = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist:
            return

        sociallogin.connect(request, existing_user)
