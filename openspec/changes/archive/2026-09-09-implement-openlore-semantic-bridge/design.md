## Context

Plane task `EKG-46` implements the boundary described by source backlog item `EKG-15`: EKG owns project context and compact evidence references; OpenLore owns code graph, symbol resolution, navigation, and deeper semantic reasoning. The repository already has two pieces that stop short of this boundary:

- `engineering_kg.openlore` validates workspace-level OpenLore source and federation configuration but never performs code resolution.
- `CodeLocator` and the completed EKG-09/ EKG-14 cross-graph contracts can retain exact repository/revision/file/symbol identities and PR-derived candidate evidence, but EKG-14 requires an upstream deterministic symbol-mapping outcome.

No OpenLore transport, request schema, response schema, or index internals are present in this repository. EKG therefore cannot own or model those provider details. The implementation must provide a runtime seam that callers can bind to an OpenLore integration while keeping local tests independent of a live server and without changing EKG's canonical graph ownership.

## Goals / Non-Goals

**Goals:**

- Provide reusable, provider-neutral operations to resolve revision-qualified changed files and to construct a revision-qualified navigation handoff.
- Make repository identity, selected federation-index or repository-index-path route, immutable revision, changed-file identity, exact symbol result, and failure state explicit at the bridge boundary.
- Reuse the workspace registry as the authority for routing a repository to an OpenLore federation index when applicable or to the registered repository local path otherwise, and reuse EKG-14's normalized implementation-evidence repository/revision semantics as the compatibility anchor.
- Produce an existing complete `CodeLocator` only for an exact singleton resolution, preserving its four-field stable identity for existing cross-graph flows.
- Ensure payload-free, deterministic results and fixture/fake-provider tests.

**Non-Goals:**

- Building, reading, rebuilding, copying, or persisting an OpenLore index or code graph; implementing an OpenLore server, MCP client transport, provider authentication, or provider-specific request/response types.
- Parsing diffs, discovering implementation evidence, resolving Git branches or current checkouts, fuzzy searching symbols, choosing a likely result, or altering EKG-14 candidate lifecycle/trust rules.
- Adding a pipeline stage, an EKG MCP tool, a new canonical graph node/edge, persistence schema, migration, or query projection. Callers invoke the reusable bridge explicitly and may separately submit a valid result to existing candidate-evidence flows.
- Returning source bodies, call/dependency graphs, impact/architecture analyses, navigation answers, credentials, URLs, or a conclusion that a symbol implements a requirement.

## Decisions

### Decision: Isolate OpenLore behind a narrow project-owned provider port

Create a dedicated module such as `engineering_kg.openlore_bridge` rather than extending `openlore.py`, whose existing responsibility is configuration validation. It will define frozen, project-owned DTOs for:

- a changed-file reference (`stable file identity`, repository-relative `file`);
- a resolution request (`implementation-evidence identity`, `repository`, immutable `revision`, and changed-file references);
- a per-file bridge outcome (`resolved`, `unresolved`, `ambiguous`, `provider-unavailable`, or `invalid-provider-response`) with optional complete `CodeLocator` and stable reason code; and
- a compact routing reference that identifies either an applicable federation `index_location` or the registered repository's resolved local path; and
- a navigation handoff containing the exact `CodeLocator` plus that routing reference.

The module will also define a minimal injected `OpenLoreProvider` protocol that receives the provider-neutral repository/revision/files request and returns provider-neutral per-file candidate symbol identities. A concrete OpenLore transport adapter, when an approved OpenLore API is available, lives outside the domain contract and translates its response into this port shape. Fakes implement the same port in unit and integration-boundary tests.

Rationale: the repository has no evidence for an OpenLore wire protocol, and coupling canonical EKG types to a guessed MCP or index schema would violate the external-boundary invariant. A port supplies a real runtime integration point without pretending EKG owns OpenLore internals.

Alternative considered: add an OpenLore MCP client and model its response directly in EKG. Rejected because the provider API is unspecified, live access conflicts with local fixture tests, and response payloads must not become canonical records. Alternative considered: put resolution in `pr_code_candidates.py`. Rejected because that would couple an external code-intelligence interaction to one evidence producer and prevent navigation of already-known locators.

### Decision: Prefer an applicable federation index and fall back to the registered repository path

`OpenLoreSemanticBridge` is constructed from a loaded `WorkspaceRegistry` and a provider port. On every resolution request it performs this ordered admission and route selection:

