import re
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

USERNAME_RE = re.compile(r'^[a-zA-Z0-9_.]{3,20}$')


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email',)

    def clean_username(self):
        username = self.cleaned_data.get('username', '')

        if username != username.strip():
            raise forms.ValidationError(
                'Username must not have leading or trailing spaces.'
            )

        if not USERNAME_RE.match(username):
            raise forms.ValidationError(
                'Username must be 3–20 characters and may only contain '
                'letters, numbers, underscores (_), and periods (.).'
            )

        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('That username is already taken.')

        return username
