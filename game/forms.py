from smtplib import SMTPException

from django import forms
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.contrib.auth.forms import PasswordResetForm
from django.core.exceptions import ValidationError
from django.core.mail import BadHeaderError


USERNAME_MIN_LENGTH = 3


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        username = self.fields['username']
        username.widget.attrs['minlength'] = str(USERNAME_MIN_LENGTH)

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if len(username) < USERNAME_MIN_LENGTH:
            raise ValidationError(
                f'Username must be at least {USERNAME_MIN_LENGTH} characters long.',
                code='username_too_short',
            )
        return username


class CustomSetPasswordForm(SetPasswordForm):
    """Prevent password resets from reusing the account's current password."""

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password2')
        if (
            new_password
            and self.user.has_usable_password()
            and self.user.check_password(new_password)
        ):
            self.add_error(
                'new_password2',
                forms.ValidationError(
                    'This password has been used before. '
                    'Please choose a new password.',
                    code='password_reused',
                ),
            )
        return cleaned_data


class CustomPasswordResetForm(PasswordResetForm):
    """Prevent password resets from reusing the account's current password."""

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None
    ):
        try:
            super().send_mail(
                subject_template_name,
                email_template_name,
                context,
                from_email,
                to_email,
                html_email_template_name)
        except (SMTPException, BadHeaderError, OSError) as err:
            raise ValidationError(
                'Failed to send password reset email. '
                'Please check your email configuration and try again.'
            ) from err
