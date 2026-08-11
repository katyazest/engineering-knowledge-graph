# Engineering KG Constraints (MVP)

- Local-first.
- Deterministic by default.
- No API keys required.
- No cloud dependency.
- No compilation or publishing.
- Run from Python scripts.
- Reusable Python modules.
- OpenLore owns code graph.
- LadybugDB stores engineering knowledge only.
- Engineering KG graph data is local generated state.
- One service = one repository.
- The project workspace may own one workspace-level OpenLore index.
- The project workspace is not required to be a Git repository.
- Implementation repositories live under the project workspace as independent Git repositories.
- One requirements repository is registered as the OpenSpec store.
- The requirements repository owns durable specifications, wiki content, and Engineering KG configuration.
- The requirements repository does not own generated OpenLore indexes or generated LadybugDB graph data.
- Every stage independently testable.

Out of scope:
- MkDocs
- llmwiki-cli
- dotMD
- Semantic extraction
- Cloud LLMs
- Publishing generated graph data
