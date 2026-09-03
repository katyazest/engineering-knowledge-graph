# cross-graph-evidence-trust-model Specification

## Purpose

The `cross-graph-evidence-trust-model` capability defines explicit evidence classification, trust boundaries, and projection rules for cross-graph claims.

## Requirements

### Requirement: Cross-graph evidence has explicit classification and trust
The system SHALL classify every cross-graph observation and lifecycle-support record with exactly one origin of `declared`, `observed`, or `inferred`; exactly one status of `authoritative` or `derived`; an explicit payload-safe confidence value; and an explicit trust disposition of `trusted` or `untrusted`. Each observation record's `strategy_id` and `observation_id` SHALL be non-empty payload-safe opaque identifiers; they MAY use a payload-safe opaque URI-shaped stable identifier, but SHALL NOT contain source content, provider payloads, credentials, tokens, URLs, hierarchical or authority-bearing URL forms, or other payload-bearing values. The classification and identifiers SHALL be retained separately from a claim's relationship kind and lifecycle state, SHALL participate in immutable support-record validation, and SHALL NOT change a cross-graph claim's stable identity. Missing, unknown, contradictory, or payload-bearing classification/trust fields or observation identifiers SHALL be rejected before serialization, graph-snapshot admission, persistence, or query exposure.

#### Scenario: Classified support is admitted deterministically
- **WHEN** a cross-graph observation or lifecycle-support record has one permitted origin and status, a non-empty payload-safe confidence value, an explicit trust disposition, complete provenance, and valid claim reference, and each observation `strategy_id` and `observation_id` is a payload-safe opaque identifier
- **THEN** the system retains its classification and trust fields in deterministic serialization order
- **THEN** the associated claim retains its existing stable identifier

#### Scenario: Invalid classification is rejected without a partial record
- **WHEN** a cross-graph support record has a missing, unknown, contradictory, or payload-bearing origin, status, confidence, trust disposition, `strategy_id`, or `observation_id`
- **THEN** admission returns a deterministic classification/trust diagnostic
- **THEN** it emits no partial observation, lifecycle record, serialized record, persistence record, query projection, or trusted projection

### Requirement: Evidence precedence does not infer trust
The system SHALL apply the following deterministic precedence rules to support for the same cross-graph claim: authoritative declared support is eligible to support an explicit trusted lifecycle decision; observed support remains evidence of observation and is not proof of implementation; inferred support remains non-authoritative; and no number, confidence value, source order, merge order, merged-PR status, or lifecycle absence SHALL promote support or a claim. Conflicting classified support SHALL be retained for audit when individually valid; the system SHALL not select a winner or discard valid support based on precedence alone.

#### Scenario: Declared support can support explicit trust
- **WHEN** a catalog-conformant claim has complete authoritative declared support and a separately supplied explicit trusted lifecycle decision that satisfies the lifecycle contract
- **THEN** the claim is eligible for trusted projection subject to all other cross-graph admission rules
- **THEN** the projection identifies the supporting classification and trust disposition

#### Scenario: Observation and inference do not self-promote
- **WHEN** a claim has observed PR/file support or inferred support, including any number of records or any confidence values, but no qualifying explicit trusted decision
- **THEN** the claim remains non-trusted
- **THEN** the system does not select a stronger support record by ordering or count

### Requirement: Implementation trust has a strict evidence boundary
The system SHALL NOT expose, count, or serialize an `IMPLEMENTS` cross-graph relation as trusted implementation truth when its supporting observation or lifecycle evidence is observed PR/file evidence or LLM-only inferred evidence. An `IMPLEMENTS` relation is eligible for trusted projection only when its complete support chain includes authoritative declared evidence and the existing explicit trusted lifecycle decision; other catalog-valid relation kinds remain governed by their own endpoint, provenance, lifecycle, and classification rules.

