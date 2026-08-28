## ADDED Requirements

### Requirement: PR-derived observations remain observed candidates, not implementation truth
The system SHALL represent a candidate emitted from an explicitly linked PR changed-symbol mapping as observed-provenance cross-graph evidence with a lifecycle state of `candidate`. It SHALL not create an `Edge` of kind `IMPLEMENTS`, expose a trusted semantic link, or otherwise promote the claim to `trusted` solely because the PR is merged, explicitly linked, or changed the resolved symbol. Promotion, rejection, and supersession SHALL remain independent lifecycle actions supported by separately supplied evidence.

#### Scenario: Merged PR candidate is not trusted
- **WHEN** PR code-candidate extraction emits a claim and observation from an explicitly linked merged PR changed-symbol mapping
- **THEN** the claim's current lifecycle state is `candidate`
- **THEN** the graph has no trusted cross-graph link or `IMPLEMENTS` edge created solely from that extraction

#### Scenario: Independent lifecycle evidence can later change the outcome
- **WHEN** a separately supplied valid lifecycle revision promotes, rejects, or supersedes a PR-derived candidate with its own provenance evidence
- **THEN** the graph applies that explicit lifecycle revision according to the existing lifecycle contract
- **THEN** the original PR-derived observation remains retained for audit
