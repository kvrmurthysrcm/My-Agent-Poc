from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session


GRAPH_RAG_ENTITY_BATCH_SIZE_KEY = "graph_rag.entity_batch_size"
GRAPH_RAG_RELATIONSHIP_BATCH_SIZE_KEY = "graph_rag.relationship_batch_size"


class RuntimeSettingsRepository:
    def __init__(self, db: Session):
        self.db = db

    def ensure_table(self) -> None:
        self.db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS rag_runtime_settings (
                    setting_key varchar(120) PRIMARY KEY,
                    setting_value text NOT NULL,
                    updated_at timestamp NOT NULL DEFAULT now()
                )
                """
            )
        )
        self.db.flush()

    def get_graph_rag_batch_sizes(self, default_entity_batch_size: int, default_relationship_batch_size: int) -> tuple[int, int]:
        values = self._get_values([GRAPH_RAG_ENTITY_BATCH_SIZE_KEY, GRAPH_RAG_RELATIONSHIP_BATCH_SIZE_KEY])
        return (
            _as_int(values.get(GRAPH_RAG_ENTITY_BATCH_SIZE_KEY), default_entity_batch_size),
            _as_int(values.get(GRAPH_RAG_RELATIONSHIP_BATCH_SIZE_KEY), default_relationship_batch_size),
        )

    def get_graph_rag_settings(self, default_entity_batch_size: int, default_relationship_batch_size: int) -> dict:
        entity_batch_size, relationship_batch_size = self.get_graph_rag_batch_sizes(
            default_entity_batch_size,
            default_relationship_batch_size,
        )
        updated_at = self._latest_updated_at([GRAPH_RAG_ENTITY_BATCH_SIZE_KEY, GRAPH_RAG_RELATIONSHIP_BATCH_SIZE_KEY])
        return {
            "entity_batch_size": entity_batch_size,
            "relationship_batch_size": relationship_batch_size,
            "updated_at": updated_at,
        }

    def update_graph_rag_settings(self, entity_batch_size: int, relationship_batch_size: int) -> dict:
        self._upsert(GRAPH_RAG_ENTITY_BATCH_SIZE_KEY, str(entity_batch_size))
        self._upsert(GRAPH_RAG_RELATIONSHIP_BATCH_SIZE_KEY, str(relationship_batch_size))
        self.db.flush()
        return {
            "entity_batch_size": entity_batch_size,
            "relationship_batch_size": relationship_batch_size,
            "updated_at": datetime.now(UTC).replace(tzinfo=None),
        }

    def _get_values(self, keys: list[str]) -> dict[str, str]:
        rows = self.db.execute(
            text(
                """
                SELECT setting_key, setting_value
                FROM rag_runtime_settings
                WHERE setting_key IN (:key1, :key2)
                """
            ),
            {"key1": keys[0], "key2": keys[1]},
        )
        return {row.setting_key: row.setting_value for row in rows}

    def _latest_updated_at(self, keys: list[str]):
        return self.db.execute(
            text(
                """
                SELECT max(updated_at) AS updated_at
                FROM rag_runtime_settings
                WHERE setting_key IN (:key1, :key2)
                """
            ),
            {"key1": keys[0], "key2": keys[1]},
        ).scalar_one_or_none()

    def _upsert(self, key: str, value: str) -> None:
        self.db.execute(
            text(
                """
                INSERT INTO rag_runtime_settings (setting_key, setting_value, updated_at)
                VALUES (:key, :value, now())
                ON CONFLICT (setting_key)
                DO UPDATE SET setting_value = EXCLUDED.setting_value, updated_at = now()
                """
            ),
            {"key": key, "value": value},
        )


def _as_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default
