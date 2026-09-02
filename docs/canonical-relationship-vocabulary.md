# Canonical relationship vocabulary (revision 1)

`engineering_kg.relationship_vocabulary` is the executable authority for
semantic-edge and trusted-code-link admission. The catalog reference below is
its deterministic, payload-free serialization: it describes contracts only,
not source documents, provider responses, evidence bodies, or code payloads.
The regression test `RelationshipVocabularyTest.test_published_reference_matches_catalog_serialization`
requires this block to equal `catalog_as_dict()` exactly.

## Relationship contracts

Direction is always **source → target**; no inverse is inferred. “CodeLocator”
means a complete locator (repository, revision, file, and symbol).

| Kind | Semantics | Directed endpoint alternatives | CodeLocator target | Maximum targets per source |
| --- | --- | --- | --- | --- |
| `CONTAINS` | Structural containment. | `SPECIFICATION → REQUIREMENT`; `REQUIREMENT → SCENARIO`; `OPENSPEC_ACTIVE_CHANGE → OPENSPEC_ARTIFACT`; `OPENSPEC_ARCHIVED_CHANGE → OPENSPEC_ARTIFACT` | no | unlimited |
| `TRACES_TO` | Traceability relationship. | `OPENSPEC_ACTIVE_CHANGE`, `OPENSPEC_ARCHIVED_CHANGE`, `REQUIREMENT`, `SCENARIO`, or `JIRA_STORY` → `SPECIFICATION`, `REQUIREMENT`, `SCENARIO`, or `JIRA_STORY` | no | unlimited |
| `IMPLEMENTS` | Implementation relationship. | `JIRA_STORY`, `PULL_REQUEST`, `SERVICE`, `REPOSITORY`, `CONTRACT`, or `BUSINESS_PROCESS` → `SERVICE`, `REPOSITORY`, `CONTRACT`, or `BUSINESS_PROCESS` | yes | unlimited |
| `VERIFIED_BY` | Verification relationship. | `REQUIREMENT`, `SCENARIO`, `JIRA_STORY`, `CONTRACT`, `SERVICE`, or `BUSINESS_PROCESS` → `SCENARIO`, `PULL_REQUEST`, or `CONTRACT` | yes | unlimited |
| `TOUCHES` | Change touches an implementation target. | `JIRA_STORY` or `PULL_REQUEST` → `SERVICE`, `REPOSITORY`, `CONTRACT`, or `BUSINESS_PROCESS` | yes | unlimited |
| `DEPENDS_ON` | Directed dependency. | `SERVICE`, `REPOSITORY`, `CONTRACT`, `BUSINESS_PROCESS`, `JIRA_STORY`, `PULL_REQUEST`, `SPECIFICATION`, `REQUIREMENT`, or `SCENARIO` → the same set | no | unlimited |
| `REFERENCES` | Non-owning reference. | any canonical node kind → any canonical node kind | yes | unlimited |
| `OWNED_BY` | Single ownership assignment. | `SERVICE`, `REPOSITORY`, `CONTRACT`, `BUSINESS_PROCESS`, `SPECIFICATION`, or `ADR` → `WORKSPACE`, `SERVICE`, or `EXTERNAL_SYSTEM` | no | 1 |
| `PROVIDES` | Provider exposes a capability. | `SERVICE`, `REPOSITORY`, or `EXTERNAL_SYSTEM` → `CONTRACT`, `BUSINESS_PROCESS`, or `EXTERNAL_SYSTEM` | no | unlimited |

## Catalog serialization

