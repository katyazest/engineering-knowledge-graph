from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from engineering_kg.ontology import (
    CodeLocator,
    ConfluencePageRef,
    Edge,
    EdgeKind,
    Evidence,
    GraphSnapshot,
    Node,
    NodeKind,
    OpenSpecLocator,
    stable_id,
)


class CanonicalOntologyTest(unittest.TestCase):
    def test_stable_id_is_deterministic_for_same_identity(self) -> None:
        first = stable_id("node", NodeKind.REPOSITORY, "Payments")
        second = stable_id("node", "repository", " payments ")

        self.assertEqual(first, second)

    def test_stable_id_changes_for_different_identity(self) -> None:
        repository_id = stable_id("node", NodeKind.REPOSITORY, "Payments")
        service_id = stable_id("node", NodeKind.SERVICE, "Payments")

        self.assertNotEqual(repository_id, service_id)

    def test_code_locator_serializes_only_reference_identity(self) -> None:
        locator = CodeLocator(
            repository="payment-service",
            revision="abc123",
            file="src/app.py",
            symbol="create_payment",
        )

        serialized = locator.as_dict()

        self.assertEqual(
            serialized,
            {
                "file": "src/app.py",
                "repository": "payment-service",
                "revision": "abc123",
                "symbol": "create_payment",
            },
        )
        forbidden = {
            "source_code",
            "call_graph",
            "dependency_graph",
            "class_body",
            "function_body",
            "openlore_analysis",
        }
        self.assertTrue(forbidden.isdisjoint(serialized))

    def test_confluence_page_ref_serializes_only_page_id(self) -> None:
        page_ref = ConfluencePageRef(page_id="123456789")

        serialized = page_ref.as_dict()

        self.assertEqual(serialized, {"page_id": "123456789"})
        forbidden = {
            "page_content",
            "content",
            "page_url",
            "url",
            "comments",
            "attachments",
            "credentials",
            "token",
            "api_response",
        }
        self.assertTrue(forbidden.isdisjoint(serialized))

    def test_evidence_accepts_confluence_page_ref_locator(self) -> None:
        evidence = Evidence(
            id=stable_id("evidence", "confluence", "123456789"),
            source="confluence",
            locator=ConfluencePageRef(page_id="123456789"),
        )

        serialized = evidence.as_dict()

        self.assertEqual(serialized["locator"], {"page_id": "123456789"})
        self.assertNotIn("content", serialized["locator"])
        self.assertNotIn("url", serialized["locator"])

    def test_graph_models_construct_and_serialize_deterministically(self) -> None:
        node = Node(
            id=stable_id("node", NodeKind.REPOSITORY, "payment-service"),
            kind=NodeKind.REPOSITORY,
            name="payment-service",
            properties={"language": "python"},
        )
        evidence = Evidence(
            id=stable_id("evidence", "repo-index", "payment-service"),
            source="repo-index",
            locator="repo-index.yaml",
        )
        edge = Edge(
            id=stable_id("edge", EdgeKind.OWNS, "payment-service", "repo-index"),
            kind=EdgeKind.OWNS,
            source_id=node.id,
            target_id=evidence.id,
        )
        snapshot = GraphSnapshot(nodes=(node,), edges=(edge,), evidence=(evidence,))

        first = snapshot.as_dict()
        second = snapshot.as_dict()

        self.assertEqual(first, second)
        self.assertEqual(first["node_count"], 1)
        self.assertEqual(first["edge_count"], 1)
        self.assertEqual(first["evidence_count"], 1)
        self.assertEqual(json.loads(snapshot.as_json()), first)

    def test_empty_graph_snapshot_contains_empty_collections(self) -> None:
        snapshot = GraphSnapshot()

        self.assertEqual(snapshot.nodes, ())
        self.assertEqual(snapshot.edges, ())
        self.assertEqual(snapshot.evidence, ())
        self.assertEqual(
            snapshot.as_dict(),
            {
                "edge_count": 0,
                "edges": [],
                "evidence": [],
                "evidence_count": 0,
                "node_count": 0,
                "nodes": [],
            },
        )

    def test_openspec_ontology_vocabulary_serializes_deterministically(self) -> None:
        self.assertEqual(NodeKind.OPENSPEC_ACTIVE_CHANGE.value, "openspec-active-change")
        self.assertEqual(NodeKind.OPENSPEC_ARCHIVED_CHANGE.value, "openspec-archived-change")
        self.assertEqual(NodeKind.OPENSPEC_SPEC.value, "openspec-spec")
        self.assertEqual(NodeKind.OPENSPEC_REQUIREMENT.value, "openspec-requirement")
        self.assertEqual(NodeKind.OPENSPEC_SCENARIO.value, "openspec-scenario")
        self.assertEqual(NodeKind.OPENSPEC_ARTIFACT.value, "openspec-artifact")
        self.assertEqual(
            EdgeKind.OPENSPEC_SPEC_CONTAINS_REQUIREMENT.value,
            "openspec-spec-contains-requirement",
        )
        self.assertEqual(
            EdgeKind.OPENSPEC_REQUIREMENT_CONTAINS_SCENARIO.value,
            "openspec-requirement-contains-scenario",
        )
        self.assertEqual(EdgeKind.OPENSPEC_CHANGE_HAS_ARTIFACT.value, "openspec-change-has-artifact")
        self.assertEqual(EdgeKind.OPENSPEC_CHANGE_TOUCHES_SPEC.value, "openspec-change-touches-spec")
        self.assertEqual(EdgeKind.OPENSPEC_RELATED_SPEC.value, "openspec-related-spec")

    def test_edge_confidence_serializes_only_when_set(self) -> None:
        structural = Edge(
            id=stable_id("edge", "structural"),
            kind=EdgeKind.OPENSPEC_SPEC_CONTAINS_REQUIREMENT,
            source_id="spec",
            target_id="requirement",
        )
        related = Edge(
            id=stable_id("edge", "related"),
            kind=EdgeKind.OPENSPEC_RELATED_SPEC,
            source_id="spec-a",
            target_id="spec-b",
            confidence="non-confident",
        )

        self.assertNotIn("confidence", structural.as_dict())
        self.assertEqual(related.as_dict()["confidence"], "non-confident")

    def test_openspec_locator_serializes_without_source_body(self) -> None:
        evidence = Evidence(
            id=stable_id("evidence", "openspec", "openspec/specs/payments/spec.md"),
            source="openspec",
            locator=OpenSpecLocator(
                relative_file_path="openspec/specs/payments/spec.md",
                artifact_type="openspec-requirement",
                openspec_identity="durable:current:payments:requirement:Payment is submitted",
                heading_name="Payment is submitted",
                line_start=8,
            ),
        )

        serialized = evidence.as_dict()

        self.assertEqual(
            serialized["locator"]["relative_file_path"],
            "openspec/specs/payments/spec.md",
        )
        self.assertEqual(serialized["locator"]["artifact_type"], "openspec-requirement")
        self.assertEqual(serialized["locator"]["heading_name"], "Payment is submitted")
        for forbidden in (
            "content",
            "full_markdown",
            "source_code",
            "generated_graph_records",
            "credentials",
            "tokens",
            "api_response",
        ):
            self.assertNotIn(forbidden, str(serialized))


if __name__ == "__main__":
    unittest.main()
