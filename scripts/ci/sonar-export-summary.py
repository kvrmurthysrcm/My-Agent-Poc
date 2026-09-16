import csv
import json
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


MODULES = [
    ("ingest", "my-agent-poc-rag-ingest"),
    ("search", "my-agent-poc-rag-search"),
    ("answer", "my-agent-poc-rag-answer"),
    ("library", "my-agent-poc-online-library"),
    ("mcp", "my-agent-poc-online-library-mcp"),
    ("library-agent", "my-agent-poc-online-library-agent"),
    ("weather", "my-agent-poc-weather-agent"),
    ("weather-ai", "my-agent-poc-weather-ai-agent"),
    ("secure", "my-agent-poc-secure-api"),
    ("angular", "my-agent-poc-angular-ui"),
]

FIELDS = [
    "build_number", "git_commit", "service", "project_key",
    "selected_for_build", "sonar_enabled", "analyzed_this_build",
    "analysis_status", "metrics_source", "quality_gate", "reliability_rating",
    "security_rating", "maintainability_rating", "security_hotspots",
    "coverage_percent", "new_coverage_percent", "duplicated_lines_percent",
    "new_duplicated_lines_percent", "lines_of_code", "tests",
    "test_failures", "test_errors", "skipped_tests",
    "test_execution_time_ms", "analysis_date", "analysis_revision",
    "build_reference", "dashboard_url", "history_url", "recommendation",
]

METRICS = [
    "alert_status", "reliability_rating", "security_rating", "sqale_rating",
    "security_hotspots", "coverage", "new_coverage",
    "duplicated_lines_density", "new_duplicated_lines_density", "ncloc",
    "tests", "test_failures", "test_errors", "skipped_tests",
    "test_execution_time",
]


def env(name, default=""):
    return os.environ.get(name, default)


