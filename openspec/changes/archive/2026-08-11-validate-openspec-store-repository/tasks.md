## 1. Store Discovery and Validation Model

- [x] 1.1 Add OpenSpec store discovery/result dataclasses for registered store id, resolved path, selection source, selected repository id, OpenSpec root, specs path, changes path, and validation status.
- [x] 1.2 Add an OpenSpec store source validation error type with explicit messages for missing store path, missing OpenSpec root, missing specs/changes directories, and registered-store mismatch.
- [x] 1.3 Add a narrow discovery adapter that can consume structured OpenSpec store list/config data without coupling validation tests to shell command execution.

## 2. Store Selection Policy

- [x] 2.1 Implement requirements repository resolution from `registry.engineering_kg.store_repository` and require the matched repository entry to have role `requirements`.
- [x] 2.2 Implement registered-store selection for exactly one registered store, accepting it only when its resolved path matches the requirements repository path.
- [x] 2.3 Implement registered-store selection for multiple registered stores, choosing the store whose resolved path matches the requirements repository path.
- [x] 2.4 Require explicit store selection or configuration when registered stores exist but none match the requirements repository path.
- [x] 2.5 Implement fallback to the requirements repository path only when OpenSpec store discovery returns no registered stores.
- [x] 2.6 Ensure validation never uses process current working directory or nearest OpenSpec root discovery as the extraction source.

## 3. OpenSpec Root Checks

- [x] 3.1 Validate that the selected registered store or fallback requirements repository path exists as a directory.
- [x] 3.2 Validate that the selected store exposes a usable OpenSpec root with `specs` and `changes` directories.
- [x] 3.3 Serialize validation metadata deterministically without specification bodies, change bodies, source code, generated graph records, credentials, tokens, or external API payloads.

## 4. Pipeline Integration

- [x] 4.1 Add `openspec-store-source` as an optional pipeline stage executed after `workspace-registry` and before later OpenSpec extraction stages.
- [x] 4.2 Add the OpenSpec store source validation result to `PipelineResult` and deterministic `as_dict()` output when the stage runs.
- [x] 4.3 Preserve existing bootstrap, registry-only, OpenLore-source, and LadybugDB persistence behavior when `openspec-store-source` is not configured.
- [x] 4.4 Update the script wrapper output so configured OpenSpec store source validation is reported through the reusable pipeline result without script-level validation logic.

## 5. Fixtures and Tests

- [x] 5.1 Add fixtures for no registered stores falling back to the repo-index requirements repository.
- [x] 5.2 Add fixtures for one registered store matching the requirements repository.
- [x] 5.3 Add fixtures for one registered store not matching the requirements repository and assert explicit-selection failure.
- [x] 5.4 Add fixtures for multiple registered stores where one matches the requirements repository.
- [x] 5.5 Add fixtures for multiple registered stores where none match the requirements repository and assert explicit-selection failure.
- [x] 5.6 Add tests for missing selected store path, missing OpenSpec root, missing `specs`, and missing `changes`.
- [x] 5.7 Add pipeline tests for configured/executed stage order and deterministic OpenSpec store source metadata.
- [x] 5.8 Run the focused test suite and `openspec validate validate-openspec-store-repository`.
