## ADDED Requirements

### Requirement: Task list and navigation

The system SHALL present a console navigation structure that includes access to tasks, individual task detail, and run history scoped to the authenticated principal.

#### Scenario: Operator opens console home

- **WHEN** an authenticated user opens the console home view
- **THEN** the system MUST display a list or searchable catalog of crawl tasks belonging to that principal

#### Scenario: Operator opens a task

- **WHEN** an authenticated user selects a task from the catalog
- **THEN** the system MUST navigate to that task's detail view showing task metadata and entry actions for editing and runs

### Requirement: Run history presentation

The system SHALL display a chronological list of runs for a task with sortable columns including status, start time, duration, and environment class (for example debug versus production).

#### Scenario: User views run list

- **WHEN** an authenticated user views the runs panel for a task
- **THEN** the system MUST list all runs visible to that principal for that task with their terminal status

#### Scenario: User opens a single run

- **WHEN** an authenticated user selects a run from the list
- **THEN** the system MUST show run summary fields and an affordance to open live or historical logs for that run

### Requirement: Responsive layout for primary workflows

The system SHALL provide layouts that remain usable on common desktop widths for code editing with adjacent log panels without destructive overlap of primary controls.

#### Scenario: Desktop editor layout

- **WHEN** an authenticated user uses a viewport width of at least 1280 CSS pixels on the task editor screen
- **THEN** the system MUST show the editor and logs or run controls in a multicolumn layout that preserves editor usability
