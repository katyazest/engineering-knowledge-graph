## Context

Plane task `a5987bd4-215c-4a3e-995e-35fe8bb3f6b9` establishes a cross-cutting provenance boundary. The current ontology has source-specific locator classes (`OpenSpecLocator`, `CodeLocator`, and `ConfluencePageRef`) embedded directly in `Evidence`; OpenSpec evidence IDs are constructed from local relative paths and an OpenSpec identity. Snapshot merge coalesces evidence only by those IDs, and persistence deserializes the locator variants directly. This does not provide one explicit identity contract usable by all current and future extractors/adapters, nor a migration rule for legacy evidence.

The change affects project-owned ontology, extractors/adapters, graph merge/validation, persistence, and tests. Graphify, Jira MCP, Bitbucket MCP, and LadybugDB remain external boundaries; provider response models and raw payloads do not enter the new model.

## Goals / Non-Goals

**Goals:**
- Give authoritative source artifacts a complete source-agnostic identity that remains stable across extraction, normalized adapters, and persistence.
- Make source-artifact/evidence deduplication and conflicts deterministic without changing canonical graph fact IDs.
- Preserve stable source navigation metadata while separating it from identity fields.
- Provide deterministic migration/diagnostics for persisted legacy evidence.

**Non-Goals:**
- Change the identity of canonical nodes, edges, cross-graph claims, or derived relationships.
- Define or retain Jira, Bitbucket, Graphify, or LadybugDB payload models; call external services; hash source contents; or implement semantic inference.
- Treat a display label, absolute checkout path, heading, line range, or timestamp as authoritative identity.

## Decisions

### 1. Introduce one immutable `SourceArtifactIdentity` value object

Add a reusable ontology value object with exactly five required strings: `source_type`, `source_identity`, `artifact_type`, `revision_or_version`, and `stable_locator`. It owns validation, canonical field-delimited identity serialization, and a stable ID helper. `Evidence` will contain this value (or a source-artifact locator that contains it) plus optional non-identity navigation detail such as heading and line range.

This separates an authoritative artifact from an extracted domain fact. Canonical node/edge IDs remain their existing natural-key IDs; evidence IDs derive from the artifact identity and only those retained provenance fields that intentionally distinguish evidence. Existing display `name` fields remain presentation data only.

Alternative: extend each provider locator independently. Rejected because adapters would retain incompatible identity rules and future source types would repeat validation/deduplication logic.

### 2. Normalize before graph construction and reject incomplete identity at the boundary

Extractor/adaptor inputs will first be translated into the shared value object. The boundary validates all five fields and rejects blank, payload-like, secret-bearing, navigation-URL, display-name, and incidental-absolute-path values before emitting nodes, edges, evidence, or persistence requests. Source-specific locator classes become navigation-detail adapters around the common identity instead of alternative identity systems.

OpenSpec uses the validated store/repository identity, an explicit OpenSpec source type, the recognized artifact type, a repository-relative artifact locator, and the validated repository's resolved Git `HEAD` commit as `revision_or_version`. Its heading and line range stay non-identity detail. A dirty checkout remains governed by the existing read-with-warning policy; its authoritative version is still the resolved commit, and source content is not hashed or included in identity. Future Jira, Bitbucket, and Graphify adapters must accept or construct the same normalized contract without importing provider response types into the ontology.

Alternative: allow missing fields and fill them at persistence. Rejected because it permits partial graph output and makes identity dependent on pipeline order.

### 3. Coalesce by identity and reject immutable conflicts

Graph merge and persistence write/readback will index authoritative artifacts/evidence by stable source-artifact ID. Identical records coalesce with sorted references. Same-ID records that disagree in any retained identity or immutable provenance field fail deterministically; ingestion order cannot choose a winner. Integrity validation verifies identity completeness, ID recomputation, no forbidden field values, reference validity, and duplicate conflict semantics before persistence accepts a snapshot.

The persistence adapter remains the only storage implementation point. Extractors and adapters return graph snapshots or normalized records and never write directly to LadybugDB-compatible storage.

Alternative: deduplicate by locator or display name. Rejected because locators can be moved and labels are not authoritative.

### 4. Use an explicit, guarded legacy migration path

The deserializer recognizes legacy locator records. A migration helper reconstructs the new identity only when retained legacy fields unambiguously supply every authoritative component; it preserves pre-existing canonical node/edge IDs and writes a backup using the existing migration convention. Otherwise it returns a deterministic compatibility diagnostic/integrity failure and does not infer values from absolute filesystem paths, working directory, or labels. New writes use only the new serialized representation.

This is intentionally stricter than lossy best-effort migration: the task prioritizes authoritative identity and reproducibility over accepting ambiguous historic provenance.

### 5. Test the verification matrix at every owned boundary

Unit fixtures test the value object and stable ID, source adapters/extractor admission, snapshot merge, persistence round-trip/migration, and graph integrity validation. Tests cover each matrix row in `source-artifact-identity`, unchanged canonical IDs, differing identity components, same-ID conflicts, absolute-path/display-name/payload rejection, and deterministic ordering. OpenSpec fixtures run locally without CLI/network dependencies by injecting validated source context.

## Data Flow

`validated source context / provider adapter input` → `SourceArtifactIdentity validation` → `normalized source artifact + optional navigation detail` → `canonical facts with evidence reference` → `GraphSnapshot merge + integrity validation` → `LadybugDB-compatible serialization/readback`.

Derived relationships continue to consume canonical graph facts and evidence IDs; they neither derive source-artifact identity nor use it as a canonical relationship identity. Existing query DTOs need no new public field unless they already expose evidence; if exposed, they serialize the stable identity and navigation detail without payload content.

## Risks / Trade-offs

- [A dirty checkout can contain content not represented by its Git `HEAD`] → retain the existing read-with-warning behavior, use the resolved commit as the authoritative version, and do not claim byte-level source-content identity.
- [Legacy evidence may be insufficient for migration] → Fail/diagnose deterministically and retain the pre-migration backup instead of manufacturing provenance.
- [Stricter validation can reject currently accepted fixtures] → Update fixtures only where a complete authoritative source context is available; test diagnostic behavior for unsupported legacy inputs.
- [Evidence-ID changes can change persisted evidence/edge references] → Migrate them as one snapshot transaction, preserve canonical node/edge IDs, and validate readback before replacing the store.

## Migration Plan

1. Implement and fixture-test the common identity model, validators, and stable serialization before changing producers.
2. Update OpenSpec extraction and normalized adapter contracts to supply the shared model; retain canonical IDs and navigation details.
3. Extend graph merge, validation, and persistence deserialization/serialization; add deterministic legacy migration, backup, and readback validation.
4. Run fixture snapshots through initial write, repeated write, compatible legacy migration, and ambiguous legacy rejection paths; publish only after deterministic validation succeeds.
5. Roll back by restoring the automatically retained pre-migration graph backup and running the prior reader; do not partially rewrite an invalid snapshot.

## Open Questions

None.
