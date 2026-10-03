from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.ontology import (
    CodeLocator, CrossGraphLinkClaim, CrossGraphLinkEvidence, CrossGraphLinkLifecycle,
    Edge, EdgeKind, Evidence, GraphSnapshot, Node, NodeKind, OpenSpecLocator,
    ProvenanceRecord, SourceArtifactIdentity, openspec_requirement_id, openspec_specification_id, stable_id,
)
from engineering_kg.persistence import initialize_ladybugdb_store
from engineering_kg.query import EngineeringKgQuery


class LocalEkgQueryApiTest(unittest.TestCase):
    def test_default_traceability_marks_conflicting_endpoint_node_unresolved_in_both_orders(self) -> None:
        change, _, _, graph = _graph()
        incompatible_endpoint = Node(change.id, NodeKind.REPOSITORY, "conflicting endpoint")
        for nodes in ((*graph.nodes, incompatible_endpoint), (incompatible_endpoint, *graph.nodes)):
            with self.subTest(first=nodes[0].kind):
                snapshot = GraphSnapshot(
                    nodes=nodes, edges=graph.edges, evidence=graph.evidence,
                    provenance=graph.provenance,
                )
                trace = EngineeringKgQuery.from_snapshot(snapshot).get_traceability(change.id)
                projected = next(
                    item for item in trace["relationships"] if item["edge_id"] == "trace"
                )
                self.assertEqual(projected["evidence_use"]["disposition"], "unresolved")
                self.assertIn("conflicting", projected["evidence_use"]["reason_codes"])

    def test_lists_canonical_requirements_with_openspec_provenance(self) -> None:
        change, specification, requirement, graph = _graph()
        result = EngineeringKgQuery.from_snapshot(graph).list_requirements(change=change.name)
        self.assertEqual(result[0]["kind"], "requirement")
        self.assertEqual(result[0]["id"], requirement.id)
        self.assertEqual(result[0]["locators"][0]["source"], "openspec")
        self.assertNotIn("openspec-requirement", str(result))

    def test_change_result_reports_canonical_assertion_and_traceability(self) -> None:
        change, specification, _, graph = _graph()
        query = EngineeringKgQuery.from_snapshot(graph)
        result = query.list_changes()[0]
        self.assertEqual(result["properties"]["asserted_spec_ids"], [specification.id])
        self.assertEqual(result["properties"]["traceability_spec_ids"], [specification.id])
        trace = next(item for item in query.get_traceability(change.id)["relationships"] if item["edge_id"] == "trace")
        self.assertEqual(trace["provenance"][0]["derivation_rule_id"], "openspec-change-to-durable-spec")
        self.assertEqual(len(trace["provenance"][0]["input_provenance_ids"]), 1)

    def test_traceability_separates_assertion_support_and_excludes_untrusted_edges(self) -> None:
        change, specification, _, graph = _graph()
        invalid = Edge(
            "invalid", EdgeKind.TOUCHES, change.id, specification.id,
            evidence_ids=(graph.evidence[0].id,),
        )
        unprovenanced = Edge(
            "unprovenanced", EdgeKind.REFERENCES, change.id, specification.id,
            evidence_ids=("unprovenanced-evidence",),
        )
        graph = GraphSnapshot(
            nodes=graph.nodes,
            edges=(*graph.edges, invalid, unprovenanced),
            evidence=(*graph.evidence, Evidence("unprovenanced-evidence", "fixture", "fixture")),
            provenance=graph.provenance,
        )

        result = EngineeringKgQuery.from_snapshot(graph).get_traceability(change.id)

        self.assertEqual([item["edge_id"] for item in result["relationships"]], ["trace"])
        self.assertEqual([item["edge_id"] for item in result["support_records"]], ["assertion"])
        self.assertNotIn("assertion", [item["edge_id"] for item in result["relationships"]])

    def test_traceability_excludes_malformed_or_unresolved_derived_provenance(self) -> None:
        change, specification, _, graph = _graph()
        stale_derived = ProvenanceRecord(
            "derived", "2026-01-02T03:04:06+00:00", "sha256", "b" * 64,
            "engineering-kg-derivation", "1", None,
            "openspec-change-to-durable-spec", ("provenance:" + "f" * 16,),
        )
        stale_evidence = Evidence(
            "stale-derived-evidence", "fixture", "derivation",
            provenance_ids=(stale_derived.id,),
        )
        stale_edge = Edge(
            "stale-trace", EdgeKind.TRACES_TO, change.id, specification.id,
            evidence_ids=(stale_evidence.id,),
        )
        malformed_derived = ProvenanceRecord(
            "derived", "2026-01-02T03:04:07+00:00", "sha256", "c" * 64,
            "engineering-kg-derivation", "1", None,
            "openspec-change-to-durable-spec", (graph.provenance[0].id,),
        )
        object.__setattr__(malformed_derived, "content_hash", "not-a-sha256-digest")
        malformed_evidence = Evidence(
            "malformed-derived-evidence", "fixture", "derivation",
            provenance_ids=(malformed_derived.id,),
        )
        malformed_edge = Edge(
            "malformed-trace", EdgeKind.TRACES_TO, change.id, specification.id,
            evidence_ids=(malformed_evidence.id,),
        )
        snapshot = GraphSnapshot(
            nodes=graph.nodes,
            edges=(*graph.edges, stale_edge, malformed_edge),
            evidence=(*graph.evidence, stale_evidence, malformed_evidence),
            provenance=(*graph.provenance, stale_derived, malformed_derived),
            allow_legacy_evidence=True,
        )

        result = EngineeringKgQuery.from_snapshot(snapshot).get_traceability(change.id)

        self.assertEqual([item["edge_id"] for item in result["relationships"]], ["trace"])

    def test_list_dtos_filter_untrusted_semantic_relationships(self) -> None:
        change, specification, _, graph = _graph()
        repository = Node("repository", NodeKind.REPOSITORY, "payments")
        service = Node("service", NodeKind.SERVICE, "payments")
        invalid_trace = Edge(
            "invalid-trace", EdgeKind.TRACES_TO, change.id, specification.id,
            evidence_ids=("missing-evidence",),
        )
        invalid_owner = Edge("invalid-owner", EdgeKind.OWNED_BY, repository.id, service.id)
        snapshot = GraphSnapshot(
            nodes=(*graph.nodes, repository, service),
            edges=(*graph.edges, invalid_trace, invalid_owner),
            evidence=graph.evidence,
            provenance=graph.provenance,
        )
        query = EngineeringKgQuery.from_snapshot(snapshot)

        change_result = query.list_changes()[0]
        service_result = query.list_services()[0]

        self.assertEqual(change_result["properties"]["traceability_spec_ids"], [specification.id])
        self.assertNotIn("repository_ids", service_result["properties"])

    def test_traceability_dangling_evidence_stays_visible_unresolved(self) -> None:
        change, specification, _, graph = _graph()
        invalid_trace = Edge(
            "invalid-trace", EdgeKind.TRACES_TO, change.id, specification.id,
            evidence_ids=("missing-evidence",),
        )
        snapshot = GraphSnapshot(
            nodes=graph.nodes,
            edges=(*graph.edges, invalid_trace),
            evidence=graph.evidence,
            provenance=graph.provenance,
        )

        result = EngineeringKgQuery.from_snapshot(snapshot).get_traceability(change.id)

        relationship = next(
            item for item in result["relationships"] if item["edge_id"] == "invalid-trace"
        )
        self.assertEqual(relationship["evidence_use"]["disposition"], "unresolved")
        self.assertIn("unknown", relationship["evidence_use"]["reason_codes"])
        self.assertEqual(relationship["evidence_use"]["evidence_ids"], [])
        self.assertEqual(relationship["evidence_use"]["provenance_ids"], [])

    def test_filters_canonical_requirements_by_evidence_reference(self) -> None:
        _, _, requirement, graph = _graph()
        result = EngineeringKgQuery.from_snapshot(graph).list_requirements(
            evidence_ref=graph.evidence[1].id
        )
        self.assertEqual([item["id"] for item in result], [requirement.id])

    def test_traceability_projects_persisted_cross_graph_provenance_chain(self) -> None:
        subject, graph, external, derived = _cross_graph_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "store")
            query = EngineeringKgQuery.from_snapshot(store.write_snapshot(graph))
            result = query.get_traceability(subject.id)

        link = result["cross_graph_links"][0]
        self.assertEqual(link["claim"]["subject_id"], subject.id)
        self.assertFalse(link["trusted_projection"])
        self.assertEqual(link["observations"][0]["origin"], "inferred")
        self.assertEqual(link["observations"][0]["trust_disposition"], "untrusted")
        self.assertEqual(
            [item["id"] for item in link["observations"][0]["provenance"]],
            [derived.id],
        )
        self.assertEqual(
            link["observations"][0]["provenance"][0]["input_provenance_ids"],
            [external.id],
        )
        self.assertEqual(
            [item["id"] for item in link["lifecycle"][0]["provenance"]],
            [external.id],
        )
        self.assertNotIn("authoritative source body", str(result))

    def test_traceability_exposes_latest_cross_graph_lifecycle_disposition(self) -> None:
        subject, graph, _, _ = _cross_graph_fixture()
        claim = graph.cross_graph_link_claims[0]
        lifecycle = (
            CrossGraphLinkLifecycle(
                claim.id, 3, "rejected", graph.evidence[0].id,
                "observed", "authoritative", "final", "untrusted",
            ),
            CrossGraphLinkLifecycle(
                claim.id, 1, "candidate", graph.evidence[0].id,
                "observed", "authoritative", "initial", "untrusted",
            ),
            CrossGraphLinkLifecycle(
                claim.id, 2, "trusted", graph.evidence[0].id,
                "observed", "authoritative", "reviewed", "trusted",
            ),
        )
        snapshot = GraphSnapshot(
            nodes=graph.nodes,
            evidence=graph.evidence,
            provenance=graph.provenance,
            cross_graph_link_claims=graph.cross_graph_link_claims,
            cross_graph_link_evidence=graph.cross_graph_link_evidence,
            cross_graph_link_lifecycle=lifecycle,
        )

        link = EngineeringKgQuery.from_snapshot(snapshot).get_traceability(subject.id)["cross_graph_links"][0]

        self.assertEqual(link["current_lifecycle_disposition"], "rejected")
        self.assertEqual([entry["revision"] for entry in link["lifecycle"]], [1, 2, 3])

    def test_cross_graph_evidence_use_preserves_subject_and_lifecycle_conflicts(self) -> None:
        subject, graph = _trusted_cross_graph_snapshot()
        self.assertTrue(graph.trusted_cross_graph_links)
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
        for conflict_kind, nodes, lifecycle in cohorts:
            for reverse in (False, True):
                ordered_nodes = tuple(reversed(nodes)) if reverse else nodes
                ordered_lifecycle = tuple(reversed(lifecycle)) if reverse else lifecycle
                with self.subTest(conflict=conflict_kind, reversed=reverse):
                    snapshot = GraphSnapshot(
                        nodes=ordered_nodes,
                        evidence=graph.evidence, provenance=graph.provenance,
                        cross_graph_link_claims=graph.cross_graph_link_claims,
                        cross_graph_link_evidence=(observation,),
                        cross_graph_link_lifecycle=ordered_lifecycle,
                    )
                    link = EngineeringKgQuery.from_snapshot(snapshot).get_traceability(subject.id)["cross_graph_links"][0]
                    for projected in (link, link["claim"], link["observations"][0]):
                        self.assertEqual(projected["evidence_use"]["disposition"], "unresolved")
                        self.assertIn("conflicting", projected["evidence_use"]["reason_codes"])
                    self.assertFalse(link["trusted_projection"])


