## ADDED Requirements

### Requirement: Agent-facing authority is grounded in represented relationships
The system SHALL permit an agent-facing authoritative relationship conclusion only for a represented catalog-conformant canonical semantic relationship or trusted cross-graph projection with complete resolvable evidence/provenance and, for a cross-graph projection, qualifying classified support and an explicit trusted lifecycle decision. It SHALL NOT turn repository/service naming conventions, textual similarity, prompt context, LLM guesses, confidence labels, PR/file observations, or an absent edge into an authoritative relationship. A related name or contextual hint SHALL NOT substitute for a graph relationship or an evidence path. Existing non-confident `REFERENCES` and candidate `TOUCHES` SHALL remain non-authoritative for implementation conclusions.

#### Scenario: Similar names do not make traceability
- **WHEN** a requirement, service and repository have similar names but no admitted relationship with supporting evidence between them
- **THEN** an agent-facing result reports no authoritative link and no implementation owner derived from those names

#### Scenario: Prompt or inference cannot override graph authority
- **WHEN** an agent proposes a relationship from prompt context or an LLM guess, or the graph has only inferred support for an implementation candidate
- **THEN** no authoritative relationship is created or returned from that proposal
- **THEN** any represented inferred support remains identifiable as inferred and non-authoritative for implementation

### Requirement: Evidence-use disposition preserves unresolved information
For each agent-facing relationship/support considered for an authoritative conclusion, the system SHALL expose whether that specific conclusion is `supported` or `unresolved`, with safe reason codes and referenced graph IDs. Absent or unresolvable support SHALL yield `unresolved` with `unknown`; explicitly stale support SHALL be identifiable as `stale`; an unresolved canonical assertion conflict SHALL be `conflicting`; a candidate lifecycle SHALL be `candidate`; inferred support SHALL be `inferred`. More than one reason SHALL be retained when applicable; no precedence, count, confidence, lexical order, or prompt context SHALL resolve these reasons into authority. `unknown` freshness (including no checked revision) SHALL NOT be relabeled `stale` or `fresh`. Historical stored trust/lifecycle and as-of freshness SHALL remain visible independently: stale/unknown freshness prevents a **current-required** conclusion, not a rewrite of the historical graph.

A represented `TOUCHES` relationship that is both a candidate and part of an unresolved canonical assertion conflict SHALL retain both `candidate` and `conflicting` in its evidence-use reason codes. Reason codes SHALL be duplicate-free and lexically sorted, retaining any other applicable reasons; when only those two reasons apply, the output SHALL be `["candidate", "conflicting"]`. The conclusion SHALL remain `unresolved` and SHALL NOT gain authority or select a conflict winner. This rule applies when the existing non-validating traceability display exposes represented assertions; it SHALL NOT bypass merge rejection or validation-required safe diagnostics/no-partial-success behavior.

#### Scenario: Missing evidence stays unknown
- **WHEN** a requested relationship has no supporting represented edge or its required provenance cannot be resolved
- **THEN** its conclusion is `unresolved` with an `unknown` reason and no fabricated evidence path

#### Scenario: Stale and uncheckable support are distinct
- **WHEN** one support chain has a checked mismatching revision and another has no matching checked revision
- **THEN** they retain `stale` and `unknown` freshness respectively
- **THEN** neither passes a request that explicitly requires current evidence; historical stored trust is not altered

#### Scenario: Conflict, candidate and inference stay visible
- **WHEN** an assertion conflict is unresolved, a cross-graph claim is still a candidate, or its support is inferred
- **THEN** the affected conclusion is `unresolved` with the applicable `conflicting`, `candidate`, or `inferred` reason and safe existing references where available
- **THEN** it does not choose a conflict winner or promote the candidate/inference

#### Scenario: Candidate TOUCHES retains its conflict reason as well
- **WHEN** non-validating traceability displays represented candidate `TOUCHES` assertions in an incompatible same-ID canonical assertion cohort, with complete support and no other applicable evidence-use reasons
- **THEN** each affected candidate relationship has disposition `unresolved` and reason codes `["candidate", "conflicting"]`, with safe existing graph references
- **THEN** repeated queries and reversal of the assertion input order preserve that disposition and ordered reason-code list; no candidate gains authority and no conflict winner is selected
- **THEN** a validation-required call on that invalid graph still returns the existing safe diagnostic with no partial success

