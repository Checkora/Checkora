from django import forms
from django.contrib.auth.forms import (
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.core.exceptions import ValidationError


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'autocomplete': 'email'
        })
    )

    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'autocomplete': 'username'
        })
    )

    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password'
        })
    )

    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password'
        })
    )

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email',)


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
    """Handle password reset email failures gracefully."""

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
                html_email_template_name,
            )

        except Exception:
            raise ValidationError(
                "Failed to send password reset email. "
                "Please check your email configuration and try again."
            )