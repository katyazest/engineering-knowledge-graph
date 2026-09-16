## ADDED Requirements

### Requirement: Reliable test-to-code observations remain observed non-implementation candidates
The cross-graph evidence model SHALL retain a normalized reliable test-to-code resolution produced with the `reliable-test-code-resolution` strategy only as an attributable `REFERENCES` claim from an existing mapped `TEST_CASE` to a complete `CodeLocator`, with observed origin, untrusted disposition, complete source evidence/provenance, and an explicit `candidate` lifecycle. It SHALL retain the resolution's payload-safe strategy and observation identities without changing test, OpenSpec target, or claim identity. It SHALL reject a test-to-code observation using that strategy when it is incomplete, unprovenanced, unscoped to a mapped test, uses a relation other than `REFERENCES`, requests a trusted lifecycle/projection, or requests `IMPLEMENTS`; it SHALL not use the observation count, confidence, declared mapping, test execution, or resolver name to promote the claim. Existing catalog-valid cross-graph records from other sources remain governed by their existing contracts.

#### Scenario: Reliable test-code observation is auditable but not implementation truth
- **WHEN** a complete observed candidate references an admitted mapped test case and exact code locator with its evidence/provenance and candidate lifecycle
- **THEN** merge, persistence, and query retain the candidate and its attribution deterministically
- **THEN** no trusted semantic link or `IMPLEMENTS` conclusion is exposed from that observation

#### Scenario: Test-code promotion attempt is rejected
- **WHEN** test-to-code input requests `IMPLEMENTS`, trusted support/lifecycle, a non-candidate lifecycle, or lacks the required mapped-test scope and provenance
- **THEN** admission or validation rejects it with a deterministic candidate-boundary diagnostic
- **THEN** it emits no trusted implementation projection or replacement candidate
