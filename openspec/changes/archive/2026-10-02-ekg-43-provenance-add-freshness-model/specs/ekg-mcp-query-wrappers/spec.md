## ADDED Requirements

### Requirement: Agent-facing query tools expose freshness through the local API
The existing FactMCP `list_requirements`, `list_services`, `list_changes`, and `get_traceability` tools SHALL return the local query API's additive per-support freshness and current-evidence eligibility fields. They SHALL optionally forward caller-supplied checked current-source revision observations to that API, with no wrapper-owned comparison, source resolution, or trust promotion. When no checked revision is supplied, the tools SHALL expose `unknown`, not an assumed fresh/stale result. Invalid checks SHALL return a structured payload-safe error with no partial success response. Tool schemas SHALL continue to exclude graph-store paths; existing invocations without the new optional input SHALL remain valid.

#### Scenario: Agent sees unknown by default
- **WHEN** an agent queries a fact through an existing tool without checked source revisions
- **THEN** the fact's represented evidence shows `unknown` freshness and ineligible current-evidence status without changing the existing fact fields

#### Scenario: Wrapper forwards checked revisions only
- **WHEN** a caller supplies valid checked authoritative revision observations with an existing tool request
- **THEN** the wrapper returns the local API's as-of freshness result for corresponding represented support
- **THEN** the wrapper does not fetch the source, compare revisions itself, or reinterpret stored trust

#### Scenario: Unsafe revision input does not leak
- **WHEN** a caller sends an invalid or conflicting checked-revision input
- **THEN** the wrapper returns a structured safe error and no partial results or source payloads
