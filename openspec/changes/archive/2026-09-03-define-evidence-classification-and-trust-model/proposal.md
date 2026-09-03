## Why

Plane task `EKG-41` (`fdd1423b-b900-4bbd-969a-0dc84bc614aa`) requires cross-graph relations to state what kind of evidence produced them and how much the system may trust that evidence. Current provenance and candidate lifecycle records retain source and promotion history, but do not provide one explicit, queryable classification and trust contract that prevents PR/file observations or LLM-only output from being presented as implementation proof.

## What Changes

- Define a deterministic evidence classification and trust model for cross-graph relation support: origin (`declared`, `observed`, or `inferred`), status (`authoritative` or `derived`), and explicit confidence/trust values.
- Define precedence for conflicting support: explicit declared mappings may be trusted only through an explicit trusted lifecycle decision; observed PR/file support is not implementation proof; LLM-only support remains inferred and untrusted for implementation.
- Require admission, merge, integrity validation, persistence/readback, and query projection to retain and enforce the classification/trust fields without changing claim identity; reject payload-bearing `strategy_id` and `observation_id` values at admission before serialization, persistence, or query exposure.
- Expose the classification, trust, confidence, supporting evidence, and the resulting trusted/non-trusted disposition through the local cross-graph relation API representation.
- **BREAKING** Reject cross-graph observation or lifecycle support that does not satisfy the new classification/trust contract. Do not infer missing values or promote claims from confidence, evidence volume, merged-PR status, or LLM output.

## Capabilities

### New Capabilities
- `cross-graph-evidence-trust-model`: The classification vocabulary, precedence, admission rules, API representation, and verification matrix for cross-graph evidence and trust.

### Modified Capabilities
- `cross-graph-link-evidence`: Candidate observations, lifecycle support, and trusted-link projection apply the explicit evidence classification and trust model.
- `fact-provenance`: Provenance records and evidence associations retain the origin and authoritative/derived classification required to explain a cross-graph claim.
- `canonical-relationship-vocabulary`: Trusted relationship admission uses the approved evidence precedence rather than treating all complete provenance alike.
- `graph-integrity-validation`: Validates classified evidence, trust decisions, precedence, and implementation-proof restrictions.
- `local-ekg-query-api`: Returns classified cross-graph evidence and trusted/non-trusted dispositions deterministically.

## Impact

Affected project-owned components are canonical ontology schemas, PR/code and future normalized source adapters, cross-graph claim lifecycle handling, relationship admission/validation, persistence/readback, local query DTOs, documentation, and fixture-based tests. Existing cross-graph claim identity and payload-free provenance boundaries remain unchanged, while persisted canonical records and query shapes gain required classification/trust fields and retain only payload-safe opaque `strategy_id` and `observation_id` values. Graphify, Jira MCP, Bitbucket MCP, OpenLore, LadybugDB, and any LLM provider remain external boundaries: this change normalizes their supplied identity-level evidence only and does not call or modify them. `EKG-41` is the traceability source.
