---
repo: payment-service
created: 2026-08-01
updated: 2026-08-12
title: Payments Capability
related:
  - Settlement Capability
  - Missing Capability
---

## ADDED Requirements

### Requirement: Payment is submitted
The system SHALL submit payments.

#### Scenario: Valid payment
- **WHEN** a valid payment is submitted
- **THEN** the payment is accepted

## Requirement: Unsupported heading is ignored

#### Scenario: Still belongs to previous requirement
- **WHEN** unsupported heading appears
- **THEN** it does not become a requirement
