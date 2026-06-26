from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.utils.hashing import sha256_file


class FileStorageService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def save_upload(self, file: UploadFile, upload_id: str | None = None) -> tuple[Path, int, str]:
        target_dir = self.settings.storage_root / "tmp" / (upload_id or str(uuid4()))
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(file.filename or "upload.bin").name
        target_path = target_dir / safe_name

        size = 0
        try:
            with target_path.open("wb") as handle:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.settings.max_upload_bytes:
                        raise ValidationError(f"Upload exceeds maximum size of {self.settings.max_upload_mb} MB")
                    handle.write(chunk)
        except Exception:
            target_path.unlink(missing_ok=True)
            try:
                target_dir.rmdir()
            except OSError:
                pass
            raise

        return target_path, size, sha256_file(target_path)
