## 1. Registry Model and Parsing

- [x] 1.1 Add registry model fields for the project workspace root and resolved workspace-level generated state paths.
- [x] 1.2 Parse workspace layout configuration from `repo-index.yaml` while preserving existing registry-file-relative repository path behavior.
- [x] 1.3 Expose deterministic resolved paths for the workspace root, workspace OpenLore location, and local graph storage location.

## 2. Validation

- [x] 2.1 Validate that `engineering_kg.store_repository` references an existing repository with the `requirements` role.
- [x] 2.2 Validate that implementation repositories remain separate repository entries under the workspace layout.
- [x] 2.3 Validate that workspace OpenLore and graph storage paths are outside configured repository roots.
- [x] 2.4 Keep validation local-first without requiring network access, API keys, OpenLore queries, LadybugDB writes, Jira, Bitbucket, Confluence, or MCP servers.

## 3. Canonical Graph Output

- [x] 3.1 Include stable workspace layout references in canonical graph serialization.
- [x] 3.2 Include the configured OpenSpec store repository reference in graph output.
- [x] 3.3 Ensure graph output excludes generated OpenLore contents, generated graph data, source code contents, and fetched external-system data.
- [x] 3.4 Verify repeated conversion of the same registry remains deterministic.

## 4. Fixtures, Schema, and Documentation

- [x] 4.1 Add a fixture for the target non-Git workspace layout with `.openlore/`, `.engineering-kg/ladybugdb/`, `src/codebase_repos/`, and `openspec/requirements_repo/`.
- [x] 4.2 Add invalid fixtures for a store repository with the wrong role and generated-state paths nested inside repository roots.
- [x] 4.3 Update the registry schema or examples to document the accepted workspace layout fields.

## 5. Verification

- [x] 5.1 Add unit tests for workspace root parsing and generated-state path resolution.
- [x] 5.2 Add unit tests for OpenSpec store repository validation.
- [x] 5.3 Add unit tests for generated-state ownership boundary validation.
- [x] 5.4 Run the focused workspace registry tests.
- [x] 5.5 Run `openspec validate support-local-workspace-layout`.