def _graph():
    identity = SourceArtifactIdentity(
        "openspec", "requirements", "openspec-spec", "a" * 40,
        "openspec/specs/payments/spec.md",
    )
    spec_evidence_id = stable_id("evidence", identity.id, "durable:payments")
    requirement_evidence_id = stable_id(
        "evidence", identity.id, "durable:payments:requirement:payment-is-submitted"
    )
    external_provenance = ProvenanceRecord(
        "external", "2026-01-02T03:04:05+00:00", "sha256", "a" * 64,
        "openspec-extractor", "1", identity,
    )
    derived_provenance = ProvenanceRecord(
        "derived", "2026-01-02T03:04:06+00:00", "sha256", "b" * 64,
        "engineering-kg-derivation", "1", None,
        "openspec-change-to-durable-spec", (external_provenance.id,),
    )
    trace_evidence_id = stable_id("evidence", derived_provenance.id)
    specification = Node(openspec_specification_id("requirements", "payments"), NodeKind.SPECIFICATION, "payments", {"repository_id": "requirements", "capability": "payments"}, (spec_evidence_id,))
    requirement = Node(openspec_requirement_id(specification.id, "Payment is submitted"), NodeKind.REQUIREMENT, "Payment is submitted", {"capability": "payments", "specification_id": specification.id, "requirement_key": "payment is submitted"}, (requirement_evidence_id,))
    change = Node("change", NodeKind.OPENSPEC_ACTIVE_CHANGE, "JIRA-1")
    graph = GraphSnapshot(
        (specification, requirement, change),
        (
            Edge("contains", EdgeKind.CONTAINS, specification.id, requirement.id, evidence_ids=(requirement_evidence_id,)),
            Edge("assertion", EdgeKind.ASSERTS, change.id, specification.id, evidence_ids=(spec_evidence_id,)),
            Edge("trace", EdgeKind.TRACES_TO, change.id, specification.id, {"derived": True, "rule_id": "openspec-change-to-durable-spec"}, (trace_evidence_id,)),
        ),
        (
            Evidence(
                spec_evidence_id, "openspec",
                OpenSpecLocator(
                    "openspec/specs/payments/spec.md", "openspec-spec", "durable:payments",
                    source_artifact_identity=identity,
                ), provenance_ids=(external_provenance.id,)
            ),
            Evidence(
                requirement_evidence_id, "openspec",
                OpenSpecLocator(
                    "openspec/specs/payments/spec.md", "openspec-spec",
                    "durable:payments:requirement:payment-is-submitted",
                    source_artifact_identity=identity,
                ), provenance_ids=(external_provenance.id,)
            ),
            Evidence(trace_evidence_id, "fixture", "derivation", provenance_ids=(derived_provenance.id,)),
        ),
        provenance=(external_provenance, derived_provenance),
    )
    return change, specification, requirement, graph


