from collections.abc import Iterable
from typing import Any

RAG_USER = "rag_user"
RAG_ADMIN = "rag_admin"
RAG_SEARCH_USER = "rag_search_user"
RAG_INGEST_USER = "rag_ingest_user"
GRAPH_RAG_USER = "graph_rag_user"
SYSTEM_ADMIN = "system_admin"


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    return [item for item in value if isinstance(item, str)]


def extract_roles(claims: dict[str, Any], *, client_id: str) -> list[str]:
    roles: set[str] = set()

    realm_access = claims.get("realm_access")
    if isinstance(realm_access, dict):
        roles.update(_as_string_list(realm_access.get("roles")))

    resource_access = claims.get("resource_access")
    if isinstance(resource_access, dict):
        client_access = resource_access.get(client_id)
        if isinstance(client_access, dict):
            roles.update(_as_string_list(client_access.get("roles")))

    return sorted(roles)


def has_any_role(user_roles: Iterable[str], required_roles: Iterable[str]) -> bool:
    return bool(set(user_roles).intersection(required_roles))
