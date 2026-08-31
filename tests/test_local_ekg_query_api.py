from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.ontology import (
    Edge, EdgeKind, Evidence, GraphSnapshot, Node, NodeKind, OpenSpecLocator,
    SourceArtifactIdentity, openspec_requirement_id, openspec_specification_id, stable_id,
)
from engineering_kg.query import EngineeringKgQuery


class LocalEkgQueryApiTest(unittest.TestCase):
    def test_lists_canonical_requirements_with_openspec_provenance(self) -> None:
        change, specification, requirement, graph = _graph()
        result = EngineeringKgQuery.from_snapshot(graph).list_requirements(change=change.name)
        self.assertEqual(result[0]["kind"], "requirement")
        self.assertEqual(result[0]["id"], requirement.id)
        self.assertEqual(result[0]["locators"][0]["source"], "openspec")
        self.assertNotIn("openspec-requirement", str(result))

    def test_change_result_reports_canonical_assertion_and_traceability(self) -> None:
        change, specification, _, graph = _graph()
        result = EngineeringKgQuery.from_snapshot(graph).list_changes()[0]
        self.assertEqual(result["properties"]["asserted_spec_ids"], [specification.id])
        self.assertEqual(result["properties"]["traceability_spec_ids"], [specification.id])

    def test_filters_canonical_requirements_by_evidence_reference(self) -> None:
        _, _, requirement, graph = _graph()
        result = EngineeringKgQuery.from_snapshot(graph).list_requirements(
            evidence_ref=graph.evidence[1].id
        )
        self.assertEqual([item["id"] for item in result], [requirement.id])


def _graph():
    identity = SourceArtifactIdentity(
        "openspec", "requirements", "openspec-spec", "a" * 40,
        "openspec/specs/payments/spec.md",
    )
    spec_evidence_id = stable_id("evidence", identity.id, "durable:payments")
    requirement_evidence_id = stable_id(
        "evidence", identity.id, "durable:payments:requirement:payment-is-submitted"
    )
    specification = Node(openspec_specification_id("requirements", "payments"), NodeKind.SPECIFICATION, "payments", {"repository_id": "requirements", "capability": "payments"}, (spec_evidence_id,))
    requirement = Node(openspec_requirement_id(specification.id, "Payment is submitted"), NodeKind.REQUIREMENT, "Payment is submitted", {"capability": "payments", "specification_id": specification.id, "requirement_key": "payment is submitted"}, (requirement_evidence_id,))
    change = Node("change", NodeKind.OPENSPEC_ACTIVE_CHANGE, "JIRA-1")
    graph = GraphSnapshot(
        (specification, requirement, change),
        (
            Edge("contains", EdgeKind.CONTAINS, specification.id, requirement.id, evidence_ids=(requirement_evidence_id,)),
            Edge("assertion", EdgeKind.ASSERTS, change.id, specification.id, evidence_ids=(spec_evidence_id,)),
            Edge("trace", EdgeKind.TRACES_TO, change.id, specification.id, {"derived": True, "rule_id": "openspec-change-to-durable-spec"}, (spec_evidence_id,)),
        ),
        (
            Evidence(
                spec_evidence_id, "openspec",
                OpenSpecLocator(
                    "openspec/specs/payments/spec.md", "openspec-spec", "durable:payments",
                    source_artifact_identity=identity,
                ),
            ),
            Evidence(
                requirement_evidence_id, "openspec",
                OpenSpecLocator(
                    "openspec/specs/payments/spec.md", "openspec-spec",
                    "durable:payments:requirement:payment-is-submitted",
                    source_artifact_identity=identity,
                ),
            ),
        ),
    )
    return change, specification, requirement, graph


if __name__ == "__main__":
    unittest.main()
