from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.mcp.factmcp_server import register_query_tools
from engineering_kg.ontology import Edge, EdgeKind, GraphSnapshot, Node, NodeKind, ProvenanceRecord
from engineering_kg.persistence import initialize_ladybugdb_store
from engineering_kg.query import EngineeringKgQuery, GraphQueryInputError, GraphQueryValidationError
from tests.test_local_ekg_query_api import _cross_graph_fixture, _graph


class _Server:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorate(function):
            self.tools[function.__name__] = function
            return function
        return decorate


def _ownership_graph():
    _, _, _, base = _graph()
    repo = Node("repo-exact", NodeKind.REPOSITORY, "similar-service-name")
    owner = Node("owner-team", NodeKind.WORKSPACE, "owner-team")
    edge = Edge("ownership-edge", EdgeKind.OWNED_BY, repo.id, owner.id,
                evidence_ids=(base.evidence[0].id,))
    graph = GraphSnapshot(nodes=(*base.nodes, repo, owner), edges=(*base.edges, edge),
                          evidence=base.evidence, provenance=base.provenance,
                          allow_legacy_evidence=True)
    return repo, owner, graph


class AgentEvidenceUsePolicyTest(unittest.TestCase):
    def test_similar_names_no_authority(self):
        change, _, _, graph = _graph()
        service = Node("similar-service", NodeKind.SERVICE, "Payment is submitted")
        repo = Node("similar-repo", NodeKind.REPOSITORY, "Payment is submitted")
        similar = GraphSnapshot(nodes=(*graph.nodes, service, repo), edges=graph.edges,
                                evidence=graph.evidence, provenance=graph.provenance,
                                allow_legacy_evidence=True)
        query = EngineeringKgQuery.from_snapshot(similar)
        output = query.get_traceability(change.id)
        result = query.explain_critical_conclusion(
            "implementation_ownership", repo.id, service.id)
        self.assertEqual(result["disposition"], "unresolved")
        self.assertEqual(result["reason_codes"], ["unknown"])
        self.assertEqual(result["path"]["edge_ids"], [])
        self.assertFalse(any(item["kind"] == "owned_by" for item in output["relationships"]))

    def test_prompt_guess_no_authority(self):
        subject, graph, _, _ = _cross_graph_fixture()
        before = (graph.edges, graph.nodes)
        result = EngineeringKgQuery.from_snapshot(graph).get_traceability(subject.id)
        observation = result["cross_graph_links"][0]["observations"][0]
        self.assertEqual(observation["origin"], "inferred")
        self.assertEqual(observation["evidence_use"]["disposition"], "unresolved")
        self.assertIn("inferred", observation["evidence_use"]["reason_codes"])
        self.assertEqual((graph.edges, graph.nodes), before)

    def test_missing_support_unknown(self):
        repo, owner, graph = _ownership_graph()
        snapshot = GraphSnapshot(nodes=graph.nodes, edges=graph.edges[:-1],
                                 evidence=graph.evidence, provenance=graph.provenance,
                                 allow_legacy_evidence=True)
        result = EngineeringKgQuery.from_snapshot(snapshot).explain_critical_conclusion(
            "implementation_ownership", repo.id, owner.id)
        self.assertEqual(result["disposition"], "unresolved")
        self.assertIn("unknown", result["reason_codes"])
        self.assertEqual(result["path"]["edge_ids"], [])
        broken = Edge("broken-owner", EdgeKind.OWNED_BY, repo.id, owner.id,
                      evidence_ids=("absent-evidence",))
        invalid = GraphSnapshot(nodes=graph.nodes, edges=(*snapshot.edges, broken),
                                evidence=graph.evidence, provenance=graph.provenance,
                                allow_legacy_evidence=True)
        with self.assertRaises(GraphQueryValidationError):
            EngineeringKgQuery.from_snapshot(invalid).explain_critical_conclusion(
                "implementation_ownership", repo.id, owner.id)

    def test_stale_and_unchecked_current_required(self):
        repo, owner, graph = _ownership_graph()
        query = EngineeringKgQuery.from_snapshot(graph)
        unchecked = query.explain_critical_conclusion("implementation_ownership", repo.id, owner.id,
                                                     current_required=True)
        self.assertEqual(unchecked["reason_codes"], ["unknown"])
        check = [{"source_type": p.source_artifact_identity.source_type,
                  "source_identity": p.source_artifact_identity.source_identity,
                  "artifact_type": p.source_artifact_identity.artifact_type,
                  "stable_locator": p.source_artifact_identity.stable_locator,
                  "revision_or_version": "different-revision", "checked_at": "2026-10-03T00:00:00+00:00"}
                 for p in graph.provenance if p.source_artifact_identity]
        stale = query.explain_critical_conclusion("implementation_ownership", repo.id, owner.id,
                                                  checked_revisions=check, current_required=True)
        self.assertEqual(stale["reason_codes"], ["stale"])
        self.assertEqual(graph.edges[-1].id, "ownership-edge")

    def test_conflict_no_winner(self):
        repo, owner, graph = _ownership_graph()
        conflict = Edge("ownership-edge", EdgeKind.OWNED_BY, repo.id, "different-owner",
                        evidence_ids=graph.edges[-1].evidence_ids)
        snapshot = GraphSnapshot(
            nodes=graph.nodes + (Node("different-owner", NodeKind.WORKSPACE, "another"),),
            edges=graph.edges + (conflict,), evidence=graph.evidence,
            provenance=graph.provenance, allow_legacy_evidence=True,
        )
        result = EngineeringKgQuery.from_snapshot(snapshot)
        traceability = result.get_traceability(repo.id)
        assertions = [item for item in traceability["relationships"]
                      if item["edge_id"] == "ownership-edge"]
        self.assertEqual(len(assertions), 2)
        self.assertTrue(all(item["evidence_use"]["disposition"] == "unresolved"
                            for item in assertions))
        self.assertTrue(all("conflicting" in item["evidence_use"]["reason_codes"]
                            for item in assertions))
        self.assertTrue(all(item["evidence_use"]["evidence_ids"] == list(graph.edges[-1].evidence_ids)
                            for item in assertions))
        with self.assertRaises(GraphQueryValidationError) as error:
            result.explain_critical_conclusion("implementation_ownership", repo.id, owner.id)
        self.assertTrue(any(
            item["affected_object_id"] == "ownership-edge"
            for item in error.exception.validation.as_dict()["metadata"]["diagnostics"]
        ))

    def test_conflicting_evidence_and_provenance_cohorts_never_support_traceability(self):
        repo, _, graph = _ownership_graph()
        original_evidence = graph.evidence[0]
        conflicting_evidence = original_evidence.__class__(
            original_evidence.id, "conflicting-source", original_evidence.locator,
            original_evidence.properties,
            original_evidence.provenance_ids,
        )
        provenance_id = original_evidence.provenance_ids[0]
        original_provenance = next(item for item in graph.provenance if item.id == provenance_id)
        class ConflictingProvenance(ProvenanceRecord):
            @property
            def id(self):
                return provenance_id

            def as_dict(self):
                return super().as_dict() | {"conflicting_record": True}

        conflicting_provenance = ConflictingProvenance(
            kind=original_provenance.kind,
            observed_at=original_provenance.observed_at,
            content_hash_algorithm=original_provenance.content_hash_algorithm,
            content_hash="0" * 64,
            extractor_id=original_provenance.extractor_id,
            extractor_version=original_provenance.extractor_version,
            source_artifact_identity=original_provenance.source_artifact_identity,
            derivation_rule_id=original_provenance.derivation_rule_id,
            input_provenance_ids=original_provenance.input_provenance_ids,
        )
        self.assertEqual(conflicting_provenance.id, provenance_id)
        for records, keyword in (
            ((original_evidence, conflicting_evidence), "evidence"),
            ((original_provenance, conflicting_provenance), "provenance"),
        ):
            for ordered in (records, tuple(reversed(records))):
                snapshot = GraphSnapshot(
                    nodes=graph.nodes, edges=graph.edges,
                    evidence=(tuple(item for item in graph.evidence if item.id != original_evidence.id) + ordered
                              if keyword == "evidence" else graph.evidence),
                    provenance=(tuple(item for item in graph.provenance if item.id != provenance_id) + ordered
                                if keyword == "provenance" else graph.provenance),
                    allow_legacy_evidence=True,
                )
                result = EngineeringKgQuery.from_snapshot(snapshot).get_traceability(repo.id)
                owner = next(item for item in result["relationships"]
                             if item["edge_id"] == "ownership-edge")
                self.assertEqual(owner["evidence_use"]["disposition"], "unresolved")
                self.assertIn("conflicting", owner["evidence_use"]["reason_codes"])

    def test_candidate_not_authoritative(self):
        subject, graph, _, _ = _cross_graph_fixture()
        projection = EngineeringKgQuery.from_snapshot(graph).get_traceability(subject.id)["cross_graph_links"][0]
        self.assertEqual(projection["observations"][0]["evidence_use"]["disposition"], "unresolved")
        self.assertIn("candidate", projection["observations"][0]["evidence_use"]["reason_codes"])

    def test_candidate_touches_not_authoritative(self):
        repo, _, graph = _ownership_graph()
        change = next(node for node in graph.nodes if node.kind == NodeKind.OPENSPEC_ACTIVE_CHANGE)
        touch = Edge("candidate-touch", EdgeKind.TOUCHES, change.id, repo.id,
                     evidence_ids=(graph.evidence[0].id,))
        snapshot = GraphSnapshot(nodes=graph.nodes, edges=(*graph.edges, touch),
                                 evidence=graph.evidence, provenance=graph.provenance,
                                 allow_legacy_evidence=True)

        result = EngineeringKgQuery.from_snapshot(snapshot).get_traceability(change.id)

        projected = next(item for item in result["relationships"] if item["edge_id"] == touch.id)
        self.assertEqual(projected["evidence_use"]["disposition"], "unresolved")
        self.assertEqual(projected["evidence_use"]["reason_codes"], ["candidate"])

    def test_candidate_touches_conflict_retains_both_reasons(self):
        repo, _, graph = _ownership_graph()
        change = next(node for node in graph.nodes if node.kind == NodeKind.OPENSPEC_ACTIVE_CHANGE)
        other_repo = Node("other-repo", NodeKind.REPOSITORY, "other repository")
        candidate = Edge("candidate-conflict-touch", EdgeKind.TOUCHES, change.id, repo.id,
                         evidence_ids=(graph.evidence[0].id,))
        incompatible = Edge("candidate-conflict-touch", EdgeKind.TOUCHES, change.id, other_repo.id,
                            evidence_ids=(graph.evidence[0].id,))
        outputs = []
        for edges in ((candidate, incompatible), (incompatible, candidate)):
            snapshot = GraphSnapshot(
                nodes=(*graph.nodes, other_repo), edges=(*graph.edges, *edges),
                evidence=graph.evidence, provenance=graph.provenance,
                allow_legacy_evidence=True,
            )
            query = EngineeringKgQuery.from_snapshot(snapshot)
            before = (snapshot.nodes, snapshot.edges, snapshot.evidence, snapshot.provenance)
            local = [
                item for item in query.get_traceability(change.id)["relationships"]
                if item["edge_id"] == candidate.id
            ]
            repeated = [
                item for item in query.get_traceability(change.id)["relationships"]
                if item["edge_id"] == candidate.id
            ]
            self.assertEqual(len(local), 2)
            for projected in local + repeated:
                self.assertEqual(projected["evidence_use"]["disposition"], "unresolved")
                self.assertEqual(projected["evidence_use"]["reason_codes"], ["candidate", "conflicting"])
                self.assertEqual(projected["evidence_use"]["edge_id"], candidate.id)
                self.assertEqual(projected["evidence_use"]["evidence_ids"], [graph.evidence[0].id])
                self.assertTrue(projected["evidence_use"]["provenance_ids"])
            self.assertEqual(
                [(item["evidence_use"]["disposition"], item["evidence_use"]["reason_codes"])
                 for item in local],
                [(item["evidence_use"]["disposition"], item["evidence_use"]["reason_codes"])
                 for item in repeated],
            )
            self.assertEqual((snapshot.nodes, snapshot.edges, snapshot.evidence, snapshot.provenance), before)

            server = _Server()
            register_query_tools(
                server, graph_store_path=".",
                query_factory=lambda _, query=query: query,
            )
            mcp = server.tools["get_traceability"](change.id)
            forwarded = [
                item for item in mcp["result"]["relationships"]
                if item["edge_id"] == candidate.id
            ]
            self.assertTrue(mcp["ok"])
            self.assertEqual(
                [(item["evidence_use"]["disposition"], item["evidence_use"]["reason_codes"])
                 for item in forwarded],
                [(item["evidence_use"]["disposition"], item["evidence_use"]["reason_codes"])
                 for item in local],
            )
            outputs.append([(item["evidence_use"]["disposition"], item["evidence_use"]["reason_codes"])
                            for item in local])

            with self.assertRaises(GraphQueryValidationError):
                query.get_traceability(change.id, require_validation=True)
            validating_server = _Server()
            register_query_tools(
                validating_server, graph_store_path=".", require_validation=True,
                query_factory=lambda _, query=query: query,
            )
            rejected = validating_server.tools["get_traceability"](change.id)
            self.assertFalse(rejected["ok"])
            self.assertNotIn("result", rejected)
            self.assertEqual(rejected["error"]["code"], "graph-validation-failed")

        self.assertEqual(outputs[0], outputs[1])

        candidate_only = Edge("candidate-only-touch", EdgeKind.TOUCHES, change.id, repo.id,
                              evidence_ids=(graph.evidence[0].id,))
        candidate_snapshot = GraphSnapshot(
            nodes=graph.nodes, edges=(*graph.edges, candidate_only),
            evidence=graph.evidence, provenance=graph.provenance, allow_legacy_evidence=True,
        )
        candidate_result = next(
            item for item in EngineeringKgQuery.from_snapshot(candidate_snapshot)
            .get_traceability(change.id)["relationships"]
            if item["edge_id"] == candidate_only.id
        )
        self.assertEqual(candidate_result["evidence_use"]["reason_codes"], ["candidate"])

        owner_conflict = Edge("conflict-only-owner", EdgeKind.OWNED_BY, repo.id, "owner-a",
                              evidence_ids=(graph.evidence[0].id,))
        other_owner = Node("owner-b", NodeKind.WORKSPACE, "other owner")
        owner_conflict_variant = Edge("conflict-only-owner", EdgeKind.OWNED_BY, repo.id, other_owner.id,
                                      evidence_ids=(graph.evidence[0].id,))
        owner_snapshot = GraphSnapshot(
            nodes=(*graph.nodes, other_owner), edges=(*graph.edges, owner_conflict, owner_conflict_variant),
            evidence=graph.evidence, provenance=graph.provenance, allow_legacy_evidence=True,
        )
        conflict_result = next(
            item for item in EngineeringKgQuery.from_snapshot(owner_snapshot)
            .get_traceability(repo.id)["relationships"]
            if item["edge_id"] == owner_conflict.id
        )
        self.assertEqual(conflict_result["evidence_use"]["reason_codes"], ["conflicting"])

    def test_conflicted_candidate_touches_missing_support_retains_unknown(self):
        repo, _, graph = _ownership_graph()
        change = next(node for node in graph.nodes if node.kind == NodeKind.OPENSPEC_ACTIVE_CHANGE)
        other_repo = Node("other-repo-missing-support", NodeKind.REPOSITORY, "other repository")
        candidate = Edge("candidate-missing-touch", EdgeKind.TOUCHES, change.id, repo.id)
        incompatible = Edge("candidate-missing-touch", EdgeKind.TOUCHES, change.id, other_repo.id)
        query = EngineeringKgQuery.from_snapshot(GraphSnapshot(
            nodes=(*graph.nodes, other_repo), edges=(*graph.edges, candidate, incompatible),
            evidence=graph.evidence, provenance=graph.provenance, allow_legacy_evidence=True,
        ))
        local = [item for item in query.get_traceability(change.id)["relationships"]
                 if item["edge_id"] == candidate.id]
        self.assertEqual(len(local), 2)
        for item in local:
            self.assertEqual(item["evidence_use"]["disposition"], "unresolved")
            self.assertEqual(item["evidence_use"]["reason_codes"], ["candidate", "conflicting", "unknown"])
            self.assertEqual(item["evidence_use"]["evidence_ids"], [])
            self.assertEqual(item["evidence_use"]["provenance_ids"], [])

        server = _Server()
        register_query_tools(server, graph_store_path=".", query_factory=lambda *_: query)
        forwarded = [item for item in server.tools["get_traceability"](change.id)["result"]["relationships"]
                     if item["edge_id"] == candidate.id]
        self.assertEqual([item["evidence_use"] for item in forwarded],
                         [item["evidence_use"] for item in local])

    def test_cross_graph_inferred_candidate_missing_support_accumulates_unknown(self):
        subject, graph, _, _ = _cross_graph_fixture()
        observation = replace(graph.cross_graph_link_evidence[0], provenance_evidence_id="absent-evidence")
        snapshot = GraphSnapshot(
            nodes=graph.nodes, evidence=graph.evidence, provenance=graph.provenance,
            cross_graph_link_claims=graph.cross_graph_link_claims,
            cross_graph_link_evidence=(observation,),
            cross_graph_link_lifecycle=graph.cross_graph_link_lifecycle,
        )
        result = EngineeringKgQuery.from_snapshot(snapshot).get_traceability(subject.id)["cross_graph_links"][0]
        self.assertEqual(result["evidence_use"]["disposition"], "unresolved")
        self.assertEqual(result["evidence_use"]["reason_codes"], ["candidate", "inferred", "unknown"])
        self.assertEqual(result["evidence_use"]["evidence_ids"], [])
        self.assertEqual(result["observations"][0]["evidence_use"]["reason_codes"],
                         ["candidate", "inferred", "unknown"])
        self.assertEqual(result["observations"][0]["evidence_use"]["evidence_ids"], [])

    def test_inferred_not_authoritative(self):
        subject, graph, _, _ = _cross_graph_fixture()
        item = EngineeringKgQuery.from_snapshot(graph).get_traceability(subject.id)["cross_graph_links"][0]["observations"][0]
        self.assertEqual(item["evidence_use"]["reason_codes"], ["candidate", "inferred"])

    def test_direct_ownership_path(self):
        repo, owner, graph = _ownership_graph()
        original = (graph.nodes, graph.edges, graph.evidence, graph.provenance)
        result = EngineeringKgQuery.from_snapshot(graph).explain_critical_conclusion(
            "implementation_ownership", repo.id, owner.id)
        self.assertEqual(result["disposition"], "supported")
        self.assertEqual(result["path"]["edge_ids"], ["ownership-edge"])
        self.assertEqual(result["path"]["evidence_ids"], [graph.evidence[0].id])
        self.assertTrue(result["path"]["provenance_ids"])
        change = next(node for node in graph.nodes if node.kind == NodeKind.OPENSPEC_ACTIVE_CHANGE)
        extrapolated = EngineeringKgQuery.from_snapshot(graph).explain_critical_conclusion(
            "implementation_ownership", change.id, owner.id)
        self.assertEqual(extrapolated["disposition"], "unresolved")
        self.assertEqual(extrapolated["path"]["edge_ids"], [])
        self.assertEqual((graph.nodes, graph.edges, graph.evidence, graph.provenance), original)

    def test_readiness_without_contract(self):
        change, _, _, graph = _graph()
        from tests.test_verification_ontology import verification_node

        evidence_id = graph.evidence[0].id
        test_case = verification_node(NodeKind.TEST_CASE, "readiness", "case-64", (evidence_id,))
        test_run = verification_node(NodeKind.TEST_RUN, "readiness", "run-64", (evidence_id,))
        pull_request = Node("readiness-pr", NodeKind.PULL_REQUEST, "merged PR", {"merged": True})
        requirement = next(node for node in graph.nodes if node.kind == NodeKind.REQUIREMENT)
        context_edges = (
            Edge("readiness-change-pr", EdgeKind.REFERENCES, change.id, pull_request.id,
                 evidence_ids=(evidence_id,)),
            Edge("readiness-requirement-test", EdgeKind.VERIFIED_BY, requirement.id, test_case.id,
                 evidence_ids=(evidence_id,)),
        )
        adjacent_graph = GraphSnapshot(
            nodes=(*graph.nodes, pull_request, test_case, test_run),
            edges=(*graph.edges, *context_edges), evidence=graph.evidence,
            provenance=graph.provenance, allow_legacy_evidence=True,
        )
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
        query = EngineeringKgQuery.from_snapshot(adjacent_graph)
        self.assertTrue(any(
            item["status"] == "fresh"
            for record in query.list_requirements(checked_revisions=checked)
            for item in record["evidence_freshness"]
        ))
        change_edges = query.get_traceability(change.id)["relationships"]
        requirement_edges = query.get_traceability(requirement.id)["relationships"]
        self.assertTrue(any(item["edge_id"] == "readiness-change-pr" for item in change_edges))
        self.assertTrue(any(item["edge_id"] == "readiness-requirement-test" for item in requirement_edges))
        self.assertTrue(all(
            item["evidence_use"]["disposition"] == "supported"
            for item in change_edges + requirement_edges
            if item["edge_id"] in {"readiness-change-pr", "readiness-requirement-test"}
        ))
        result = query.explain_critical_conclusion(
            "change_readiness", change.id, checked_revisions=checked)
        self.assertEqual((result["disposition"], result["reason_codes"]), ("unresolved", ["unknown"]))
        self.assertEqual(result["path"], {"edge_ids": [], "evidence_ids": [],
                                           "node_ids": [], "provenance_ids": []})
        self.assertNotIn(result["disposition"], {"ready", "not-ready"})
        self.assertNotIn("ready", result)
        self.assertNotIn("not-ready", result)

    def test_default_traceability_rejects_multiple_owners(self):
        repo, owner, graph = _ownership_graph()
        second = Node("second-owner", NodeKind.WORKSPACE, "second")
        edge = Edge("second-ownership-edge", EdgeKind.OWNED_BY, repo.id, second.id,
                    evidence_ids=graph.edges[-1].evidence_ids)
        snapshot = GraphSnapshot(nodes=(*graph.nodes, second), edges=(*graph.edges, edge),
                                 evidence=graph.evidence, provenance=graph.provenance,
                                 allow_legacy_evidence=True)
        result = EngineeringKgQuery.from_snapshot(snapshot).get_traceability(repo.id)
        ownership = [item for item in result["relationships"] if item["kind"] == "owned_by"]
        self.assertEqual({item["edge_id"] for item in ownership}, {"ownership-edge", edge.id})
        self.assertTrue(all(item["evidence_use"]["disposition"] == "unresolved" for item in ownership))
        self.assertTrue(all("conflicting" in item["evidence_use"]["reason_codes"] for item in ownership))

    def test_e2e_missing_evidence(self):
        change, _, _, graph = _graph()
        missing_graph = GraphSnapshot(nodes=graph.nodes,
                                      edges=tuple(edge for edge in graph.edges if edge.id != "trace"),
                                      evidence=graph.evidence, provenance=graph.provenance,
                                      allow_legacy_evidence=True)
        local = EngineeringKgQuery.from_snapshot(missing_graph).get_traceability(change.id)
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "store")
            persisted = store.write_snapshot(missing_graph)
            server = _Server()
            register_query_tools(server, graph_store_path=tmp,
                                 query_factory=lambda _: EngineeringKgQuery.from_snapshot(persisted))
            result = server.tools["get_traceability"](change.id)
        self.assertTrue(result["ok"])
        self.assertEqual(local["relationships"], [])
        self.assertEqual(result["result"]["relationships"], [])
        self.assertEqual(result["result"]["cross_graph_links"], [])
        self.assertNotIn("edge_ids", str(result))

    def test_malformed_input_fails_without_partial_result(self):
        with self.assertRaises(GraphQueryInputError):
            EngineeringKgQuery.from_snapshot(_graph()[3]).explain_critical_conclusion(
                "implementation_ownership", "https://secret")


if __name__ == "__main__":
    unittest.main()
