## Why

Plane task `EKG-38` requires a minimal stable relationship vocabulary for the Engineering Knowledge Graph (EKG). The current ontology has relationship names but no single executable contract for their semantics, direction, allowed endpoint kinds, cardinality, source mappings, or the boundary between trusted semantic links and candidate/evidence observations. That leaves extraction, derivation, validation, and documentation able to diverge.

## What Changes

- Define the canonical relationship vocabulary: `TRACES_TO`, `IMPLEMENTS`, `VERIFIED_BY`, `TOUCHES`, `DEPENDS_ON`, `REFERENCES`, `OWNED_BY`, and `PROVIDES`, including semantics, directed endpoints, and cardinality.
- Make relationship admission deterministic: validate canonical edges and trusted cross-graph semantic links against the vocabulary, preserving existing stable IDs and provenance requirements.
- Define source-specific mappings for currently supported OpenSpec extraction and PR-to-code candidate extraction, including explicit handling of unsupported source relationship claims.
- Preserve the existing separation between trusted semantic relationships and candidate/evidence links; candidate observations MUST NOT become trusted semantics without the existing explicit trust lifecycle decision.
- Update relationship extraction, derivation, validation, and repository documentation to use the approved vocabulary.
- **BREAKING**: Relationship kinds outside the approved vocabulary are invalid at the canonical validation boundary. EKG is greenfield: it has no historical deployment or persisted graph data. Therefore this change provides no legacy-alias compatibility, persisted-data migration, backup, or rollback work. Future compatibility work requires an explicit future requirement supported by concrete evidence of pre-canonical data.

## Capabilities

### New Capabilities
- `canonical-relationship-vocabulary`: The stable relationship catalog, source mapping contract, and trusted-versus-candidate boundary.

### Modified Capabilities
- `canonical-ontology`: Canonical relationship representations and compatibility behavior use the vocabulary.
- `openspec-graph-extraction`: OpenSpec structural and traceability relationship extraction maps to approved kinds.
- `graph-derivation`: Deterministic relationship derivation admits only vocabulary-defined outputs.
- `graph-integrity-validation`: Canonical edge and trusted-link endpoint/cardinality validation enforces the vocabulary.
- `cross-graph-link-evidence`: Trusted semantic-link projection is constrained by the vocabulary while candidates remain non-semantic.

## Impact

Affected project-owned components are canonical schemas, OpenSpec extraction, PR candidate handling, derivation, validation, current canonical-format persistence/readback, tests, and relationship documentation. The change does not provide migration, backup, rollback, or compatibility support for historical graph data because no such data exists; compatibility work is out of scope unless a future approved requirement is supported by actual pre-canonical data. It does not modify Graphify, Jira MCP, Bitbucket MCP, OpenLore, LadybugDB, llmwiki-cli, or MkDocs internals. EKG-38 is the traceability source for this change.
