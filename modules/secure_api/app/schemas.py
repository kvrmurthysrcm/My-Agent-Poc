from pydantic import BaseModel, Field, SecretStr


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: SecretStr = Field(..., min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: SecretStr = Field(..., min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: SecretStr = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str
    expires_in: int | None = None
    refresh_expires_in: int | None = None
    scope: str | None = None


class RegistrationRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., min_length=3, max_length=320)
    username: str = Field(..., min_length=3, max_length=100)
    password: SecretStr = Field(..., min_length=8)
    subscription_tier: str = Field("FREE", min_length=1, max_length=30)


class RegistrationOptionTier(BaseModel):
    tier_code: str
    tier_name: str
    description: str | None = None


class RegistrationOptionsResponse(BaseModel):
    subscription_tiers: list[RegistrationOptionTier] = Field(default_factory=list)
    assigned_roles: list[str] = Field(default_factory=list)
    role_assignment_mode: str = "automatic"


class RegistrationResponse(BaseModel):
    status: str = "REGISTERED"
    keycloak_user_id: str
    library_user_id: str
    username: str
    email: str
    assigned_roles: list[str] = Field(default_factory=list)
    subscription_tier: str
    approval_status: str = "APPROVED"


class LogoutResponse(BaseModel):
    status: str = "LOGGED_OUT"


class CurrentUser(BaseModel):
    sub: str
    preferred_username: str | None = None
    email: str | None = None
    name: str | None = None
    roles: list[str] = Field(default_factory=list)
    issuer: str
