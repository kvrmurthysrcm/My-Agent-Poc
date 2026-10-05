# Step 4 — Add OpenTelemetry Dependencies to Answer

Modify only rag-answer-service.

Determine the existing dependency-management style. Add capability equivalent to:
- opentelemetry-distro
- opentelemetry-exporter-otlp

During Docker build, after normal dependencies, run:
`opentelemetry-bootstrap -a install`

Requirements:
- preserve existing dependencies/base image/Python version
- no manual installs inside running pods
- image must contain opentelemetry-instrument and OTLP exporter support
- do not change startup command yet
- do not build yet

Show changed files, diff, why dependencies were added, where bootstrap runs, and expected auto-instrumentation.
