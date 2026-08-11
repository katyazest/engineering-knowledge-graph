# Engineering Knowledge Graph Development Plan

## Stage 0 — Project skeleton

Tasks

- Create repository
- Configure Python environment
- Create scripts/
- Create src/
- Configure tests

Verification

- CLI starts

---

## Stage 1 — Canonical schemas

Tasks

- Pydantic models
- Node model
- Edge model
- Evidence model
- Stable IDs

Verification

- Serialization tests pass

---

## Stage 2 — Service registry

Tasks

- product-registry.yaml
- Registry loader

Verification

- Repository → Service mapping

---

## Stage 3 — LadybugDB

Tasks

- Initialize database
- Persistence layer

Verification

- Empty graph created

---

## Stage 4 — OpenLore (single repository)

Tasks

- Install OpenLore
- Analyze one repository
- Verify MCP connectivity

Verification

- Repository indexed
- Basic MCP queries succeed

---

## Stage 5 — OpenLore federation

Tasks

- Register repositories
- Configure spec-store
- Validate federation

Verification

- Cross-repository queries work

---

## Stage 6 — OpenSpec extractor

Tasks

- Parse changes
- Parse specifications
- Parse requirements

Verification

- Change → Specification → Requirement graph exists

---

## Stage 7 — Jira MCP

Tasks

- Import stories

Verification

- Jira Story nodes created

---

## Stage 8 — Bitbucket MCP

Tasks

- Import pull requests

Verification

- PR metadata imported

---

## Stage 9 — Normalization

Tasks

- Map OpenSpec
- Map Jira
- Map Bitbucket
- Create canonical models

Verification

- Canonical graph objects produced

---

## Stage 10 — Persistence

Tasks

- Persist engineering entities
- Store CodeLocator references only

Verification

- Engineering graph stored
- No code graph duplicated

---

## Stage 11 — Derivation

Tasks

- IMPLEMENTS_CHANGE
- IMPLEMENTS
- Other deterministic rules

Verification

- Derived relationships generated

---

## Stage 12 — Validation

Tasks

- Integrity rules
- Traceability rules
- Provenance validation

Verification

- Broken links detected

---

## Stage 13 — Projection

Tasks

- DTO models
- Projection queries

Verification

- DTOs generated

---

## Stage 14 — Markdown renderer

Tasks

- Templates
- Markdown generation

Verification

- Pages generated

---

## Stage 15 — llmwiki-cli

Verification

- Wiki updated

---

## Stage 16 — MkDocs

Verification

- Site builds

---

## Stage 17 — dotMD (optional)

Verification

- Documentation search works

---

## Stage 18 — Reusable API

Tasks

- Expose every pipeline stage as reusable Python functions

Verification

- Functions callable independently

---

## Stage 19 — Script wrappers

Tasks

- Local scripts wrapping reusable API

Verification

uv run python scripts/build.py executes complete pipeline

---

## Stage 20 — MCP wrappers

Tasks

- Thin MCP wrappers

Verification

- Same reusable functions callable through MCP
- No business logic duplicated

---

## Final Architecture

Scripts        MCP
    \        /
     \      /
  Reusable Python modules
           |
      LadybugDB
 (Engineering Knowledge Graph)

OpenLore
(authoritative code graph)
        ^
        |
   accessed through MCP

## Rule

Every stage must be independently testable and verifiable.
