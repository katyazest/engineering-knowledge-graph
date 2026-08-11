## Context

The MVP currently has a local bootstrap runner and an in-memory canonical ontology. The product docs define the next useful input as a service registry, but the user clarified that the existing `repo-index.yaml` must evolve into the canonical workspace registry instead of adding another configuration file.

The source material for this evolution is the existing multirepo exploration `repo-index.yaml` template and JSON schema. Today that structure describes workspace identity, repository inventory, local paths, repository roles, exploration rules, and Git safety rules. The Engineering KG needs to extend that stable inventory with local EKG and OpenLore federation configuration while keeping derived facts outside the registry.

## Goals / Non-Goals

**Goals:**

- Treat `repo-index.yaml` as the canonical workspace registry for MVP pipeline bootstrapping.
- Preserve compatibility with the existing repository discovery fields where practical.
- Add explicit local Engineering KG configuration and OpenLore federation inputs.
- Convert registry topology into deterministic canonical graph objects.
- Keep every behavior local-first, independently testable, and free of external-service requirements.

**Non-Goals:**

- Do not add a separate `product-registry.yaml`.
- Do not query OpenLore, Jira, Bitbucket, LadybugDB, Confluence, or cloud services.
- Do not store code structure, architecture relationships, implementation details, Jira data, Bitbucket data, OpenSpec requirements, or generated documentation in the registry.
- Do not implement LadybugDB persistence, OpenLore indexing, wiki generation, MkDocs, llmwiki-cli, dotMD, or semantic extraction.

## Decisions

### `repo-index.yaml` is the registry boundary

The implementation will add a workspace registry loader for `repo-index.yaml` rather than introducing a new file. This avoids duplicate configuration and aligns the multirepository exploration index with the EKG bootstrap input.

Alternative considered: create `product-registry.yaml` as a separate EKG-only registry. Rejected because it would duplicate repository identity, local paths, and roles already maintained by `repo-index.yaml`.

### Preserve repository inventory and add EKG-specific top-level sections

The existing `version`, `workspace`, and `repositories` fields remain the base schema. EKG-specific settings should be introduced under explicit top-level sections such as `engineering_kg` and `openlore` rather than overloading repository discovery fields.

Alternative considered: place all EKG data under each repository. Rejected because pipeline-level configuration and federation policy are workspace-level concerns.

### Model stable topology only

The registry stores stable workspace facts: workspace identity, repositories, roles, local paths, service ownership for MVP, EKG configuration, OpenLore federation inputs, and pipeline stage inputs. It does not store facts that can be derived from repositories or external systems.

Alternative considered: enrich the registry with architecture, code ownership, Jira links, and generated docs. Rejected because it would make the registry compete with OpenLore, OpenSpec, Jira, Bitbucket, and LadybugDB.

### One service maps to one repository in MVP

The MVP constraints state one service equals one repository. The loader should validate this rule and emit deterministic `SERVICE` and `REPOSITORY` nodes plus an ownership edge for each service repository.

Alternative considered: support many-to-many service/repository mappings immediately. Deferred because it complicates validation and does not match the MVP constraint.

### Pipeline integration is optional by configuration

The existing bootstrap runner should remain able to return an empty graph when no registry is configured. When a registry path is supplied, the runner configures and executes the workspace registry stage and includes the resulting graph snapshot.

Alternative considered: require a registry for every runner execution. Rejected because the existing bootstrap behavior is already specified and useful for smoke tests.

## Risks / Trade-offs

- Schema drift from the source multirepo exploration schema → Keep MVP additions explicit and validate the evolved schema with focused fixtures.
- Registry becomes a dumping ground for derived facts → Add validation/tests for forbidden fields and document the ownership boundary in the spec.
- Ambiguous repository roles for EKG behavior → Keep the initial mapping small and deterministic; only repositories with service identity participate in service graph generation.
- YAML dependency adds package surface → Prefer a small local dependency only if needed and keep parsing isolated behind the registry loader.
- Future many-to-many topology may require schema migration → Version the registry and keep MVP validation strict so later migrations are explicit.
