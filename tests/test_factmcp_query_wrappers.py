from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.mcp.factmcp_server import register_query_tools
from engineering_kg.ontology import GraphSnapshot, Node, NodeKind
from engineering_kg.query import EngineeringKgQuery
from tests.test_local_ekg_query_api import _graph


class _Server:
    def __init__(self): self.tools = {}
    def tool(self):
        def decorator(function): self.tools[function.__name__] = function; return function
        return decorator


class FactMcpQueryWrappersTest(unittest.TestCase):
    def test_requirement_tool_delegates_canonical_result(self) -> None:
        server = _Server()
        _, _, _, graph = _graph()
        register_query_tools(server, graph_store_path=".", query_factory=lambda _: EngineeringKgQuery.from_snapshot(graph))
        result = server.tools["list_requirements"]()
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"][0]["kind"], "requirement")
        self.assertEqual(result["result"][0]["evidence_freshness"][0]["status"], "unknown")
        self.assertNotIn("openspec-requirement", str(result))

    def test_traceability_tool_delegates_canonical_result(self) -> None:
        server = _Server()
        change, _, _, graph = _graph()
        register_query_tools(server, graph_store_path=".", query_factory=lambda _: EngineeringKgQuery.from_snapshot(graph))
        result = server.tools["get_traceability"](change.id)
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["object_id"], change.id)
        self.assertTrue(any(edge["kind"] == "traces_to" for edge in result["result"]["relationships"]))
        trace = next(edge for edge in result["result"]["relationships"] if edge["kind"] == "traces_to")
        self.assertEqual([item["evidence_id"] for item in trace["evidence_freshness"]], trace["evidence_ids"])
        self.assertTrue(all(item["status"] == "unknown" for item in trace["evidence_freshness"]))
        self.assertTrue(all(not item["current_evidence_eligible"] for item in trace["evidence_freshness"]))

    def test_wrapper_forwards_checked_revisions_and_returns_safe_invalid_error(self) -> None:
        server = _Server()
        _, _, _, graph = _graph()
        register_query_tools(server, graph_store_path=".", query_factory=lambda _: EngineeringKgQuery.from_snapshot(graph))
        checked = [{"source_type": "openspec", "source_identity": "requirements", "artifact_type": "openspec-spec",
                    "stable_locator": "openspec/specs/payments/spec.md", "revision_or_version": "a" * 40,
                    "checked_at": "2026-01-02T03:04:05+00:00"}]
        result = server.tools["list_requirements"](checked_revisions=checked)
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"][0]["evidence_freshness"][0]["status"], "fresh")
        unsafe = server.tools["list_requirements"](checked_revisions=[dict(checked[0], stable_locator="https://secret/token")])
        self.assertFalse(unsafe["ok"])
        self.assertNotIn("result", unsafe)
        self.assertNotIn("https://secret/token", str(unsafe))

    def test_service_and_change_tools_forward_checked_revisions(self) -> None:
        server = _Server()
        _, _, _, graph = _graph()
        service = Node("service", NodeKind.SERVICE, "payments", evidence_ids=graph.nodes[0].evidence_ids)
        change = next(node for node in graph.nodes if node.kind == NodeKind.OPENSPEC_ACTIVE_CHANGE)
        change = Node(change.id, change.kind, change.name, evidence_ids=graph.nodes[0].evidence_ids)
        graph = GraphSnapshot(
            nodes=tuple(change if node.id == change.id else node for node in graph.nodes) + (service,), edges=graph.edges,
            evidence=graph.evidence, provenance=graph.provenance,
        )
        register_query_tools(server, graph_store_path=".", query_factory=lambda _: EngineeringKgQuery.from_snapshot(graph))
        checked = [
            {
                "source_type": provenance.source_artifact_identity.source_type,
                "source_identity": provenance.source_artifact_identity.source_identity,
                "artifact_type": provenance.source_artifact_identity.artifact_type,
                "stable_locator": provenance.source_artifact_identity.stable_locator,
                "revision_or_version": provenance.source_artifact_identity.revision_or_version,
                "checked_at": "2026-10-01T00:00:00+00:00",
            }
            for provenance in graph.provenance
            if provenance.source_artifact_identity is not None
        ]

        services = server.tools["list_services"](checked_revisions=checked)
        changes = server.tools["list_changes"](checked_revisions=checked)

        self.assertTrue(services["ok"])
        self.assertTrue(changes["ok"])
        self.assertTrue(any(
            projection["status"] == "fresh"
            for service in services["result"]
            for projection in service["evidence_freshness"]
        ))
        self.assertTrue(any(
            projection["status"] == "fresh"
            for change in changes["result"]
            for projection in change["evidence_freshness"]
        ))


if __name__ == "__main__":
    unittest.main()