1. validate the request's compact, payload-safe field shapes and unique changed-file identities;
2. find the repository by exact registry ID; registry membership, not `include_in_federation`, is the admission condition;
3. when workspace federation is enabled and that repository is included in it, require a non-empty `index_location` and select it as the federation-index route; otherwise select the repository's registry-resolved local path as the repository-index fallback route;
4. require the request repository and complete Git object ID to equal the attached normalized implementation-evidence repository and immutable merged revision; and
5. invoke the provider only after the context is admitted.

An applicable federation entry whose index location is blank is invalid configuration, not a fallback case: this preserves the existing workspace OpenLore-source validation boundary. Conversely, federation-disabled registries and registered repositories not included in federation are valid fallback cases; they do not require `include_in_federation` or `index_location`. The selected compact routing reference is passed to the provider port for resolution and is carried unchanged in a navigation handoff. It is derived solely from the loaded registry, never from a caller-supplied filesystem path, repository URL, current checkout, or provider response.

The request contract is deliberately shaped so a caller can build it from EKG-14 normalized PR evidence: its evidence identity, repository, merged revision, and existing stable mapping/file identities. The bridge does not mutate PR evidence, create a PR candidate, or invent a replacement provenance chain. Its result can be explicitly adapted to EKG-14's `ChangedSymbolMapping` input only after a caller preserves the original source-mapping identity and applies the existing candidate-admission rules.

The bridge validates its own compact identifiers and relative paths using shared extraction/validation helpers factored from the current PR candidate module where possible. It does not tighten global `CodeLocator` construction, because existing persistence and graph contracts permit locators outside bridge use. The bridge separately requires an immutable Git object ID and registry-routed repository for bridge resolution and navigation.

Rationale: registry matching prevents cross-service routing; evidence matching prevents the current checkout, a branch, or a different PR revision from silently replacing implementation evidence. Federation remains the preferred route where it is configured, while the registry path preserves useful exact-revision routing for registered repositories that deliberately have no federation. Keeping this narrower validation at the bridge boundary avoids breaking existing persisted `CodeLocator` compatibility.

Alternative considered: require every repository to be included in federation. Rejected because it makes federation mandatory and prevents resolution/navigation for otherwise registered repositories. Alternative considered: add a separate provider configuration file, environment-variable mapping, dynamic provider discovery, or convention-derived index path. Rejected because each adds a new configuration source, runtime dependency, or non-approved inference; the registry-resolved local path is already deterministic. Alternative considered: accept a caller-supplied repository path, SSH URL, service name, or provider-selected repository as a fallback. Rejected because none is the stable registry/evidence route required by EKG-46. Alternative considered: resolve a short SHA, tag, or branch to a commit in the bridge. Rejected because that makes outcomes environment- and time-dependent.

### Decision: Treat provider output as a strict one-to-one resolution report

The port's neutral response identifies each input changed-file identity and echoes its repository, revision, and file along with zero, one, or multiple compact symbol identities. The bridge verifies that response entries correspond exactly to requested files and context; duplicate/conflicting entries, unknown entries, unsupported status, malformed compact fields, or context mismatches are invalid provider responses. A provider exception or explicit unavailable result becomes `provider-unavailable` without preserving exception text.

The bridge maps a singleton valid symbol to `resolved` and constructs `CodeLocator(request.repository, request.revision, request.file, symbol)` verbatim. Zero symbols map to `unresolved`; multiple map to `ambiguous`; all failures keep an explicit non-resolved status/reason. Results and diagnostics are sorted by changed-file identity. The bridge never performs a broad fallback query or uses a partial file, line range, bare display name, or a provider ranking to produce a locator.

Rationale: explicit classifications preserve the EKG-14 rule that unresolved and ambiguous changed symbols do not yield cross-graph candidates. A single result is the only evidence that preserves the required precision without probabilistic policy.

Alternative considered: return the first provider symbol with a confidence score. Rejected because it would convert provider ordering into an unapproved inference and can create a false code reference. Alternative considered: persist all candidate symbols for later analysis. Rejected because it duplicates code intelligence in EKG and has no approved semantic/lifecycle contract.

### Decision: Make navigation a compact handoff, not a result import

`build_navigation_handoff(locator)` revalidates the exact registry-selected route, immutable revision, repository-relative file, and complete symbol identity. It applies the same route selection as resolution: an applicable federation index is used when available; otherwise the registry-resolved repository local path is used. It returns only the locator and selected routing reference that a runtime integration needs to address OpenLore. It does not invoke deeper analysis or retain a navigation result. A caller may pass the handoff to its OpenLore client, but the client response remains owned by OpenLore and outside EKG records.

