# Online Library SonarQube governance

## Rollout state

Online Library is the pilot SonarQube project. Its Jenkins stage remains advisory. No additional module should be enabled until one validation build confirms that tests, coverage, reporting, history export, and deployment all complete successfully.

## Credentials

Use two credentials with different responsibilities:

1. `sonarqube-token`: a project analysis token limited to `my-agent-poc-online-library`.
2. `sonarqube-report-token`: a user token owned by a dedicated reporting service account. Grant only the permissions needed to browse this project and read its Web API data. Do not grant global administrator access.

Create both as Jenkins **Secret text** credentials. The pipeline sends the first token only to the scanner and the second token only to the report exporter.

## New-code baseline

For this continuously deployed POC, use a rolling 30-day new-code period while the team gathers data. From PowerShell:

```powershell
$env:SONAR_ADMIN_TOKEN = '<temporary-user-token-with-administer-project>'
.\scripts\sonar\configure-online-library-new-code.ps1
Remove-Item Env:\SONAR_ADMIN_TOKEN
```

The helper never stores the token. Revoke the temporary administrative token after the setting is verified in **Project Settings > New Code**.

Do not make the Jenkins Quality Gate blocking yet. Observe several builds first, then agree on a new-code coverage target and hotspot-review policy.

## Security-hotspot review

Open **Online Library > Security Hotspots** and review each of the three findings individually.

For every hotspot, record:

- rule and source location;
- data entering the sensitive operation;
- authentication and authorization boundary;
- input validation, escaping, or parameterization;
- runtime exposure and compensating controls;
- final decision and evidence.

Use **Safe** only when the implementation and its operating context make exploitation implausible. Use **Fixed** only after changing and retesting the code. Do not bulk-classify findings merely to make the dashboard green.

The reviewer needs **Administer Security Hotspots**. The reporting service account does not need that permission.

## Pilot exit criteria

Online Library is stable enough for the next module when one complete Jenkins run shows all of the following:

- repository and API tests pass;
- `coverage.xml` and `pytest.xml` are imported;
- `sonar-summary.tsv` has an analysis date and revision without HTTP 403;
- the Quality Gate is reported but remains advisory;
- the three hotspots have documented review decisions;
- deployment and three-image retention cleanup succeed.

After those criteria are met, onboard only one additional module. `rag-search-service` is the recommended next pilot because it already has a meaningful automated test suite and exercises a different project structure.
