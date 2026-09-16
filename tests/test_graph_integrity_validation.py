from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.ontology import (
    Edge, EdgeKind, Evidence, GraphSnapshot, Node, NodeKind, ProvenanceRecord,
    SourceArtifactIdentity, SourceArtifactLocator, openspec_specification_id,
    stable_id, verification_node,
)
from engineering_kg.validation import validate_graph_integrity


class GraphIntegrityValidationTest(unittest.TestCase):
    def test_canonical_change_traceability_requires_valid_endpoints_and_evidence(self) -> None:
        change = Node("change", NodeKind.OPENSPEC_ACTIVE_CHANGE, "JIRA-1")
        spec = Node(openspec_specification_id("requirements", "payments"), NodeKind.SPECIFICATION, "payments", {"repository_id": "requirements", "capability": "payments"})
        edge = Edge("assertion", EdgeKind.ASSERTS, change.id, spec.id, evidence_ids=("e",))
        identity = SourceArtifactIdentity("openspec", "requirements", "openspec-spec", "a" * 40, "openspec/specs/payments/spec.md")
        provenance = ProvenanceRecord("external", "2026-01-02T03:04:05+00:00", "sha256", "a" * 64, "test-extractor", "1", identity)
        evidence = Evidence(stable_id("evidence", identity.id), "openspec", SourceArtifactLocator(identity), provenance_ids=(provenance.id,))
        edge = Edge("assertion", EdgeKind.ASSERTS, change.id, spec.id, evidence_ids=(evidence.id,))
        self.assertEqual(validate_graph_integrity(GraphSnapshot((change, spec), (edge,), (evidence,), provenance=(provenance,))).status, "valid")

    def test_retired_vocabulary_is_invalid(self) -> None:
        legacy = Node("legacy", "openspec-spec", "Payments")
        result = validate_graph_integrity(GraphSnapshot(nodes=(legacy,)))
        self.assertEqual(result.status, "invalid")
        self.assertEqual(result.metadata.diagnostics[0].rule_id, "retired-openspec-domain-vocabulary")

    def test_duplicate_conflicts_remain_invalid(self) -> None:
        first = Node("id", NodeKind.SPECIFICATION, "one", {"repository_id": "a", "capability": "x"})
        second = Node("id", NodeKind.SPECIFICATION, "two", {"repository_id": "b", "capability": "x"})
        self.assertEqual(validate_graph_integrity(GraphSnapshot(nodes=(first, second))).status, "invalid")

    def test_compatible_duplicate_evidence_is_valid(self) -> None:
        specification_id = openspec_specification_id("requirements", "payments")
        first = Node(
            specification_id,
            NodeKind.SPECIFICATION,
            "Payments",
            {"repository_id": "requirements", "capability": "payments"},
            ("first-evidence",),
        )
        second = Node(
            specification_id,
            NodeKind.SPECIFICATION,
            "Payments",
            {"repository_id": "requirements", "capability": "payments"},
            ("second-evidence",),
        )
        graph = GraphSnapshot(
            nodes=(first, second),
            evidence=(
                Evidence("first-evidence", "fixture", "first"),
                Evidence("second-evidence", "fixture", "second"),
            ),
        )
        self.assertEqual(validate_graph_integrity(graph).status, "valid")

    def test_generic_ekg48_execution_without_openspec_mapping_remains_valid(self) -> None:
        identity = SourceArtifactIdentity(
            "verification-provider", "payments", "test-execution", "run-1", "runs/run-1",
        )
        provenance = ProvenanceRecord(
            "external", "2026-01-02T03:04:05+00:00", "sha256", "a" * 64,
            "verification-extractor", "1", identity,
        )
        evidence = Evidence(
            stable_id("evidence", identity.id), "verification-provider",
            SourceArtifactLocator(identity), provenance_ids=(provenance.id,),
        )
        test_case = verification_node(NodeKind.TEST_CASE, "payments", "case-001", (evidence.id,))
        test_run = verification_node(NodeKind.TEST_RUN, "payments", "run-001", (evidence.id,))
        execution = Edge(
            "case-executed-run", EdgeKind.EXECUTED_IN, test_case.id, test_run.id,
            evidence_ids=(evidence.id,),
        )

        result = validate_graph_integrity(GraphSnapshot(
            nodes=(test_case, test_run), edges=(execution,),
            evidence=(evidence,), provenance=(provenance,),
        ))

        self.assertEqual(result.status, "valid", result.metadata.as_dict())

    def test_external_evidence_without_identity_is_invalid_but_generated_evidence_is_allowed(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid-source-artifact-identity"):
            GraphSnapshot(evidence=(Evidence("external", "confluence", "123"),))
        self.assertEqual(validate_graph_integrity(GraphSnapshot(evidence=(Evidence("generated", "openlore", "derived"),))).status, "valid")

    def test_canonical_node_id_must_match_natural_key(self) -> None:
        node = Node("wrong", NodeKind.SPECIFICATION, "payments", {"repository_id": "requirements", "capability": "payments"})
        result = validate_graph_integrity(GraphSnapshot(nodes=(node,)))
        self.assertEqual(result.status, "invalid")
        self.assertEqual(result.metadata.diagnostics[0].rule_id, "canonical-natural-key-identity")

    def test_conflict_diagnostic_is_stable_and_payload_free_for_direct_duplicates(self) -> None:
        first = Node("shared", NodeKind.REPOSITORY, "provider payload one", {"revision": "one"}, ("evidence-one",))
        second = Node("shared", NodeKind.REPOSITORY, "provider payload two", {"revision": "two"}, ("evidence-two",))
        evidence = (Evidence("evidence-one", "fixture", "one"), Evidence("evidence-two", "fixture", "two"))

        forward = validate_graph_integrity(GraphSnapshot(nodes=(first, second), evidence=evidence))
        reverse = validate_graph_integrity(GraphSnapshot(nodes=(second, first), evidence=evidence[::-1]))
        forward_conflict = next(item for item in forward.metadata.diagnostics if item.rule_id == "duplicate-identity-conflict")
        reverse_conflict = next(item for item in reverse.metadata.diagnostics if item.rule_id == "duplicate-identity-conflict")

        self.assertEqual(forward.status, "invalid")
        self.assertEqual(forward_conflict.as_dict(), reverse_conflict.as_dict())
        self.assertEqual(forward_conflict.contributor_evidence_ids, ("evidence-one", "evidence-two"))
        self.assertNotIn("provider payload", forward_conflict.message)
        self.assertNotIn("revision", forward_conflict.message)


if __name__ == "__main__":
    unittest.main()
