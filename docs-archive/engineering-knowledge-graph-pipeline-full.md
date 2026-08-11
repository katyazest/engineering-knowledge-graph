# Engineering Knowledge Graph Pipeline

## Goal

Build a product-level Engineering Knowledge Graph (EKG) that connects engineering artifacts while **keeping OpenLore as the authoritative code intelligence platform**.

## High-Level Architecture

The solution consists of two cooperating graphs:

### OpenLore (authoritative code graph)

Owns:

- Static code graph
- Files, modules, packages
- Classes, interfaces, functions
- Call graph
- Dependency graph
- Architecture graph
- Cross-repository federation
- Impact analysis
- Structural diff
- Incremental indexing
- Code navigation
- Symbol resolution

OpenLore is queried through MCP and is never duplicated into LadybugDB.

### LadybugDB (canonical Engineering Knowledge Graph)

Owns:

- Services
- Repositories
- Specifications
- Requirements
- OpenSpec Changes
- Jira Stories
- Pull Requests
- ADRs
- Business Processes
- External Systems
- Contracts
- Provenance
- Deterministic derived relationships
- CodeLocator references

LadybugDB never stores the complete code graph.

Important runtime caveat:

- `@ladybugdb/core` exposes a Node in-process API and no `ladybugdb` CLI.
- The Python MVP uses an isolated deterministic local adapter-compatible store.
- A later adapter-focused change can bind this persistence boundary to the Node package through a bridge without changing pipeline callers.

### OpenSpec

Owns:

- Intended changes
- Specifications
- Deterministic implementation requirements

### Wiki

Generated projection of LadybugDB.

Markdown is never the canonical source of engineering facts.

---

## Ownership

| Component | Responsibility |
|-----------|----------------|
| OpenLore | Code intelligence |
| OpenSpec | Intended engineering changes |
| Jira | Work tracking |
| Bitbucket | Implementation evidence |
| LadybugDB | Canonical Engineering Knowledge Graph |
| Wiki | Generated documentation |

---

## Repository Topology

```text
workspace/
├── engineering-kg/
├── product-specs/
├── payment-service/
├── order-service/
├── customer-service/
└── shared-contracts/
```

---

## Store Repository Responsibilities

The store (product-specs) repository owns:

- OpenSpec repository
- Federation configuration
- Engineering KG configuration
- LadybugDB database
- Generated Wiki
- Pipeline orchestration

The store repository DOES NOT own:

- Source code
- OpenLore indexes
- MCP servers

---

## OpenLore Federation

Every code repository owns its own OpenLore index.

The store repository only:

- registers repositories
- configures federation
- validates freshness
- performs cross-repository queries

It never rebuilds code indexes.

---

## Code Locator

LadybugDB references code using:

- repository
- revision
- file
- symbol

Detailed code information is resolved dynamically through OpenLore MCP.

---

## Pipeline

1. Service registry
2. OpenLore indexing (per repository)
3. OpenSpec extraction
4. Jira MCP extraction
5. Bitbucket MCP extraction
6. Normalize external data
7. Persist canonical graph
8. Derive deterministic relationships
9. Validate graph
10. Build Projection DTOs
11. Render Markdown
12. Update Wiki using llmwiki-cli
13. Publish with MkDocs
14. Index documentation with dotMD (optional)

---

## Index Lifecycle

Developer edits code

↓

OpenLore watcher updates local index

↓

Repository CI runs openlore analyze

↓

Updated repository index

↓

Store repository validates federation freshness

↓

Engineering KG pipeline

---

## Traceability

OpenSpec Change
→ Jira Story
→ Pull Request
→ Repository
→ Service
→ CodeLocator
→ OpenLore MCP
