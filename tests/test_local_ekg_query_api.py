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
            CrossGraphLinkEvidence(claim.id, "fixture", "derived-observation", derived_evidence.id),
        ),
        cross_graph_link_lifecycle=(
            CrossGraphLinkLifecycle(claim.id, 1, "candidate", external_evidence.id),
        ),
    )
    return subject, graph, external, derived


if __name__ == "__main__":
    unittest.main()
