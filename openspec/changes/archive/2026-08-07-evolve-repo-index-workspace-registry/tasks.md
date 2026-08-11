## 1. Registry Schema And Fixtures

- [x] 1.1 Add a local evolved `repo-index.yaml` fixture based on the multirepo exploration template.
- [x] 1.2 Add schema coverage for workspace identity, repository inventory, repository roles, local paths, Engineering KG configuration, OpenLore federation configuration, and pipeline orchestration inputs.
- [x] 1.3 Add negative fixtures or tests for duplicate MVP service mappings and forbidden derived/external-system fields.

## 2. Workspace Registry Loader

- [x] 2.1 Add a reusable `engineering_kg.project` registry module for loading `repo-index.yaml` from a local path.
- [x] 2.2 Resolve repository paths relative to the registry file location.
- [x] 2.3 Validate required repository inventory fields compatible with the existing repo-index format.
- [x] 2.4 Validate the MVP rule that each service identity maps to exactly one repository.
- [x] 2.5 Ensure registry loading does not contact external services or require credentials.

## 3. Canonical Graph Conversion

- [x] 3.1 Add any minimal ontology support needed for workspace registry graph output.
- [x] 3.2 Convert valid registry content into deterministic workspace, service, and repository nodes.
- [x] 3.3 Create deterministic workspace-to-repository and service-to-repository ownership edges.
- [x] 3.4 Preserve the OpenLore boundary by storing only configured federation inputs and no code graph details.

## 4. Pipeline And Script Integration

- [x] 4.1 Extend the reusable pipeline function to accept an optional workspace registry path.
- [x] 4.2 Configure and execute the workspace registry stage when a registry path is supplied.
- [x] 4.3 Preserve the existing empty bootstrap result when no registry path is supplied.
- [x] 4.4 Extend `scripts/build.py` to accept an optional local registry path and delegate it to the reusable pipeline function.

## 5. Verification

- [x] 5.1 Add unit tests proving valid registry loading and deterministic serialization.
- [x] 5.2 Add validation tests for relative path resolution and duplicate service mapping rejection.
- [x] 5.3 Add pipeline tests proving registry-stage execution is deterministic and graph counts are reported.
- [x] 5.4 Add script smoke tests for both empty bootstrap execution and registry-path execution.
- [x] 5.5 Run the local test suite and validate the OpenSpec change.
