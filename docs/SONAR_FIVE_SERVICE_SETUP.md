# SonarQube setup for the five-service Python pilot

## Included services

| Service ID | Sonar project key | Jenkins project-token credential |
|---|---|---|
| `ingest` | `my-agent-poc-rag-ingest` | `sonarqube-token-rag-ingest` |
| `search` | `my-agent-poc-rag-search` | `sonarqube-token-rag-search` |
| `answer` | `my-agent-poc-rag-answer` | `sonarqube-token-rag-answer` |
| `library` | `my-agent-poc-online-library` | `sonarqube-token` |
| `secure` | `my-agent-poc-secure-api` | `sonarqube-token-secure-api` |

MCP, Library Agent, Weather Agent, Weather AI Agent, and Angular UI remain explicitly `NOT_CONFIGURED`.

## Required preparation before pushing the overlay

Create the four new projects in SonarQube with the exact keys in the table. Generate a **Project analysis token** for each project. Store each token in Jenkins as **Secret text**, using the exact credential ID shown above.

Credentials must be created under:

`Manage Jenkins > Credentials > System > Global credentials (unrestricted)`

Do not create them in an individual Jenkins user's credential store.

Keep the existing credentials:

- `sonarqube-token` for Online Library analysis;
- `sonarqube-report-token` for read-only Web API reporting.

Grant the reporting service user **Browse Project** on each new private SonarQube project. The reporting token does not need Execute Analysis, Administer Project, Administer Issues, or Administer Security Hotspots.

## Pipeline behavior

The build/test stage generates `pytest.xml` and `coverage.xml` for all five pilot services. Application test failures remain blocking.

After tests pass, the Sonar stage analyzes only pilot services selected by change detection. Scans run sequentially to avoid unnecessary load on the local SonarQube container. A scanner or Quality Gate failure is advisory and does not block deployment.

Each selected service produces:

- `build-reports/sonar/<module>-scanner.log`;
- `build-reports/sonar/<module>-summary.txt`;
- a row with current measures and history in `build-reports/sonar/sonar-summary.tsv`;
- `test-results/<module>/pytest.xml`;
- `test-results/<module>/coverage.xml`.

The all-module TSV remains a ten-row inventory. The five deferred modules stay visible as `NOT_CONFIGURED`.

## First-build expectations

The overlay changes shared CI files, so the first commit is expected to select all modules for build/deployment and all five pilot services for SonarQube analysis. Create every required project and Jenkins credential before pushing.

Initial coverage and hotspot counts are observations, not release gates. Record the baseline and keep Sonar advisory while the project prepares the session-aware feature.

## Failure isolation

Each service token is bound separately. If one credential is missing or one scan fails, Jenkins continues with the remaining selected scans. The final report marks the affected service `ATTENTION_REQUIRED`.

The reporting exporter runs separately with `sonarqube-report-token`. A reporting failure cannot invalidate completed scanner results and remains advisory.

## Deferred tightening

The following remain future governance work:

- project-specific new-code periods for the four newly onboarded projects;
- agreed new-code coverage thresholds;
- blocking Quality Gates;
- formal hotspot disposition workflow;
- dependency/SCA scanning;
- onboarding MCP, agents, weather services, and Angular UI.

## Next high-priority feature

After one successful five-service analysis, implement session-aware behavior as a separate change set. Keep that work separate from Sonar onboarding so interview preparation can demonstrate a clean architectural feature with focused tests, diagrams, persistence decisions, and API contracts.
