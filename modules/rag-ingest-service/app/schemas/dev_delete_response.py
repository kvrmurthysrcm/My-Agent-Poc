from pydantic import BaseModel


class DevDeleteResourceResponse(BaseModel):
    resource_id: str
    deleted: bool
    deleted_file_path: str | None = None
    deleted_counts: dict[str, int]
