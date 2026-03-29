## ADDED Requirements

### Requirement: Run-centric status model

The system SHALL represent each run with a finite state machine including at least queued, running, succeeded, failed, cancelled, and limit-exceeded terminal states, visible in the console without requiring direct cluster access.

#### Scenario: Status transitions visible

- **WHEN** a run transitions from queued to running and then to succeeded
- **THEN** the console MUST reflect each state change with timestamps recorded by the control plane

#### Scenario: Failure visibility

- **WHEN** a run ends in failed status
- **THEN** the console MUST display an error summary field populated from the worker or control plane and MUST link to log details

### Requirement: Platform health and throughput indicators

The system SHALL expose in the console an overview or dashboard showing worker availability or heartbeat, recent run success ratio, and a backlog or queue depth metric when job queuing is enabled.

#### Scenario: Operator opens monitoring view

- **WHEN** an authenticated operator opens the platform monitoring or overview page
- **THEN** the system MUST display at least one freshness-indicated widget for worker health and at least one widget summarizing recent run outcomes

#### Scenario: Stale data indication

- **WHEN** underlying metrics have not updated beyond an operator-configured staleness interval
- **THEN** the console MUST indicate that metrics are stale or unavailable

### Requirement: Exportable metrics hooks

The API or worker processes SHALL expose machine-readable metrics compatible with Prometheus text exposition or OpenTelemetry such that external monitoring stacks MAY scrape the same signals used for console aggregates.

#### Scenario: Metrics endpoint availability

- **WHEN** metrics exposure is enabled in a deployment
- **THEN** operators MUST be able to configure Prometheus or compatible scrapers against a documented HTTP path or OTLP receiver without parsing application logs
