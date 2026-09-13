# Model Comparison SSE Prompt

Review the POST SSE comparison flow end to end. Preserve gateway role enforcement, client trace/bearer headers, event parsing, per-model progress/cards, terminal errors, browser cancellation/teardown, and non-streaming fallback. Do not use EventSource for authenticated POST streaming. Add/update unit and gateway tests plus `docs/SSE_STREAMING.md`.
