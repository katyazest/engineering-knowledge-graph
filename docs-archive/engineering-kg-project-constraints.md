# Engineering Knowledge Graph — Project Constraints

## General
- Local-first architecture.
- Deterministic processing by default.
- Engineering Knowledge Graph is the canonical engineering knowledge source.
- OpenLore is the canonical code intelligence source.
- Generated documentation is never the source of truth.

## Runtime
- Runs completely locally.
- No cloud dependency for the core pipeline.
- No Internet required after dependencies are installed.
- Executable from Python scripts.

## API Keys
- Core pipeline requires no API keys.
- Cloud LLM integrations are optional.
- Components requiring API keys must be replaceable or disabled.

## Packaging
- No compilation.
- No build artifacts.
- No PyPI publishing.
- No Docker requirement.
- No wheel generation.
- Reusable logic in Python modules.
- Scripts are the primary execution interface.
- Same modules can later be exposed via MCP.

## Preferred Stack
- Python 3.12+
- uv
- Pydantic
- LadybugDB
- OpenLore
- OpenSpec
- Jinja2
- MkDocs
- llmwiki-cli
- dotMD (optional)

## Code Intelligence
- OpenLore owns the complete code graph.
- LadybugDB never duplicates the code graph.
- LadybugDB references code through CodeLocator:
  - repository
  - revision
  - file
  - symbol
- Detailed code information is resolved through OpenLore MCP.

## Multi-Repository
- One service = one repository.
- Product = multiple repositories.
- Each repository owns its own OpenLore index.
- Store/OpenSpec repository owns federation configuration only.
- Store validates federation freshness but never rebuilds indexes.

## Pipeline
Service Registry → OpenLore → OpenSpec → Jira MCP → Bitbucket MCP → Normalization → LadybugDB → Derivation → Validation → Projection → Markdown → llmwiki-cli → MkDocs → dotMD (optional)

## MCP
- Business logic is independent of MCP.
- Scripts and MCP wrappers call the same reusable functions.
- MCP wrappers contain no business logic.

## Testing
- Every stage is independently testable.
- Every stage has explicit verification criteria.
- Unit tests do not require live external infrastructure.
- External systems are mocked or replayed from fixtures.

## External Infrastructure
External dependencies:
- OpenLore
- Jira MCP
- Bitbucket MCP
- LadybugDB
- llmwiki-cli
- MkDocs

The project owns only adapters and orchestration.

## Out of Scope
- Mandatory cloud LLMs.
- Mandatory semantic extraction.
- Copying the full code graph into LadybugDB.
- Runtime distributed tracing.
- Modifying external tools.
- AI-generated specifications.