#### Scenario: Merged PR/file evidence is not implementation proof
- **WHEN** an explicitly linked merged PR changed-symbol observation supports an `IMPLEMENTS` claim or is supplied as lifecycle support for that claim
- **THEN** validation rejects trusted implementation projection with a deterministic implementation-trust diagnostic
- **THEN** the observed evidence remains auditable only as non-trusted support where otherwise valid

#### Scenario: LLM-only evidence is untrusted for implementation
- **WHEN** an `IMPLEMENTS` claim is supported only by evidence classified as inferred and identified as LLM-only
- **THEN** the system does not expose or count a trusted implementation relation
- **THEN** it retains the valid inferred support as non-trusted evidence with its classification

### Requirement: Classified evidence and trust are queryable without payloads
The local query API SHALL return each cross-graph claim's deterministic relationship kind, current lifecycle disposition, observations, lifecycle support, origin, status, confidence, explicit trust disposition, and trusted-projection result. It SHALL return only existing provenance references and payload-safe locator identity; it SHALL not return source bodies, provider payloads, LLM prompts/responses, source code, credentials, tokens, URLs, or an inferred implementation conclusion not represented by a trusted projection.

#### Scenario: Query distinguishes observed evidence from trusted implementation
- **WHEN** a caller queries a claim supported by observed PR/file evidence and a separate claim with qualifying declared implementation support
- **THEN** the response distinguishes their classifications and trusted-projection results deterministically
- **THEN** it does not label the PR/file-supported claim as implemented

### Requirement: Evidence classification verification matrix bounds admission testing
The change SHALL document and exercise this verification matrix. Cases outside it SHALL be reported as change candidates unless they violate another approved requirement or applicable baseline.

| Input class | Expected admission or projection behavior | Compatibility anchor |
| --- | --- | --- |
| Complete authoritative declared support with explicit `trusted` disposition and a separately valid trusted lifecycle decision | Admit support; eligible to project a catalog-conformant relation, including `IMPLEMENTS` | EKG-41 declared mappings may be trusted |
| Complete observed PR/file support with any explicit confidence/trust disposition | Admit as non-trusted observation; never proves `IMPLEMENTS` | EKG-41 observed PR/file boundary; existing PR candidate baseline |
| Complete LLM-only inferred support with any explicit confidence/trust disposition | Admit as non-trusted support; never projects `IMPLEMENTS` as trusted | EKG-41 LLM-only boundary |
| Individually valid declared, observed, and inferred support for one claim | Retain all; do not select or promote by precedence, count, confidence, or order | EKG-41 precedence boundary; idempotency baseline |
| Missing, unknown, contradictory, or payload-bearing classification/trust field | Reject before graph emission and persistence | EKG-41 explicit model; payload-free baseline |
| Payload-bearing `strategy_id` or `observation_id`, including source content, provider payload, credentials, tokens, or URL-like/hierarchical identifier forms | Reject at classified-evidence admission; emit no serialized record, persistence record, or query projection | Approved revision to EKG-41 change; payload-free and opaque-identifier baselines |
| Complete payload-safe opaque `strategy_id` and `observation_id`, including an allowed opaque URI-shaped stable identifier | Admit only with all other classified-evidence requirements; retain as identifiers, not navigable links or payloads, through deterministic serialization, persistence/readback, and query | Approved revision to EKG-41 change; opaque-identifier baseline |
| Repeated equivalent classified support | Coalesce deterministically without changing claim identity | Existing stable-ID/idempotency baseline |
| Existing canonical record lacking the new required classification/trust fields | Reject on admission/readback; do not infer or backfill fields | EKG-41 breaking contract; no approved legacy mapping |

#### Scenario: Matrix cases are executable
- **WHEN** automated model, adapter, validation, persistence, and query tests exercise each matrix row at its applicable boundary
- **THEN** each row has the documented admission, rejection, retention, or projection outcome
- **THEN** tests verify that no authoritative source, LLM payload, or rejected `strategy_id`/`observation_id` value is serialized, persisted, or queryable
