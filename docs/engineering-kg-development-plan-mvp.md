# Engineering KG Development Plan (MVP)

## Target workspace layout

The MVP assumes a local project workspace that is not itself a Git repository:

```text
project-directory/
├── .engineering-kg/
│   └── ladybugdb/              # local generated Engineering KG store
├── .openlore/                  # local generated OpenLore workspace index
├── src/
│   └── codebase_repos/
│       ├── service-a/          # one or more implementation Git repositories
│       └── service-b/
└── openspec/
    └── requirements_repo/      # one Git repository registered as the OpenSpec store
        ├── openspec/
        ├── wiki/
        └── repo-index.yaml
```

The local project directory owns generated graph/index state. The requirements
repository owns durable requirements, OpenSpec specifications, wiki content, and
Engineering KG configuration. Source repositories remain independent Git
repositories under `src/codebase_repos/`.

## MVP sequence

1. Project skeleton
2. Canonical ontology
3. Workspace and service registry
4. Local LadybugDB-compatible graph store
5. Workspace-level OpenLore source validation
6. Requirements repository / OpenSpec store extractor
7. OpenSpec extractor
8. Jira MCP adapter
9. Bitbucket MCP adapter
10. Normalization
11. Persistence merge/readback
12. Deterministic derivation
13. Validation
14. Reusable Python API
15. Script wrappers
16. MCP wrappers

Final architecture:
Scripts/MCP → Reusable Python modules → LadybugDB
OpenLore remains the authoritative code graph. The Engineering KG stores only
local canonical engineering facts and `CodeLocator` references.
