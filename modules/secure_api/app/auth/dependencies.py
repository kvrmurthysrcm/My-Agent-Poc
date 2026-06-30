from collections.abc import Callable
from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette import status

from app.auth.jwt_validator import JwksUnavailableError, JwtValidationError, KeycloakJwtValidator
from app.auth.roles import extract_roles, has_any_role
from app.config import Settings, get_settings
from app.exceptions import AppError
from app.schemas import CurrentUser

bearer_scheme = HTTPBearer(auto_error=False)


def get_jwt_validator(settings: Settings = Depends(get_settings)) -> KeycloakJwtValidator:
    return KeycloakJwtValidator(settings)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
    validator: KeycloakJwtValidator = Depends(get_jwt_validator),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(
            "Missing bearer token.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="missing_bearer_token",
        )

    try:
        claims = await validator.validate_token(credentials.credentials)
    except JwtValidationError as exc:
        raise AppError(
            "Invalid or expired bearer token.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="invalid_bearer_token",
        ) from exc
    except JwksUnavailableError as exc:
        raise AppError(
            "Keycloak JWKS is unavailable.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="jwks_unavailable",
        ) from exc

    return build_current_user(claims, settings=settings)


def build_current_user(claims: dict[str, Any], *, settings: Settings) -> CurrentUser:
    subject = claims.get("sub")
    issuer = claims.get("iss")
    if not isinstance(subject, str) or not subject:
        raise AppError(
            "Token does not contain a valid subject.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="invalid_bearer_token",
        )
    if not isinstance(issuer, str) or not issuer:
        raise AppError(
            "Token does not contain a valid issuer.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="invalid_bearer_token",
        )

    return CurrentUser(
        sub=subject,
        preferred_username=_optional_string(claims.get("preferred_username")),
        email=_optional_string(claims.get("email")),
        name=_optional_string(claims.get("name")),
        roles=extract_roles(claims, client_id=settings.keycloak_client_id),
        issuer=issuer,
    )


def require_role(required_role: str) -> Callable[[CurrentUser], CurrentUser]:
    return require_any_role(required_role)


def require_any_role(*required_roles: str) -> Callable[[CurrentUser], CurrentUser]:
    async def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not has_any_role(user.roles, required_roles):
            raise AppError(
                "Insufficient role.",
                status_code=status.HTTP_403_FORBIDDEN,
                error_code="insufficient_role",
            )

        return user

    return dependency


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None
