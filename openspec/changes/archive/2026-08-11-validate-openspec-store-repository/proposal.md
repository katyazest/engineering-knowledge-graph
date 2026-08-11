## Why

Engineering KG must extract specifications and intended changes from the correct OpenSpec store, not from the local project workspace, implementation repositories, generated OpenLore indexes, or generated graph storage. OpenSpec's local store registry/config is the primary source of store identity; when no store is registered, the pipeline needs an explicit fallback to the requirements repository from `repo-index.yaml` so extraction still uses the intended source of truth.

## What Changes

- Add validation for the selected OpenSpec store repository before any OpenSpec specification or change extraction runs.
- Resolve the store from OpenSpec's registered store list/config when a store is registered.
- If multiple OpenSpec stores are registered, choose the registered store whose path matches the requirements repository identified in `repo-index.yaml`.
- If exactly one OpenSpec store is registered, require it to match the requirements repository identified in `repo-index.yaml`.
- If registered store discovery and `repo-index.yaml` do not identify the same requirements repository store, require explicit store selection.
- If no OpenSpec store is registered, fall back to the requirements repository identified by `engineering_kg.store_repository` in `repo-index.yaml`.
- Cross-check the selected or fallback store repository against the workspace registry so it is the requirements repository and contains a usable OpenSpec root.
- Ensure extraction inputs resolve from the validated store path, while generated OpenLore and LadybugDB state remain outside all configured Git repositories.
- Report deterministic validation metadata for the store repository source without reading implementation code or generated graph contents.
- Preserve local-first behavior with no network, credentials, cloud services, Jira, Bitbucket, Confluence, OpenLore MCP, or generated documentation dependency.

## Capabilities

### New Capabilities

- `openspec-store-source`: Validates the OpenSpec store source for durable specifications, intended changes, wiki content, and versioned Engineering KG configuration, using OpenSpec's registered store configuration first and falling back to the requirements repository from `repo-index.yaml` only when no store is registered.

### Modified Capabilities

- `workspace-registry`: Strengthen the requirements repository contract so the registry can cross-check a registered OpenSpec store or provide the fallback store path when no OpenSpec store is registered.
- `pipeline-runner`: Add execution and reporting for an OpenSpec store source validation stage before later OpenSpec extraction stages.

## Impact

- Affected specs: `workspace-registry`, `pipeline-runner`, and new `openspec-store-source`.
- Affected code will likely include registry validation models/helpers, pipeline stage orchestration, deterministic validation metadata, and tests.
- No changes to external APIs, credentials, network integrations, OpenLore-owned code intelligence, Jira/Bitbucket/Confluence adapters, or LadybugDB persistence format are intended.
