## ADDED Requirements

### Requirement: Conversational assistant surface

The system SHALL expose a chat interface associated with a task where authenticated users MUST be able to request explanations, scaffolding, or modifications relevant to Crawlee-based Python crawl tasks.

#### Scenario: User opens assistant for a task

- **WHEN** an authenticated user opens the assistant panel while editing a task
- **THEN** the system MUST display the conversation scoped to that task and MUST load prior messages for that task if persistence is enabled

#### Scenario: User sends a message

- **WHEN** an authenticated user submits a natural-language message
- **THEN** the system MUST forward the message to the configured model provider service and MUST append the assistant reply to the visible thread when available

### Requirement: Human-in-the-loop apply for generated code

The system SHALL NOT directly overwrite saved task source from an assistant reply without an explicit user confirmation action that applies a proposed code change.

#### Scenario: Assistant proposes code

- **WHEN** the assistant response includes a proposed code change block
- **THEN** the system MUST present the proposal with a distinct **Apply** or equivalent confirmation control separate from ordinary chat scrolling

#### Scenario: User declines proposal

- **WHEN** an authenticated user dismisses or ignores a proposed code change
- **THEN** the system MUST leave persisted task versions unchanged

#### Scenario: User applies proposal

- **WHEN** an authenticated user confirms apply for a proposed change
- **THEN** the system MUST insert or replace editor content according to the platform-defined merge rules and MUST create a new saved task version or staged draft consistent with editor rules

### Requirement: Audit metadata for AI interactions

The system SHALL persist for each assistant turn at minimum the timestamp, acting user identifier, model identifier when available, and a stable correlation identifier linking chat to any resulting saved versions.

#### Scenario: Review after apply

- **WHEN** an operator audits changes to a task
- **THEN** the system MUST expose that a version was created following an assistant apply action and MUST link to the correlated chat turn identifiers
