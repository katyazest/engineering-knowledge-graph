from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.ingest.pr_code_candidates import (
    MappingOutcome,
    PrCodeCandidateValidationError,
    extract_pr_code_candidates,
    normalize_pull_request_evidence,
)
from engineering_kg.ontology import GraphSnapshot, Node, NodeKind
from engineering_kg.persistence import initialize_ladybugdb_store
from engineering_kg.validation import validate_graph_integrity


class PrCodeCandidateExtractionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Node("repository-1", NodeKind.REPOSITORY, "payment-service")
        self.subject = Node("change-1", NodeKind.JIRA_STORY, "EKG-72")
        self.raw = {
            "pull_request_id": "bitbucket:pr-42",
            "repository_node_id": self.repository.id,
            "base_revision": "a" * 40,
            "head_revision": "b" * 40,
            "merged": True,
            "observed_at": "2026-09-01T12:00:00+00:00",
            "provenance": {"pr": "complete"},
            "pr_source_reference": "urn:example.org/pr-42",
            "repository_source_reference": "urn:example.org/repository-42",
            "association": {
                "id": "association-42",
                "intended_change_id": self.subject.id,
                "source_reference": "urn:example.org/association-42",
                "intended_change_kind": "jira_story",
            },
            "mappings": [{
                "id": "graphify:mapping-42",
                "file": "src/payments.py",
                "symbol": "payments.submit",
                "outcome": "resolved",
                "repository": self.repository.id,
                "revision": "b" * 40,
            }],
        }

    def test_normalization_is_deterministic_and_payload_free(self) -> None:
        first = normalize_pull_request_evidence(self.raw)
        second = normalize_pull_request_evidence(self.raw)
        self.assertEqual(first, second)
        self.assertEqual(first.id, second.id)
        self.assertNotIn("provider_payload", repr(first))
        with self.assertRaisesRegex(ValueError, "must be merged"):
            normalize_pull_request_evidence({**self.raw, "merged": False})
        with self.assertRaisesRegex(ValueError, "immutable"):
            normalize_pull_request_evidence({**self.raw, "head_revision": "main"})

    def test_pr_source_artifact_revision_is_bound_to_head_revision(self) -> None:
        bound = normalize_pull_request_evidence({
            **self.raw,
            "pr_source_reference": {
                "source_identity": "urn:example.org/pr-42",
                "stable_locator": "references/pr-42",
                "revision_or_version": self.raw["head_revision"],
            },
        })
        source_evidence = next(
            item for item in bound.evidence if item.id == bound.pull_request.source_evidence_id
        )
        self.assertEqual(
            source_evidence.locator.source_artifact_identity.revision_or_version,
            bound.pull_request.head_revision,
        )
        for revision, message in (("main", "immutable"), ("c" * 40, "match head_revision")):
            with self.subTest(revision=revision):
                raw = {
                    **self.raw,
                    "pr_source_reference": {
                        "source_identity": "urn:example.org/pr-42",
                        "stable_locator": "references/pr-42",
                        "revision_or_version": revision,
                    },
                }
                with self.assertRaisesRegex(ValueError, message):
                    normalize_pull_request_evidence(raw)

    def test_resolved_mapping_is_observed_untrusted_and_idempotent(self) -> None:
        source = GraphSnapshot(nodes=(self.repository, self.subject))
        normalized = normalize_pull_request_evidence(self.raw)
        result = extract_pr_code_candidates((normalized, normalized), source)
        graph = source.merged_with(result.graph)
        self.assertEqual(len(graph.cross_graph_link_claims), 1)
        self.assertEqual(len(graph.cross_graph_link_evidence), 1)
        self.assertEqual(graph.cross_graph_link_evidence[0].origin, "observed")
        self.assertEqual(graph.cross_graph_link_evidence[0].trust_disposition, "untrusted")
        self.assertEqual(graph.trusted_cross_graph_links, ())
        self.assertEqual(validate_graph_integrity(graph).status, "valid")

    def test_unresolved_and_scope_mismatched_mappings_emit_no_candidate(self) -> None:
        unresolved = normalize_pull_request_evidence({
            **self.raw,
            "mappings": [{"id": "graphify:unresolved", "file": "src/payments.py", "outcome": "unresolved"}],
        })
        result = extract_pr_code_candidates(
            (unresolved,), GraphSnapshot(nodes=(self.repository, self.subject))
        )
        self.assertEqual(result.graph.cross_graph_link_claims, ())
        self.assertEqual(result.metadata.skipped_reason_counts, {"unresolved-symbol": 1})

        mismatched = normalize_pull_request_evidence({
            **self.raw,
            "mappings": [{**self.raw["mappings"][0], "revision": "c" * 40}],
        })
        mismatch_result = extract_pr_code_candidates(
            (mismatched,), GraphSnapshot(nodes=(self.repository, self.subject))
        )
        self.assertEqual(mismatch_result.graph.cross_graph_link_claims, ())
        self.assertEqual(mismatch_result.metadata.skipped_reason_counts, {"revision-mismatch": 1})

    def test_invalid_mapping_symbol_is_classified_without_retaining_payload(self) -> None:
        normalized = normalize_pull_request_evidence({
            **self.raw,
            "mappings": [{
                "id": "graphify:malformed",
                "file": "src/payments.py",
                "outcome": "resolved",
                "symbol": "def submit():\n    return None",
            }],
        })
        self.assertEqual(normalized.mappings[0].outcome, MappingOutcome.MALFORMED)
        self.assertIsNone(normalized.mappings[0].symbol)
        result = extract_pr_code_candidates(
            (normalized,), GraphSnapshot(nodes=(self.repository, self.subject))
        )
        self.assertEqual(result.graph.cross_graph_link_claims, ())
        self.assertNotIn("def submit", result.graph.as_json())

    def test_persistence_readback_is_stable(self) -> None:
        source = GraphSnapshot(nodes=(self.repository, self.subject))
        graph = source.merged_with(
            extract_pr_code_candidates(
                (normalize_pull_request_evidence(self.raw),), source
            ).graph
        )
        with tempfile.TemporaryDirectory() as temporary:
            store = initialize_ladybugdb_store(Path(temporary) / "store")
            readback = store.write_snapshot(graph)
            self.assertEqual(readback.as_json(), graph.as_json())
            self.assertEqual(store.write_snapshot(graph).as_json(), graph.as_json())


if __name__ == "__main__":
    unittest.main()
