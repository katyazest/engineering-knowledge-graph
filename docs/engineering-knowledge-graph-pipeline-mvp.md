# Engineering Knowledge Graph Pipeline (MVP)

## Goal
Build a deterministic, local-first Engineering Knowledge Graph.

- OpenLore = authoritative code intelligence.
- LadybugDB-compatible local store = canonical engineering knowledge graph.
- The graph is local generated state, not a cloud service and not a published artifact.

## Workspace layout

```text
project-directory/                 # local workspace, not a Git repository
├── .engineering-kg/ladybugdb/      # local generated EKG graph store
├── .openlore/                      # local generated OpenLore workspace index
├── src/codebase_repos/*            # implementation Git repositories
└── openspec/requirements_repo/     # OpenSpec store Git repository
```

## Ownership
- Local project directory: generated OpenLore index and generated EKG graph data.
- OpenLore: code graph, architecture, impact, and symbol resolution.
- OpenSpec store repository: specifications, intended changes, wiki, and EKG configuration.
- Jira: work tracking.
- Bitbucket: implementation evidence.
- LadybugDB-compatible local store: canonical engineering knowledge graph.

## Store repository
Owns OpenSpec, requirements, wiki, and versioned Engineering KG configuration.
Does not own source code, OpenLore indexes, or generated LadybugDB graph data.

## Local graph storage
The MVP graph is stored under the local project directory, for example:

```text
project-directory/.engineering-kg/ladybugdb/
```

The requirements repository may define the graph configuration, but the graph
itself is generated local state.

## CodeLocator
LadybugDB stores only:
- repository
- revision
- file
- symbol

Details are resolved through OpenLore MCP.

## Pipeline
Workspace Registry → Workspace OpenLore → OpenSpec Store → Jira MCP → Bitbucket MCP → Normalize → LadybugDB-compatible local store → Derive → Validate → MCP queries

## Index lifecycle
Developer → OpenLore workspace analysis → Requirements repo validates configured workspace layout → EKG pipeline
