# RAG Agent Angular UI

## WHAT

`rag-agent-angular-ui` is an Angular 21.2.22 standalone SPA for the existing My-Agent-Poc RAG and Online Library services. It preserves the browser-to-gateway security boundary: the browser talks only to the Secure API Gateway through `/api`.

## WHY

The module replaces the server-served, single-page vanilla JavaScript UI with an enterprise-style Angular reference application. It is deliberately structured for learning and Java + Angular Architect interview discussion.

## HOW

```text
Browser :4200 -> Angular development proxy /api -> Secure API Gateway :8010
                                                   -> internal RAG/library services
```

The gateway owns the internal `X-API-Key`. It never appears in Angular source, browser storage, network requests from the browser, or environment configuration.

## Prerequisites

- Node `24.10.x` (project pin; supported by Angular CLI 21.2.22).
- npm 11+.
- Secure API Gateway on `http://localhost:8010`.
- Keycloak and the downstream services required by the feature being tested.

The checked-in `.nvmrc`, `.node-version`, package engine, and Windows wrapper all select Node 24.10.0.

## Commands

```powershell
cd modules/angular-ui
npm install
npm start             # http://localhost:4200; proxy enabled
npm test -- --watch=false
npm run build
```

On Windows, [`run-ui.bat`](run-ui.bat) pins the project to `D:\common\node-v24.10.0-win-x64`, so another Node installation earlier in the global `PATH` cannot be selected:

```powershell
cd modules/angular-ui
.\run-ui.bat                  # starts http://localhost:4200
.\run-ui.bat install          # installs from package-lock.json
.\run-ui.bat test --watch=false
.\run-ui.bat build
.\run-ui.bat start --host 127.0.0.1 --port 4200
npm run start:win -- --host 127.0.0.1 --port 4200
npm run build:win
npm run test:win -- --watch=false
```

Angular 22.1 requires Node 24.15 or newer. This project uses Angular 21.2.22 so it can remain on Node 24.10.

`npm start` proxies `/api/*` to `:8010` and removes `/api`. Production deployments must configure actual CORS at the gateway; the proxy only makes local development simpler.

## Feature routes

| Route | Capability |
| --- | --- |
| `/login`, `/register` | Public authentication |
| `/books`, `/catalog`, `/library-search` | Authenticated user |
| `/search` | Search role |
| `/answer`, `/compare` | RAG user/admin |
| `/ingest` | Ingest user/admin |
| `/admin/resources`, `/admin/library-tools` | RAG/system admin |

## Project structure

```text
src/app/
  core/       auth, typed API clients, interceptors, guards, configuration
  shared/     presentation components and a formatting pipe
  layout/     responsive authenticated application shell
  features/   lazy pages for each user workflow
docs/         architecture, operations, security, parity and interview notes
prompts/      reusable maintenance prompts
```

## Troubleshooting

- **Login loops:** verify Keycloak and the gateway, then remove expired POC keys from browser local storage.
- **`401` after startup:** check the gateway token issuer/audience configuration and Keycloak availability.
- **`502`:** inspect the UI diagnostics panel and gateway logs; it indicates an unavailable/downstream failing service.
- **SSE appears stuck:** start the Answer Service and use a model name available to its configured provider. Browser cancellation stops reading; it cannot promise server-side model cancellation because no backend cancellation API exists.
- **CLI rejects Node:** update Node to the prerequisite range above.

See [RUNBOOK.md](docs/RUNBOOK.md), [SECURITY_NOTES.md](docs/SECURITY_NOTES.md), and [IMPLEMENTATION_REPORT.md](docs/IMPLEMENTATION_REPORT.md).
