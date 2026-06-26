from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter, sleep

from app.core.config import Settings
from app.services.embedding_providers.base import EmbeddingProvider


EmbeddingBatchProfile = Callable[[dict], None]


class EmbeddingService:
    def __init__(self, provider: EmbeddingProvider, settings: Settings):
        self.provider = provider
        self.settings = settings

    def embed_chunks(
        self,
        texts: list[str],
        batch_size: int | None = None,
        concurrency: int | None = None,
        on_batch_profile: EmbeddingBatchProfile | None = None,
    ) -> list[list[float]]:
        effective_batch_size = batch_size or self.settings.embedding_batch_size
        effective_concurrency = concurrency or self.settings.embedding_concurrency
        batches = [
            (batch_index, texts[start : start + effective_batch_size])
            for batch_index, start in enumerate(range(0, len(texts), effective_batch_size), start=1)
        ]

        if effective_concurrency == 1:
            vectors: list[list[float]] = []
            for batch_index, batch in batches:
                vectors.extend(self._embed_batch(batch_index, batch, len(batches), on_batch_profile))
            self._validate_vectors(texts, vectors)
            return vectors

        ordered: dict[int, list[list[float]]] = {}
        with ThreadPoolExecutor(max_workers=effective_concurrency) as executor:
            futures = {
                executor.submit(self._embed_batch, batch_index, batch, len(batches), on_batch_profile): batch_index
                for batch_index, batch in batches
            }
            for future in as_completed(futures):
                ordered[futures[future]] = future.result()

        vectors = []
        for batch_index, _ in batches:
            vectors.extend(ordered[batch_index])
        self._validate_vectors(texts, vectors)
        return vectors

    def _embed_batch(
        self,
        batch_index: int,
        batch: list[str],
        batch_count: int,
        on_batch_profile: EmbeddingBatchProfile | None,
    ) -> list[list[float]]:
        return self._embed_batch_with_retry(
            batch_index=batch_index,
            batch=batch,
            batch_count=batch_count,
            on_batch_profile=on_batch_profile,
            attempt=1,
        )

    def _embed_batch_with_retry(
        self,
        batch_index: int,
        batch: list[str],
        batch_count: int,
        on_batch_profile: EmbeddingBatchProfile | None,
        attempt: int,
    ) -> list[list[float]]:
        started = perf_counter()
        status = "DONE"
        error_message = None
        try:
            return self.provider.embed_texts(batch)
        except Exception as exc:
            status = "FAILED"
            error_message = str(exc)
            if attempt > self.settings.embedding_max_retries:
                raise
            retry_vectors = self._retry_batch(batch_index, batch, batch_count, on_batch_profile, attempt)
            status = "RETRIED"
            return retry_vectors
        finally:
            if on_batch_profile:
                on_batch_profile(
                    {
                        "batch_index": batch_index,
                        "batch_count": batch_count,
                        "batch_size": len(batch),
                        "status": status,
                        "attempt": attempt,
                        "error_message": error_message,
                        "elapsed_ms": round((perf_counter() - started) * 1000, 2),
                    }
                )

    def _retry_batch(
        self,
        batch_index: int,
        batch: list[str],
        batch_count: int,
        on_batch_profile: EmbeddingBatchProfile | None,
        attempt: int,
    ) -> list[list[float]]:
        if self.settings.embedding_retry_backoff_seconds:
            sleep(self.settings.embedding_retry_backoff_seconds * attempt)

        if self.settings.embedding_retry_shrink_batch and len(batch) > self.settings.embedding_min_batch_size:
            next_size = max(self.settings.embedding_min_batch_size, len(batch) // 2)
            vectors: list[list[float]] = []
            for part_index, start in enumerate(range(0, len(batch), next_size), start=1):
                vectors.extend(
                    self._embed_batch_with_retry(
                        batch_index=batch_index,
                        batch=batch[start : start + next_size],
                        batch_count=batch_count,
                        on_batch_profile=on_batch_profile,
                        attempt=attempt + 1,
                    )
                )
            return vectors

        return self._embed_batch_with_retry(
            batch_index=batch_index,
            batch=batch,
            batch_count=batch_count,
            on_batch_profile=on_batch_profile,
            attempt=attempt + 1,
        )

    def _validate_vectors(self, texts: list[str], vectors: list[list[float]]) -> None:
        if len(vectors) != len(texts):
            raise ValueError(f"Embedding count mismatch: chunks={len(texts)}, vectors={len(vectors)}")
        for index, vector in enumerate(vectors):
            if len(vector) != self.settings.embedding_dimension:
                raise ValueError(
                    f"Embedding dimension mismatch at index {index}: "
                    f"expected={self.settings.embedding_dimension}, actual={len(vector)}"
                )
