## 1. Extraction Tests

- [x] 1.1 Add nested durable `spec.md` fixture coverage under the OpenSpec graph extraction test workspace.
- [x] 1.2 Add nested active-change and archived-change delta `spec.md` fixture coverage under the OpenSpec graph extraction test workspace.
- [x] 1.3 Update extraction assertions to verify flat capabilities remain unchanged and nested capabilities use slash-delimited relative identities.
- [x] 1.4 Update deterministic extraction assertions to include nested durable and change-scoped specs in counts and evidence paths.

## 2. Extraction Implementation

- [x] 2.1 Replace one-level durable spec discovery with sorted recursive `spec.md` discovery under the validated durable specs path.
- [x] 2.2 Replace one-level change-scoped spec discovery with sorted recursive `spec.md` discovery under each change's local `specs` path.
- [x] 2.3 Add a helper that derives capability identity from the path relative to the scope-specific `specs` root with the trailing `spec.md` removed.
- [x] 2.4 Use the derived capability identity consistently for spec, requirement, scenario, relationship, and OpenSpec identity properties.

## 3. Derivation Verification

- [x] 3.1 Add derivation test coverage proving a change-scoped `service/payments` spec traces to a durable `service/payments` spec.
- [x] 3.2 Add derivation test coverage proving `service-a/payments` does not trace to `service-b/payments`.
- [x] 3.3 Confirm derivation implementation needs no filesystem-aware matching changes beyond consuming the extracted capability identity.

## 4. Validation

- [x] 4.1 Run focused extraction and derivation tests.
- [x] 4.2 Run the full test suite.
- [x] 4.3 Run `openspec validate --changes "support-nested-durable-specs"` and resolve any validation failures.
