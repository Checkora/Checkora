from django import forms

from .services_avatar import process_avatar_image, validate_avatar_upload


class AvatarUploadForm(forms.Form):
    image = forms.ImageField(required=True)


    def clean_image(self):
        f = self.cleaned_data.get("image")
        if not f:
            raise forms.ValidationError("No image uploaded.")

        file_name = getattr(f, "name", "") or "avatar"
        content_type = getattr(f, "content_type", "") or ""
        size_bytes = getattr(f, "size", 0)

        # Read bytes once; validations use magic bytes + Pillow verify.
        file_bytes = f.read()

        # Ensure pointer reset for any downstream consumers.
        try:
            f.seek(0)
        except Exception:
            pass

        try:
            validate_avatar_upload(
                file_name=file_name,
                content_type=content_type,
                size_bytes=size_bytes,
                file_bytes=file_bytes,
            )
        except ValueError as exc:
            raise forms.ValidationError(str(exc))

        # Ensure decodable/processable.
        try:
            process_avatar_image(file_bytes)
        except Exception:
            raise forms.ValidationError("Invalid or corrupted image.")

        return f

