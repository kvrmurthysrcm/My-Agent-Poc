# Security Notes

## Boundaries

- **Keycloak/OIDC:** Keycloak issues tokens; the Secure API Gateway validates JWT signature/issuer/roles.
- **Access vs refresh token:** access tokens reach protected gateway endpoints; refresh tokens obtain a new access token. Both are currently isolated behind `TokenStorageService`.
- **Browser authorization:** route guards and navigation use `/auth/me` roles for UX only.
- **Backend authorization:** the gateway is authoritative and rechecks roles on every proxy endpoint.
- **Internal API key:** `X-API-Key` exists only in gateway-to-service calls. It is not placed in TypeScript, proxy config, local storage, headers emitted by Angular, or browser-visible configuration.

## POC token storage risk

The legacy UI stores tokens in localStorage and this implementation reproduces that behavior. Any successful XSS can read local storage. Use strict CSP, output encoding, dependency controls, and avoid dangerous DOM APIs in the interim. The production recommendation is an HttpOnly/Secure/SameSite cookie/BFF pattern where refresh material is never script-readable.

## CORS and CSRF

The development proxy avoids a browser CORS preflight path for `:4200 -> :8010`; it does not replace production CORS configuration. Cookie/BFF architecture needs explicit CSRF mitigation; bearer headers have different CSRF properties but higher XSS token-theft exposure.

## Added proxy routes

The Graph search, debug/combined search, compare SSE, job polling/errors, and Graph settings routes are explicit gateway routes with role checks. They do not create a generic open proxy.

## Interview takeaway

Security belongs at trust boundaries. Never solve a missing gateway route by moving internal service credentials into an SPA.