```json
{
  "revision": "1",
  "relationships": [
    {"classification": "structural", "kind": "contains", "max_targets_per_source": null, "permits_code_locator": false, "semantics": "Structural containment.", "source_kinds": ["openspec-active-change", "openspec-archived-change", "requirement", "specification"], "target_kinds": ["openspec-artifact", "requirement", "scenario"]},
    {"classification": "semantic", "kind": "traces_to", "max_targets_per_source": null, "permits_code_locator": false, "semantics": "Traceability relationship.", "source_kinds": ["jira_story", "openspec-active-change", "openspec-archived-change", "requirement", "scenario"], "target_kinds": ["jira_story", "requirement", "scenario", "specification"]},
    {"classification": "semantic", "kind": "implements", "max_targets_per_source": null, "permits_code_locator": true, "semantics": "Implementation relationship.", "source_kinds": ["business_process", "contract", "jira_story", "pull_request", "repository", "service"], "target_kinds": ["business_process", "contract", "repository", "service"]},
    {"classification": "semantic", "kind": "verified_by", "max_targets_per_source": null, "permits_code_locator": true, "semantics": "Verification relationship.", "source_kinds": ["business_process", "contract", "jira_story", "requirement", "scenario", "service"], "target_kinds": ["contract", "pull_request", "scenario"]},
    {"classification": "semantic", "kind": "touches", "max_targets_per_source": null, "permits_code_locator": true, "semantics": "Change touches an implementation target.", "source_kinds": ["jira_story", "pull_request"], "target_kinds": ["business_process", "contract", "repository", "service"]},
    {"classification": "semantic", "kind": "depends_on", "max_targets_per_source": null, "permits_code_locator": false, "semantics": "Directed dependency.", "source_kinds": ["business_process", "contract", "jira_story", "pull_request", "repository", "requirement", "scenario", "service", "specification"], "target_kinds": ["business_process", "contract", "jira_story", "pull_request", "repository", "requirement", "scenario", "service", "specification"]},
    {"classification": "semantic", "kind": "references", "max_targets_per_source": null, "permits_code_locator": true, "semantics": "Non-owning reference.", "source_kinds": ["*"], "target_kinds": ["*"]},
    {"classification": "semantic", "kind": "owned_by", "max_targets_per_source": 1, "permits_code_locator": false, "semantics": "Single ownership assignment.", "source_kinds": ["adr", "business_process", "contract", "repository", "service", "specification"], "target_kinds": ["external_system", "service", "workspace"]},
    {"classification": "semantic", "kind": "provides", "max_targets_per_source": null, "permits_code_locator": false, "semantics": "Provider exposes a capability.", "source_kinds": ["external_system", "repository", "service"], "target_kinds": ["business_process", "contract", "external_system"]}
  ],
  "source_mappings": [
    {"classification": "structural", "kind": "contains", "source": "openspec-hierarchy", "unsupported_behavior": "diagnose-and-skip"},
    {"classification": "support", "kind": "asserts", "source": "openspec-assertion", "unsupported_behavior": "diagnose-and-skip"},
    {"classification": "non-confident", "kind": "references", "source": "openspec-related", "unsupported_behavior": "diagnose-and-skip"},
    {"classification": "candidate", "kind": "touches", "source": "merged-pr-changed-symbol", "unsupported_behavior": "diagnose-and-skip"}
  ]
}
```

## Source mapping, canonical persistence, and trust boundary

OpenSpec hierarchy maps to structural `CONTAINS`. An OpenSpec assertion is
non-semantic `ASSERTS` support for derived `TRACES_TO`; uniquely resolved
OpenSpec `related` maps to non-confident `REFERENCES`; and merged-PR changed
symbols map to candidate `TOUCHES` claims. Unsupported source claims are
diagnosed and skipped. No supported mapper emits `IMPLEMENTS`, `VERIFIED_BY`,
`DEPENDS_ON`, `OWNED_BY`, or `PROVIDES`.

Persistence and readback accept only revision 1's current canonical format.
Relationship aliases, reversed encodings (including `OWNS`), and historical
candidate claim kinds fail with deterministic diagnostics; they are not
converted, migrated, or backed up.

## Greenfield constraint

EKG has no historical deployment or persisted graph data. This catalog does
not provide compatibility, migration, backup, or rollback behavior. Any future
such work requires an explicit requirement backed by concrete evidence of
pre-canonical data.

Candidates, rejected claims, superseded claims, raw evidence, and `ASSERTS`
support are never trusted semantic projections. Only an explicitly `trusted`
lifecycle, complete provenance, and a catalog-conformant relationship project
as trusted.

## Verification matrix

| Case | Expected outcome |
| --- | --- |
| valid catalog endpoints and complete provenance | admitted |
| reversed/disallowed endpoint or unknown kind | deterministic error |
| two `OWNED_BY` targets | cardinality error |
| non-canonical relationship alias or reversed encoding | deterministic error; no conversion |
| OpenSpec and PR source mappings | catalog mapping above |
| candidate/rejected/superseded claims | not trusted |
| explicit trusted conformant claim | trusted projection |

### Matrix rationale

The matrix has no compatibility, migration, backup, or rollback case because
EKG-38 is bounded by the greenfield constraint above. A future case requires
an explicit requirement backed by concrete evidence of pre-canonical data; it
does not imply compatibility behavior in this revision.