def _cross_graph_fixture():
    subject = Node("cross-graph-requirement", NodeKind.JIRA_STORY, "Cross-graph requirement")
    identity = SourceArtifactIdentity(
        "fixture", "cross-graph", "record", "rev-1", "fixtures/cross-graph.json"
    )
    external = ProvenanceRecord(
        "external", "2026-01-02T03:04:05+00:00", "sha256", "c" * 64,
        "fixture-extractor", "1", identity,
    )
    derived = ProvenanceRecord(
        "derived", "2026-01-02T03:04:06+00:00", "sha256", "d" * 64,
        "fixture-deriver", "1", None, "fixture-cross-graph-rule", (external.id,),
    )
    external_evidence = Evidence(
        stable_id("evidence", identity.id, "external"), "fixture", OpenSpecLocator(
            "fixtures/cross-graph.json", "record", "external", source_artifact_identity=identity,
        ), provenance_ids=(external.id,),
    )
    derived_evidence = Evidence(
        stable_id("evidence", derived.id), "fixture", "derived",
        provenance_ids=(derived.id,),
    )
    claim = CrossGraphLinkClaim(
        subject.id, "implements", CodeLocator("payments", "rev-1", "src/payments.py", "submit")
    )
    graph = GraphSnapshot(
        nodes=(subject,), evidence=(external_evidence, derived_evidence), provenance=(external, derived),
        cross_graph_link_claims=(claim,),
        cross_graph_link_evidence=(
            CrossGraphLinkEvidence(claim.id, "fixture", "derived-observation", derived_evidence.id, "inferred", "derived", "fixture", "untrusted"),
        ),
        cross_graph_link_lifecycle=(
            CrossGraphLinkLifecycle(claim.id, 1, "candidate", external_evidence.id, "observed", "authoritative", "fixture", "untrusted"),
        ),
    )
    return subject, graph, external, derived


def _trusted_cross_graph_snapshot():
    original_subject, graph, _, _ = _cross_graph_fixture()
    subject = Node(original_subject.id, NodeKind.REPOSITORY, original_subject.name)
    claim = CrossGraphLinkClaim(subject.id, "implements", graph.cross_graph_link_claims[0].target)
    observation = CrossGraphLinkEvidence(
        claim.id, "fixture", "declared-observation", graph.evidence[0].id,
        "declared", "authoritative", "fixture", "trusted",
    )
    lifecycle = CrossGraphLinkLifecycle(
        claim.id, 1, "trusted", graph.evidence[0].id,
        "declared", "authoritative", "fixture", "trusted",
    )
    snapshot = GraphSnapshot(
        nodes=(subject,), evidence=graph.evidence, provenance=graph.provenance,
        cross_graph_link_claims=(claim,),
        cross_graph_link_evidence=(observation,),
        cross_graph_link_lifecycle=(lifecycle,),
    )
    return subject, snapshot


if __name__ == "__main__":
    unittest.main()