No `GraphSnapshot`, `Evidence`, provenance record, trusted link, persistence serializer, query DTO, derivation rule, or pipeline result changes are made. Existing `CodeLocator` and candidate flows remain stable: a successful bridge result can be an input reference, but is not itself an asserted or trusted relationship.

Rationale: a data-only handoff gives callers a precise path from EKG traceability to code navigation while preserving the no-code-graph/no-semantic-inference boundary.

Alternative considered: add a bridge result to the graph or expose an OpenLore navigation query through EKG MCP. Rejected because it either retains OpenLore-owned information or makes a local EKG query surface depend on an external runtime provider.

### Decision: Retain only compact diagnostics; add no persistence migration

Bridge DTO serializers expose a finite allowlist of IDs, status/reason codes, locator identity, and routing reference. They must never include provider exceptions, response objects, unknown fields, or code/payload-bearing values. The bridge returns immutable in-memory result objects and performs no writes. Equivalent request entries are deduplicated by stable changed-file identity; conflicting duplicate entries return invalid-request outcomes deterministically rather than being selected by input order.

The change is additive. It does not alter `CodeLocator` stable identity or serialized graph collection shapes, so existing snapshots, cross-graph evidence, persistence readback, derivation, and query consumers require no migration. The bridge is not a graph-producing pipeline stage and cannot cause a persisted partial resolution.

Rationale: no persistence change is necessary for an ephemeral external boundary, and allowing only compact data prevents a provider integration from bypassing existing query sanitization and source-artifact safeguards.

## Data Flow

```text
normalized implementation evidence
  (evidence id, registry repository id, immutable merged revision,
   stable changed-file id + relative path)
        |
        v
OpenLoreSemanticBridge admission
  - federation index route, when applicable
  - otherwise registry repository-path route
  - evidence repository/revision equality
  - compact-field validation
        |
        v
injected OpenLoreProvider port
        |
        v
strict per-file outcomes
  resolved -> exact CodeLocator
  zero/multiple/failure -> explicit non-resolved outcome
        |
        +--> caller may adapt exact result to existing EKG-14 candidate extraction
        +--> complete CodeLocator -> compact OpenLore navigation handoff

No provider payload or code-intelligence response flows into GraphSnapshot or persistence.
```

## Risks / Trade-offs

- [OpenLore transport and symbol identity format are not defined in the approved task] → Define and test only the provider-neutral port; a concrete transport adapter needs its own approved integration contract rather than changing the bridge DTOs.
- [Provider output can be stale, unavailable, or keyed to another revision] → Require exact response echoes and emit non-resolved diagnostics; never fall back to a checkout or broader search.
- [A provider bound to a repository-path route may not support local-path resolution] → Pass the deterministic fallback route through the provider port and classify provider unavailability or invalid response explicitly; do not invent an index location or retry through another repository.
- [Existing EKG-14 mapping IDs originate from Graphify] → Keep the bridge request's changed-file identity generic and require callers adapting EKG-14 evidence to retain its source-mapping identity; do not relabel evidence provenance.
- [A caller may mistake a resolved locator for implementation proof] → Do not create graph records or trusted links; retain the existing EKG-09/EKG-14 lifecycle and trust boundaries.
- [Provider messages may carry code or secrets] → Use closed DTO schemas, reason codes rather than exception text, and tests asserting serialization contains only allowlisted compact fields.
- [Large PRs can contain many files] → Process each batch in deterministic linear order with ID-based deduplication; do not materialize provider payloads or code graph data.

## Migration Plan

1. Factor any reusable compact file/symbol identity validation from the PR candidate extractor without changing its observable candidate output.
2. Add the bridge DTOs, federation-or-repository-path registry/evidence admission and routing, provider protocol, deterministic outcomes, and navigation-handoff builder with fake-provider tests.
3. Add adapter-level coverage showing a valid bridge result can be explicitly converted into existing EKG-14 mapping input while unresolved/ambiguous/provider-failed results cannot produce a candidate.
4. Run focused bridge, PR candidate, workspace OpenLore-source, persistence, query, and full-suite tests with no live OpenLore provider.

Rollback removes the additive bridge module and its callers. Because the bridge makes no schema, graph, or storage writes, no data rollback or migration is required.

## Open Questions

None for this change. The exact OpenLore transport/authentication and provider-native symbol schema are intentionally excluded; they require a future approved adapter contract and do not block implementation of the project-owned runtime port.
