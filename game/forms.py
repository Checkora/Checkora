from django import forms
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email',)

    def clean_email(self):
        email = self.cleaned_data.get('email')

        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(
                "An account with this email already exists. Please log in instead."
            )

        return email 

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
        except Exception:
            raise ValidationError("Failed to send password reset email. Please check your email configuration and try again.")