import logging
from typing import Any

import httpx
import jwt
from jwt import PyJWK
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError, PyJWTError

from app.config import Settings

logger = logging.getLogger(__name__)


class JwtValidationError(Exception):
    pass


class JwksUnavailableError(Exception):
    pass


class KeycloakJwtValidator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._jwks: dict[str, Any] | None = None

    async def validate_token(self, token: str) -> dict[str, Any]:
        header = self._get_unverified_header(token)
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise JwtValidationError("Token header does not include a valid kid.")

        jwk = await self._get_jwk(kid, refresh=False)
        if jwk is None:
            jwk = await self._get_jwk(kid, refresh=True)
        if jwk is None:
            raise JwtValidationError("No matching signing key found for token.")

        try:
            signing_key = PyJWK.from_dict(jwk).key
            decode_kwargs: dict[str, Any] = {
                "jwt": token,
                "key": signing_key,
                "algorithms": ["RS256"],
                "issuer": self._settings.keycloak_issuer_url,
                "options": {
                    "require": ["exp", "iss", "sub"],
                    "verify_aud": self._settings.token_audience_validation_enabled,
                },
            }
            if self._settings.token_audience_validation_enabled:
                decode_kwargs["audience"] = self._settings.keycloak_client_id

            return jwt.decode(**decode_kwargs)
        except ExpiredSignatureError as exc:
            raise JwtValidationError("Token has expired.") from exc
        except InvalidTokenError as exc:
            raise JwtValidationError("Token is invalid.") from exc
        except PyJWTError as exc:
            raise JwtValidationError("Token could not be validated.") from exc

    async def _get_jwk(self, kid: str, *, refresh: bool) -> dict[str, Any] | None:
        jwks = await self._get_jwks(refresh=refresh)
        keys = jwks.get("keys", [])
        if not isinstance(keys, list):
            raise JwksUnavailableError("JWKS payload does not contain a keys list.")

        for key in keys:
            if isinstance(key, dict) and key.get("kid") == kid:
                return key

        return None

    async def _get_jwks(self, *, refresh: bool = False) -> dict[str, Any]:
        if self._jwks is not None and not refresh:
            return self._jwks

        try:
            async with httpx.AsyncClient(timeout=self._settings.keycloak_timeout_seconds) as client:
                response = await client.get(self._settings.keycloak_jwks_url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("keycloak_jwks_unavailable", extra={"error_type": type(exc).__name__})
            raise JwksUnavailableError("Keycloak JWKS is unavailable.") from exc

        jwks = response.json()
        if not isinstance(jwks, dict):
            raise JwksUnavailableError("Keycloak JWKS response was not a JSON object.")

        self._jwks = jwks
        return jwks

    def _get_unverified_header(self, token: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except PyJWTError as exc:
            raise JwtValidationError("Token header is invalid.") from exc

        if not isinstance(header, dict):
            raise JwtValidationError("Token header is invalid.")

        return header