### Requirement: Critical conclusions require a traversable evidence path
For a caller-requested `implementation_ownership` or `change_readiness` conclusion, the system SHALL return a `supported` conclusion only if an existing approved graph contract can establish it, every required directed relationship is represented and eligible, and the response contains an explainable path of relationship/claim IDs, evidence IDs, provenance IDs and applicable lifecycle/trust and as-of freshness dispositions. A required missing, conflicting, candidate or inferred-only step SHALL produce `unresolved` and identify the failing step without inventing a replacement path. A direct `OWNED_BY` assertion for a represented service or repository SHALL explain ownership of that subject only when fully supported; it SHALL NOT be extrapolated to a code locator, change, PR or similarly named service. No approved change-readiness decision contract exists in the current graph: the system SHALL return `unresolved`/`unknown` for a readiness request rather than infer ready/not-ready from tests, merged PRs, freshness, name matching or prompt text. It SHALL not treat a merely available graph path as a readiness decision.

#### Scenario: Direct ownership has an explainable path
- **WHEN** a represented service or repository has a catalog-valid directed `OWNED_BY` edge to the requested owner, with complete resolvable evidence/provenance and no conflicting assertion, and a caller requests ownership for that same subject
- **THEN** the result is `supported` for that direct ownership only and returns the directed edge and its evidence/provenance IDs

#### Scenario: Missing ownership path fails closed
- **WHEN** a caller requests implementation ownership for a change or code locator using only a repository's name or a PR's changed files
- **THEN** the result is `unresolved`/`unknown`, with no inferred owner or fabricated edge path

#### Scenario: Readiness is not inferred from adjacent evidence
- **WHEN** a change has related test facts, a merged PR, or fresh evidence but no approved readiness decision contract and evidence path
- **THEN** the answer is `unresolved`/`unknown`, not `ready` or `not-ready`

### Requirement: Evidence-use verification matrix bounds this revision
The change SHALL exercise the named tests and observable assertions below at their applicable local-query and MCP boundaries. Other adversarial cases are change candidates unless they violate another approved requirement or applicable baseline.

| Named test / input class | Observable assertion | Anchor |
| --- | --- | --- |
| `test_similar_names_no_authority`: similar service/repo/requirement names, no graph edge | No authoritative relationship or owner; missing traceability stays empty/unresolved | EKG-64 criterion 1; local-ekg-query-api represented-only baseline |
| `test_prompt_guess_no_authority`: caller-proposed text/LLM-only inferred support | No promotion; inferred support remains labeled, implementation unresolved | EKG-64 criterion 1; EKG-41 implementation trust boundary |
| `test_missing_support_unknown`: absent edge or broken evidence/provenance reference | `unresolved`/`unknown`, empty path; required validation produces existing safe graph diagnostic instead of partial success | EKG-64 criteria 2, 4; fact-provenance baseline |
| `test_stale_and_unchecked_current_required`: checked mismatch vs absent check | `stale` vs `unknown` as-of; both fail current-required check, no change to stored trust | EKG-64 criterion 2; EKG-43 freshness/current-required baseline |
| `test_conflict_no_winner`: incompatible same-ID assertions | `conflicting`/unresolved or existing merge/validation error; no selected authority | EKG-64 criterion 2; conflict-aware-graph-merge baseline |
| `test_candidate_not_authoritative`: candidate `TOUCHES`/`IMPLEMENTS` | `candidate`/unresolved for authoritative implementation; retained support | EKG-64 criterion 2; EKG-41 and relationship catalog |
| `test_candidate_touches_conflict_retains_both_reasons`: represented candidate `TOUCHES` assertions in an incompatible same-ID cohort, complete support; repeat and reverse assertion order | Non-validating local traceability and its registered fake/local MCP forwarding retain `unresolved` with exactly `["candidate", "conflicting"]` when no other reasons apply, and safe existing references; no authority or conflict winner. Validation-required calls retain safe error/no partial result; no conflicting graph is admitted or persisted. Non-conflicting candidate `TOUCHES` retains its existing `candidate`-only disposition | Approved EKG-64 revision; criterion 2; multiple-reason requirement; EKG-41/catalog candidate boundary; conflict-aware-graph-merge baseline |
| `test_inferred_not_authoritative`: inferred-only claim with high confidence | `inferred`/unresolved; no trusted implementation | EKG-64 criteria 1, 2; EKG-41 trust model |
| `test_direct_ownership_path`: complete direct `OWNED_BY` of service/repository | `supported` for same subject only, with edge/evidence/provenance IDs; no extrapolation | EKG-64 criterion 3; canonical relationship catalog |
| `test_readiness_without_contract`: change with adjacent PR/test/freshness but no readiness policy | `unresolved`/`unknown`; never `ready`/`not-ready` | EKG-64 criterion 3; EKG-43 explicit non-goal |
| `test_e2e_missing_evidence`: fixture persisted snapshot queried through local API and FactMCP | No fabricated traceability; absent support returns `unknown`/unresolved and no invented path | EKG-64 criterion 4; existing MCP local-first baseline |

#### Scenario: Matrix is executable
- **WHEN** tests exercise every named matrix row using local fixtures and a fake or local MCP boundary
- **THEN** each row asserts the documented status, evidence-path shape and absence of fabricated authority without requiring live external infrastructure
