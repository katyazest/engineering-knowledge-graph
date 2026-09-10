# Cross-graph evidence classification and trust

Every cross-graph observation and lifecycle support record stores one `origin`
(`declared`, `observed`, or `inferred`), one `status` (`authoritative` or
`derived`), an opaque payload-safe non-empty `confidence` label, and one
explicit `trust_disposition` (`trusted` or `untrusted`). Confidence has no
scale, ordering, threshold, or promotion semantics.

`IMPLEMENTS` is projected only with catalog-valid endpoints, complete
provenance, an explicit trusted lifecycle, and authoritative declared trusted
observation support. PR/file observations and LLM-only inference remain
auditable, non-trusted evidence. Valid conflicting support is retained; count,
order, confidence, and merged PR state never select or promote a record.

The catalog revision is `3`. Older persisted support records lacking these
fields are rejected at readback: there is no legacy backfill or migration.

## EKG-41 verification matrix

| Input class | Executable coverage |
| --- | --- |
| Authoritative declared support + trusted lifecycle | `CrossGraphLinkEvidenceTest.test_declared_authoritative_support_with_explicit_trusted_lifecycle_projects` |
| Observed PR/file support | `PrCodeCandidateExtractionTest.test_candidates_are_observed_complete_and_idempotent` |
| LLM-only inferred support | `CrossGraphLinkEvidenceTest.test_observed_and_inferred_implementation_never_project` |
| Conflicting valid support | `CrossGraphLinkEvidenceTest.test_conflicting_valid_support_is_retained_and_repeated_support_coalesces` |
| Missing, unknown, contradictory, or payload-bearing classification/trust field | `CrossGraphLinkEvidenceTest.test_classification_is_required_payload_safe_and_part_of_identity`; `CrossGraphLinkEvidenceTest.test_inferred_authoritative_support_is_rejected_at_admission_and_validation`; `CrossGraphLinkEvidenceTest.test_persistence_round_trip_and_missing_classification_rejection` |
| Repeated equivalent classified support | `CrossGraphLinkEvidenceTest.test_conflicting_valid_support_is_retained_and_repeated_support_coalesces` |
| Legacy record missing fields | `CrossGraphLinkEvidenceTest.test_persistence_round_trip_and_missing_classification_rejection` |
