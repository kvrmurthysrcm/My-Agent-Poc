from __future__ import annotations

from typing import Any

import httpx


class DependencyUnavailableError(RuntimeError):
    """A dependency failure that is safe to report to an API client."""

    def __init__(self, *, code: str, message: str, details: dict[str, str] | None = None) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(message)

    def to_public_detail(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "details": self.details,
        }


class OllamaUnavailableError(DependencyUnavailableError):
    def __init__(self, *, base_url: str, model: str, cause: Exception | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.cause = cause
        super().__init__(
            code="ollama_unavailable",
            message=(
                f"Ollama is unavailable at {self.base_url}. Start Ollama, then make sure the "
                f"'{self.model}' model is installed with `ollama pull {self.model}`."
            ),
            details={"dependency": "ollama", "model": self.model},
        )


class OllamaModelUnavailableError(DependencyUnavailableError):
    def __init__(self, *, base_url: str, model: str, cause: Exception | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.cause = cause
        super().__init__(
            code="ollama_model_unavailable",
            message=(
                f"Ollama is running at {self.base_url}, but the configured model '{self.model}' is not "
                f"available. Install it with `ollama pull {self.model}`."
            ),
            details={"dependency": "ollama", "model": self.model},
        )


def check_ollama_available(*, base_url: str, model: str, timeout_seconds: float = 3.0) -> None:
    """Confirm that Ollama is reachable and the configured model is installed.

    This intentionally performs a lightweight tags request rather than generating a
    response, so it is safe to call during application startup and readiness checks.
    """

    normalized_base_url = base_url.rstrip("/")
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(f"{normalized_base_url}/api/tags")
            response.raise_for_status()
            payload = response.json()
    except httpx.RequestError as exc:
        raise OllamaUnavailableError(base_url=normalized_base_url, model=model, cause=exc) from exc
    except (httpx.HTTPStatusError, ValueError) as exc:
        raise OllamaUnavailableError(base_url=normalized_base_url, model=model, cause=exc) from exc

    if not isinstance(payload, dict):
        raise OllamaUnavailableError(
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
        raise OllamaModelUnavailableError(base_url=normalized_base_url, model=model)


def dependency_error_from_response(response: httpx.Response) -> DependencyUnavailableError | None:
    """Translate the known safe 503 payload emitted by rag-search into an app error."""

    if response.status_code != 503:
        return None

    try:
        payload = response.json()
    except ValueError:
        return None

    detail = payload.get("detail") if isinstance(payload, dict) else None
    if not isinstance(detail, dict):
        return None

    code = detail.get("code")
    message = detail.get("message")
    details = detail.get("details")
    if code not in {"ollama_unavailable", "ollama_model_unavailable"} or not isinstance(message, str):
        return None

    safe_details = {
        key: value
        for key, value in (details.items() if isinstance(details, dict) else [])
        if key in {"dependency", "model"} and isinstance(value, str)
    }
    return DependencyUnavailableError(code=code, message=message, details=safe_details)


def _model_is_installed(model_names: set[str], requested_model: str) -> bool:
    normalized = requested_model.strip()
    if normalized in model_names:
        return True
    return ":" not in normalized and f"{normalized}:latest" in model_names
