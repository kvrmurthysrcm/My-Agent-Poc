from app.auth.roles import extract_roles, has_any_role


def test_extract_roles_from_realm_and_client_access() -> None:
    claims = {
        "realm_access": {"roles": ["rag_user", "rag_search_user"]},
        "resource_access": {
            "fastapi-auth-gateway": {"roles": ["client_role", "rag_user"]},
            "other-client": {"roles": ["ignored"]},
        },
    }

    roles = extract_roles(claims, client_id="fastapi-auth-gateway")

    assert roles == ["client_role", "rag_search_user", "rag_user"]


def test_extract_roles_ignores_malformed_claims() -> None:
    claims = {
        "realm_access": {"roles": "rag_user"},
        "resource_access": {"fastapi-auth-gateway": {"roles": [123, "rag_admin"]}},
    }

    roles = extract_roles(claims, client_id="fastapi-auth-gateway")

    assert roles == ["rag_admin"]


def test_has_any_role() -> None:
    assert has_any_role(["rag_user"], ["rag_user", "rag_admin"])
    assert not has_any_role(["rag_search_user"], ["rag_ingest_user", "rag_admin"])
