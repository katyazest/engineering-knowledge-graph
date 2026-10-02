## Purpose

The `evidence-freshness` capability defines a pure, source-agnostic assessment of whether retained provenance observations are still current relative to authoritative source revisions checked by the caller, together with a fail-closed current-evidence eligibility decision.

## Requirements

### Requirement: Freshness compares an observation to a checked authoritative revision
The system SHALL assess an external provenance observation as `fresh` only when its complete retained source-artifact identity/revision and extraction metadata are valid and a caller-supplied, explicitly checked authoritative revision for the same logical artifact matches its extracted revision/version, with the check at or after the extraction observation. It SHALL assess it as `stale` when those revisions differ under the same ordering condition. The comparison SHALL use the source type, source identity, artifact type, and stable locator to identify the same logical artifact independently of revision, and SHALL report the status and the comparison's `checked_at` instant as an as-of assessment. It SHALL NOT treat a content hash, extractor version, observation age, or checked-at age as a substitute for a checked source revision, nor claim to have checked the external source itself.

#### Scenario: Matching checked revision
- **WHEN** valid external provenance has revision `r1` and an explicit checked authoritative revision for the same logical artifact is `r1`
- **THEN** the assessment is `fresh` as of that check's timestamp, with a revision-match basis

#### Scenario: Differing checked revision
- **WHEN** valid external provenance has revision `r1` and an explicit checked authoritative revision for the same logical artifact is `r2`
- **THEN** the assessment is `stale` as of that check's timestamp, with a revision-mismatch basis

### Requirement: Uncheckable evidence remains unknown
The system SHALL assess external provenance as `unknown` when a checked current revision is absent, unavailable, supplied only for a different logical artifact, or checked before that provenance observation. Internal evidence without external provenance SHALL also be `unknown`. An old observation time, a changed extraction time, a different extractor version, or a content hash without an authoritative revision comparison SHALL NOT by itself produce `stale` or `fresh`.

#### Scenario: Old observation without current revision
- **WHEN** complete external provenance has an old `observed_at` value but no matching checked current revision
- **THEN** its freshness is `unknown` with a no-check basis
- **THEN** it is not silently treated as stale or fresh

#### Scenario: Unrelated check cannot make evidence fresh
- **WHEN** the only checked revision belongs to another source identity or stable locator, even if its revision string matches
- **THEN** the evidence's freshness is `unknown`

#### Scenario: Check predates extraction
- **WHEN** a checked revision for the correct artifact has `checked_at` earlier than that provenance's `observed_at`
- **THEN** the evidence's freshness is `unknown` with a check-predates-observation basis rather than fresh or stale

### Requirement: Derived and multiply supported evidence propagate freshness without erasing support
The system SHALL assess a derived provenance chain as `stale` if any required transitive input is stale, `unknown` if none is stale and at least one required input is unknown, and `fresh` only if all required inputs are fresh. For one evidence record supported by multiple independent provenance chains, it SHALL be eligible as fresh if at least one complete chain is fresh; otherwise it SHALL be unknown if any chain is unknown and stale only if every chain is stale. Assessment SHALL retain the individual per-provenance statuses and references; it SHALL NOT overwrite provenance, collapse asserted and derived support, or infer currentness from a derived record's own timestamp or hash.

#### Scenario: Derived chain contains stale input
- **WHEN** derived provenance depends transitively on one stale external observation and one fresh observation
- **THEN** that derived chain assesses as `stale` and exposes its input statuses

#### Scenario: Fresh independent support remains usable
- **WHEN** an evidence record has one stale independent chain and another fresh independent chain
- **THEN** both chain statuses remain visible and the record has one fresh eligible chain

#### Scenario: Unknown input remains unknown
- **WHEN** a derived chain has only fresh and unknown inputs
- **THEN** its freshness is `unknown` and it cannot claim current evidence

