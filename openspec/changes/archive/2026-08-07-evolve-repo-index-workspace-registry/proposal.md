## Why

The existing `repo-index.yaml` already inventories repositories for product workspace discovery, but the Engineering KG MVP needs a canonical local workspace description that can also bootstrap deterministic pipeline stages. Evolving this file avoids duplicate registry/configuration files and establishes one human-editable source of truth for stable workspace topology.

## What Changes

- Evolve `repo-index.yaml` from repository inventory into the canonical workspace registry.
- Define workspace identity, repository roles, local repository paths, Engineering KG configuration, OpenLore federation configuration, and pipeline orchestration inputs in the registry.
- Add a registry loader that validates the local registry and converts stable topology into canonical graph objects.
- Keep the registry deterministic, version-controlled, local-first, and independent of external services.
- Explicitly exclude derived or external-system facts from the registry: code structure, architecture relationships, implementation details, Jira data, Bitbucket data, OpenSpec requirements, and generated documentation.
- Integrate the registry as the first real pipeline input while preserving the existing bootstrap behavior when no registry path is provided.

## Capabilities

### New Capabilities
- `workspace-registry`: Defines loading, validation, and canonical graph conversion for the evolved `repo-index.yaml` workspace registry.

### Modified Capabilities
- `pipeline-runner`: Allows the local runner to execute the workspace registry stage when configured, while preserving deterministic empty bootstrap behavior without configured stages.

## Impact

- Affected code: `src/engineering_kg/project/`, `src/engineering_kg/pipeline.py`, `scripts/build.py`, and tests.
- Affected artifacts: `repo-index.yaml` schema/template source material from the multirepo exploration skill may be adapted into this repository as local test fixtures or documentation examples.
- Dependencies: local YAML parsing and JSON schema validation may be introduced if needed, but the core behavior remains local-first and does not require API keys, network access, OpenLore queries, Jira, Bitbucket, LadybugDB persistence, generated documentation, or cloud services.
