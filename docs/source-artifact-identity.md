# Source-artifact identity contract

Every authoritative artifact admitted to an extractor, normalized adapter,
graph evidence record, or persisted snapshot has a `SourceArtifactIdentity`.
Its identity consists of exactly these five non-empty, payload-safe fields:

```json
{
  "source_type": "openspec",
  "source_identity": "requirements",
  "artifact_type": "openspec-spec",
  "revision_or_version": "0123456789abcdef0123456789abcdef01234567",
  "stable_locator": "openspec/specs/payments/spec.md"
}
```

`source_type` identifies the producer class, `source_identity` is the stable
authoritative source identifier, `artifact_type` identifies the record class,
`revision_or_version` identifies its authoritative version, and
`stable_locator` is a source-relative navigation locator. The source-artifact
ID is deterministically derived from those five fields using field-delimited
serialization. Display names, local checkout paths, headings, line ranges,
timestamps, and source content do not affect it.

## OpenSpec policy

OpenSpec extraction sets `source_type` to `openspec`, uses the validated
requirements repository ID as `source_identity`, and uses a repository-relative
path for `stable_locator`. `revision_or_version` is the resolved Git `HEAD`
commit of the validated OpenSpec store repository. A dirty worktree remains
readable under the configured `read-with-warning` policy, but does not replace
the Git commit with a content hash or local path. If Git `HEAD`, the store
identity, or another required field is unavailable, extraction stops before
emitting graph facts with an `invalid-source-artifact-identity` diagnostic.

OpenSpec headings and line ranges remain navigation detail. They can identify
a requirement or scenario within the artifact, but do not alter the
source-artifact ID or canonical node and edge IDs.

## Adapter boundary and safety

Jira, Bitbucket, Graphify, and future producers must normalize records through
the common identity contract before graph construction. Adapter input retains
only the five identity fields and payload-safe navigation detail. It must not
include provider responses, source bodies, credentials, tokens, or navigation
URLs. A display name cannot substitute for `source_identity`, and an absolute
path cannot substitute for `stable_locator`.

## Persistence and legacy evidence

Persistence coalesces compatible records with the same source-artifact ID and
uses deterministic ordering. A same-ID record with conflicting retained
identity or immutable provenance fails rather than choosing an ingestion-order
winner.

Legacy OpenSpec evidence without an explicit identity is accepted only when
retained authoritative fields unambiguously reconstruct all five fields. The
migration rewrites evidence references atomically, preserves canonical node and
edge IDs, and creates `graph.pre-canonical-migration.json` before replacing the
persisted graph. If reconstruction is insufficient or inconsistent, readback
fails with the deterministic
`legacy-source-artifact-identity: OpenSpec evidence lacks sufficient authoritative identity fields`
diagnostic. Migration never infers identity from a display name, absolute path,
or current filesystem layout.