### Requirement: Checked revision input is validated and assessment is deterministic
The system SHALL accept a checked-revision input only as a payload-safe complete logical source-artifact key, non-empty revision/version, and offset-aware ISO-8601 `checked_at` instant explicitly supplied as a checked authoritative-source observation by the caller. It SHALL reject malformed/unsafe fields and same-key conflicting checked revisions or check instants with a deterministic payload-safe input error before emitting a partial query result. Equivalent duplicates SHALL coalesce. For identical graph data and checked-revision inputs it SHALL return identical ordered freshness results without external reads; it SHALL never mutate retained provenance, fact identities, or stored graph data.

#### Scenario: Conflicting current checks fail safely
- **WHEN** a caller supplies two non-equivalent checked revisions for the same logical artifact in one assessment
- **THEN** the assessment rejects the input deterministically and exposes no partial freshness result

#### Scenario: Missing or malformed check is not invented
- **WHEN** a check includes a blank revision, unsafe locator, or naive timestamp
- **THEN** the check is rejected with a payload-safe diagnostic, rather than treated as a trustworthy source comparison

### Requirement: Current-required evidence eligibility fails closed
The system SHALL provide an explicit reusable current-evidence eligibility decision for checks that declare current evidence required. Only a valid, represented fresh support chain SHALL satisfy that decision; stale, unknown, missing, or invalid support SHALL NOT satisfy it. The decision SHALL operate on the specific support used by the check (including all required derived inputs), SHALL NOT promote evidence classification, trusted implementation, or verification outcome, and SHALL NOT change checks that do not declare current evidence required.

#### Scenario: Stale support does not pass a current-required check
- **WHEN** a current-required check names support whose only valid chain assesses as `stale`
- **THEN** the support is ineligible as current and its stale status remains visible

#### Scenario: Unknown support does not pass a current-required check
- **WHEN** a current-required check has no checked authoritative revision for its required support
- **THEN** the support is ineligible as current, rather than implicitly ready

#### Scenario: Fresh support does not grant other trust
- **WHEN** a fresh PR/file observation is assessed for current evidence
- **THEN** freshness eligibility does not turn the observation into trusted `IMPLEMENTS` proof

### Requirement: Freshness verification matrix bounds this revision
The change SHALL verify the following classes at assessment and applicable query/guard boundaries. Cases outside this matrix are change candidates unless they violate another approved requirement or applicable baseline.

| Input class | Assessment/admission and current-required behavior | Anchor |
| --- | --- | --- |
| Complete external provenance and checked matching revision for same artifact | `fresh` as of check; eligible as current support only subject to other policies | EKG-43 revision semantics; EKG-40 completeness |
| Complete external provenance and checked differing revision for same artifact | `stale`; ineligible as current | EKG-43 stale-evidence constraint |
| No matching check, unavailable revision, or only unrelated artifact check | `unknown`; ineligible as current | EKG-43 no timestamp-only guess |
| Matching-artifact check before provenance `observed_at` | `unknown`; ineligible as current | EKG-43 extraction metadata/currentness boundary |
| Old `observed_at`, changed extractor version/hash, no checked revision | `unknown`; ineligible as current | EKG-43 no timestamp-only guess; EKG-40 metadata |
| Derived chain containing stale input; derived chain with unknown but no stale input; all-fresh chain | `stale`; `unknown`; `fresh` respectively; only fresh chain eligible | EKG-43 derived evidence; EKG-40 derivation chain |
| Independent stale and fresh chains on one evidence record | Preserve both statuses; fresh chain may satisfy current-required check | Existing multiple-evidence/idempotency baseline |
| Internal evidence or missing resolvable chain | `unknown` or existing invalid-graph diagnostic; never eligible as current | EKG-40 provenance/validation baseline |
| Missing/blank/unsafe key or revision, naive/invalid check instant, or conflicting same-key checks | Reject input without partial output, with safe diagnostic | EKG-43 input boundary; payload-free baseline |
| Repeated equivalent checks or repeated assessment of same snapshot | Coalesce and return identical ordered results; no persistence mutation | Existing idempotency/identity baseline |

#### Scenario: Matrix is exercised
- **WHEN** automated tests exercise every matrix row at applicable model, query, wrapper, and guard boundaries
- **THEN** each case has the documented status, rejection, and current-required decision
- **THEN** no source bodies, provider responses, credentials, or tokens are serialized