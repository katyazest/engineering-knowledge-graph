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

from engineering_kg.ingest.openspec import (
    RegisteredOpenSpecStore,
    extract_openspec_graph,
    validate_openspec_store_source,
)
from engineering_kg.ontology import EdgeKind, NodeKind
from engineering_kg.project import load_workspace_registry


class OpenSpecGraphExtractionTest(unittest.TestCase):
    def test_extracts_durable_specs_requirements_and_scenarios(self) -> None:
        result = _extract().as_dict()
        nodes = result["graph"]["nodes"]
        edges = result["graph"]["edges"]

        durable_specs = [
            node
            for node in nodes
            if node["kind"] == NodeKind.OPENSPEC_SPEC.value
            and node["properties"]["scope"] == "durable"
        ]
        durable_requirements = [
            node
            for node in nodes
            if node["kind"] == NodeKind.OPENSPEC_REQUIREMENT.value
            and node["properties"]["scope"] == "durable"
        ]
        durable_scenarios = [
            node
            for node in nodes
            if node["kind"] == NodeKind.OPENSPEC_SCENARIO.value
            and node["properties"]["scope"] == "durable"
        ]

        self.assertEqual(
            {node["properties"]["capability"] for node in durable_specs},
            {"payments", "service/payments", "settlement"},
        )
        self.assertEqual(
            {node["name"] for node in durable_requirements},
            {"Payment is submitted", "Service payment is routed", "Settlement is posted"},
        )
        self.assertEqual(
            {node["name"] for node in durable_scenarios},
            {
                "Valid payment",
                "Still belongs to previous requirement",
                "Service payment route selected",
                "Settlement complete",
            },
        )
        self.assertFalse(any(node["name"] == "Unsupported heading is ignored" for node in durable_requirements))
        self.assertTrue(
            any(edge["kind"] == EdgeKind.OPENSPEC_SPEC_CONTAINS_REQUIREMENT.value for edge in edges)
        )
        self.assertTrue(
            any(edge["kind"] == EdgeKind.OPENSPEC_REQUIREMENT_CONTAINS_SCENARIO.value for edge in edges)
        )

    def test_extracts_active_and_archived_changes_with_scoped_delta_specs(self) -> None:
        nodes = _extract().as_dict()["graph"]["nodes"]

        active_changes = [node for node in nodes if node["kind"] == NodeKind.OPENSPEC_ACTIVE_CHANGE.value]
        archived_changes = [
            node for node in nodes if node["kind"] == NodeKind.OPENSPEC_ARCHIVED_CHANGE.value
        ]
        payment_specs = [
            node
            for node in nodes
            if node["kind"] == NodeKind.OPENSPEC_SPEC.value
            and node["properties"]["capability"] == "payments"
        ]
        service_payment_specs = [
            node
            for node in nodes
            if node["kind"] == NodeKind.OPENSPEC_SPEC.value
            and node["properties"]["capability"] == "service/payments"
        ]

        self.assertEqual([node["name"] for node in active_changes], ["JIRA-123-add-refund"])
        self.assertEqual(
            [node["name"] for node in archived_changes],
            ["2026-08-01-JIRA-122-add-payments"],
        )
        self.assertEqual(
            {node["properties"]["scope"] for node in payment_specs},
            {"durable", "active-change", "archived-change"},
        )
        self.assertEqual(
            {node["properties"]["scope"] for node in service_payment_specs},
            {"durable", "active-change", "archived-change"},
        )
        self.assertEqual(active_changes[0]["properties"]["jira_reference_hints"], ["JIRA-123"])

    def test_extracts_frontmatter_related_edges_and_unresolved_refs(self) -> None:
        result = _extract().as_dict()
        payment_spec = _spec_by_capability(result["graph"]["nodes"], "payments", "durable")
        related_edges = [
            edge
            for edge in result["graph"]["edges"]
            if edge["kind"] == EdgeKind.OPENSPEC_RELATED_SPEC.value
        ]

        self.assertEqual(payment_spec["name"], "Payments Capability")
        self.assertEqual(payment_spec["properties"]["frontmatter"]["repo"], "payment-service")
        self.assertEqual(len(related_edges), 1)
        self.assertEqual(related_edges[0]["confidence"], "non-confident")
        self.assertEqual(related_edges[0]["properties"]["related_title"], "Settlement Capability")
        self.assertEqual(
            result["metadata"]["unresolved_related_spec_references"],
            [
                {
                    "capability": "payments",
                    "reason": "missing",
                    "related_title": "Missing Capability",
                }
            ],
        )

    def test_extraction_is_deterministic_and_evidence_excludes_bodies(self) -> None:
        first = _extract().as_dict()
        second = _extract().as_dict()
        serialized = str(first)

        self.assertEqual(first, second)
        self.assertEqual(first["metadata"]["status"], "completed")
        self.assertEqual(first["metadata"]["durable_spec_count"], 3)
        self.assertEqual(first["metadata"]["active_change_count"], 1)
        self.assertEqual(first["metadata"]["archived_change_count"], 1)
        self.assertEqual(first["metadata"]["requirement_count"], 3)
        self.assertEqual(first["metadata"]["scenario_count"], 4)
        self.assertTrue(
            any(
                item["locator"]["relative_file_path"]
                == "openspec/specs/service/payments/spec.md"
                for item in first["graph"]["evidence"]
            )
        )
        self.assertTrue(
            all(
                "relative_file_path" in item["locator"]
                and "openspec_identity" in item["locator"]
                and "artifact_type" in item["locator"]
                for item in first["graph"]["evidence"]
            )
        )
        for forbidden in (
            "The system SHALL submit payments",
            "source_code",
            "openlore_analysis",
            "generated_graph_records",
            "credentials",
            "tokens",
            "api_response",
        ):
            self.assertNotIn(forbidden, serialized)


def _extract():
    registry = load_workspace_registry(NON_GIT_REQUIREMENTS / "repo-index-openspec-graph-stage.yaml")
    store_source = validate_openspec_store_source(
        registry,
        registered_stores=(RegisteredOpenSpecStore("requirements-store", NON_GIT_REQUIREMENTS),),
    )
    return extract_openspec_graph(store_source)


def _spec_by_capability(nodes: list[dict[str, object]], capability: str, scope: str) -> dict[str, object]:
    matches = [
        node
        for node in nodes
        if node["kind"] == NodeKind.OPENSPEC_SPEC.value
        and node["properties"]["capability"] == capability
        and node["properties"]["scope"] == scope
    ]
    assert len(matches) == 1
    return matches[0]


if __name__ == "__main__":
    unittest.main()
