from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
FIXTURES = REPO_ROOT / "tests" / "fixtures"
NON_GIT_REQUIREMENTS = FIXTURES / "non-git-workspace" / "openspec" / "requirements_repo"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from engineering_kg.derivation import derive_graph_relationships
from engineering_kg.ingest.openspec import (
    RegisteredOpenSpecStore,
    extract_openspec_graph,
    validate_openspec_store_source,
)
from engineering_kg.ontology import Edge, EdgeKind, GraphSnapshot, Node, NodeKind, stable_id
from engineering_kg.project import load_workspace_registry


class GraphDerivationTest(unittest.TestCase):
    def test_derives_openspec_change_to_durable_spec_relationships(self) -> None:
        graph = _extract_graph()

        result = derive_graph_relationships(graph).as_dict()
        derived_edges = [
            edge
            for edge in result["graph"]["edges"]
            if edge["kind"] == EdgeKind.OPENSPEC_CHANGE_TRACES_TO_SPEC.value
        ]

        self.assertEqual(result["metadata"]["status"], "completed")
        self.assertEqual(result["metadata"]["derived_edge_count"], 2)
        self.assertEqual(len(derived_edges), 2)
        self.assertEqual(
            {edge["properties"]["capability"] for edge in derived_edges},
            {"payments"},
        )
        self.assertTrue(all(edge["properties"]["derived"] for edge in derived_edges))
        self.assertTrue(
            all(edge["properties"]["target_scope"] == "durable" for edge in derived_edges)
        )

    def test_derivation_is_deterministic_and_does_not_duplicate_edges(self) -> None:
        graph = _extract_graph()

        first = derive_graph_relationships(graph)
        second = derive_graph_relationships(graph)
        repeated = derive_graph_relationships(first.graph)

        self.assertEqual(first.as_dict(), second.as_dict())
        self.assertEqual(first.graph.as_dict(), repeated.graph.as_dict())
        self.assertEqual(first.metadata.derived_edge_count, repeated.metadata.derived_edge_count)

    def test_missing_durable_spec_is_reported_without_inventing_node(self) -> None:
        change = Node(
            id=stable_id("node", NodeKind.OPENSPEC_ACTIVE_CHANGE, "JIRA-999-add-refunds"),
            kind=NodeKind.OPENSPEC_ACTIVE_CHANGE,
            name="JIRA-999-add-refunds",
            properties={"change_identity": "JIRA-999-add-refunds"},
        )
        change_spec = Node(
            id=stable_id("node", NodeKind.OPENSPEC_SPEC, "active-change", "JIRA-999-add-refunds", "refunds"),
            kind=NodeKind.OPENSPEC_SPEC,
            name="Refunds",
            properties={
                "capability": "refunds",
                "change_identity": "JIRA-999-add-refunds",
                "scope": "active-change",
            },
        )
        touches = Edge(
            id=stable_id("edge", EdgeKind.OPENSPEC_CHANGE_TOUCHES_SPEC, change.id, change_spec.id),
            kind=EdgeKind.OPENSPEC_CHANGE_TOUCHES_SPEC,
            source_id=change.id,
            target_id=change_spec.id,
        )
        graph = GraphSnapshot(nodes=(change, change_spec), edges=(touches,))

        result = derive_graph_relationships(graph).as_dict()

        self.assertEqual(result["metadata"]["derived_edge_count"], 0)
        self.assertEqual(result["metadata"]["unresolved_input_count"], 1)
        self.assertEqual(result["graph"]["node_count"], 2)
        self.assertIn("No durable OpenSpec spec exists", result["metadata"]["diagnostics"][0]["message"])

    def test_non_confident_related_spec_relationship_is_preserved(self) -> None:
        graph = _extract_graph()

        result = derive_graph_relationships(graph).as_dict()
        related_edges = [
            edge
            for edge in result["graph"]["edges"]
            if edge["kind"] == EdgeKind.OPENSPEC_RELATED_SPEC.value
        ]

        self.assertEqual(len(related_edges), 1)
        self.assertEqual(related_edges[0]["confidence"], "non-confident")
        serialized = str(result)
        for forbidden in (
            "source_code",
            "openlore_analysis",
            "generated_graph_records",
            "credentials",
            "tokens",
            "api_response",
        ):
            self.assertNotIn(forbidden, serialized)


def _extract_graph() -> GraphSnapshot:
    registry = load_workspace_registry(NON_GIT_REQUIREMENTS / "repo-index-openspec-graph-stage.yaml")
    store_source = validate_openspec_store_source(
        registry,
        registered_stores=(RegisteredOpenSpecStore("requirements-store", NON_GIT_REQUIREMENTS),),
    )
    return extract_openspec_graph(store_source).graph


if __name__ == "__main__":
    unittest.main()
