# Routing and Guards

All feature screens use lazy `loadComponent` routes beneath an authenticated shell. `authGuard` restores a valid session before allowing the shell. `roleGuard` reads route data and returns a `UrlTree` for an unauthorized navigation.

```text
/login, /register
/
  /books, /catalog, /search, /answer, /compare
  /library-search, /ingest
  /admin/resources, /admin/library-tools
```

The root fallback redirects to `/books`; an anonymous request is redirected to `/login?returnUrl=...`.

## Interview takeaway

Lazy loading changes download behavior, not authorization. A guard provides UI policy while the backend independently protects the corresponding APIs.
