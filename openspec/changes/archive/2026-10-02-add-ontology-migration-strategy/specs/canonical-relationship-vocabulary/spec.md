## MODIFIED Requirements

### Requirement: Relationship verification matrix bounds admission testing
The change SHALL document and test the following verification matrix: catalog kind with permitted ordered endpoints and complete provenance is admitted; catalog kind with reversed/disallowed endpoints is rejected; two `OWNED_BY` targets for one source are rejected; relationship kinds outside the current canonical vocabulary are rejected at current-format and in-memory admission; OpenSpec hierarchy, traceability support, related metadata, and PR changed-symbol observations are mapped as specified; candidate, rejected, and superseded claims are not trusted; and only an explicitly trusted, catalog-conformant claim is projected as trusted. A version-scoped persisted-snapshot migration may convert a retired relationship only when its registered source descriptor, deterministic mapping, complete retained identity/provenance data, and target catalog validation are all satisfied. It SHALL reject rather than guess a legacy alias, reversed direction, endpoint, mapping, or trust classification outside that approved migration. The EKG-38 greenfield compatibility exclusion is superseded for persisted-snapshot migration by Plane task `EKG-66`; other cases outside this matrix remain change candidates unless another approved requirement or baseline is violated.

#### Scenario: Matrix cases are executable
- **WHEN** the relationship and persisted-snapshot migration test suites run the approved matrix cases
- **THEN** every current-format admission case and version-scoped migration case has the documented outcome

#### Scenario: Current admission does not accept a legacy relationship
- **WHEN** a caller supplies a retired, aliased, or reversed relationship outside an approved migration input document
- **THEN** canonical admission rejects it with a deterministic vocabulary or endpoint-contract diagnostic
- **THEN** it does not convert the relationship merely because a migration for another source version exists

#### Scenario: Ambiguous legacy relationship is not migrated
- **WHEN** a supported migration source document contains a legacy relationship whose retained data cannot establish the registered direction, endpoint contract, or relationship meaning
- **THEN** migration rejects the complete snapshot with a deterministic compatibility or integrity diagnostic
- **THEN** no replacement snapshot contains a guessed relationship
