from pathlib import Path

from fastapi import UploadFile

from app.core.config import Settings
from app.core.constants import SUPPORTED_MIME_TYPES
from app.core.exceptions import ValidationError


def validate_upload_file(file: UploadFile, settings: Settings) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in settings.supported_extensions:
        raise ValidationError(f"Unsupported file extension '{suffix}'. Supported extensions: {settings.supported_extensions}")

    allowed_mime_types = SUPPORTED_MIME_TYPES.get(suffix, set())
    if file.content_type and allowed_mime_types and file.content_type not in allowed_mime_types:
        raise ValidationError(f"Unsupported MIME type '{file.content_type}' for '{suffix}' files")

    return suffix
