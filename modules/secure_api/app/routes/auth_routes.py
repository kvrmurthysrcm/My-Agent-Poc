from fastapi import APIRouter, Depends
from starlette import status

from app.auth.keycloak_client import (
    KeycloakAuthenticationError,
    KeycloakAdminClient,
    KeycloakClient,
    KeycloakConflictError,
    KeycloakUnavailableError,
)
from app.auth.dependencies import get_current_user
from app.config import Settings, get_settings
from app.exceptions import AppError
from app.schemas import (
    CurrentUser,
    LoginRequest,
    LogoutRequest,
    LogoutResponse,
    RefreshRequest,
    RegistrationOptionsResponse,
    RegistrationOptionTier,
    RegistrationRequest,
    RegistrationResponse,
    TokenResponse,
)
from app.services.library_registration_repository import (
    DuplicateLibraryUserError,
    InvalidSubscriptionTierError,
    LibraryRegistrationRepository,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def get_keycloak_client(settings: Settings = Depends(get_settings)) -> KeycloakClient:
    return KeycloakClient(settings)


def get_keycloak_admin_client(settings: Settings = Depends(get_settings)) -> KeycloakAdminClient:
    return KeycloakAdminClient(settings)


def get_registration_repository(settings: Settings = Depends(get_settings)) -> LibraryRegistrationRepository:
    return LibraryRegistrationRepository(settings)


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


@router.get("/register/options", response_model=RegistrationOptionsResponse)
async def registration_options(
    settings: Settings = Depends(get_settings),
    repository: LibraryRegistrationRepository = Depends(get_registration_repository),
) -> RegistrationOptionsResponse:
    tiers = [
        RegistrationOptionTier.model_validate(tier)
        for tier in repository.list_subscription_tiers()
    ]
    return RegistrationOptionsResponse(
        subscription_tiers=tiers,
        assigned_roles=list(settings.default_registration_roles),
    )


@router.post("/register", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegistrationRequest,
    settings: Settings = Depends(get_settings),
    keycloak_admin_client: KeycloakAdminClient = Depends(get_keycloak_admin_client),
    repository: LibraryRegistrationRepository = Depends(get_registration_repository),
) -> RegistrationResponse:
    assigned_roles = list(settings.default_registration_roles)
    subscription_tier = payload.subscription_tier.strip().upper()
    try:
        keycloak_user_id = await keycloak_admin_client.create_registered_user(
            username=payload.username.strip(),
            email=payload.email.strip(),
            full_name=payload.full_name.strip(),
            password=payload.password.get_secret_value(),
            roles=assigned_roles,
        )
    except KeycloakConflictError as exc:
        raise AppError(
            "A user with this username or email already exists.",
            status_code=status.HTTP_409_CONFLICT,
            error_code="registration_user_exists",
        ) from exc
    except KeycloakAuthenticationError as exc:
        raise AppError(
            "Keycloak rejected the registration request.",
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code="keycloak_registration_rejected",
        ) from exc
    except KeycloakUnavailableError as exc:
        raise AppError(
            "Keycloak is unavailable.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="keycloak_unavailable",
        ) from exc

    try:
        library_user_id = repository.create_approved_user_subscription(
            full_name=payload.full_name.strip(),
            email=payload.email.strip(),
            keycloak_user_id=keycloak_user_id,
            tier_code=subscription_tier,
        )
    except InvalidSubscriptionTierError as exc:
        await keycloak_admin_client.delete_user(user_id=keycloak_user_id)
        raise AppError(
            "Invalid subscription tier.",
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="invalid_subscription_tier",
        ) from exc
    except DuplicateLibraryUserError as exc:
        await keycloak_admin_client.delete_user(user_id=keycloak_user_id)
        raise AppError(
            "A library user with this email already exists.",
            status_code=status.HTTP_409_CONFLICT,
            error_code="library_user_exists",
        ) from exc
    except Exception as exc:
        await keycloak_admin_client.delete_user(user_id=keycloak_user_id)
        raise AppError(
            "Unable to save library registration.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="library_registration_unavailable",
        ) from exc

    return RegistrationResponse(
        keycloak_user_id=keycloak_user_id,
        library_user_id=library_user_id,
        username=payload.username.strip(),
        email=payload.email.strip(),
        assigned_roles=assigned_roles,
        subscription_tier=subscription_tier,
    )


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
