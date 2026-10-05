# Step 6 — Instrument Answer Startup

Modify only rag-answer-service startup.

Inspect the actual current startup. Conceptually change:
`uvicorn <module>:app ...`
to:
`opentelemetry-instrument uvicorn <module>:app ...`

Preserve the real module path, port, and all existing Uvicorn options.

Check BOTH:
- Dockerfile CMD/ENTRYPOINT
- Kubernetes command/args overrides

Ensure the effective runtime command in Kubernetes actually goes through `opentelemetry-instrument`.

Show effective command and diff. Do not deploy yet.
