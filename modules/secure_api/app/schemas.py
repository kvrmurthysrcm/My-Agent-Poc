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


class LogoutResponse(BaseModel):
    status: str = "LOGGED_OUT"
