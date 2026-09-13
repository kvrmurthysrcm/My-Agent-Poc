# Error Handling

## WHAT

`errorInterceptor` maps raw HTTP and network failures to `AppHttpError`. Pages use its friendly message in a live error panel and retain a safe diagnostics object for developers.

| Condition | UI behavior |
| --- | --- |
| 400 / 422 | Explain validation and retain server message |
| 401 | Attempt coordinated refresh once; then clear session/sign in |
| 403 | State that the role is insufficient; do not retry |
| 404 | Explain missing resource/job/tool |
| 409 | Explain conflicting job/resource state |
| 5xx / 502 / 503 / 504 | Explain gateway/dependency availability issue |
| status 0 / timeout | Explain network or unreachable service |

The gateway intentionally reduces downstream failures to a safe 502 envelope, so the UI does not expose service secrets or internal API keys.

## Interview takeaway

Normalize errors once, preserve diagnostics separately from user copy, and avoid displaying unescaped raw server payloads as page HTML.
