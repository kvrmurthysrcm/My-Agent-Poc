# My-Agent-Poc CI/CD Parallel Workers Release

- Date: 2026-09-15
- Time: 12:42:53 EDT (UTC-04:00)
- Purpose: reduce full-pipeline elapsed time by running up to two independent service workers concurrently while preserving test isolation, dependency-safe Kubernetes rollout order, failure handling, diagnostics, and the three-image retention policy.
- Release type: Jenkins CI/CD performance and reliability update
- Default concurrency: 2 workers
- Supported configured concurrency: 1 through 4 workers

## Summary

The pipeline previously processed every selected service in one sequential loop. A full ten-service build therefore accumulated every Docker build, test execution, image import, manifest application, and Kubernetes rollout wait into a single approximately 35-minute critical path.

This release introduces bounded parallel service execution. Build and test work is completed first for every selected service. Kubernetes deployment begins only if the entire build/test phase succeeds. Deployment then proceeds in dependency-aware waves, with up to the configured number of services running concurrently inside each wave.

## Changed files

### `Jenkinsfile`

- Added the `MAX_PARALLEL_SERVICES` Jenkins choice parameter.
- Set the default choice to `2` workers.
- Exposed safe choices of `1`, `2`, `3`, and `4` workers.
- Added preflight validation for the new service worker script.
- Added preflight checks for `xargs` and `flock`, which provide bounded execution and shared-database test locking.
- Added a visible log message showing the concurrency selected for each run.
- Retained `disableConcurrentBuilds()` so separate Jenkins runs cannot modify the same Docker daemon and Kubernetes namespace simultaneously.
- Kept the Jenkinsfile compact; the service orchestration remains in shell scripts to avoid recurrence of the Jenkins Groovy CPS `MethodTooLargeException`.

### `scripts/ci/build-test-deploy.sh`

- Replaced the sequential service loop with a bounded parallel coordinator.
- Reads `MAX_PARALLEL_SERVICES`, defaulting to `2` when invoked outside Jenkins.
- Rejects invalid worker counts and unknown service identifiers before starting work.
- Runs all selected test-target builds, tests, and runtime-image builds before starting deployment.
- Prevents deployment from starting when any selected test target or runtime image fails to build, or when any test suite fails.
- Uses null-delimited service arguments with `xargs -0` so worker dispatch remains safe and predictable.
- Uses `xargs -P` to enforce the configured maximum instead of launching every service simultaneously.
- Invokes workers with the coordinator's current Bash executable, avoiding shell-path ambiguity on hosts that expose more than one `bash` command.
- Introduced dependency-aware deployment waves:
  1. Foundation services: ingest, search, online library, weather, and secure API.
  2. Direct dependents: answer, online-library MCP, and weather AI agent.
  3. Online-library agent, after the MCP rollout.
  4. Angular UI, after backend rollout waves.
- Waits for all deployments in one wave to become ready before starting the next wave.
- Preserves selective CI/CD: only services selected by `detect-changes.sh` are dispatched.

### `scripts/ci/service-worker.sh`

- Added a dedicated single-service worker used by the parallel coordinator.
- Supports separate `build-test` and `deploy` actions. The first action builds the test target, executes tests, and builds the final runtime image; the second imports and rolls out that prebuilt image.
- Preserves the existing Dockerfiles, build contexts, Kubernetes manifests, deployment names, rollout timeouts, test modes, and test environment variables for all ten services.
- Prefixes every output line with the action and service identifier so concurrent Jenkins logs remain readable.
- Uses unique service-specific Docker image and test-container names.
- Continues collecting JUnit XML under service-specific `test-results` directories.
- Explicitly propagates container-test exit codes through the worker so a failed test blocks runtime-image creation and prevents the deployment phase.
- Retains exit traps that remove interrupted or failed test containers and temporary test images.
- Serializes only the ingest and search container test executions with `flock`. Those suites share `online_library_test` and both drop/recreate database tables; running them simultaneously could otherwise cause intermittent test corruption. Docker builds for those services may still run concurrently.
- Creates the lock-file parent directory when needed, allowing the worker to run safely both inside Jenkins and from a local shell with a custom workspace path.
- Verifies that each expected runtime image exists before importing it into the Kubernetes node.
- Keeps Docker runtime builds, image imports, manifest applications, and rollout waits isolated per service.

## Reliability and failure behavior

- A build/test failure prevents the deployment phase from starting.
- Parallel build/test workers already in progress are allowed to finish, producing complete logs and JUnit results for the run.
- A deployment failure stops later dependency waves.
- Existing successful deployments are not removed or rolled back automatically.
- The Jenkins failure diagnostics remain active.
- The always-run cleanup remains active after success or failure.

## Image retention and cache behavior

- The existing cleanup policy remains unchanged: at most three runtime CI image tags are retained per service.
- The currently deployed image is protected from deletion.
- Temporary `test-*` images are removed after use and by final cleanup if an interruption leaves one behind.
- Recent BuildKit layers are preserved because builder-cache pruning targets entries older than 24 hours.
- Parallel workers share the same local Docker BuildKit cache, so unchanged dependency layers can be reused across later builds.

## Configuration guidance

- `2` workers is the recommended default for a Jenkins controller using a shared Docker Desktop and local Kubernetes environment.
- Use `1` to troubleshoot resource pressure or compare behavior with the previous sequential pipeline.
- Consider `3` only when Docker has sufficient CPU and memory and the host remains responsive during a full run.
- Use `4` cautiously; excessive concurrency can increase elapsed time through CPU, memory, disk, or Docker daemon contention.
- The parameter limits parallel service work inside one Jenkins run. It does not permit multiple Jenkins runs concurrently because `disableConcurrentBuilds()` remains enabled intentionally.

## Expected performance

Actual results depend on Docker cache state, test duration, image size, host resources, and Kubernetes readiness time. With two workers, a full cached build is expected to improve materially over the previous sequential run. Cold dependency installation and database-backed tests will still dominate some builds, while ordinary module-specific commits continue to benefit from selective service detection.

## Validation performed

- Parsed both CI shell scripts with `bash -n` successfully.
- Confirmed an invalid worker count exits with status `2` before any build begins.
- Confirmed an invalid worker action exits with status `2`.
- Ran a ten-service smoke simulation with stubbed Docker and Kubernetes commands.
- Confirmed the build/test phase dispatched no more than two workers concurrently.
- Confirmed runtime images were built before the first deployment wave.
- Confirmed foundation, direct-dependent, library-agent, and Angular deployment waves ran in order.
- Confirmed output lines carried action/service prefixes during concurrent execution.
- Injected a simulated service build failure and confirmed the coordinator returned non-zero without emitting or starting any deployment wave.
- Live Docker and Kubernetes execution remains the responsibility of the Jenkins environment because the release validation intentionally did not alter the running local cluster.

## Rollback

To restore strictly sequential execution without reverting files, choose `1` for `MAX_PARALLEL_SERVICES` when starting the Jenkins build. This provides an operational rollback while retaining the two-phase build/test-before-deploy safety behavior.
