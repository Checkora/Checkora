from django import forms
from django.contrib.auth.forms import (
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.core.exceptions import ValidationError


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['username'].widget.attrs.update({
            'autocomplete': 'username'
        })

        self.fields['email'].widget.attrs.update({
            'autocomplete': 'email'
        })

        self.fields['password1'].widget.attrs.update({
            'autocomplete': 'new-password'
        })

        self.fields['password2'].widget.attrs.update({
            'autocomplete': 'new-password'
        })


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

        except ValidationError:
            raise ValidationError(
                "Failed to send password reset email. "
                "Please check your email configuration and try again."
            )