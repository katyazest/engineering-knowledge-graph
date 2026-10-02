from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from engineering_kg.ontology import (
    CodeLocator,
    CrossGraphLinkClaim,
    CrossGraphLinkEvidence,
    CrossGraphLinkLifecycle,
    Edge,
    EdgeKind,
    Evidence,
    GraphSnapshot,
    Node,
    NodeKind,
    ProvenanceRecord,
    SourceArtifactIdentity,
    SourceArtifactLocator,
    stable_id,
    verification_node,
    verification_node_id,
)
from engineering_kg.persistence import PersistenceIntegrityError, initialize_ladybugdb_store
from engineering_kg.query import EngineeringKgQuery
from engineering_kg.validation import validate_graph_integrity


class VerificationOntologyTest(unittest.TestCase):
    def test_identity_uses_only_kind_scope_and_opaque_key(self) -> None:
        first = verification_node_id(NodeKind.TEST_CASE, "payments", "case-001")
        second = verification_node_id(NodeKind.TEST_CASE, "payments", "case-001")
        self.assertEqual(first, second)
        self.assertNotEqual(first, verification_node_id(NodeKind.TEST_SUITE, "payments", "case-001"))
        self.assertNotEqual(first, verification_node_id(NodeKind.TEST_CASE, "other", "case-001"))
        self.assertNotEqual(first, verification_node_id(NodeKind.TEST_CASE, "payments", "case-002"))
        self.assertEqual(
            first,
            verification_node_id(NodeKind.TEST_CASE, "payments", "case-001"),
        )
        node = verification_node(NodeKind.TEST_CASE, "payments", "case-001")
        self.assertEqual(node.name, "case-001")
        self.assertEqual(
            node.properties,
            {"test_case_key": "case-001", "verification_scope_id": "payments"},
        )
        for kind, key_name, key in (
            (NodeKind.TEST_CASE, "test_case_key", "case-001"),
            (NodeKind.TEST_SUITE, "test_suite_key", "suite-001"),
            (NodeKind.TEST_RUN, "test_run_key", "run-001"),
            (NodeKind.VERIFICATION_EVIDENCE, "verification_evidence_key", "evidence-001"),
        ):
            with self.subTest(kind=kind):
                identity = verification_node(kind, "payments", key)
                self.assertEqual(identity.id, verification_node_id(kind, "payments", key))
                self.assertEqual(
                    identity.properties,
                    {"verification_scope_id": "payments", key_name: key},
                )

    def test_identity_rejects_display_paths_and_payloads(self) -> None:
        for field, value in (
            ("scope", ""),
            ("scope", "payments suite"),
            ("key", "Checkout succeeds"),
            ("key", "tests/checkout.py"),
            ("key", "provider-payload"),
            ("key", "https://provider.example/test"),
        ):
            with self.subTest(field=field, value=value):
                args = (NodeKind.TEST_CASE, value, "case-001") if field == "scope" else (NodeKind.TEST_CASE, "payments", value)
                with self.assertRaisesRegex(ValueError, "invalid-verification-identity"):
                    verification_node_id(*args)

    def test_explicit_chain_is_catalog_valid_and_missing_links_are_not_inferred(self) -> None:
        graph, claim, support, lifecycle = _verification_graph()
        self.assertEqual(validate_graph_integrity(graph).status, "valid")
        self.assertEqual(
            [edge.kind for edge in graph.edges],
            [EdgeKind.CONTAINS, EdgeKind.VERIFIED_BY, EdgeKind.EXECUTED_IN, EdgeKind.VALIDATES],
        )
        self.assertEqual(graph.trusted_cross_graph_links[0].claim_id, claim.id)
        facts_only = GraphSnapshot(
            nodes=tuple(item for item in graph.nodes if item.kind in {
                NodeKind.TEST_CASE, NodeKind.TEST_RUN, NodeKind.VERIFICATION_EVIDENCE,
            }),
            evidence=graph.evidence,
            provenance=graph.provenance,
        )
        self.assertEqual(facts_only.edges, ())
        self.assertEqual(facts_only.cross_graph_link_evidence, ())
        self.assertEqual(support.verification_evidence_id, graph.nodes[-1].id)
        self.assertEqual(lifecycle.claim_id, claim.id)

    def test_verification_endpoints_are_directed_and_provenanced(self) -> None:
        graph, _, _, _ = _verification_graph()
        suite = next(node for node in graph.nodes if node.kind == NodeKind.TEST_SUITE)
        case = next(node for node in graph.nodes if node.kind == NodeKind.TEST_CASE)
        run = next(node for node in graph.nodes if node.kind == NodeKind.TEST_RUN)
        evidence = graph.evidence[0]
        invalid = (
            Edge("reverse-contains", EdgeKind.CONTAINS, case.id, suite.id, evidence_ids=(evidence.id,)),
            Edge("reverse-execution", EdgeKind.EXECUTED_IN, run.id, case.id, evidence_ids=(evidence.id,)),
            Edge("missing-proof", EdgeKind.VALIDATES, suite.id, case.id, evidence_ids=(evidence.id,)),
            Edge("unprovenanced", EdgeKind.EXECUTED_IN, case.id, run.id),
            Edge("unsupported-implementation", EdgeKind.IMPLEMENTS, case.id, run.id, evidence_ids=(evidence.id,)),
        )
        result = validate_graph_integrity(GraphSnapshot(
            nodes=graph.nodes, edges=invalid, evidence=graph.evidence, provenance=graph.provenance,
        ))
        self.assertEqual(result.status, "invalid")
        self.assertEqual(
            {item.rule_id for item in result.metadata.diagnostics},
            {"relationship-endpoint-contract", "relationship-provenance-complete"},
        )

    def test_missing_verification_evidence_is_rejected_before_graph_emission(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid-verification-provenance"):
            GraphSnapshot(nodes=(verification_node(NodeKind.TEST_RUN, "payments", "run-001"),))
        incomplete = Evidence("incomplete", "fixture", "fixture")
        with self.assertRaisesRegex(ValueError, "invalid-verification-provenance"):
            GraphSnapshot(
                nodes=(verification_node(NodeKind.TEST_RUN, "payments", "run-002", (incomplete.id,)),),
                evidence=(incomplete,),
            )
        external_without_identity = Evidence("external", "verification-provider", "provider-record")
        with self.assertRaisesRegex(ValueError, "invalid-source-artifact-identity"):
            GraphSnapshot(
                nodes=(verification_node(NodeKind.TEST_RUN, "payments", "run-003", (external_without_identity.id,)),),
                evidence=(external_without_identity,),
            )

    def test_same_fact_coalesces_evidence_and_conflicting_identity_is_rejected(self) -> None:
        evidence_one = _source_evidence("case-source-1")
        evidence_two = _source_evidence("case-source-2")
        first = verification_node(NodeKind.TEST_CASE, "payments", "case-001", (evidence_one.id,))
        second = verification_node(NodeKind.TEST_CASE, "payments", "case-001", (evidence_two.id,))
        merged = GraphSnapshot(
            nodes=(first,), evidence=(evidence_one,), provenance=(_provenance(evidence_one),)
        ).merged_with(
            GraphSnapshot(nodes=(second,), evidence=(evidence_two,), provenance=(_provenance(evidence_two),))
        )
        self.assertEqual(merged.nodes[0].evidence_ids, tuple(sorted((evidence_one.id, evidence_two.id))))
        conflicting = Node(first.id, NodeKind.TEST_CASE, "case-001", {"verification_scope_id": "other", "test_case_key": "case-001"}, (evidence_one.id,))
        with self.assertRaises(ValueError):
            GraphSnapshot(nodes=(first,), evidence=(evidence_one,), provenance=(_provenance(evidence_one),)).merged_with(
                GraphSnapshot(nodes=(conflicting,), evidence=(evidence_one,), provenance=(_provenance(evidence_one),))
            )

    def test_verification_support_requires_validated_evidence_and_cannot_implement(self) -> None:
        graph, _, support, _ = _verification_graph()
        self.assertEqual(support.verification_evidence_id, next(
            node.id for node in graph.nodes if node.kind == NodeKind.VERIFICATION_EVIDENCE
        ))
        other_support = CrossGraphLinkEvidence(
            support.claim_id, support.strategy_id, "support-002", support.provenance_evidence_id,
            support.origin, support.status, support.confidence, support.trust_disposition,
            verification_evidence_id="node:another-verification-evidence",
        )
        self.assertNotEqual(support.id, other_support.id)
        self.assertEqual(support.claim_id, CrossGraphLinkClaim(
            "subject", "verified_by", CodeLocator("repo", "rev", "app.py", "submit")
        ).id)
        without_binding = tuple(
            edge for edge in graph.edges if edge.kind != EdgeKind.VALIDATES
        )
        with self.assertRaisesRegex(ValueError, "verification-support-validates-subject"):
            GraphSnapshot(
                nodes=graph.nodes, edges=without_binding, evidence=graph.evidence,
                provenance=graph.provenance, cross_graph_link_claims=graph.cross_graph_link_claims,
                cross_graph_link_evidence=graph.cross_graph_link_evidence,
            )
        claim = CrossGraphLinkClaim("subject", "implements", CodeLocator("repo", "rev", "app.py", "submit"))
        with self.assertRaisesRegex(ValueError, "verification-support-relation-kind"):
            GraphSnapshot(
                nodes=graph.nodes,
                edges=graph.edges,
                evidence=graph.evidence,
                provenance=graph.provenance,
                cross_graph_link_claims=(claim,),
                cross_graph_link_evidence=(CrossGraphLinkEvidence(
                    claim.id, "manual", "verification-support", graph.evidence[-1].id,
                    "declared", "authoritative", "explicit", "trusted",
                    verification_evidence_id=support.verification_evidence_id,
                ),),
            )
        for reference in ("node:missing-verification-evidence", next(
            node.id for node in graph.nodes if node.kind == NodeKind.TEST_CASE
        )):
            with self.subTest(reference=reference), self.assertRaisesRegex(
                ValueError, "verification-support-reference-kind"
            ):
                GraphSnapshot(
                    nodes=graph.nodes,
                    edges=graph.edges,
                    evidence=graph.evidence,
                    provenance=graph.provenance,
                    cross_graph_link_claims=graph.cross_graph_link_claims,
                    cross_graph_link_evidence=(CrossGraphLinkEvidence(
                        support.claim_id, support.strategy_id, f"support-{reference}",
                        support.provenance_evidence_id, support.origin, support.status,
                        support.confidence, support.trust_disposition,
                        verification_evidence_id=reference,
                    ),),
                )
        verification = next(
            node for node in graph.nodes if node.kind == NodeKind.VERIFICATION_EVIDENCE
        )
        test_case = next(node for node in graph.nodes if node.kind == NodeKind.TEST_CASE)
        mismatched_edges = tuple(
            edge for edge in graph.edges if edge.kind != EdgeKind.VALIDATES
        ) + (Edge(
            "mismatched-validation", EdgeKind.VALIDATES, verification.id, test_case.id,
            evidence_ids=(verification.evidence_ids[0],),
        ),)
        with self.assertRaisesRegex(ValueError, "verification-support-validates-subject"):
            GraphSnapshot(
                nodes=graph.nodes,
                edges=mismatched_edges,
                evidence=graph.evidence,
                provenance=graph.provenance,
                cross_graph_link_claims=graph.cross_graph_link_claims,
                cross_graph_link_evidence=(support,),
            )

    def test_verification_support_rejects_invalid_claim_endpoints_at_all_boundaries(self) -> None:
        graph, _, support, _ = _verification_graph()
        verification = next(
            node for node in graph.nodes if node.kind == NodeKind.VERIFICATION_EVIDENCE
        )
        invalid_claim = CrossGraphLinkClaim(
            verification.id, EdgeKind.VERIFIED_BY.value,
            CodeLocator("repo", "rev", "app.py", "submit"),
        )
        invalid_support = CrossGraphLinkEvidence(
            invalid_claim.id, support.strategy_id, "invalid-claim-endpoint",
            support.provenance_evidence_id, support.origin, support.status,
            support.confidence, support.trust_disposition,
            verification_evidence_id=verification.id,
        )
        invalid_binding = Edge(
            "invalid-validates-endpoint", EdgeKind.VALIDATES,
            verification.id, verification.id,
            evidence_ids=(verification.evidence_ids[0],),
        )
        invalid_edges = tuple(
            edge for edge in graph.edges if edge.kind != EdgeKind.VALIDATES
        ) + (invalid_binding,)
        invalid_kwargs = dict(
            nodes=graph.nodes, edges=invalid_edges, evidence=graph.evidence,
            provenance=graph.provenance, cross_graph_link_claims=(invalid_claim,),
            cross_graph_link_evidence=(invalid_support,),
        )

        with self.assertRaisesRegex(ValueError, "verification-support-claim-endpoint-contract"):
            GraphSnapshot(**invalid_kwargs)

        object.__setattr__(graph, "edges", invalid_edges)
        object.__setattr__(graph, "cross_graph_link_claims", (invalid_claim,))
        object.__setattr__(graph, "cross_graph_link_evidence", (invalid_support,))
        for boundary in (
            lambda: graph.as_json(),
            lambda: graph.merged_with(GraphSnapshot()),
            lambda: EngineeringKgQuery.from_snapshot(graph).get_traceability(verification.id),
        ):
            with self.subTest(boundary=boundary), self.assertRaisesRegex(
                ValueError, "verification-support-claim-endpoint-contract"
            ):
                boundary()

    def test_verification_node_evidence_cannot_support_trusted_implementation(self) -> None:
        target = Node("implementation-subject", NodeKind.JIRA_STORY, "implementation-subject")
        test_evidence = _source_evidence("implementation-test-case")
        test_case = verification_node(
            NodeKind.TEST_CASE, "payments", "case-implementation", (test_evidence.id,)
        )
        claim = CrossGraphLinkClaim(
            target.id, "implements", CodeLocator("repo", "rev", "app.py", "submit")
        )
        support = CrossGraphLinkEvidence(
            claim.id, "manual", "test-derived-implementation", test_evidence.id,
            "declared", "authoritative", "explicit", "trusted",
        )
        lifecycle = CrossGraphLinkLifecycle(
            claim.id, 1, "trusted", test_evidence.id,
            "declared", "authoritative", "explicit", "trusted",
        )
        graph = GraphSnapshot(
            nodes=(target, test_case),
            evidence=(test_evidence,),
            provenance=(_provenance(test_evidence),),
            cross_graph_link_claims=(claim,),
            cross_graph_link_evidence=(support,),
            cross_graph_link_lifecycle=(lifecycle,),
        )

        self.assertEqual(validate_graph_integrity(graph).status, "valid")
        self.assertEqual(graph.trusted_cross_graph_links, ())
        result = EngineeringKgQuery.from_snapshot(graph).get_traceability(target.id)
        self.assertFalse(result["cross_graph_links"][0]["trusted_projection"])

    def test_persistence_and_query_round_trip_remain_payload_free(self) -> None:
        graph, claim, _, _ = _verification_graph()
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "store")
            readback = store.write_snapshot(graph)
            self.assertEqual(readback.as_json(), graph.as_json())
            result = EngineeringKgQuery.from_store(Path(tmp) / "store", require_validation=True).get_traceability("subject")
        kinds = {item["kind"] for item in result["relationships"]}
        self.assertEqual(kinds, {"verified_by", "validates"})
        self.assertEqual(result["cross_graph_links"][0]["observations"][0]["verification_evidence_id"], next(
            node.id for node in graph.nodes if node.kind == NodeKind.VERIFICATION_EVIDENCE
        ))
        self.assertFalse(result["cross_graph_links"][0]["claim"]["id"] != claim.id)
        for forbidden in ("framework", "payload", "output", "log", "source_code", "url"):
            self.assertNotIn(forbidden, str(result).lower())
        verification_id = next(
            node.id for node in graph.nodes if node.kind == NodeKind.VERIFICATION_EVIDENCE
        )
        verification_trace = EngineeringKgQuery.from_snapshot(readback).get_traceability(verification_id)
        self.assertEqual(
            [item["kind"] for item in verification_trace["relationships"]],
            [EdgeKind.VALIDATES.value],
        )
        suite_id = next(node.id for node in graph.nodes if node.kind == NodeKind.TEST_SUITE)
        case_id = next(node.id for node in graph.nodes if node.kind == NodeKind.TEST_CASE)
        self.assertEqual(
            [item["edge_id"] for item in EngineeringKgQuery.from_snapshot(readback)
             .get_traceability(suite_id)["relationships"]],
            ["contains-suite-case"],
        )
        self.assertEqual(
            [item["edge_id"] for item in EngineeringKgQuery.from_snapshot(readback)
             .get_traceability(case_id)["relationships"]],
            ["case-executed-run", "contains-suite-case", "subject-verified-by-case"],
        )
        evidence_result = EngineeringKgQuery.from_snapshot(readback).get_traceability(verification_id)
        self.assertEqual(
            [item["claim"]["id"] for item in evidence_result["cross_graph_links"]],
            [claim.id],
        )
        self.assertEqual(
            evidence_result["cross_graph_links"][0]["observations"][0]["verification_evidence_id"],
            verification_id,
        )
        self.assertEqual(
            evidence_result["cross_graph_links"][0]["current_lifecycle_disposition"],
            "trusted",
        )
        self.assertTrue(evidence_result["cross_graph_links"][0]["trusted_projection"])

    def test_empty_snapshot_remains_verification_compatible(self) -> None:
        empty = GraphSnapshot()
        self.assertEqual(empty.nodes, ())
        self.assertEqual(empty.edges, ())
        self.assertEqual(empty.cross_graph_link_evidence, ())
        self.assertEqual(empty.as_json(), GraphSnapshot().as_json())

    def test_revision_three_is_rejected_without_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "store")
            store._write_raw({"catalog_revision": "3"})
            with self.assertRaisesRegex(PersistenceIntegrityError, "unsupported-catalog-revision: unsupported-catalog-revision") as raised:
                store.read_snapshot()
            self.assertNotIn("'3'", str(raised.exception))

    def test_validation_and_readback_report_malformed_verification_records_safely(self) -> None:
        evidence = _source_evidence("malformed-verification")
        node = verification_node(NodeKind.TEST_CASE, "payments", "case-001", (evidence.id,))
        graph = GraphSnapshot(nodes=(node,), evidence=(evidence,), provenance=(_provenance(evidence),))
        object.__setattr__(node, "properties", None)
        result = validate_graph_integrity(graph)
        self.assertEqual(result.status, "invalid")
        self.assertIn("verification-natural-key-identity", {
            item.rule_id for item in result.metadata.diagnostics
        })

        raw_node = verification_node(NodeKind.TEST_CASE, "payments", "case-001").as_dict()
        raw_node["unexpected"] = "provider payload"
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "store")
            store._write_raw({
                "catalog_revision": "4",
                "nodes": {raw_node["id"]: raw_node},
                "node_order": [raw_node["id"]],
            })
            with self.assertRaisesRegex(PersistenceIntegrityError, "invalid-record-shape"):
                store.read_snapshot()

    def test_verification_edge_and_evidence_payloads_are_rejected_before_persistence(self) -> None:
        for record_kind in ("edge", "evidence"):
            with self.subTest(record_kind=record_kind):
                graph, _, _, _ = _verification_graph()
                if record_kind == "edge":
                    edge = next(item for item in graph.edges if item.kind == EdgeKind.VERIFIED_BY)
                    object.__setattr__(edge, "properties", {
                        "framework_metadata": {"raw": "provider test output"},
                    })
                else:
                    evidence = graph.evidence[0]
                    object.__setattr__(evidence, "properties", {
                        "ci_metadata": {"raw": "provider run payload"},
                    })

                validation = validate_graph_integrity(graph)
                self.assertEqual(validation.status, "invalid")
                self.assertIn(
                    "verification-payload-boundary",
                    {item.rule_id for item in validation.metadata.diagnostics},
                )
                with tempfile.TemporaryDirectory() as tmp:
                    store = initialize_ladybugdb_store(Path(tmp) / "store")
                    with self.assertRaisesRegex(PersistenceIntegrityError, "verification-payload-boundary"):
                        store.write_snapshot(graph)
                    self.assertNotIn("provider test output", store._graph_file.read_text(encoding="utf-8"))
                    self.assertNotIn("provider run payload", store._graph_file.read_text(encoding="utf-8"))

    def test_query_projection_sanitizes_nested_provider_and_ci_metadata(self) -> None:
        graph, _, _, _ = _verification_graph()
        edge = next(item for item in graph.edges if item.kind == EdgeKind.VERIFIED_BY)
        object.__setattr__(edge, "properties", {
            "framework_metadata": {"raw": "framework secret output"},
        })
        evidence = graph.evidence[0]
        object.__setattr__(evidence.locator, "navigation_detail", {
            "ci_metadata": {"raw": "ci secret output"},
        })

        result = EngineeringKgQuery.from_snapshot(graph).get_traceability("subject")

        serialized = str(result).lower()
        for forbidden in (
            "framework_metadata", "ci_metadata", "framework secret output",
            "ci secret output", "raw",
        ):
            self.assertNotIn(forbidden, serialized)
        verified = next(
            item for item in result["relationships"] if item["kind"] == EdgeKind.VERIFIED_BY.value
        )
        self.assertEqual(verified["properties"], {})

    def test_query_projection_omits_neutral_verification_edge_properties_by_default(self) -> None:
        graph, _, _, _ = _verification_graph()
        edge = next(item for item in graph.edges if item.kind == EdgeKind.VERIFIED_BY)
        object.__setattr__(edge, "properties", {
            "neutral_metadata": {"sensitive_value": "provider payload"},
        })

        result = EngineeringKgQuery.from_snapshot(graph).get_traceability("subject")

        verified = next(
            item for item in result["relationships"] if item["kind"] == EdgeKind.VERIFIED_BY.value
        )
        self.assertEqual(verified["properties"], {})
        self.assertNotIn("neutral_metadata", str(result))
        self.assertNotIn("provider payload", str(result))


