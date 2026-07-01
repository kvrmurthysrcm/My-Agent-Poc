# Phase 1 Registration Implementation Note

## Implemented

- Added Keycloak admin client configuration to the secure gateway.
- Added Keycloak setup automation for `secure-gateway-admin`.
- Added public registration endpoints:
  - `GET /auth/register/options`
  - `POST /auth/register`
- Added secure gateway UI registration form on the login screen.
- Added library DB persistence:
  - creates `library_users`
  - sets `status = ACTIVE`
  - sets `approval_status = APPROVED`
  - creates an approved `user_approval_requests` row
  - creates an active `user_subscriptions` row
- Added rollback behavior:
  - if library DB persistence fails after Keycloak user creation, the newly created Keycloak user is deleted

## Role Decision

For Phase 1, public self-registration automatically assigns safe default roles:

- `rag_user`
- `rag_search_user`

The registration UI shows the assigned roles but does not let users select roles.

Reason:

- Public role multi-select would allow users to request privileged roles such as `rag_admin`, `rag_ingest_user`, or `system_admin`.
- Admin role management should be a separate authenticated admin workflow.

## Role Synchronization Status

The live `online_library` DB currently has no role reference table. Current tables include `library_users`, `subscription_tiers`, and `user_subscriptions`, but no role table.

For Phase 1, Keycloak realm roles are the source of truth for authentication/authorization roles.

Before building admin role management, add explicit library role tables, for example:

- `application_roles`
- `library_user_roles`

Then sync those tables with Keycloak realm roles and use them for admin-facing role management.

## Verified

- Unit tests for secure gateway registration pass.
- Full secure gateway test suite passes.
- Live local smoke test passed against real Keycloak and PostgreSQL:
  - created a temporary Keycloak user
  - assigned default roles
  - saved the approved library user
  - created active subscription
  - cleaned up the temporary user and DB rows

