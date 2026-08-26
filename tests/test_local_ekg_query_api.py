from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.ontology import Edge, EdgeKind, Evidence, GraphSnapshot, Node, NodeKind, openspec_requirement_id, openspec_specification_id
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
            evidence_ref="requirement-evidence"
        )
        self.assertEqual([item["id"] for item in result], [requirement.id])


def _graph():
    specification = Node(openspec_specification_id("requirements", "payments"), NodeKind.SPECIFICATION, "payments", {"repository_id": "requirements", "capability": "payments"}, ("spec-evidence",))
    requirement = Node(openspec_requirement_id(specification.id, "Payment is submitted"), NodeKind.REQUIREMENT, "Payment is submitted", {"capability": "payments", "specification_id": specification.id, "requirement_key": "payment is submitted"}, ("requirement-evidence",))
    change = Node("change", NodeKind.OPENSPEC_ACTIVE_CHANGE, "JIRA-1")
    graph = GraphSnapshot(
        (specification, requirement, change),
        (
            Edge("contains", EdgeKind.CONTAINS, specification.id, requirement.id, evidence_ids=("requirement-evidence",)),
            Edge("assertion", EdgeKind.ASSERTS, change.id, specification.id, evidence_ids=("spec-evidence",)),
            Edge("trace", EdgeKind.TRACES_TO, change.id, specification.id, {"derived": True, "rule_id": "openspec-change-to-durable-spec"}, ("spec-evidence",)),
        ),
        (Evidence("spec-evidence", "openspec", "spec.md"), Evidence("requirement-evidence", "openspec", "spec.md")),
    )
    return change, specification, requirement, graph


if __name__ == "__main__":
    unittest.main()
