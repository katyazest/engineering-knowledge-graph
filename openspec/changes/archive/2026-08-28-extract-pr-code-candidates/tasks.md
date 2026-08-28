## 1. Normalized admission boundary

- [x] 1.1 Add frozen, project-owned normalized records and deterministic validation for explicit engineering-change/merged-PR associations, immutable change-set identity, and changed-symbol mapping outcomes; verify valid fixtures normalize identically and missing, blank, malformed, or non-merged inputs return deterministic failures.
- [x] 1.2 Add adapter-boundary tests using local fixture/mocked Jira, Bitbucket, and Graphify-shaped inputs to prove provider response models, source payloads, and URL-like external links do not enter normalized records or canonical graph data, while opaque URI-shaped stable identifiers are not rejected solely because of their syntax.

## 2. Candidate extraction and provenance

- [x] 2.1 Implement the reusable PR code-candidate extractor and result/diagnostic metadata using the normalized contract; verify it only admits explicit associations whose engineering-change subject exists and reports deterministic reason-coded non-admission outcomes.
- [x] 2.2 Construct complete revision-qualified `CodeLocator`, `CrossGraphLinkClaim`, safe generic provenance `Evidence`, `CrossGraphLinkEvidence`, and initial candidate lifecycle records for each unique resolved mapping; verify stable identities, deterministic order, idempotent snapshot merging, and that any retained opaque URI-shaped value is an identifier rather than a URL-like external link.
- [x] 2.3 Implement unresolved, ambiguous, file-only, incomplete-locator, and mutable-reference handling without target selection; verify each case emits no claim/observation/lifecycle and retains only permitted explainability/provenance identifiers and diagnostics, never source payloads or URL-like external links.
- [x] 2.4 Add candidate trust-boundary regressions; verify merged/linked PR extraction creates no `IMPLEMENTS` edge or trusted projection and that an independently supplied lifecycle revision can change lifecycle state while retaining the original PR observation.

## 3. Graph compatibility and integrity

- [x] 3.1 Extend producer-facing graph-integrity validation coverage for candidate subject, claim, provenance, and lifecycle references; verify invalid extracted/hand-built records fail deterministically and valid PR candidates pass without changing existing trusted-link behavior.
- [x] 3.2 Add persistence/readback and legacy-snapshot regression coverage for extracted candidates; verify stable serialized output, repeated merge/readback idempotency, exclusion of payload fields and URL-like external links, permitted opaque URI-shaped identifier retention, and continued readability of snapshots without PR candidates.

## 4. Pipeline orchestration

- [x] 4.1 Add optional normalized PR change-set input and `pr-code-candidate-extraction` result metadata to the reusable pipeline API without changing unconfigured pipeline behavior; verify metadata contains only counts, safe diagnostics, and graph counts, excluding source payloads and URL-like external links while permitting opaque URI-shaped stable identifiers.
- [x] 4.2 Implement stage dependency/order enforcement and graph merge orchestration so candidate extraction runs after required subject/input producers and before derivation/validation; verify missing dependencies stop later graph-mutation stages with deterministic errors and a complete configured run is stable across repeats.
- [x] 4.3 Add pipeline integration fixtures and execute focused candidate, cross-graph, persistence, validation, and pipeline tests plus the full pytest suite without live external infrastructure; verify all tests pass and no network/MCP/OpenLore call is required.

## 5. Revision 3 subject and identifier admission regressions

- [x] 5.1 Restrict candidate admission to an existing `JIRA_STORY` subject; reject `WORKSPACE` and every other node kind with a deterministic ineligible-subject-kind non-admission diagnostic, no candidate records, and no trusted link.
- [x] 5.2 Tighten retained stable-identity validation to accept payload-safe opaque URI-shaped IDs including `urn:example.org/link-42`, while rejecting `https://…`, `custom://…`, `https:host/path`, and payload-like values before provenance persistence; add direct boundary regressions for each case.
- [x] 5.3 Update extractor, pipeline, persistence, and full-suite regressions to prove non-story subjects never yield candidates, valid opaque IDs remain deterministic and payload-safe through readback/metadata, and rejected URL/payload values create no candidate or provenance records.
