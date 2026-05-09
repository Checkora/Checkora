import os
from io import BytesIO

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.validators import FileExtensionValidator
from PIL import Image

MAX_AVATAR_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp']
MAX_AVATAR_DIMENSION = 256


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    avatar = forms.ImageField(
        required=False,
        validators=[FileExtensionValidator(ALLOWED_EXTENSIONS)],
        help_text='Optional. JPG, PNG, or WEBP files only. Max 5MB.',
    )

    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email',)

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if not avatar:
            return avatar

        if avatar.size > MAX_AVATAR_SIZE:
            raise ValidationError('Avatar must be 5MB or smaller.')

        if avatar.content_type not in ALLOWED_IMAGE_TYPES:
            raise ValidationError('Unsupported avatar file type.')

        extension = os.path.splitext(avatar.name)[1].lower().lstrip('.')
        if extension not in ALLOWED_EXTENSIONS:
            raise ValidationError('Unsupported avatar file extension.')

        try:
            avatar.seek(0)
            image = Image.open(avatar)
            image.verify()
        except Exception:
            raise ValidationError('Uploaded file must be a valid image.')
        finally:
            avatar.seek(0)

        return avatar

    def optimize_avatar(self, avatar):
        if not avatar:
            return None

        avatar.seek(0)
        image = Image.open(avatar)
        source_format = image.format or 'PNG'

        if source_format.upper() in ('PNG', 'WEBP'):
            if image.mode not in ('RGBA', 'RGB'):
                image = image.convert('RGBA')
        else:
            image = image.convert('RGB')

        image.thumbnail((MAX_AVATAR_DIMENSION, MAX_AVATAR_DIMENSION), Image.LANCZOS)

        output = BytesIO()
        if avatar.content_type == 'image/png':
            image.save(output, format='PNG', optimize=True)
            content_type = 'image/png'
            extension = 'png'
        elif avatar.content_type == 'image/webp':
            image.save(output, format='WEBP', quality=85, optimize=True)
            content_type = 'image/webp'
            extension = 'webp'
        else:
            image = image.convert('RGB')
            image.save(output, format='JPEG', quality=85, optimize=True)
            content_type = 'image/jpeg'
            extension = 'jpg'

        output.seek(0)
        filename = f"{os.path.splitext(avatar.name)[0]}.{extension}"
        return InMemoryUploadedFile(
            output,
            field_name='avatar',
            name=filename,
            content_type=content_type,
            size=output.getbuffer().nbytes,
            charset=None,
        )
