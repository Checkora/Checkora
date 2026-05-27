from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, SetPasswordForm, PasswordResetForm

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email',)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add autocomplete attributes for username field
        if 'username' in self.fields:
            self.fields['username'].widget.attrs['autocomplete'] = 'username'
        # Add autocomplete attributes for password fields
        if 'password1' in self.fields:
            self.fields['password1'].widget.attrs['autocomplete'] = 'new-password'
        if 'password2' in self.fields:
            self.fields['password2'].widget.attrs['autocomplete'] = 'new-password'
        # Add autocomplete attribute for email field
        if 'email' in self.fields:
            self.fields['email'].widget.attrs['autocomplete'] = 'email'


class CustomAuthenticationForm(AuthenticationForm):
    """Custom authentication form with autocomplete attributes."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add autocomplete attributes for login form
        if 'username' in self.fields:
            self.fields['username'].widget.attrs['autocomplete'] = 'username'
        if 'password' in self.fields:
            self.fields['password'].widget.attrs['autocomplete'] = 'current-password'


class CustomSetPasswordForm(SetPasswordForm):
    """Custom set password form with autocomplete attributes for password reset."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add autocomplete attributes for password reset form
        if 'new_password1' in self.fields:
            self.fields['new_password1'].widget.attrs['autocomplete'] = 'new-password'
        if 'new_password2' in self.fields:
            self.fields['new_password2'].widget.attrs['autocomplete'] = 'new-password'


class CustomPasswordResetForm(PasswordResetForm):
    """Custom password reset form with autocomplete attributes."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add autocomplete attribute for email field
        if 'email' in self.fields:
            self.fields['email'].widget.attrs['autocomplete'] = 'email'

