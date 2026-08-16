## Why

The MVP has local-first stage contracts for registry loading, OpenSpec store validation, graph extraction, persistence, derivation, validation, and query access, but there is not yet one local scenario proving those contracts work together as a single flow. A system analyst needs a deterministic end-to-end check to verify that the generated Engineering KG can be built and queried from the intended workspace and OpenSpec inputs without relying on cloud services, credentials, or implementation-specific assumptions.

## What Changes

- Add one end-to-end local MVP scenario that starts from a workspace registry and selected OpenSpec store source.
- Run the configured pipeline through local graph persistence, persistence readback, deterministic derivation, graph integrity validation, and local query access.
- Use local fixture data that represents the non-Git project workspace layout with independent implementation repositories and one requirements/OpenSpec store repository.
- Verify that the final graph and query outputs are deterministic across repeated runs.
- Verify that stage metadata and query results preserve ownership boundaries by excluding source bodies, OpenLore-owned code intelligence, external-system payloads, credentials, and generated graph internals.
- Preserve the existing local-first, credential-free execution model.

## Capabilities

### New Capabilities
- `mvp-e2e-scenario`: Defines the deterministic local end-to-end MVP scenario used to prove the full Engineering KG flow from configured workspace inputs through persisted, derived, validated, and queryable graph facts.

### Modified Capabilities
- `pipeline-runner`: Adds the requirement that the runner can execute the complete MVP stage sequence in one configured local run and expose enough deterministic result metadata for end-to-end verification.

## Impact

- OpenSpec specs: add a new `mvp-e2e-scenario` capability and update `pipeline-runner` requirements.
- Python pipeline modules and script wrappers may need to compose existing stage outputs without adding stage-specific business logic to scripts.
- Tests and fixtures may need one representative local workspace/OpenSpec store fixture covering registry, OpenSpec extraction, persistence, derivation, validation, and query assertions.
- No API, cloud, publishing, compilation, OpenLore query, Jira, Bitbucket, Confluence, or credential dependency is introduced.
