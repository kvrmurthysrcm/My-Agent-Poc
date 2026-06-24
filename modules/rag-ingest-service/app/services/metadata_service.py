import json

from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import ValidationError
from app.schemas.ingest_request import IngestMetadata


class MetadataService:
    def parse(self, metadata_json: str) -> IngestMetadata:
        try:
            payload = json.loads(metadata_json)
        except json.JSONDecodeError as exc:
            raise ValidationError("metadata must be a valid JSON string") from exc
        try:
            return IngestMetadata.model_validate(payload)
        except PydanticValidationError as exc:
            raise ValidationError(f"metadata validation failed: {exc}") from exc
