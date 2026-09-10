## ADDED Requirements

### Requirement: PR implementation-evidence relationship mappings distinguish declaration from observation
The relationship catalog SHALL define the directed `PULL_REQUEST REFERENCES OPENSPEC_ACTIVE_CHANGE|OPENSPEC_ARCHIVED_CHANGE|JIRA_STORY` mapping as a declared explicit-association relation and the directed `PULL_REQUEST TOUCHES REPOSITORY` mapping as an observed revision-evidence relation. It SHALL permit an `OPENSPEC_ACTIVE_CHANGE`, `OPENSPEC_ARCHIVED_CHANGE`, or `JIRA_STORY` subject to carry an observed candidate `TOUCHES` cross-graph claim to a complete `CodeLocator`. The catalog revision SHALL advance with these mapping and endpoint changes and persistence SHALL admit only that current revision; no prior catalog mapping is converted or migrated. No PR mapping in this capability SHALL emit `IMPLEMENTS`, and unsupported/reversed endpoint pairs SHALL be rejected with deterministic diagnostics.

#### Scenario: Declared and observed PR relations use their distinct catalog mappings
- **WHEN** valid PR implementation evidence is associated explicitly with an active OpenSpec change, archived OpenSpec change, or Jira work item and references one repository
- **THEN** the graph admits the directed declared `REFERENCES` association and observed `TOUCHES` repository relation
- **THEN** a resolved symbol observation may produce only the catalog-valid observed candidate `TOUCHES` claim for that same intended-change scope

#### Scenario: PR evidence cannot use an implementation mapping
- **WHEN** a PR association, repository revision record, or changed-symbol observation requests `IMPLEMENTS`, a reversed endpoint order, or an unsupported intended-change kind
- **THEN** relationship admission returns a deterministic catalog diagnostic
- **THEN** it emits no semantic implementation edge or trusted implementation projection
