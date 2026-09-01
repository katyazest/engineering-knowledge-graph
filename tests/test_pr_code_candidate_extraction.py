from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.ingest.pr_code_candidates import (
    ChangedSymbolMapping,
    EngineeringChangePrAssociation,
    MappingOutcome,
    MergedPrChangeSet,
    PrCodeCandidateValidationError,
    extract_pr_code_candidates,
    normalize_merged_pr_change_set,
)
from engineering_kg.ontology import (
    CrossGraphLinkLifecycle,
    Evidence,
    GraphSnapshot,
    Node,
    NodeKind,
    SourceArtifactLocator,
)
from engineering_kg.persistence import initialize_ladybugdb_store
from engineering_kg.query import EngineeringKgQuery
from engineering_kg.validation import validate_graph_integrity


class PrCodeCandidateExtractionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.subject = Node("change-1", NodeKind.JIRA_STORY, "EKG-72")
        self.raw = {
            "association": {"id": "jira-link-1", "engineering_change_subject_id": self.subject.id, "pull_request_id": "pr-42", "provider_payload": {"secret": "ignored"}},
            "pull_request_id": "pr-42", "repository": "payment-service", "merged_revision": "a" * 40, "merged": True,
            "observed_at": "2026-09-01T12:00:00+00:00",
            "mappings": [{"id": "graphify:mapping-1", "file": "src/payments.py", "outcome": "resolved", "symbol": "payments.submit", "source_code": "ignored"}],
            "diff": "ignored",
        }

    def test_normalization_is_frozen_deterministic_and_payload_free(self) -> None:
        first = normalize_merged_pr_change_set(self.raw)
        second = normalize_merged_pr_change_set(self.raw)
        self.assertEqual(first, second)
        self.assertEqual(first.id, second.id)
        self.assertNotIn("ignored", repr(first))
        with self.assertRaisesRegex(PrCodeCandidateValidationError, "change_set must be merged"):
            normalize_merged_pr_change_set({**self.raw, "merged": False})
        with self.assertRaisesRegex(PrCodeCandidateValidationError, "mapping.file"):
            normalize_merged_pr_change_set({**self.raw, "mappings": [{"id": "graphify:m", "file": "", "outcome": "unresolved"}]})
        with self.assertRaisesRegex(PrCodeCandidateValidationError, "immutable revision"):
            normalize_merged_pr_change_set({**self.raw, "merged_revision": "main"})
        with self.assertRaisesRegex(PrCodeCandidateValidationError, "immutable revision"):
            normalize_merged_pr_change_set({**self.raw, "merged_revision": "deadbee"})
        with self.assertRaisesRegex(PrCodeCandidateValidationError, "observed_at is required"):
            normalize_merged_pr_change_set({**self.raw, "observed_at": ""})
        with self.assertRaisesRegex(PrCodeCandidateValidationError, "offset-aware ISO-8601"):
            normalize_merged_pr_change_set({**self.raw, "observed_at": "2026-09-01T12:00:00"})

    def test_resolved_mapping_requires_qualified_symbol_identity(self) -> None:
        invalid_symbols = (
            "submit",
            "payments..submit",
            "def submit(amount):\n    return amount",
            "class Payments:\n    def submit(self): pass",
        )
        results = []
        for symbol in invalid_symbols:
            normalized = normalize_merged_pr_change_set({
                **self.raw,
                "mappings": [{
                    "id": "graphify:mapping-1",
                    "file": "src/payments.py",
                    "outcome": "resolved",
                    "symbol": symbol,
                }],
            })
            mapping = normalized.mappings[0]
            self.assertEqual(mapping.outcome, MappingOutcome.MALFORMED)
            self.assertIsNone(mapping.symbol)
            self.assertNotIn(symbol, repr(normalized))
            results.append(extract_pr_code_candidates(
                (normalized,), GraphSnapshot(nodes=(self.subject,))
            ))

        for result in results:
            self.assertEqual(result.graph.cross_graph_link_claims, ())
            self.assertEqual(result.graph.cross_graph_link_evidence, ())
            self.assertEqual(result.graph.cross_graph_link_lifecycle, ())
            self.assertEqual(result.metadata.skipped_reason_counts, {"malformed-symbol": 1})
            diagnostic = result.metadata.diagnostics[0]
            self.assertEqual(diagnostic.reason_code, "malformed-symbol")
            self.assertEqual(diagnostic.mapping_id, "graphify:mapping-1")
            self.assertNotIn("symbol", result.graph.evidence[0].properties)

    def test_classified_malformed_mapping_discards_its_symbol_payload(self) -> None:
        source_body = "def submit(amount):\n    return amount"
        normalized = normalize_merged_pr_change_set({
            **self.raw,
            "mappings": [{
                "id": "graphify:mapping-1",
                "file": "src/payments.py",
                "outcome": "malformed",
                "symbol": source_body,
            }],
        })

        self.assertEqual(normalized.mappings[0].outcome, MappingOutcome.MALFORMED)
        self.assertIsNone(normalized.mappings[0].symbol)
        self.assertNotIn(source_body, repr(normalized))

    def test_candidates_are_observed_complete_and_idempotent(self) -> None:
        result = extract_pr_code_candidates((normalize_merged_pr_change_set(self.raw),) * 2, GraphSnapshot(nodes=(self.subject,)))
        self.assertEqual(result.metadata.accepted_change_set_count, 1)
        self.assertEqual(result.metadata.emitted_candidate_count, 1)
        claim = result.graph.cross_graph_link_claims[0]
        self.assertEqual(claim.relation_kind, "observed-pr-change")
        self.assertEqual(claim.target.revision, "a" * 40)
        self.assertEqual(result.graph.trusted_cross_graph_links, ())
        self.assertEqual(result.graph.edges, ())
        graph = GraphSnapshot(nodes=(self.subject,)).merged_with(result.graph)
        self.assertEqual(validate_graph_integrity(graph).status, "valid")
        promoted = GraphSnapshot(
            nodes=graph.nodes,
            evidence=(*graph.evidence, Evidence("review", "review", "review-1")),
            provenance=graph.provenance,
            cross_graph_link_claims=graph.cross_graph_link_claims, cross_graph_link_evidence=graph.cross_graph_link_evidence,
            cross_graph_link_lifecycle=(*graph.cross_graph_link_lifecycle, CrossGraphLinkLifecycle(claim.id, 2, "trusted", "review")),
        )
        self.assertEqual(promoted.trusted_cross_graph_links[0].claim_id, claim.id)
        self.assertEqual(len(promoted.cross_graph_link_evidence), 1)

    def test_separate_pr_observations_of_one_claim_merge_without_lifecycle_conflict(self) -> None:
        first = normalize_merged_pr_change_set(self.raw)
        second = MergedPrChangeSet(
            EngineeringChangePrAssociation("jira-link-2", self.subject.id, "pr-43"),
            "pr-43",
            first.repository,
            first.merged_revision,
            (ChangedSymbolMapping("graphify:mapping-2", first.mappings[0].file, "resolved", first.mappings[0].symbol),),
            observed_at=first.observed_at,
        )
        subject_graph = GraphSnapshot(nodes=(self.subject,))

        first_result = extract_pr_code_candidates((first,), subject_graph)
        second_result = extract_pr_code_candidates((second,), subject_graph)
        merged = subject_graph.merged_with(first_result.graph).merged_with(second_result.graph)

        self.assertEqual(len(merged.cross_graph_link_claims), 1)
        self.assertEqual(len(merged.cross_graph_link_evidence), 2)
        self.assertEqual(len(merged.cross_graph_link_lifecycle), 1)
        self.assertEqual(len(merged.evidence), 3)
        mapping_provenance_ids = {
            observation.provenance_evidence_id
            for observation in merged.cross_graph_link_evidence
        }
        evidence_by_id = {item.id: item for item in merged.evidence}
        self.assertEqual(
            {evidence_by_id[item_id].properties["association_id"] for item_id in mapping_provenance_ids},
            {"jira-link-1", "jira-link-2"},
        )
        lifecycle = merged.cross_graph_link_lifecycle[0]
        self.assertEqual(lifecycle.revision, 1)
        self.assertEqual(lifecycle.state, "candidate")
        self.assertNotIn(
            lifecycle.provenance_evidence_id,
            {observation.provenance_evidence_id for observation in merged.cross_graph_link_evidence},
        )
        self.assertEqual(validate_graph_integrity(merged).status, "valid")
        reverse_merged = subject_graph.merged_with(second_result.graph).merged_with(first_result.graph)
        self.assertEqual(
            {item.id for item in merged.evidence},
            {item.id for item in reverse_merged.evidence},
        )
        self.assertEqual(merged.cross_graph_link_evidence, reverse_merged.cross_graph_link_evidence)
        self.assertEqual(merged.cross_graph_link_lifecycle, reverse_merged.cross_graph_link_lifecycle)

    def test_skips_unresolved_and_ambiguous_mappings_with_source_provenance(self) -> None:
        base = normalize_merged_pr_change_set(self.raw)
        skipped = MergedPrChangeSet(base.association, base.pull_request_id, base.repository, base.merged_revision, (
            ChangedSymbolMapping("graphify:unresolved", "a.py", MappingOutcome.UNRESOLVED),
            ChangedSymbolMapping("graphify:ambiguous", "b.py", MappingOutcome.AMBIGUOUS),
        ), observed_at=base.observed_at)
        result = extract_pr_code_candidates((skipped,), GraphSnapshot(nodes=(self.subject,)))
        self.assertEqual(result.graph.cross_graph_link_claims, ())
        self.assertEqual([item.reason_code for item in result.metadata.diagnostics], ["ambiguous-symbol", "unresolved-symbol"])
        diagnostics = {item.mapping_id: item for item in result.metadata.diagnostics}
        provenance = {item.id: item for item in result.graph.evidence}
        self.assertEqual(len(provenance), 2)
        for mapping_id, diagnostic in diagnostics.items():
            self.assertIn(diagnostic.provenance_evidence_id, provenance)
            self.assertEqual(provenance[diagnostic.provenance_evidence_id].properties["source_mapping_id"], mapping_id)
        missing = extract_pr_code_candidates((base,), GraphSnapshot())
        self.assertEqual(missing.metadata.diagnostics[0].reason_code, "missing-subject")

    def test_conflicting_source_mapping_identity_is_not_admitted(self) -> None:
        base = normalize_merged_pr_change_set(self.raw)
        conflicting = MergedPrChangeSet(
            base.association,
            base.pull_request_id,
            base.repository,
            base.merged_revision,
            (
                ChangedSymbolMapping("graphify:mapping-1", "src/payments.py", MappingOutcome.RESOLVED, "payments.submit"),
                ChangedSymbolMapping("graphify:mapping-1", "src/refunds.py", MappingOutcome.RESOLVED, "refunds.refund"),
            ),
            observed_at=base.observed_at,
        )

        result = extract_pr_code_candidates((conflicting,), GraphSnapshot(nodes=(self.subject,)))

        self.assertEqual(result.graph.cross_graph_link_claims, ())
        self.assertEqual(result.graph.cross_graph_link_evidence, ())
        self.assertEqual(result.graph.cross_graph_link_lifecycle, ())
        self.assertEqual(result.metadata.emitted_candidate_count, 0)
        self.assertEqual(result.metadata.skipped_reason_counts, {"conflicting-mapping-identity": 1})
        diagnostic = result.metadata.diagnostics[0]
        self.assertEqual(diagnostic.reason_code, "conflicting-mapping-identity")
        self.assertEqual(diagnostic.mapping_id, "graphify:mapping-1")
        self.assertEqual(len(result.graph.evidence), 1)
        self.assertEqual(diagnostic.provenance_evidence_id, result.graph.evidence[0].id)
        self.assertEqual(result.graph.evidence[0].properties["source_mapping_id"], "graphify:mapping-1")

    def test_conflicting_duplicate_change_set_identity_is_not_admitted(self) -> None:
        base = normalize_merged_pr_change_set(self.raw)
        conflicting = MergedPrChangeSet(
            base.association,
            base.pull_request_id,
            base.repository,
            base.merged_revision,
            (ChangedSymbolMapping("graphify:mapping-1", "src/refunds.py", MappingOutcome.RESOLVED, "refunds.refund"),),
            observed_at=base.observed_at,
        )

        first = extract_pr_code_candidates(
            (base, conflicting), GraphSnapshot(nodes=(self.subject,))
        )
        second = extract_pr_code_candidates(
            (conflicting, base), GraphSnapshot(nodes=(self.subject,))
        )

        self.assertEqual(first.graph.as_json(), second.graph.as_json())
        self.assertEqual(first.metadata.as_dict(), second.metadata.as_dict())
        self.assertEqual(first.graph.cross_graph_link_claims, ())
        self.assertEqual(first.graph.cross_graph_link_evidence, ())
        self.assertEqual(first.graph.cross_graph_link_lifecycle, ())
        self.assertEqual(first.metadata.accepted_change_set_count, 0)
        self.assertEqual(first.metadata.emitted_candidate_count, 0)
        self.assertEqual(first.metadata.skipped_reason_counts, {"conflicting-change-set-identity": 1})
        diagnostic = first.metadata.diagnostics[0]
        self.assertEqual(diagnostic.reason_code, "conflicting-change-set-identity")
        self.assertEqual(diagnostic.change_set_id, base.id)
        self.assertEqual(diagnostic.mapping_id, "")
        self.assertEqual(len(first.graph.evidence), 1)
        self.assertEqual(diagnostic.provenance_evidence_id, first.graph.evidence[0].id)
        self.assertEqual(
            first.graph.evidence[0].properties,
            {
                "association_id": "jira-link-1",
                "merged_revision": "a" * 40,
                "pull_request_id": "pr-42",
                "repository": "payment-service",
            },
        )

    def test_case_normalized_repository_and_revision_conflicts_are_order_independent(self) -> None:
        base = normalize_merged_pr_change_set(self.raw)
        conflicting = MergedPrChangeSet(
            base.association,
            base.pull_request_id,
            "PAYMENT-SERVICE",
            base.merged_revision.upper(),
            (ChangedSymbolMapping("graphify:mapping-1", "src/refunds.py", "resolved", "refunds.refund"),),
            observed_at=base.observed_at,
        )

        self.assertEqual(base.id, conflicting.id)
        first = extract_pr_code_candidates((base, conflicting), GraphSnapshot(nodes=(self.subject,)))
        second = extract_pr_code_candidates((conflicting, base), GraphSnapshot(nodes=(self.subject,)))

        self.assertEqual(first.graph.as_json(), second.graph.as_json())
        self.assertEqual(first.metadata.as_dict(), second.metadata.as_dict())
        self.assertEqual(first.graph.cross_graph_link_claims, ())
        self.assertEqual(first.graph.cross_graph_link_evidence, ())
        self.assertEqual(first.graph.cross_graph_link_lifecycle, ())
        self.assertEqual(first.metadata.accepted_change_set_count, 0)
        self.assertEqual(first.metadata.skipped_reason_counts, {"conflicting-change-set-identity": 1})
        self.assertEqual(len(first.graph.evidence), 1)
        self.assertEqual(first.graph.evidence[0].properties["repository"], "payment-service")
        self.assertEqual(first.graph.evidence[0].properties["merged_revision"], "a" * 40)

    def test_rejects_every_existing_non_story_subject_without_records(self) -> None:
        change_set = normalize_merged_pr_change_set(self.raw)
        for kind in NodeKind:
            if kind is NodeKind.JIRA_STORY:
                continue
            with self.subTest(kind=kind):
                subject = Node(self.subject.id, kind, "Not a Jira story")
                result = extract_pr_code_candidates(
                    (change_set,), GraphSnapshot(nodes=(subject,))
                )

                self.assertEqual(result.graph.cross_graph_link_claims, ())
                self.assertEqual(result.graph.cross_graph_link_evidence, ())
                self.assertEqual(result.graph.cross_graph_link_lifecycle, ())
                self.assertEqual(result.graph.evidence, ())
                self.assertEqual(result.graph.trusted_cross_graph_links, ())
                self.assertEqual(result.metadata.accepted_change_set_count, 0)
                self.assertEqual(
                    result.metadata.skipped_reason_counts,
                    {"ineligible-subject-kind": 1},
                )
                self.assertEqual(
                    result.metadata.diagnostics[0].reason_code,
                    "ineligible-subject-kind",
                )

    def test_retained_identity_and_locator_fields_reject_payload_like_values(self) -> None:
        payload = "def submit(amount):\n    return amount"
        invalid_fields = (
            ("association", {**self.raw["association"], "id": payload}, "association.id"),
            ("association", {**self.raw["association"], "engineering_change_subject_id": payload}, "association.engineering_change_subject_id"),
            ("association", {**self.raw["association"], "pull_request_id": payload}, "association.pull_request_id"),
            ("pull_request_id", payload, "change_set.pull_request_id"),
            ("repository", payload, "change_set.repository"),
            ("mappings", [{**self.raw["mappings"][0], "file": payload}], "mapping.file"),
        )
        for field, value, error in invalid_fields:
            raw = {**self.raw, field: value}
            with self.subTest(field=field), self.assertRaisesRegex(PrCodeCandidateValidationError, error):
                normalize_merged_pr_change_set(raw)

    def test_url_like_pr_and_association_ids_are_rejected_before_provenance(self) -> None:
        url_like_ids = (
            "https://bitbucket.example/pr/42",
            "https:bitbucket.example/pr/42",
            "HTTP:bitbucket.example/pr/42",
            "ssh:bitbucket.example/team/repo",
            "git:bitbucket.example/team/repo",
            "custom://provider.example/pr/42",
            "custom:/provider.example/pr/42",
            "file:/private/secret",
            "s3://bucket/changes/pr-42",
            "vscode://extension.example/pr/42",
            "//bitbucket.example/pr/42",
        )
        for url_like_id in url_like_ids:
            for field in ("id", "pull_request_id"):
                association = {**self.raw["association"], field: url_like_id}
                with self.subTest(url_like_id=url_like_id, association_field=field), self.assertRaisesRegex(
                    PrCodeCandidateValidationError, f"association.{field} must not be URL-like"
                ):
                    normalize_merged_pr_change_set({**self.raw, "association": association})

            with self.subTest(url_like_id=url_like_id, change_set_field="pull_request_id"), self.assertRaisesRegex(
                PrCodeCandidateValidationError,
                "change_set.pull_request_id must not be URL-like",
            ):
                normalize_merged_pr_change_set({**self.raw, "pull_request_id": url_like_id})

    def test_opaque_uri_shaped_association_and_pr_ids_remain_valid(self) -> None:
        namespaced_id = "urn:example.org/link-42"
        normalized = normalize_merged_pr_change_set({
            **self.raw,
            "association": {
                **self.raw["association"],
                "id": namespaced_id,
                "pull_request_id": namespaced_id,
            },
            "pull_request_id": namespaced_id,
        })

        self.assertEqual(normalized.association.id, namespaced_id)
        self.assertEqual(normalized.association.pull_request_id, namespaced_id)
        self.assertEqual(normalized.pull_request_id, namespaced_id)
        result = extract_pr_code_candidates(
            (normalized,), GraphSnapshot(nodes=(self.subject,))
        )
        self.assertEqual(result.graph.evidence[0].properties["association_id"], namespaced_id)
        self.assertEqual(result.graph.evidence[0].properties["pull_request_id"], namespaced_id)
        self.assertIn(namespaced_id, result.graph.as_json())
        self.assertNotIn("https://", result.graph.as_json())

    def test_rejects_mutable_revision_at_normalized_construction_boundary(self) -> None:
        base = normalize_merged_pr_change_set(self.raw)
        with self.assertRaisesRegex(PrCodeCandidateValidationError, "immutable revision"):
            MergedPrChangeSet(
                base.association, base.pull_request_id, base.repository, "main", base.mappings,
                observed_at=base.observed_at,
            )
        with self.assertRaisesRegex(PrCodeCandidateValidationError, "immutable revision"):
            MergedPrChangeSet(
                base.association, base.pull_request_id, base.repository, "deadbee", base.mappings,
                observed_at=base.observed_at,
            )

    def test_invalid_mapping_identity_never_enters_graph_records(self) -> None:
        source_body = "def submit(amount):\n    return amount"
        normalized = normalize_merged_pr_change_set({
            **self.raw,
            "mappings": [{
                "id": source_body,
                "file": "src/payments.py",
                "outcome": "resolved",
                "symbol": "payments.submit",
            }],
        })

        mapping = normalized.mappings[0]
        self.assertEqual(mapping.id, "")
        self.assertEqual(mapping.outcome, MappingOutcome.MALFORMED)
        self.assertNotIn(source_body, repr(normalized))
        result = extract_pr_code_candidates(
            (normalized,), GraphSnapshot(nodes=(self.subject,))
        )

        self.assertEqual(result.graph.cross_graph_link_claims, ())
        self.assertEqual(result.graph.cross_graph_link_evidence, ())
        self.assertEqual(result.graph.cross_graph_link_lifecycle, ())
        self.assertEqual(result.graph.evidence, ())
        self.assertEqual(
            result.metadata.skipped_reason_counts, {"invalid-mapping-identity": 1}
        )
        self.assertEqual(result.metadata.diagnostics[0].mapping_id, "")
        serialized = result.graph.as_json()
        self.assertNotIn(source_body, serialized)
        self.assertNotIn("source_mapping_id", serialized)

    def test_qualified_mapping_identity_is_trimmed_and_retained(self) -> None:
        mapping_id = "graphify:changed-symbol:mapping-1"
        normalized = normalize_merged_pr_change_set({
            **self.raw,
            "mappings": [{
                "id": f"  {mapping_id}  ",
                "file": "src/payments.py",
                "outcome": "resolved",
                "symbol": "payments.submit",
            }],
        })

        result = extract_pr_code_candidates(
            (normalized,), GraphSnapshot(nodes=(self.subject,))
        )
        self.assertEqual(normalized.mappings[0].id, mapping_id)
        self.assertEqual(
            result.graph.cross_graph_link_evidence[0].observation_id, mapping_id
        )
        locator = result.graph.evidence[0].locator
        self.assertIsInstance(locator, SourceArtifactLocator)
        self.assertEqual(locator.source_artifact_identity.source_type, "graphify")
        self.assertEqual(locator.source_artifact_identity.source_identity, "payment-service")
        self.assertEqual(locator.source_artifact_identity.artifact_type, "pull-request-mapping")
        self.assertEqual(locator.source_artifact_identity.revision_or_version, "a" * 40)
        self.assertEqual(
            locator.source_artifact_identity.stable_locator,
            f"pr-change-set:{normalized.id}:mapping:{mapping_id}",
        )
        self.assertEqual(locator.navigation_detail["source_mapping_id"], mapping_id)
        self.assertEqual(
            result.graph.evidence[0].properties["source_mapping_id"], mapping_id
        )

    def test_persistence_readback_is_stable_and_legacy_snapshots_remain_readable(self) -> None:
        opaque_id = "urn:example.org/link-42"
        normalized = normalize_merged_pr_change_set({
            **self.raw,
            "association": {
                **self.raw["association"],
                "id": opaque_id,
                "pull_request_id": opaque_id,
            },
            "pull_request_id": opaque_id,
        })
        result = extract_pr_code_candidates((normalized,), GraphSnapshot(nodes=(self.subject,)))
        graph = GraphSnapshot(nodes=(self.subject,)).merged_with(result.graph)
        with tempfile.TemporaryDirectory() as temporary:
            store = initialize_ladybugdb_store(Path(temporary) / "store")
            readback = store.write_snapshot(graph)
            self.assertEqual(readback.as_json(), graph.as_json())
            self.assertIn(opaque_id, readback.as_json())
            locator = readback.evidence[0].locator
            self.assertIsInstance(locator, SourceArtifactLocator)
            self.assertEqual(locator.source_artifact_identity.source_type, "graphify")
            self.assertNotIn("source_code", readback.as_json())
            self.assertNotIn("provider_payload", readback.as_json())
            self.assertEqual(store.write_snapshot(graph).as_json(), graph.as_json())

    def test_lifecycle_readback_retains_the_mapping_external_provenance_chain(self) -> None:
        result = extract_pr_code_candidates(
            (normalize_merged_pr_change_set(self.raw),),
            GraphSnapshot(nodes=(self.subject,)),
        )
        graph = GraphSnapshot(nodes=(self.subject,)).merged_with(result.graph)
        claim = graph.cross_graph_link_claims[0]

        with tempfile.TemporaryDirectory() as temporary:
            store = initialize_ladybugdb_store(Path(temporary) / "store")
            readback = store.write_snapshot(graph)
            traceability = EngineeringKgQuery.from_snapshot(readback).get_traceability(
                self.subject.id
            )

        lifecycle_provenance = traceability["cross_graph_links"][0]["lifecycle"][0][
            "provenance"
        ]
        self.assertEqual(len(lifecycle_provenance), 1)
        derived = lifecycle_provenance[0]
        self.assertEqual(derived["kind"], "derived")
        self.assertEqual(
            derived["derivation_rule_id"], "cross-graph-candidate-initialization"
        )
        external_id = derived["input_provenance_ids"][0]
        mapping_external = next(record for record in readback.provenance if record.id == external_id)
        self.assertEqual(mapping_external.kind, "external")
        self.assertEqual(
            mapping_external.source_artifact_identity.artifact_type,
            "pull-request-mapping",
        )
        self.assertEqual(
            traceability["cross_graph_links"][0]["claim"]["id"], claim.id
        )


if __name__ == "__main__":
    unittest.main()
