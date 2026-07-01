import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class KeycloakAuthenticationError(Exception):
    pass


class KeycloakUnavailableError(Exception):
    pass


class KeycloakConflictError(Exception):
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


class KeycloakAdminClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def create_registered_user(
        self,
        *,
        username: str,
        email: str,
        full_name: str,
        password: str,
        roles: list[str],
    ) -> str:
        token = await self._admin_access_token()
        await self._ensure_user_absent(token, username=username, email=email)
        first_name, last_name = _split_name(full_name)
        user_payload = {
            "username": username,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "emailVerified": True,
            "requiredActions": [],
        }

        try:
            async with httpx.AsyncClient(timeout=self._settings.keycloak_timeout_seconds) as client:
                response = await client.post(
                    self._settings.keycloak_admin_users_url,
                    headers=self._admin_headers(token),
                    json=user_payload,
                )
        except httpx.RequestError as exc:
            logger.warning("keycloak_admin_create_user_unavailable", extra={"error_type": type(exc).__name__})
            raise KeycloakUnavailableError("Keycloak is unavailable.") from exc

        if response.status_code == 409:
            raise KeycloakConflictError("A Keycloak user already exists for this username or email.")
        if response.status_code >= 500:
            raise KeycloakUnavailableError("Keycloak is unavailable.")
        if response.status_code >= 400:
            raise KeycloakAuthenticationError("Keycloak user creation was rejected.")

        user_id = await self.find_user_id(username=username)
        if not user_id:
            raise KeycloakUnavailableError("Created Keycloak user could not be resolved.")

        try:
            await self.set_user_password(user_id=user_id, password=password)
            await self.assign_realm_roles(user_id=user_id, roles=roles)
        except Exception:
            await self.delete_user(user_id=user_id)
            raise

        return user_id

    async def find_user_id(self, *, username: str) -> str | None:
        token = await self._admin_access_token()
        try:
            async with httpx.AsyncClient(timeout=self._settings.keycloak_timeout_seconds) as client:
                response = await client.get(
                    self._settings.keycloak_admin_users_url,
                    headers=self._admin_headers(token),
                    params={"username": username, "exact": "true"},
                )
        except httpx.RequestError as exc:
            raise KeycloakUnavailableError("Keycloak is unavailable.") from exc
        if response.status_code >= 400:
            raise KeycloakAuthenticationError("Keycloak user lookup was rejected.")
        users = response.json()
        if not users:
            return None
        return users[0].get("id")

    async def set_user_password(self, *, user_id: str, password: str) -> None:
        token = await self._admin_access_token()
        payload = {"type": "password", "value": password, "temporary": False}
        try:
            async with httpx.AsyncClient(timeout=self._settings.keycloak_timeout_seconds) as client:
                response = await client.put(
                    f"{self._settings.keycloak_admin_users_url}/{user_id}/reset-password",
                    headers=self._admin_headers(token),
                    json=payload,
                )
        except httpx.RequestError as exc:
            raise KeycloakUnavailableError("Keycloak is unavailable.") from exc
        if response.status_code >= 400:
            raise KeycloakAuthenticationError("Keycloak password update was rejected.")

    async def assign_realm_roles(self, *, user_id: str, roles: list[str]) -> None:
        if not roles:
            return
        token = await self._admin_access_token()
        role_payload = []
        async with httpx.AsyncClient(timeout=self._settings.keycloak_timeout_seconds) as client:
            for role_name in roles:
                role_response = await client.get(
                    f"{self._settings.keycloak_admin_roles_url}/{role_name}",
                    headers=self._admin_headers(token),
                )
                if role_response.status_code == 404:
                    raise KeycloakAuthenticationError(f"Keycloak role does not exist: {role_name}")
                if role_response.status_code >= 400:
                    raise KeycloakAuthenticationError("Keycloak role lookup was rejected.")
                role = role_response.json()
                role_payload.append({"id": role["id"], "name": role["name"]})

            response = await client.post(
                f"{self._settings.keycloak_admin_users_url}/{user_id}/role-mappings/realm",
                headers=self._admin_headers(token),
                json=role_payload,
            )
        if response.status_code >= 400:
            raise KeycloakAuthenticationError("Keycloak role assignment was rejected.")

    async def delete_user(self, *, user_id: str) -> None:
        token = await self._admin_access_token()
        try:
            async with httpx.AsyncClient(timeout=self._settings.keycloak_timeout_seconds) as client:
                await client.delete(
                    f"{self._settings.keycloak_admin_users_url}/{user_id}",
                    headers=self._admin_headers(token),
                )
        except httpx.RequestError:
            logger.warning("keycloak_admin_delete_user_unavailable", extra={"user_id": user_id})

    async def _ensure_user_absent(self, token: str, *, username: str, email: str) -> None:
        async with httpx.AsyncClient(timeout=self._settings.keycloak_timeout_seconds) as client:
            for query in ({"username": username, "exact": "true"}, {"email": email, "exact": "true"}):
                response = await client.get(
                    self._settings.keycloak_admin_users_url,
                    headers=self._admin_headers(token),
                    params=query,
                )
                if response.status_code >= 400:
                    raise KeycloakAuthenticationError("Keycloak duplicate check was rejected.")
                if response.json():
                    raise KeycloakConflictError("A Keycloak user already exists for this username or email.")

    async def _admin_access_token(self) -> str:
        data = {
            "grant_type": "client_credentials",
            "client_id": self._settings.keycloak_admin_client_id,
            "client_secret": self._settings.keycloak_admin_client_secret,
        }
        token_data = await self._post_admin_token(data)
        access_token = token_data.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise KeycloakUnavailableError("Keycloak admin token response did not include an access token.")
        return access_token

    async def _post_admin_token(self, data: dict[str, str]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self._settings.keycloak_timeout_seconds) as client:
                response = await client.post(self._settings.keycloak_token_url, data=data)
        except httpx.RequestError as exc:
            logger.warning("keycloak_admin_token_unavailable", extra={"error_type": type(exc).__name__})
            raise KeycloakUnavailableError("Keycloak is unavailable.") from exc
        if response.status_code in {400, 401, 403}:
            raise KeycloakAuthenticationError("Invalid Keycloak admin client credentials.")
        if response.status_code >= 500:
            raise KeycloakUnavailableError("Keycloak is unavailable.")
        if response.status_code >= 400:
            raise KeycloakAuthenticationError("Keycloak admin token request was rejected.")
        return response.json()

    def _admin_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}


def _split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split(maxsplit=1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]
