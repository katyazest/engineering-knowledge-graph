## Why

Plane `EKG-64` asks for anti-hallucination and evidence-use rules for agent-facing graph facts. EKG-41 already classifies support and constrains trusted implementation; EKG-43 already assesses as-of freshness, but neither defines a single agent-facing contract for unknown, stale, conflicting, candidate and inferred answers or for explaining critical conclusions. The existing local query and FactMCP boundaries make prose alone insufficient for the task's observable E2E criterion.

## What Changes

- Establish a deterministic, executable evidence-use policy over **represented** graph relationships and support: naming conventions, textual similarity, prompt context and LLM guesses never create or promote authoritative relationships.
- Expose explicit unresolved/`unknown` treatment for missing evidence, stale or uncheckable support, unresolved conflicts, candidate claims and inferred support, without suppressing their auditable references or changing their stored classifications.
- Require a resolvable path of canonical relationship, evidence and provenance references before an agent-facing result can assert an implementation-ownership or change-readiness conclusion. No new rule for *which* owner or *when* a change is ready is introduced; without an approved readiness decision contract, readiness remains unresolved rather than guessed.
- Add fixture-driven E2E checks through the local query and thin MCP boundaries demonstrating that missing evidence produces `unknown`/unresolved output, not fabricated traceability. Document the same rules for agent consumers.

## Capabilities

### New Capabilities
- `agent-evidence-use-policy`: Evidence-use states, authority gate, explainable critical conclusions, and named verification matrix.

### Modified Capabilities
- `local-ekg-query-api`: Project the shared policy and evidence paths without generating absent relationships or breaking existing fact/traceability output.
- `ekg-mcp-query-wrappers`: Forward the policy result and critical-conclusion explanation through agent-facing tools without wrapper-owned inference.

## Impact

Project-owned Python policy/query modules, thin FactMCP wrappers, documentation and fixture/E2E tests change. Current catalog, classified evidence/trust, as-of freshness, merge and persistence remain authoritative inputs; canonical schemas, stable graph IDs, persisted snapshots and migration format do not change. Existing response fields and tool calls remain valid; policy fields and an opt-in explanation operation are additive. Graphify, Jira/Bitbucket MCP, OpenLore, LadybugDB and any LLM remain external; no new external calls, external configuration or infrastructure implementation is proposed. This change follows completed EKG-41 and EKG-43 and precedes EKG-61. EKG-10's upstream issue references are context only, not asserted dependencies. Non-goals: deriving owners from repository naming, choosing a conflict winner, inventing checked revisions, approving a readiness checklist/threshold, changing trust promotion or implementing an autonomous agent.
