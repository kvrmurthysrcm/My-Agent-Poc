import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class KeycloakAuthenticationError(Exception):
    pass


class KeycloakUnavailableError(Exception):
    pass


class KeycloakClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def password_grant(self, *, username: str, password: str) -> dict[str, Any]:
        data = {
            "grant_type": "password",
            "client_id": self._settings.keycloak_client_id,
            "client_secret": self._settings.keycloak_client_secret,
            "username": username,
            "password": password,
        }
        return await self._post_token(data)

    async def refresh(self, *, refresh_token: str) -> dict[str, Any]:
        data = {
            "grant_type": "refresh_token",
            "client_id": self._settings.keycloak_client_id,
            "client_secret": self._settings.keycloak_client_secret,
            "refresh_token": refresh_token,
        }
        return await self._post_token(data)

    async def logout(self, *, refresh_token: str) -> None:
        data = {
            "client_id": self._settings.keycloak_client_id,
            "client_secret": self._settings.keycloak_client_secret,
            "refresh_token": refresh_token,
        }

        try:
            async with httpx.AsyncClient(timeout=self._settings.keycloak_timeout_seconds) as client:
                response = await client.post(self._settings.keycloak_logout_url, data=data)
        except httpx.RequestError as exc:
            logger.warning("keycloak_logout_unavailable", extra={"error_type": type(exc).__name__})
            raise KeycloakUnavailableError("Keycloak is unavailable.") from exc

        if response.status_code in {400, 401}:
            raise KeycloakAuthenticationError("Invalid refresh token.")
        if response.status_code >= 500:
            logger.warning("keycloak_logout_server_error", extra={"status_code": response.status_code})
            raise KeycloakUnavailableError("Keycloak is unavailable.")
        if response.status_code >= 400:
            raise KeycloakAuthenticationError("Logout rejected by Keycloak.")

    async def _post_token(self, data: dict[str, str]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self._settings.keycloak_timeout_seconds) as client:
                response = await client.post(self._settings.keycloak_token_url, data=data)
        except httpx.RequestError as exc:
            logger.warning("keycloak_token_unavailable", extra={"error_type": type(exc).__name__})
            raise KeycloakUnavailableError("Keycloak is unavailable.") from exc

        if response.status_code in {400, 401}:
            raise KeycloakAuthenticationError("Invalid Keycloak credentials.")
        if response.status_code >= 500:
            logger.warning("keycloak_token_server_error", extra={"status_code": response.status_code})
            raise KeycloakUnavailableError("Keycloak is unavailable.")
        if response.status_code >= 400:
            raise KeycloakAuthenticationError("Keycloak token request was rejected.")

        return response.json()
