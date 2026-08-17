## Why

OpenSpec graph extraction currently discovers only one-level durable specs, so valid nested files under `openspec/specs/**/spec.md` are invisible to the Engineering KG. Nested specs also need an explicit capability identity rule because derivation links change-scoped specs to durable specs by exact capability match.

## What Changes

- Discover durable OpenSpec specification files recursively under the validated durable specs directory.
- Define capability identity as the path relative to the relevant `specs/` directory with the trailing `/spec.md` removed.
- Preserve existing flat capability identities unchanged; for example, `openspec/specs/payments/spec.md` remains capability `payments`.
- Represent nested durable specs with namespaced capability identities; for example, `openspec/specs/service/directory1-n/spec.md` becomes capability `service/directory1-n`.
- Apply the same capability identity rule to change-scoped delta specs so derivation can continue using exact capability matching.
- Keep extraction deterministic by sorting recursive discovery results and preserving source evidence paths.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `openspec-graph-extraction`: durable and change-scoped spec extraction must support nested `spec.md` paths and produce deterministic namespaced capability identities.
- `graph-derivation`: OpenSpec change-to-durable spec derivation must continue to match by exact capability identity, including namespaced identities emitted by extraction.

## Impact

- Affects OpenSpec graph extraction in `src/engineering_kg/ingest/openspec.py`.
- Affects derivation expectations and tests for exact capability matching in `src/engineering_kg/derivation.py`.
- Requires tests for recursive durable spec discovery, namespaced capability identity, and traceability between nested change-scoped and durable specs.
