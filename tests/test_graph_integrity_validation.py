from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from engineering_kg.ontology import Edge, EdgeKind, Evidence, GraphSnapshot, Node, NodeKind, stable_id
from engineering_kg.validation import validate_graph_integrity


class GraphIntegrityValidationTest(unittest.TestCase):
    def test_validates_broken_edge_endpoints_and_missing_evidence(self) -> None:
        node = Node(
            id=stable_id("node", NodeKind.OPENSPEC_SPEC, "payments"),
            kind=NodeKind.OPENSPEC_SPEC,
            name="payments",
            evidence_ids=("missing-evidence",),
        )
        edge = Edge(
            id=stable_id("edge", "broken", node.id, "missing-node"),
            kind=EdgeKind.OPENSPEC_CHANGE_TRACES_TO_SPEC,
            source_id=node.id,
            target_id="missing-node",
            evidence_ids=("missing-edge-evidence",),
        )
        graph = GraphSnapshot(nodes=(node,), edges=(edge,))

        result = validate_graph_integrity(graph).as_dict()
        rule_ids = {item["rule_id"] for item in result["metadata"]["diagnostics"]}

        self.assertEqual(result["status"], "invalid")
        self.assertIn("edge-target-exists", rule_ids)
        self.assertIn("evidence-reference-exists", rule_ids)
        self.assertEqual(result["metadata"]["severity_counts"]["error"], 3)

    def test_duplicate_identical_objects_are_counted_without_conflict(self) -> None:
        node = Node(
            id=stable_id("node", NodeKind.REPOSITORY, "payments"),
            kind=NodeKind.REPOSITORY,
            name="payments",
        )
        graph = GraphSnapshot(nodes=(node, node))

        result = validate_graph_integrity(graph).as_dict()

        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["metadata"]["duplicate_counts"]["node"], 1)
        self.assertEqual(result["metadata"]["diagnostics"], [])

    def test_duplicate_conflicting_objects_are_invalid(self) -> None:
        node_id = stable_id("node", NodeKind.REPOSITORY, "payments")
        graph = GraphSnapshot(
            nodes=(
                Node(id=node_id, kind=NodeKind.REPOSITORY, name="payments"),
                Node(id=node_id, kind=NodeKind.REPOSITORY, name="payments-v2"),
            )
        )

        result = validate_graph_integrity(graph).as_dict()

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(
            result["metadata"]["diagnostics"][0]["rule_id"],
            "duplicate-identity-conflict",
        )

    def test_traceability_shape_requires_openspec_change_to_durable_spec(self) -> None:
        repository = Node(
            id=stable_id("node", NodeKind.REPOSITORY, "payments"),
            kind=NodeKind.REPOSITORY,
            name="payments",
        )
        active_spec = Node(
            id=stable_id("node", NodeKind.OPENSPEC_SPEC, "active-change", "JIRA-1", "payments"),
            kind=NodeKind.OPENSPEC_SPEC,
            name="payments",
            properties={"scope": "active-change"},
        )
        edge = Edge(
            id=stable_id("edge", EdgeKind.OPENSPEC_CHANGE_TRACES_TO_SPEC, repository.id, active_spec.id),
            kind=EdgeKind.OPENSPEC_CHANGE_TRACES_TO_SPEC,
            source_id=repository.id,
            target_id=active_spec.id,
        )
        graph = GraphSnapshot(nodes=(repository, active_spec), edges=(edge,))

        result = validate_graph_integrity(graph).as_dict()
        rule_ids = [item["rule_id"] for item in result["metadata"]["diagnostics"]]

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(
            rule_ids,
            ["openspec-traceability-source-kind", "openspec-traceability-target-kind"],
        )

    def test_generic_traces_to_is_not_forced_to_openspec_shape(self) -> None:
        repository = Node(
            id=stable_id("node", NodeKind.REPOSITORY, "payments"),
            kind=NodeKind.REPOSITORY,
            name="payments",
        )
        requirement = Node(
            id=stable_id("node", NodeKind.REQUIREMENT, "payment requirement"),
            kind=NodeKind.REQUIREMENT,
            name="Payment requirement",
        )
        edge = Edge(
            id=stable_id("edge", EdgeKind.TRACES_TO, repository.id, requirement.id),
            kind=EdgeKind.TRACES_TO,
            source_id=repository.id,
            target_id=requirement.id,
        )
        graph = GraphSnapshot(nodes=(repository, requirement), edges=(edge,))

        result = validate_graph_integrity(graph).as_dict()

        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["metadata"]["diagnostics"], [])

    def test_unresolved_non_confident_related_spec_is_warning(self) -> None:
        spec = Node(
            id=stable_id("node", NodeKind.OPENSPEC_SPEC, "durable", "payments"),
            kind=NodeKind.OPENSPEC_SPEC,
            name="Payments",
            properties={
                "frontmatter": {"related": ["Missing Capability"]},
                "scope": "durable",
            },
        )
        graph = GraphSnapshot(nodes=(spec,), evidence=(Evidence("ev", "test", "fixture"),))

        first = validate_graph_integrity(graph).as_dict()
        second = validate_graph_integrity(graph).as_dict()

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "valid")
        self.assertEqual(first["metadata"]["severity_counts"], {"warning": 1})
        self.assertEqual(
            first["metadata"]["diagnostics"][0]["rule_id"],
            "unresolved-non-confident-related-spec",
        )
        serialized = str(first)
        for forbidden in (
            "source_code",
            "openlore_analysis",
            "generated_graph_records",
            "credentials",
            "tokens",
            "api_response",
        ):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
