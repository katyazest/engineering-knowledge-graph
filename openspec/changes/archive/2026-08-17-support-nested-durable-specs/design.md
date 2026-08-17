## Context

OpenSpec graph extraction currently assumes every durable specification lives at
`openspec/specs/<capability>/spec.md` and every change-scoped delta lives at
`openspec/changes/<change>/specs/<capability>/spec.md`. The implementation reflects
that contract through one-level glob patterns and by deriving `capability` from
`spec_file.parent.name`.

The graph derivation layer does not read OpenSpec files. It receives extracted
graph nodes and links change-scoped specs to durable specs by exact
`properties.capability` equality. That keeps derivation deterministic, but means
extraction must emit stable and matching capability identities for nested paths.

## Goals / Non-Goals

**Goals:**

- Discover durable specs recursively under the validated `openspec/specs` path.
- Discover active and archived change-scoped specs recursively under each change's
  local `specs` path.
- Preserve current flat capability identities without migration.
- Represent nested spec capabilities as slash-delimited paths relative to the
  relevant `specs` directory.
- Keep graph node IDs, evidence IDs, extraction metadata, and derivation output
  deterministic.

**Non-Goals:**

- Do not introduce a new capability aliasing or normalization registry.
- Do not infer service ownership from nested path prefixes.
- Do not change derivation to read OpenSpec files or inspect repository paths.
- Do not support arbitrary spec filenames; `spec.md` remains the only extracted
  spec artifact.

## Decisions

1. Use recursive `rglob("spec.md")` discovery for durable and change-scoped specs.

   Rationale: recursive discovery directly supports nested durable specs and the
   same shape in change deltas while keeping `spec.md` as the explicit artifact
   marker. Results will be sorted before parsing to preserve deterministic graph
   output.

   Alternative considered: use a broader `**/*.md` search and filter content.
   That would expand the extractor's artifact surface and risk treating non-spec
   markdown as authoritative OpenSpec requirements.

2. Derive capability identity from the path relative to the scope-specific
   `specs` root.

   For durable specs, the capability root is `store_source.specs_path`. For
   change-scoped specs, the capability root is `change_dir / "specs"`. The
   relative path must end with `spec.md`; removing that final segment yields the
   capability identity. Examples:

   - `openspec/specs/payments/spec.md` -> `payments`
   - `openspec/specs/service/payments/spec.md` -> `service/payments`
   - `openspec/changes/add-x/specs/service/payments/spec.md` -> `service/payments`

   Rationale: this keeps existing flat specs byte-for-byte compatible at the
   capability-property level and makes nested paths traceable by exact identity.

   Alternative considered: keep using only the parent directory name. That would
   discover nested files but collapse `service-a/payments` and
   `service-b/payments` into the same capability, breaking traceability.

3. Keep derivation matching by exact capability identity.

   Rationale: derivation already receives canonical graph facts and should remain
   independent from OpenSpec filesystem layout. Once extraction emits namespaced
   capability identities, the existing exact-match rule remains correct for flat
   and nested specs.

   Alternative considered: teach derivation to match by suffix or parent folder.
   That would introduce ambiguity and could link a change delta to the wrong
   durable spec when several nested specs share a final directory name.

4. Store namespaced capability identity in existing graph properties.

   The existing `capability` and `openspec_identity` fields should carry the
   namespaced value. Source evidence already preserves the relative file path, so
   no new graph field is required for traceability.

   Alternative considered: add separate `capability_namespace` or `spec_path`
   graph properties. That can be added later if query ergonomics require it, but
   it is not necessary for deterministic matching.

## Risks / Trade-offs

- Nested path separators in `capability` may affect callers that assume a single
  path segment -> Cover with query and derivation tests using namespaced
  capabilities.
- Recursive discovery could include intentionally nested examples under
  `openspec/specs` -> Maintain the strict `spec.md` filename contract and rely on
  the validated OpenSpec store layout as source of truth.
- Two physical specs with the same relative capability identity are impossible
  under one `specs` root, but flat and nested specs may share the same title ->
  Continue using capability identity, not title, for deterministic spec identity.

## Migration Plan

No data migration is required. Existing flat specs keep their current capability
identity. After implementation, rerunning extraction over the same flat store
should produce unchanged capability values, while nested specs become newly
visible graph facts.

## Open Questions

None.
