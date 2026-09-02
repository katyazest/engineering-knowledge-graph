## ADDED Requirements

### Requirement: Cross-graph claims use catalog relationship kinds
Cross-graph link claims SHALL use only catalog-defined relationship kinds that permit the claim subject kind and a complete `CodeLocator` target. Candidate observations SHALL remain candidate evidence until an explicit trusted lifecycle revision; trusted projection SHALL reject a claim that no longer conforms to the catalog.

#### Scenario: PR observation is a candidate TOUCHES claim
- **WHEN** PR-code candidate extraction produces a valid explicitly linked merged-PR changed-symbol observation
- **THEN** it produces a `TOUCHES` candidate claim and attributable evidence
- **THEN** it does not produce a trusted semantic link or an `IMPLEMENTS` edge
