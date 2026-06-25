from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter

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
        return vectors

    def _embed_batch(
        self,
        batch_index: int,
        batch: list[str],
        batch_count: int,
        on_batch_profile: EmbeddingBatchProfile | None,
    ) -> list[list[float]]:
        started = perf_counter()
        status = "DONE"
        try:
            return self.provider.embed_texts(batch)
        except Exception:
            status = "FAILED"
            raise
        finally:
            if on_batch_profile:
                on_batch_profile(
                    {
                        "batch_index": batch_index,
                        "batch_count": batch_count,
                        "batch_size": len(batch),
                        "status": status,
                        "elapsed_ms": round((perf_counter() - started) * 1000, 2),
                    }
                )
