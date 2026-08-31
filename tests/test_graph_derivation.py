from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.derivation import derive_graph_relationships
from engineering_kg.ontology import Edge, EdgeKind, Evidence, GraphSnapshot, Node, NodeKind, openspec_specification_id, stable_id


class GraphDerivationTest(unittest.TestCase):
    def test_derives_traceability_from_evidenced_assertion(self) -> None:
        change = Node("change", NodeKind.OPENSPEC_ACTIVE_CHANGE, "JIRA-1")
        specification = Node(openspec_specification_id("requirements", "payments"), NodeKind.SPECIFICATION, "payments", {"repository_id": "requirements", "capability": "payments"})
        assertion = Edge("assertion", EdgeKind.ASSERTS, change.id, specification.id, evidence_ids=("e",))
        graph = GraphSnapshot((change, specification), (assertion,), (Evidence("e", "fixture", "fixture"),))
        result = derive_graph_relationships(graph)
        derived = [edge for edge in result.graph.edges if edge.kind == EdgeKind.TRACES_TO]
        self.assertEqual(len(derived), 1)
        self.assertEqual(derived[0].properties["input_edge_ids"], ("assertion",))
        self.assertTrue(derived[0].properties["derived"])
        self.assertEqual(result.graph.as_dict(), derive_graph_relationships(result.graph).graph.as_dict())

    def test_invalid_assertion_is_reported_without_traceability(self) -> None:
        change = Node("change", NodeKind.OPENSPEC_ACTIVE_CHANGE, "JIRA-1")
        target = Node("target", NodeKind.REQUIREMENT, "Requirement")
        graph = GraphSnapshot((change, target), (Edge("assertion", EdgeKind.ASSERTS, change.id, target.id),))
        result = derive_graph_relationships(graph)
        self.assertEqual(result.metadata.derived_edge_count, 0)
        self.assertEqual(result.metadata.unresolved_input_count, 1)

    def test_missing_endpoint_and_evidence_are_reported_without_traceability(self) -> None:
        change = Node("change", NodeKind.OPENSPEC_ACTIVE_CHANGE, "JIRA-1")
        specification = Node(
            openspec_specification_id("requirements", "payments"),
            NodeKind.SPECIFICATION,
            "payments",
            {"repository_id": "requirements", "capability": "payments"},
        )
        graph = GraphSnapshot(
            (change, specification),
            (
                Edge("missing-endpoint", EdgeKind.ASSERTS, change.id, "missing", evidence_ids=("e",)),
                Edge("missing-evidence", EdgeKind.ASSERTS, change.id, specification.id, evidence_ids=("e",)),
            ),
        )
        result = derive_graph_relationships(graph)
        self.assertEqual(result.metadata.derived_edge_count, 0)
        self.assertEqual(result.metadata.unresolved_input_count, 2)
        self.assertEqual(
            {item.affected_object_id for item in result.metadata.diagnostics},
            {"missing-endpoint", "missing-evidence"},
        )


if __name__ == "__main__":
    unittest.main()
