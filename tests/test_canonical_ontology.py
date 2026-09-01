from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.ontology import (
    Edge, EdgeKind, Evidence, GraphSnapshot, Node, NodeKind, OpenSpecLocator,
    ProvenanceRecord, SourceArtifactIdentity, SourceArtifactLocator,
    openspec_requirement_id, openspec_scenario_id, openspec_specification_id,
    stable_id,
)


class CanonicalOntologyTest(unittest.TestCase):
    def test_openspec_backed_ids_ignore_source_locator_details(self) -> None:
        specification_id = openspec_specification_id("requirements", "payments")
        self.assertEqual(specification_id, openspec_specification_id(" REQUIREMENTS ", " Payments "))
        requirement_id = openspec_requirement_id(specification_id, "Payment is submitted")
        self.assertEqual(requirement_id, openspec_requirement_id(specification_id, " payment   is submitted "))
        self.assertEqual(
            openspec_scenario_id(requirement_id, "Valid payment"),
            openspec_scenario_id(requirement_id, " valid payment "),
        )

    def test_canonical_vocabulary_retains_only_source_owned_openspec_nodes(self) -> None:
        self.assertEqual(NodeKind.SPECIFICATION.value, "specification")
        self.assertEqual(NodeKind.REQUIREMENT.value, "requirement")
        self.assertEqual(NodeKind.SCENARIO.value, "scenario")
        self.assertEqual(NodeKind.OPENSPEC_ACTIVE_CHANGE.value, "openspec-active-change")
        self.assertEqual(NodeKind.OPENSPEC_ARTIFACT.value, "openspec-artifact")
        self.assertFalse(hasattr(NodeKind, "OPENSPEC_SPEC"))

    def test_snapshot_merges_compatible_provenance_and_rejects_conflicts(self) -> None:
        node_id = openspec_specification_id("requirements", "payments")
        left = Node(node_id, NodeKind.SPECIFICATION, "Payments", {"repository_id": "requirements", "capability": "payments"}, ("a",))
        right = Node(node_id, NodeKind.SPECIFICATION, "Payments capability", {"repository_id": "requirements", "capability": "payments"}, ("b",))
        graph = GraphSnapshot(nodes=(left,)).merged_with(GraphSnapshot(nodes=(right,)))
        self.assertEqual(graph.nodes[0].evidence_ids, ("a", "b"))
        conflict = Node(node_id, NodeKind.SPECIFICATION, "Payments", {"repository_id": "other", "capability": "payments"})
        with self.assertRaises(ValueError):
            graph.merged_with(GraphSnapshot(nodes=(conflict,)))

    def test_openspec_evidence_excludes_content(self) -> None:
        evidence = Evidence("e", "openspec", OpenSpecLocator("openspec/specs/payments/spec.md", "openspec-requirement", "durable:payments", "Payment", 4))
        self.assertNotIn("content", evidence.as_dict()["locator"])

    def test_equivalent_external_evidence_coalesces_and_conflicts_are_order_independent(self) -> None:
        identity = SourceArtifactIdentity("jira", "ENG", "issue", "42", "issues/ENG-42")
        provenance = _external_provenance(identity)
        evidence = Evidence(stable_id("evidence", identity.id), "jira", SourceArtifactLocator(identity), provenance_ids=(provenance.id,))
        self.assertEqual(
            GraphSnapshot(evidence=(evidence,), provenance=(provenance,)).merged_with(GraphSnapshot(evidence=(evidence,), provenance=(provenance,))).evidence,
            (evidence,),
        )
        conflicting = Evidence(
            evidence.id, "jira", SourceArtifactLocator(identity, {"heading_name": "Conflicting"}), provenance_ids=(provenance.id,)
        )
        for first, second in ((evidence, conflicting), (conflicting, evidence)):
            with self.assertRaisesRegex(ValueError, "Conflicting graph record values"):
                GraphSnapshot(evidence=(first,), provenance=(provenance,)).merged_with(GraphSnapshot(evidence=(second,), provenance=(provenance,)))


def _external_provenance(identity: SourceArtifactIdentity) -> ProvenanceRecord:
    return ProvenanceRecord(
        "external", "2026-01-02T03:04:05+00:00", "sha256", "a" * 64,
        "test-extractor", "1", identity,
    )


if __name__ == "__main__":
    unittest.main()