def api_get(path, params):
    base = env("SONAR_HOST_URL", "http://sonarqube:9000").rstrip("/")
    url = f"{base}{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": (
                f"Bearer {env('SONAR_REPORT_TOKEN') or env('SONAR_TOKEN')}"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def rating(value):
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return value or ""
    return {1: "A", 2: "B", 3: "C", 4: "D", 5: "E"}.get(number, str(number))


def base_row(service, project_key, selected):
    public_url = env("SONAR_PUBLIC_URL", "http://localhost:9000").rstrip("/")
    row = {field: "" for field in FIELDS}
    row.update(
        build_number=env("BUILD_NUMBER", "local"),
        git_commit=env("GIT_COMMIT", "unknown"),
        service=service,
        project_key=project_key,
        selected_for_build=str(selected).lower(),
        sonar_enabled=str(service == "library").lower(),
        analyzed_this_build="false",
        analysis_status="NOT_CONFIGURED" if service != "library" else "NOT_SELECTED",
        build_reference=f"jenkins-{env('BUILD_NUMBER', 'local')}",
        dashboard_url=f"{public_url}/dashboard?id={project_key}",
        history_url=f"{public_url}/project/activity?id={project_key}",
        recommendation=(
            "Create the SonarQube project and onboard this module in a future release."
            if service != "library"
            else "The module was unchanged, so this build did not analyze it."
        ),
    )
    return row


def add_local_test_metrics(row):
    report_dir = "/usr/src/modules/online_library/.ci-reports"
    sources = []
    try:
        coverage_root = ET.parse(f"{report_dir}/coverage.xml").getroot()
        line_rate = coverage_root.attrib.get("line-rate")
        if line_rate and not row["coverage_percent"]:
            row["coverage_percent"] = f"{float(line_rate) * 100:.2f}"
            sources.append("LOCAL_COVERAGE_XML")
    except (OSError, ET.ParseError, ValueError):
        pass

    try:
        junit_root = ET.parse(f"{report_dir}/pytest.xml").getroot()
        suites = [junit_root] if junit_root.tag == "testsuite" else list(junit_root.findall("./testsuite"))
        totals = {name: 0.0 for name in ("tests", "failures", "errors", "skipped", "time")}
        for suite in suites:
            for name in totals:
                totals[name] += float(suite.attrib.get(name, "0") or "0")
        mapping = {
            "tests": "tests",
            "failures": "test_failures",
            "errors": "test_errors",
            "skipped": "skipped_tests",
        }
        for source, target in mapping.items():
            if not row[target]:
                row[target] = str(int(totals[source]))
        if not row["test_execution_time_ms"]:
            row["test_execution_time_ms"] = str(int(round(totals["time"] * 1000)))
        sources.append("LOCAL_JUNIT_XML")
    except (OSError, ET.ParseError, ValueError):
        pass

    if sources:
        existing = row["metrics_source"]
        row["metrics_source"] = "+".join(([existing] if existing else []) + sources)
    return row


def enrich_library(row):
    project_key = row["project_key"]
    scanner_status = env("SONAR_SCANNER_STATUS", "ATTENTION_REQUIRED")
    row["analysis_status"] = scanner_status
    row["recommendation"] = env(
        "SONAR_RECOMMENDATION",
        "Review the scanner log and SonarQube dashboard.",
    )
    api_warnings = []
    try:
        measure_data = api_get(
            "/api/measures/component",
            {"component": project_key, "metricKeys": ",".join(METRICS)},
        )
        measures = {
            item["metric"]: item.get("value", "")
            for item in measure_data.get("component", {}).get("measures", [])
        }
        row["metrics_source"] = "SONAR_API"
        row.update(
            quality_gate={"OK": "PASSED", "ERROR": "FAILED"}.get(
                measures.get("alert_status", ""), measures.get("alert_status", "")
            ),
            reliability_rating=rating(measures.get("reliability_rating", "")),
            security_rating=rating(measures.get("security_rating", "")),
            maintainability_rating=rating(measures.get("sqale_rating", "")),
            security_hotspots=measures.get("security_hotspots", ""),
            coverage_percent=measures.get("coverage", ""),
            new_coverage_percent=measures.get("new_coverage", ""),
            duplicated_lines_percent=measures.get("duplicated_lines_density", ""),
            new_duplicated_lines_percent=measures.get("new_duplicated_lines_density", ""),
            lines_of_code=measures.get("ncloc", ""),
            tests=measures.get("tests", ""),
            test_failures=measures.get("test_failures", ""),
            test_errors=measures.get("test_errors", ""),
            skipped_tests=measures.get("skipped_tests", ""),
            test_execution_time_ms=measures.get("test_execution_time", ""),
        )
    except Exception as exc:
        api_warnings.append(f"measures API: {type(exc).__name__}: {exc}")

    try:
        history_data = api_get(
            "/api/project_analyses/search",
            {"project": project_key, "ps": "1"},
        )
        latest = (history_data.get("analyses") or [{}])[0]
        row.update(
            analysis_date=latest.get("date", ""),
            analysis_revision=latest.get("revision", ""),
        )
        current_commit = env("GIT_COMMIT")
        row["analyzed_this_build"] = str(
            bool(current_commit) and latest.get("revision") == current_commit
        ).lower()
        if row["analyzed_this_build"] == "true":
            row["analysis_status"] = "SUCCESS"
            if row["quality_gate"] == "FAILED":
                row["recommendation"] = (
                    "Analysis completed; review failed Quality Gate conditions before enforcement."
                )
            else:
                row["recommendation"] = (
                    "Review issues, hotspots, coverage, duplication, and historical trends."
                )
    except Exception as exc:
        api_warnings.append(f"history API: {type(exc).__name__}: {exc}")

    if scanner_status == "SUCCESS":
        row["analysis_status"] = "SUCCESS"
        row["analyzed_this_build"] = "true"
        if not row["quality_gate"]:
            row["quality_gate"] = "PASSED"

    row = add_local_test_metrics(row)
    if api_warnings:
        warning = "; ".join(api_warnings).replace("\t", " ").replace("\n", " ")
        row["recommendation"] = f"{row['recommendation']} Metrics note: {warning}"
    return row


def main():
    selected = {item for item in env("CI_SERVICES").split(",") if item}
    rows = []
    for service, project_key in MODULES:
        row = base_row(service, project_key, service in selected)
        if service == "library" and service in selected:
            row = enrich_library(row)
        rows.append(row)

    writer = csv.DictWriter(
        sys.stdout,
        fieldnames=FIELDS,
        dialect="excel-tab",
        lineterminator="\n",
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(rows)


if __name__ == "__main__":
    main()
