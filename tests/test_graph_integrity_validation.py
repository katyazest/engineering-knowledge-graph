from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.ontology import Edge, EdgeKind, Evidence, GraphSnapshot, Node, NodeKind, openspec_specification_id
from engineering_kg.validation import validate_graph_integrity


class GraphIntegrityValidationTest(unittest.TestCase):
    def test_canonical_change_traceability_requires_valid_endpoints_and_evidence(self) -> None:
        change = Node("change", NodeKind.OPENSPEC_ACTIVE_CHANGE, "JIRA-1")
        spec = Node(openspec_specification_id("requirements", "payments"), NodeKind.SPECIFICATION, "payments", {"repository_id": "requirements", "capability": "payments"})
        edge = Edge("assertion", EdgeKind.ASSERTS, change.id, spec.id, evidence_ids=("e",))
        self.assertEqual(validate_graph_integrity(GraphSnapshot((change, spec), (edge,), (Evidence("e", "openspec", "fixture"),))).status, "valid")

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
            "Payments specification",
            {"repository_id": "requirements", "capability": "payments"},
            ("second-evidence",),
        )
        graph = GraphSnapshot(
            nodes=(first, second),
            evidence=(
                Evidence("first-evidence", "openspec", "first"),
                Evidence("second-evidence", "openspec", "second"),
            ),
        )
        self.assertEqual(validate_graph_integrity(graph).status, "valid")

    def test_canonical_node_id_must_match_natural_key(self) -> None:
        node = Node("wrong", NodeKind.SPECIFICATION, "payments", {"repository_id": "requirements", "capability": "payments"})
        result = validate_graph_integrity(GraphSnapshot(nodes=(node,)))
        self.assertEqual(result.status, "invalid")
        self.assertEqual(result.metadata.diagnostics[0].rule_id, "canonical-natural-key-identity")


if __name__ == "__main__":
    unittest.main()
