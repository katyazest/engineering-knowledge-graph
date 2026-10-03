from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import PropertyMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.mcp.factmcp_server import register_query_tools
from engineering_kg.ontology import (
    CrossGraphLinkLifecycle, Edge, EdgeKind, GraphSnapshot, Node, NodeKind, ProvenanceRecord,
    graph_merge_conflicts,
)
from engineering_kg.query import EngineeringKgQuery
from tests.test_local_ekg_query_api import _graph, _trusted_cross_graph_snapshot


class _Server:
    def __init__(self): self.tools = {}
    def tool(self):
        def decorator(function): self.tools[function.__name__] = function; return function
        return decorator


class FactMcpQueryWrappersTest(unittest.TestCase):
    def test_traceability_tool_marks_conflicting_endpoint_node_unresolved_in_both_orders(self) -> None:
        change, _, _, graph = _graph()
        incompatible_endpoint = Node(change.id, NodeKind.REPOSITORY, "conflicting endpoint")
        for nodes in ((*graph.nodes, incompatible_endpoint), (incompatible_endpoint, *graph.nodes)):
            with self.subTest(first=nodes[0].kind):
                snapshot = GraphSnapshot(
                    nodes=nodes, edges=graph.edges, evidence=graph.evidence,
                    provenance=graph.provenance,
                )
                server = _Server()
                register_query_tools(
                    server, graph_store_path=".",
                    query_factory=lambda _, snapshot=snapshot: EngineeringKgQuery.from_snapshot(snapshot),
                )
                result = server.tools["get_traceability"](change.id)
                projected = next(
                    item for item in result["result"]["relationships"]
                    if item["edge_id"] == "trace"
                )
                self.assertTrue(result["ok"])
                self.assertEqual(projected["evidence_use"]["disposition"], "unresolved")
                self.assertIn("conflicting", projected["evidence_use"]["reason_codes"])

    def test_registered_traceability_preserves_cross_graph_subject_and_lifecycle_conflicts(self) -> None:
        subject, graph = _trusted_cross_graph_snapshot()
        claim = graph.cross_graph_link_claims[0]
        observation = graph.cross_graph_link_evidence[0]
        trusted_lifecycle = graph.cross_graph_link_lifecycle[0]
        conflicting_subject = Node(subject.id, NodeKind.REPOSITORY, "conflicting subject")
        conflicting_lifecycle = CrossGraphLinkLifecycle(
            claim.id, trusted_lifecycle.revision, "candidate",
            graph.evidence[1].id, trusted_lifecycle.origin, trusted_lifecycle.status,
            trusted_lifecycle.confidence, trusted_lifecycle.trust_disposition,
        )
        cohorts = (
            ("subject", (subject, conflicting_subject), (trusted_lifecycle,)),
            ("lifecycle", (subject,), (trusted_lifecycle, conflicting_lifecycle)),
        )
        for conflict_kind, nodes, lifecycles in cohorts:
            for reverse in (False, True):
                ordered_nodes = tuple(reversed(nodes)) if reverse else nodes
                ordered_lifecycles = tuple(reversed(lifecycles)) if reverse else lifecycles
                snapshot = GraphSnapshot(
                    nodes=ordered_nodes, evidence=graph.evidence, provenance=graph.provenance,
                    cross_graph_link_claims=graph.cross_graph_link_claims,
                    cross_graph_link_evidence=(observation,),
                    cross_graph_link_lifecycle=ordered_lifecycles,
                )
                server = _Server()
                register_query_tools(
                    server, graph_store_path=".",
                    query_factory=lambda _, snapshot=snapshot: EngineeringKgQuery.from_snapshot(snapshot),
                )
                result = server.tools["get_traceability"](subject.id)
                self.assertTrue(result["ok"])
                link = result["result"]["cross_graph_links"][0]
                for projected in (link, link["claim"], link["observations"][0]):
                    self.assertEqual(projected["evidence_use"]["disposition"], "unresolved")
                    self.assertIn("conflicting", projected["evidence_use"]["reason_codes"])
                self.assertFalse(link["trusted_projection"])

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

    def test_critical_conclusion_tool_is_additive_and_delegates(self) -> None:
        server = _Server()
        _, _, _, graph = _graph()
        register_query_tools(server, graph_store_path=".", query_factory=lambda _: EngineeringKgQuery.from_snapshot(graph))
        self.assertIn("get_traceability", server.tools)
        result = server.tools["explain_critical_conclusion"]("change_readiness", "absent-change")
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["disposition"], "unresolved")
        invalid = server.tools["explain_critical_conclusion"]("unsupported", "absent-change")
        self.assertFalse(invalid["ok"])
        self.assertNotIn("result", invalid)

    def test_traceability_tool_marks_same_id_canonical_conflict_unresolved(self) -> None:
        server = _Server()
        _, _, _, graph = _graph()
        subject = Node("conflict-subject", NodeKind.REPOSITORY, "repository")
        first = Node("owner-one", NodeKind.WORKSPACE, "one")
        second = Node("owner-two", NodeKind.WORKSPACE, "two")
        edge = Edge("same-owner-edge", EdgeKind.OWNED_BY, subject.id, first.id,
                    evidence_ids=(graph.evidence[0].id,))
        incompatible = Edge("same-owner-edge", EdgeKind.OWNED_BY, subject.id, second.id,
                            evidence_ids=(graph.evidence[0].id,))
        conflicted = GraphSnapshot(
            nodes=(*graph.nodes, subject, first, second),
            edges=(*graph.edges, edge, incompatible), evidence=graph.evidence,
            provenance=graph.provenance, allow_legacy_evidence=True,
        )
        register_query_tools(server, graph_store_path=".",
                             query_factory=lambda _: EngineeringKgQuery.from_snapshot(conflicted))

        result = server.tools["get_traceability"](subject.id)

        self.assertTrue(result["ok"])
        conflicting_edges = [item for item in result["result"]["relationships"]
                             if item["edge_id"] == edge.id]
        self.assertEqual(len(conflicting_edges), 2)
        self.assertTrue(all(item["evidence_use"]["disposition"] == "unresolved"
                            for item in conflicting_edges))
        self.assertTrue(all("conflicting" in item["evidence_use"]["reason_codes"]
                            for item in conflicting_edges))

    def test_traceability_tool_rejects_conflicting_support_cohorts_in_either_order(self) -> None:
        _, _, _, graph = _graph()
        subject = Node("mcp-cohort-subject", NodeKind.REPOSITORY, "repo")
        owner = Node("mcp-cohort-owner", NodeKind.WORKSPACE, "owner")
        edge = Edge("mcp-cohort-edge", EdgeKind.OWNED_BY, subject.id, owner.id,
                    evidence_ids=(graph.evidence[0].id,))
        evidence = graph.evidence[0]
        conflicting_evidence = evidence.__class__(
            evidence.id, "conflicting-source", evidence.locator,
            evidence.properties, evidence.provenance_ids,
        )
        provenance_id = evidence.provenance_ids[0]
        provenance = next(item for item in graph.provenance if item.id == provenance_id)

        conflicting_provenance = ProvenanceRecord(
            kind=provenance.kind, observed_at=provenance.observed_at,
            content_hash_algorithm=provenance.content_hash_algorithm,
            content_hash=("f" * 64 if provenance.content_hash != "f" * 64 else "e" * 64),
            extractor_id=provenance.extractor_id,
            extractor_version=provenance.extractor_version,
            source_artifact_identity=provenance.source_artifact_identity,
            derivation_rule_id=provenance.derivation_rule_id,
            input_provenance_ids=provenance.input_provenance_ids,
        )
        self.assertIs(type(provenance), ProvenanceRecord)
        self.assertIs(type(conflicting_provenance), ProvenanceRecord)
        cohorts = (
            ("evidence", (evidence, conflicting_evidence)),
            ("provenance", (provenance, conflicting_provenance)),
        )
        for collection, cohort in cohorts:
            for records in (cohort, tuple(reversed(cohort))):
                # Hold the canonical ID constant to exercise conflict comparison
                # between two ordinary ProvenanceRecord instances with different
                # serialized fields, independent of the ID derivation algorithm.
                with patch.object(ProvenanceRecord, "id", new_callable=PropertyMock,
                                  return_value=provenance_id):
                    snapshot_evidence = graph.evidence
                    snapshot_provenance = graph.provenance
                    if collection == "evidence":
                        snapshot_evidence = tuple(
                            item for item in graph.evidence if item.id != evidence.id
                        ) + records
                    else:
                        snapshot_provenance = tuple(
                            item for item in graph.provenance if item.id != provenance_id
                        ) + records

                    snapshot = GraphSnapshot(
                        nodes=(*graph.nodes, subject, owner), edges=(*graph.edges, edge),
                        evidence=snapshot_evidence,
                        provenance=snapshot_provenance,
                        allow_legacy_evidence=True,
                    )
                    if collection == "provenance":
                        matching_provenance = tuple(
                            item for item in snapshot.provenance if item.id == provenance_id
                        )
                        self.assertEqual(matching_provenance, records)
                        self.assertEqual(len(matching_provenance), 2)
                        self.assertEqual(records[0].id, records[1].id)
                        self.assertNotEqual(records[0].as_dict(), records[1].as_dict())
                        conflicts = graph_merge_conflicts(snapshot)
                        self.assertTrue(any(
                            conflict.collection == "provenance"
                            and conflict.canonical_id == provenance_id
                            for conflict in conflicts
                        ))

                    server = _Server()
                    register_query_tools(server, graph_store_path=".",
                                         query_factory=lambda _, snapshot=snapshot: EngineeringKgQuery.from_snapshot(snapshot))
                    result = server.tools["get_traceability"](subject.id)
                    projected = next(item for item in result["result"]["relationships"]
                                     if item["edge_id"] == edge.id)
                    self.assertEqual(projected["evidence_use"]["disposition"], "unresolved")
                    self.assertIn("conflicting", projected["evidence_use"]["reason_codes"])

    def test_readiness_tool_forwards_freshness_without_making_decision(self) -> None:
        from tests.test_verification_ontology import verification_node

        server = _Server()
        change, _, _, graph = _graph()
        evidence_id = graph.evidence[0].id
        test_case = verification_node(NodeKind.TEST_CASE, "readiness", "case-mcp-64", (evidence_id,))
        test_run = verification_node(NodeKind.TEST_RUN, "readiness", "run-mcp-64", (evidence_id,))
        pull_request = Node("readiness-mcp-pr", NodeKind.PULL_REQUEST, "merged PR", {"merged": True})
        requirement = next(node for node in graph.nodes if node.kind == NodeKind.REQUIREMENT)
        context_edges = (
            Edge("readiness-mcp-change-pr", EdgeKind.REFERENCES, change.id, pull_request.id,
                 evidence_ids=(evidence_id,)),
            Edge("readiness-mcp-requirement-test", EdgeKind.VERIFIED_BY, requirement.id, test_case.id,
                 evidence_ids=(evidence_id,)),
        )
        graph = GraphSnapshot(
            nodes=(*graph.nodes, pull_request, test_case, test_run),
            edges=(*graph.edges, *context_edges),
            evidence=graph.evidence, provenance=graph.provenance, allow_legacy_evidence=True,
        )
        register_query_tools(server, graph_store_path=".",
                             query_factory=lambda _: EngineeringKgQuery.from_snapshot(graph))
        checked = [
            {
                "source_type": item.source_artifact_identity.source_type,
                "source_identity": item.source_artifact_identity.source_identity,
                "artifact_type": item.source_artifact_identity.artifact_type,
                "stable_locator": item.source_artifact_identity.stable_locator,
                "revision_or_version": item.source_artifact_identity.revision_or_version,
                "checked_at": "2026-10-01T00:00:00+00:00",
            }
            for item in graph.provenance if item.source_artifact_identity is not None
        ]
        self.assertTrue(any(
            item["status"] == "fresh"
            for record in EngineeringKgQuery.from_snapshot(graph).list_requirements(checked_revisions=checked)
            for item in record["evidence_freshness"]
        ))
        local_query = EngineeringKgQuery.from_snapshot(graph)
        self.assertTrue(any(item["edge_id"] == context_edges[0].id
                            for item in local_query.get_traceability(change.id)["relationships"]))
        self.assertTrue(any(item["edge_id"] == context_edges[1].id
                            for item in local_query.get_traceability(requirement.id)["relationships"]))
        self.assertTrue(all(
            item["evidence_use"]["disposition"] == "supported"
            for subject_id, edge_id in ((change.id, context_edges[0].id),
                                        (requirement.id, context_edges[1].id))
            for item in local_query.get_traceability(subject_id)["relationships"]
            if item["edge_id"] == edge_id
        ))

        result = server.tools["explain_critical_conclusion"](
            "change_readiness", change.id, checked_revisions=checked)

        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["disposition"], "unresolved")
        self.assertEqual(result["result"]["reason_codes"], ["unknown"])
        self.assertEqual(result["result"]["path"], {
            "edge_ids": [], "evidence_ids": [], "node_ids": [], "provenance_ids": [],
        })
        self.assertNotIn("ready", result["result"])
        self.assertNotIn("not-ready", result["result"])

    def test_default_traceability_tool_rejects_multiple_owners(self) -> None:
        _, _, _, graph = _graph()
        subject = Node("mcp-cardinality-subject", NodeKind.REPOSITORY, "repo")
        first = Node("mcp-cardinality-owner-one", NodeKind.WORKSPACE, "one")
        second = Node("mcp-cardinality-owner-two", NodeKind.WORKSPACE, "two")
        edges = (
            Edge("mcp-cardinality-edge-one", EdgeKind.OWNED_BY, subject.id, first.id,
                 evidence_ids=(graph.evidence[0].id,)),
            Edge("mcp-cardinality-edge-two", EdgeKind.OWNED_BY, subject.id, second.id,
                 evidence_ids=(graph.evidence[0].id,)),
        )
        snapshot = GraphSnapshot(nodes=(*graph.nodes, subject, first, second),
                                 edges=(*graph.edges, *edges), evidence=graph.evidence,
                                 provenance=graph.provenance, allow_legacy_evidence=True)
        server = _Server()
        register_query_tools(server, graph_store_path=".",
                             query_factory=lambda _: EngineeringKgQuery.from_snapshot(snapshot))
        result = server.tools["get_traceability"](subject.id)
        ownership = [item for item in result["result"]["relationships"] if item["kind"] == "owned_by"]
        self.assertEqual({item["edge_id"] for item in ownership}, {edge.id for edge in edges})
        self.assertTrue(all(item["evidence_use"]["disposition"] == "unresolved" for item in ownership))
        self.assertTrue(all("conflicting" in item["evidence_use"]["reason_codes"] for item in ownership))

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
