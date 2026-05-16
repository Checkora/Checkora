from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm


class CustomAuthenticationForm(AuthenticationForm):
    """Login form with proper autocomplete attributes."""
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'autocomplete': 'username',
            'class': 'form-control'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'current-password',
            'class': 'form-control'
        })
    )


class CustomUserCreationForm(UserCreationForm):
    """Registration form with proper autocomplete attributes."""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'autocomplete': 'email',
            'class': 'form-control'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'autocomplete': 'username'
        })
        self.fields['password1'].widget.attrs.update({
            'autocomplete': 'new-password'
        })
        self.fields['password2'].widget.attrs.update({
            'autocomplete': 'new-password'
        })

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email',)