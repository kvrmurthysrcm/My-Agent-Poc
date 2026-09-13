from __future__ import annotations

from typing import Any

import httpx


class OllamaDependencyError(RuntimeError):
    """An Ollama failure that can be safely returned by the search API."""

    def __init__(self, *, code: str, message: str, model: str, cause: Exception | None = None) -> None:
        self.code = code
        self.model = model
        self.cause = cause
        super().__init__(message)

    def to_public_detail(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "details": {"dependency": "ollama", "model": self.model},
        }


def ollama_unavailable_error(*, base_url: str, model: str, cause: Exception | None = None) -> OllamaDependencyError:
    return OllamaDependencyError(
        code="ollama_unavailable",
        message=(
            f"Ollama is unavailable at {base_url.rstrip('/')}. Start Ollama, then make sure the "
            f"'{model}' model is installed with `ollama pull {model}`."
        ),
        model=model,
        cause=cause,
    )


def ollama_model_unavailable_error(*, base_url: str, model: str, cause: Exception | None = None) -> OllamaDependencyError:
    return OllamaDependencyError(
        code="ollama_model_unavailable",
        message=(
            f"Ollama is running at {base_url.rstrip('/')}, but the configured embedding model '{model}' "
            f"is not available. Install it with `ollama pull {model}`."
        ),
        model=model,
        cause=cause,
    )


def check_ollama_available(*, base_url: str, model: str, timeout_seconds: float = 3.0) -> None:
    """Confirm that the local Ollama server and embedding model are ready to use."""

    normalized_base_url = base_url.rstrip("/")
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(f"{normalized_base_url}/api/tags")
            response.raise_for_status()
            payload = response.json()
    except httpx.RequestError as exc:
        raise ollama_unavailable_error(base_url=normalized_base_url, model=model, cause=exc) from exc
    except (httpx.HTTPStatusError, ValueError) as exc:
        raise ollama_unavailable_error(base_url=normalized_base_url, model=model, cause=exc) from exc

    if not isinstance(payload, dict):
        raise ollama_unavailable_error(
            base_url=normalized_base_url,
            model=model,
            cause=ValueError("Ollama returned an invalid tags response"),
        )

    names = {
        str(item.get("name") or "").strip()
        for item in payload.get("models") or []
        if isinstance(item, dict)
    }
    if not _model_is_installed(names, model):
        raise ollama_model_unavailable_error(base_url=normalized_base_url, model=model)


def _model_is_installed(model_names: set[str], requested_model: str) -> bool:
    normalized = requested_model.strip()
    if normalized in model_names:
        return True
    return ":" not in normalized and f"{normalized}:latest" in model_names