def _provenance(evidence: Evidence) -> ProvenanceRecord:
    identity = evidence.locator.source_artifact_identity
    return ProvenanceRecord(
        "external", "2026-01-02T03:04:05+00:00", "sha256", "a" * 64,
        "verification-extractor", "1", identity,
    )


def _source_evidence(key: str) -> Evidence:
    identity = SourceArtifactIdentity("verification", "payments", "test-record", "rev-1", f"records/{key}")
    provenance = ProvenanceRecord(
        "external", "2026-01-02T03:04:05+00:00", "sha256", "a" * 64,
        "verification-extractor", "1", identity,
    )
    return Evidence(
        stable_id("evidence", identity.id), "verification-provider", SourceArtifactLocator(identity),
        provenance_ids=(provenance.id,),
    )


def _verification_graph() -> tuple[GraphSnapshot, CrossGraphLinkClaim, CrossGraphLinkEvidence, CrossGraphLinkLifecycle]:
    target = Node("subject", NodeKind.JIRA_STORY, "subject")
    test_evidence = _source_evidence("test-case")
    suite_evidence = _source_evidence("test-suite")
    run_evidence = _source_evidence("test-run")
    verification_evidence = _source_evidence("verification-evidence")
    support_evidence = _source_evidence("support")
    evidence = (test_evidence, suite_evidence, run_evidence, verification_evidence, support_evidence)
    provenance = tuple(_provenance(item) for item in evidence)
    test_case = verification_node(NodeKind.TEST_CASE, "payments", "case-001", (test_evidence.id,))
    suite = verification_node(NodeKind.TEST_SUITE, "payments", "suite-001", (suite_evidence.id,))
    test_run = verification_node(NodeKind.TEST_RUN, "payments", "run-001", (run_evidence.id,))
    verification = verification_node(NodeKind.VERIFICATION_EVIDENCE, "payments", "evidence-001", (verification_evidence.id,))
    edge_evidence = verification_evidence.id
    edges = (
        Edge("contains-suite-case", EdgeKind.CONTAINS, suite.id, test_case.id, evidence_ids=(suite_evidence.id,)),
        Edge("subject-verified-by-case", EdgeKind.VERIFIED_BY, target.id, test_case.id, evidence_ids=(test_evidence.id,)),
        Edge("case-executed-run", EdgeKind.EXECUTED_IN, test_case.id, test_run.id, evidence_ids=(run_evidence.id,)),
        Edge("evidence-validates-subject", EdgeKind.VALIDATES, verification.id, target.id, evidence_ids=(edge_evidence,)),
    )
    claim = CrossGraphLinkClaim(target.id, "verified_by", CodeLocator("repo", "rev", "app.py", "submit"))
    support = CrossGraphLinkEvidence(
        claim.id, "manual-verification", "support-001", support_evidence.id,
        "declared", "authoritative", "explicit", "trusted",
        verification_evidence_id=verification.id,
    )
    lifecycle = CrossGraphLinkLifecycle(
        claim.id, 1, "trusted", support_evidence.id,
        "declared", "authoritative", "explicit", "trusted",
    )
    return GraphSnapshot(
        nodes=(target, test_case, suite, test_run, verification), edges=edges,
        evidence=evidence, provenance=provenance,
        cross_graph_link_claims=(claim,), cross_graph_link_evidence=(support,),
        cross_graph_link_lifecycle=(lifecycle,),
    ), claim, support, lifecycle


if __name__ == "__main__":
    unittest.main()
