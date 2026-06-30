from fastapi import APIRouter, Depends
from starlette import status

from app.auth.keycloak_client import (
    KeycloakAuthenticationError,
    KeycloakClient,
    KeycloakUnavailableError,
)
from app.auth.dependencies import get_current_user
from app.config import Settings, get_settings
from app.exceptions import AppError
from app.schemas import CurrentUser, LoginRequest, LogoutRequest, LogoutResponse, RefreshRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def get_keycloak_client(settings: Settings = Depends(get_settings)) -> KeycloakClient:
    return KeycloakClient(settings)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    keycloak_client: KeycloakClient = Depends(get_keycloak_client),
) -> TokenResponse:
    try:
        token_data = await keycloak_client.password_grant(
            username=payload.username,
            password=payload.password.get_secret_value(),
        )
    except KeycloakAuthenticationError as exc:
        raise AppError(
            "Invalid username or password.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="invalid_credentials",
        ) from exc
    except KeycloakUnavailableError as exc:
        raise AppError(
            "Keycloak is unavailable.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="keycloak_unavailable",
        ) from exc

    return TokenResponse.model_validate(token_data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    keycloak_client: KeycloakClient = Depends(get_keycloak_client),
) -> TokenResponse:
    try:
        token_data = await keycloak_client.refresh(
            refresh_token=payload.refresh_token.get_secret_value()
        )
    except KeycloakAuthenticationError as exc:
        raise AppError(
            "Invalid refresh token.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="invalid_refresh_token",
        ) from exc
    except KeycloakUnavailableError as exc:
        raise AppError(
            "Keycloak is unavailable.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="keycloak_unavailable",
        ) from exc

    return TokenResponse.model_validate(token_data)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    payload: LogoutRequest,
    keycloak_client: KeycloakClient = Depends(get_keycloak_client),
) -> LogoutResponse:
    try:
        await keycloak_client.logout(refresh_token=payload.refresh_token.get_secret_value())
    except KeycloakAuthenticationError as exc:
        raise AppError(
            "Invalid refresh token.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="invalid_refresh_token",
        ) from exc
    except KeycloakUnavailableError as exc:
        raise AppError(
            "Keycloak is unavailable.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="keycloak_unavailable",
        ) from exc

    return LogoutResponse()


@router.get("/me", response_model=CurrentUser)
async def me(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return current_user
