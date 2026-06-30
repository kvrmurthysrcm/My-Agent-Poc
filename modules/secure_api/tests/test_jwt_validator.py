from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.auth.jwt_validator import JwksUnavailableError, JwtValidationError, KeycloakJwtValidator
from app.config import Settings


def _settings() -> Settings:
    return Settings(KEYCLOAK_REALM="rag-auth-gateway")


def _key_pair() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwk(private_key: rsa.RSAPrivateKey, *, kid: str) -> dict[str, Any]:
    public_jwk = RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    public_jwk["kid"] = kid
    public_jwk["use"] = "sig"
    public_jwk["alg"] = "RS256"
    return public_jwk


def _token(
    private_key: rsa.RSAPrivateKey,
    *,
    kid: str = "kid-1",
    issuer: str | None = None,
    expires_delta: timedelta = timedelta(minutes=5),
    extra_claims: dict[str, Any] | None = None,
) -> str:
    settings = _settings()
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": "user-123",
        "iss": issuer or settings.keycloak_issuer_url,
        "exp": now + expires_delta,
        "iat": now,
        "preferred_username": "raguser",
    }
    claims.update(extra_claims or {})
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


@pytest.mark.anyio
async def test_validate_token_returns_claims_with_cached_jwks() -> None:
    private_key = _key_pair()
    jwks_calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal jwks_calls
        jwks_calls += 1
        return httpx.Response(200, json={"keys": [_jwk(private_key, kid="kid-1")]})

    settings = _settings()
    validator = KeycloakJwtValidator(settings)
    transport = httpx.MockTransport(handler)

    original_async_client = httpx.AsyncClient
    httpx.AsyncClient = lambda *args, **kwargs: original_async_client(transport=transport)
    try:
        claims = await validator.validate_token(_token(private_key))
        second_claims = await validator.validate_token(_token(private_key))
    finally:
        httpx.AsyncClient = original_async_client

    assert claims["sub"] == "user-123"
    assert second_claims["preferred_username"] == "raguser"
    assert jwks_calls == 1


@pytest.mark.anyio
async def test_validate_token_refreshes_jwks_once_when_kid_missing() -> None:
    private_key = _key_pair()
    jwks_calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal jwks_calls
        jwks_calls += 1
        keys = [] if jwks_calls == 1 else [_jwk(private_key, kid="kid-2")]
        return httpx.Response(200, json={"keys": keys})

    validator = KeycloakJwtValidator(_settings())
    transport = httpx.MockTransport(handler)

    original_async_client = httpx.AsyncClient
    httpx.AsyncClient = lambda *args, **kwargs: original_async_client(transport=transport)
    try:
        claims = await validator.validate_token(_token(private_key, kid="kid-2"))
    finally:
        httpx.AsyncClient = original_async_client

    assert claims["sub"] == "user-123"
    assert jwks_calls == 2


@pytest.mark.anyio
async def test_validate_token_rejects_expired_token() -> None:
    private_key = _key_pair()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"keys": [_jwk(private_key, kid="kid-1")]})

    validator = KeycloakJwtValidator(_settings())
    transport = httpx.MockTransport(handler)

    original_async_client = httpx.AsyncClient
    httpx.AsyncClient = lambda *args, **kwargs: original_async_client(transport=transport)
    try:
        with pytest.raises(JwtValidationError):
            await validator.validate_token(_token(private_key, expires_delta=timedelta(minutes=-1)))
    finally:
        httpx.AsyncClient = original_async_client


@pytest.mark.anyio
async def test_validate_token_raises_when_jwks_unavailable() -> None:
    private_key = _key_pair()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    validator = KeycloakJwtValidator(_settings())
    transport = httpx.MockTransport(handler)

    original_async_client = httpx.AsyncClient
    httpx.AsyncClient = lambda *args, **kwargs: original_async_client(transport=transport)
    try:
        with pytest.raises(JwksUnavailableError):
            await validator.validate_token(_token(private_key))
    finally:
        httpx.AsyncClient = original_async_client
