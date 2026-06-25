from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import RagProfilingEvent


class RagProfilingRepository:
    def __init__(self, db: Session):
        self.db = db

    def replace_events(self, job_id: str, resource_id: str, events: list[dict]) -> None:
        self.db.execute(delete(RagProfilingEvent).where(RagProfilingEvent.job_id == job_id))
        self.db.add_all(
            [
                RagProfilingEvent(
                    job_id=job_id,
                    resource_id=resource_id,
                    step=event["step"],
                    status=event.get("status", "DONE"),
                    elapsed_ms=event.get("elapsed_ms", 0),
                    event_index=index,
                    event_details=event.get("details", {}),
                )
                for index, event in enumerate(events)
            ]
        )
        self.db.flush()

    def list_events(self, job_id: str) -> list[dict]:
        rows = self.db.scalars(
            select(RagProfilingEvent)
            .where(RagProfilingEvent.job_id == job_id)
            .order_by(RagProfilingEvent.event_index)
        )
        return [
            {
                "step": row.step,
                "status": row.status,
                "elapsed_ms": float(row.elapsed_ms),
                "details": row.event_details,
            }
            for row in rows
        ]
