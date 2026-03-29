## ADDED Requirements

### Requirement: Publishable worker container image

The system SHALL ship or build a documented Docker image that acts as the default execution environment for task runs, embedding a pinned Crawlee for Python installation appropriate to the platform release.

#### Scenario: Image build succeeds

- **WHEN** a maintainer runs the documented image build procedure for a tagged release
- **THEN** the build MUST produce an OCI image manifest with labels or metadata recording Crawlee version and platform version

#### Scenario: Image run contract

- **WHEN** a container is started with the required environment variables and mounted or fetched task bundle per documentation
- **THEN** the worker entrypoint MUST start the assigned run, emit structured logs to standard streams, and exit with a non-zero code on fatal task failure

### Requirement: Runtime isolation for user code

The worker container SHALL execute user task code as an unprivileged process without host filesystem mounts except explicitly defined ephemeral workspace paths, and SHALL not mount Docker socket or host network namespaces unless an operator override is documented as unsafe.

#### Scenario: Default isolation profile

- **WHEN** a production run is scheduled under the default profile
- **THEN** the container MUST run as a non-root user and MUST use a read-only root filesystem configuration when supported by the deployment target

### Requirement: Configuration via environment and secrets

The worker SHALL receive non-code configuration and secrets exclusively through environment variables or files injected by the orchestrator, not from user-editable task source for platform credentials.

#### Scenario: Secret injection

- **WHEN** a run requires an API token for an external integration provisioned by the platform
- **THEN** the worker MUST read that token from an operator-defined secret mount or environment key and the task source MUST NOT persist the raw token in saved versions when supplied this way
