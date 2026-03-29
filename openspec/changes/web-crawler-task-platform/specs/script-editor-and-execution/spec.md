## ADDED Requirements

### Requirement: In-browser code editing and versioning

The system SHALL provide an in-browser editor for Python task source that saves changes into versioned task revisions attributed to the acting user or session.

#### Scenario: User saves a new version

- **WHEN** an authenticated user edits task source and confirms save
- **THEN** the system MUST persist a new immutable task version and return its version identifier for subsequent runs

#### Scenario: User inspects prior version

- **WHEN** an authenticated user selects an older saved version from history
- **THEN** the system MUST load read-only content for that version with metadata including timestamp and author if available

### Requirement: Debug execution with constraints

The system SHALL allow starting a debug-class run that executes the selected task version under enforced concurrency, time, and network policy limits defined by the platform operator.

#### Scenario: Debug run starts

- **WHEN** an authenticated user triggers a debug run for a task version
- **THEN** the system MUST enqueue or start an isolated worker execution labeled as debug and associate it with a unique run identifier

#### Scenario: Debug run enforces limits

- **WHEN** a debug run exceeds operator-configured limits for wall time or resource usage
- **THEN** the system MUST terminate the run and record terminal status indicating limit exceeded

### Requirement: Production deployment and execution

The system SHALL allow promoting a task version to the production execution track and SHALL start production-class runs only from explicitly promoted or tagged versions.

#### Scenario: Promote version to production

- **WHEN** an authenticated user promotes a saved task version to production
- **THEN** the system MUST record that version as the production pointer for the task and MUST reject production starts unless a production pointer exists

#### Scenario: Start production run

- **WHEN** an authenticated user starts a production run
- **THEN** the system MUST execute the task at the current production version using production isolation policies and MUST bind the run record to that version identifier

### Requirement: Log streaming and historical logs

The system SHALL stream standard output and error lines for active runs to the UI and SHALL retain historical log segments addressable by run identifier for later inspection.

#### Scenario: Live logs during run

- **WHEN** an authenticated user views an active run's logs panel
- **THEN** the system MUST deliver new log lines in near real time using a push or streaming transport

#### Scenario: Logs after completion

- **WHEN** an authenticated user opens a completed run's logs
- **THEN** the system MUST retrieve and display the persisted log content associated with that run

### Requirement: Crawlee-backed worker execution

Production and debug worker processes SHALL execute user task entrypoints using the Crawlee for Python library as the primary crawling engine, compatible with the worker image's pinned Crawlee major version family.

#### Scenario: Worker executes task

- **WHEN** a worker picks up a run job for a task bundle
- **THEN** the worker MUST load the task entrypoint in its configured Python environment and MUST import and invoke Crawlee APIs expected by the platform contract for starting the crawl
