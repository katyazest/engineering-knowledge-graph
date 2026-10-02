from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from engineering_kg.freshness import (CheckedSourceRevision, FreshnessAssessor,
    FreshnessInputError, current_evidence_eligibility, normalize_checked_revisions)
from engineering_kg.ontology import Edge, EdgeKind, Evidence, GraphSnapshot, Node, NodeKind, ProvenanceRecord, SourceArtifactIdentity
from engineering_kg.query import EngineeringKgQuery, GraphQueryInputError
from engineering_kg.persistence import initialize_ladybugdb_store
from engineering_kg.relationship_vocabulary import CATALOG_REVISION
from engineering_kg.snapshot_codec import CURRENT_SCHEMA_VERSION, deserialize_snapshot, serialize_snapshot
from tests.test_local_ekg_query_api import _cross_graph_fixture, _graph


def record(revision="r1", *, when="2020-01-01T00:00:00+00:00", extractor="1", digest="a"):
    identity = SourceArtifactIdentity("git", "repo", "commit", revision, "src/a.py")
    return ProvenanceRecord("external", when, "sha256", digest * 64, "extractor", extractor, identity)


def check(revision="r1", *, locator="src/a.py", at="2020-01-02T00:00:00+00:00"):
    return {"source_type": "git", "source_identity": "repo", "artifact_type": "commit",
            "stable_locator": locator, "revision_or_version": revision, "checked_at": at}


class EvidenceFreshnessTest(unittest.TestCase):
    def test_checked_input_complete_safe_duplicate_and_deterministic(self):
        entry = check()
        normalized = normalize_checked_revisions([entry, dict(entry)])
        self.assertEqual(len(normalized), 1)
        self.assertEqual(CheckedSourceRevision(**entry).as_dict(), entry)
        for invalid in (dict(entry, revision_or_version=""), dict(entry, stable_locator="https://secret"),
                        dict(entry, checked_at="2020-01-02T00:00:00")):
            with self.assertRaises(FreshnessInputError):
                normalize_checked_revisions([invalid])
        with self.assertRaises(FreshnessInputError):
            normalize_checked_revisions([entry, dict(entry, revision_or_version="r2")])

    def test_external_matching_mismatch_unrelated_unavailable_and_predating(self):
        item = record()
        def assess(entries):
            return FreshnessAssessor({item.id: item}, normalize_checked_revisions(entries)).assess(item.id)
        matching = assess([check()])
        self.assertEqual((matching.status, matching.reason), ("fresh", "revision-match"))
        self.assertEqual(assess([check("r2")]).status, "stale")
        unrelated = assess([check(locator="src/b.py")])
        self.assertEqual((unrelated.status, unrelated.reason), ("unknown", "no-check"))
        self.assertEqual(assess([]).status, "unknown")
        self.assertEqual(assess([check(at="2019-12-31T23:00:00+00:00")]).reason, "check-predates-observation")

    def test_old_observation_and_changed_metadata_do_not_infer_status(self):
        item = record(when="2000-01-01T00:00:00+00:00", extractor="new", digest="b")
        result = FreshnessAssessor({item.id: item}, {}).assess(item.id)
        self.assertEqual((result.status, result.reason), ("unknown", "no-check"))

    def test_derived_chain_aggregates_without_timestamp_guess_and_keeps_independent_support(self):
        stale = record("r1", digest="c")
        fresh_identity = SourceArtifactIdentity("git", "repo", "commit", "r2", "src/b.py")
        fresh = ProvenanceRecord("external", "2020-01-01T00:00:00+00:00", "sha256", "b" * 64,
                                 "extractor", "2", fresh_identity)
        derived = ProvenanceRecord("derived", "2020-01-03T00:00:00+00:00", "sha256", "d" * 64,
                                   "derive", "1", None, "rule", (stale.id, fresh.id))
        evidence = Evidence("e", "fixture", "ref", provenance_ids=(derived.id, fresh.id))
        graph = {item.id: item for item in (stale, fresh, derived)}
        checks = normalize_checked_revisions([check("r2"), check("r2", locator="src/b.py")])
        assessment = FreshnessAssessor(graph, checks)
        self.assertEqual(assessment.assess(derived.id).status, "stale")
        all_fresh = ProvenanceRecord("derived", "2020-01-03T00:00:00+00:00", "sha256", "f" * 64,
                                     "derive", "1", None, "rule", (fresh.id,))
        all_fresh_assessment = FreshnessAssessor({**graph, all_fresh.id: all_fresh}, checks)
        self.assertEqual(all_fresh_assessment.assess(all_fresh.id).status, "fresh")
        independent = assessment.evidence(evidence)
        self.assertEqual(independent["status"], "fresh")
        self.assertEqual([item["status"] for item in independent["provenance"]], ["stale", "fresh"])
        self.assertTrue(assessment.evidence(evidence)["current_evidence_eligible"])
        unknown_derived = ProvenanceRecord("derived", "2020-01-10T00:00:00+00:00", "sha256", "e" * 64,
                                           "derive", "1", None, "rule", (fresh.id,))
        self.assertEqual(FreshnessAssessor({**graph, unknown_derived.id: unknown_derived},
                                           normalize_checked_revisions([])).assess(unknown_derived.id).status, "unknown")

    def test_guard_fails_closed_on_missing_and_unknown_support(self):
        item = record()
        evidence = Evidence("supported", "fixture", "ref", provenance_ids=(item.id,))
        evidence_by_id = {evidence.id: evidence}
        assessor = FreshnessAssessor({item.id: item}, {})
        result = current_evidence_eligibility([evidence.id, "missing"], evidence_by_id, assessor)
        self.assertFalse(result["eligible"])
        self.assertEqual(result["ineligible_evidence_ids"], [evidence.id, "missing"])

    def test_guard_rejects_stale_and_internal_or_unresolved_chains(self):
        stale = record()
        stale_evidence = Evidence("stale", "fixture", "ref", provenance_ids=(stale.id,))
        internal = Evidence("internal", "fixture", "ref")
        decision = current_evidence_eligibility([stale_evidence.id, internal.id],
            {stale_evidence.id: stale_evidence, internal.id: internal},
            FreshnessAssessor({stale.id: stale}, normalize_checked_revisions([check("r2")])) )
        self.assertFalse(decision["eligible"])
        self.assertEqual([item["status"] for item in decision["evidence"]], ["stale", "unknown"])

    def test_joint_guard_accepts_all_fresh_required_evidence(self):
        first = record("r1")
        second_identity = SourceArtifactIdentity("git", "repo", "commit", "r2", "src/b.py")
        second = ProvenanceRecord("external", "2020-01-01T00:00:00+00:00", "sha256", "d" * 64,
                                  "extractor", "1", second_identity)
        first_evidence = Evidence("first", "fixture", "first", provenance_ids=(first.id,))
        second_evidence = Evidence("second", "fixture", "second", provenance_ids=(second.id,))
        checks = normalize_checked_revisions([check("r1"), check("r2", locator="src/b.py")])
        decision = current_evidence_eligibility(
            [first_evidence.id, second_evidence.id],
            {first_evidence.id: first_evidence, second_evidence.id: second_evidence},
            FreshnessAssessor({first.id: first, second.id: second}, checks),
        )
        self.assertTrue(decision["eligible"])
        self.assertEqual(decision["eligible_evidence_ids"], [first_evidence.id, second_evidence.id])

    def test_missing_or_cyclic_provenance_is_unknown_and_never_eligible(self):
        broken = ProvenanceRecord("derived", "2020-01-03T00:00:00+00:00", "sha256", "c" * 64,
                                  "derive", "1", None, "rule", ("provenance:" + "f" * 16,))
        self.assertFalse(FreshnessAssessor({broken.id: broken}, normalize_checked_revisions([check()])).assess(broken.id).valid)
        cyclic = ProvenanceRecord("derived", "2020-01-03T00:00:00+00:00", "sha256", "d" * 64,
                                  "derive", "1", None, "rule", (broken.id,))
        object.__setattr__(cyclic, "input_provenance_ids", (cyclic.id,))
        result = FreshnessAssessor({cyclic.id: cyclic}, normalize_checked_revisions([check()])).assess(cyclic.id)
        self.assertEqual(result.status, "unknown")
        self.assertFalse(result.valid)
        cyclic_evidence = Evidence("cyclic-support", "fixture", "ref", provenance_ids=(cyclic.id,))
        cyclic_decision = current_evidence_eligibility(
            [cyclic_evidence.id], {cyclic_evidence.id: cyclic_evidence},
            FreshnessAssessor({cyclic.id: cyclic}, normalize_checked_revisions([check()]))
        )
        self.assertFalse(cyclic_decision["eligible"])
        broken_evidence = Evidence("broken-support", "fixture", "ref", provenance_ids=(broken.id,))
        broken_decision = current_evidence_eligibility(
            [broken_evidence.id], {broken_evidence.id: broken_evidence},
            FreshnessAssessor({broken.id: broken}, normalize_checked_revisions([check()]))
        )
        self.assertFalse(broken_decision["eligible"])

    def test_query_associations_checked_as_of_and_safe_invalid_error(self):
        item = record()
        evidence = Evidence("evidence", "fixture", "ref", provenance_ids=(item.id,))
        node = Node("requirement", NodeKind.REQUIREMENT, "Requirement", evidence_ids=(evidence.id,))
        graph = GraphSnapshot(nodes=(node,), evidence=(evidence,), provenance=(item,))
        query = EngineeringKgQuery.from_snapshot(graph)
        default = query.list_requirements()[0]["evidence_freshness"][0]
        self.assertEqual(default["status"], "unknown")
        fresh = query.list_requirements(checked_revisions=[check()])[0]["evidence_freshness"][0]
        self.assertTrue(fresh["current_evidence_eligible"])
        self.assertEqual(fresh["provenance"][0]["checked_at"], check()["checked_at"])
        guard = query.get_traceability(node.id, checked_revisions=[check()], current_required_evidence_ids=(evidence.id,))
        self.assertTrue(guard["current_evidence_eligibility"]["eligible"])
        stale_guard = query.get_traceability(
            node.id, checked_revisions=[check("different-revision")],
            current_required_evidence_ids=(evidence.id,),
        )
        self.assertFalse(stale_guard["current_evidence_eligibility"]["eligible"])
        self.assertEqual(stale_guard["current_evidence_eligibility"]["evidence"][0]["status"], "stale")
        with self.assertRaises(GraphQueryInputError):
            query.list_requirements(checked_revisions=[check(), check("r2")])
        with self.assertRaises(GraphQueryInputError) as caught:
            query.list_requirements(checked_revisions=[check(locator="https://secret/token")])
        self.assertNotIn("secret", str(caught.exception))

    def test_query_current_required_relationship_rejects_stale_support(self):
        change, _, _, graph = _graph()
        external = next(item for item in graph.provenance if item.source_artifact_identity is not None)
        identity = external.source_artifact_identity
        stale_check = {
            "source_type": identity.source_type,
            "source_identity": identity.source_identity,
            "artifact_type": identity.artifact_type,
            "stable_locator": identity.stable_locator,
            "revision_or_version": "changed-revision",
            "checked_at": "2026-10-01T00:00:00+00:00",
        }
        trace_edge = next(item for item in graph.edges if item.kind.value == "traces_to")
        result = EngineeringKgQuery.from_snapshot(graph).get_traceability(
            change.id, checked_revisions=[stale_check],
            current_required_evidence_ids=trace_edge.evidence_ids,
        )
        self.assertFalse(result["current_evidence_eligibility"]["eligible"])
        self.assertEqual(
            result["current_evidence_eligibility"]["evidence"][0]["status"], "stale",
        )

    def test_traceability_projects_freshness_per_specific_edge_support(self):
        change, _, _, original = _graph()
        fresh_provenance = record("r1", when="2020-01-01T00:00:00+00:00", digest="a")
        # Keep artifact identity distinct so each represented support has its own check.
        stale_identity = SourceArtifactIdentity("git", "repo", "commit", "r1", "src/b.py")
        stale_provenance = ProvenanceRecord(
            "external", "2020-01-01T00:00:00+00:00", "sha256", "b" * 64,
            "extractor", "1", stale_identity,
        )
        fresh_evidence = Evidence("trace-fresh-support", "fixture", "fresh", provenance_ids=(fresh_provenance.id,))
        stale_evidence = Evidence("trace-stale-support", "fixture", "stale", provenance_ids=(stale_provenance.id,))
        trace = next(edge for edge in original.edges if edge.kind == EdgeKind.TRACES_TO)
        trace = Edge(trace.id, trace.kind, trace.source_id, trace.target_id, trace.properties,
                     evidence_ids=(fresh_evidence.id, stale_evidence.id), confidence=trace.confidence)
        snapshot = GraphSnapshot(
            nodes=original.nodes,
            edges=tuple(trace if edge.id == trace.id else edge for edge in original.edges),
            evidence=(*original.evidence, fresh_evidence, stale_evidence),
            provenance=(*original.provenance, fresh_provenance, stale_provenance),
        )
        checks = [
            check("r1", locator="src/a.py"),
            check("r2", locator="src/b.py"),
        ]
        result = EngineeringKgQuery.from_snapshot(snapshot).get_traceability(
            change.id, checked_revisions=checks,
        )
        relationship = next(item for item in result["relationships"] if item["edge_id"] == trace.id)
        support = next(item for item in result["support_records"] if item["edge_id"] == "assertion")
        self.assertEqual(relationship["evidence_ids"], [fresh_evidence.id, stale_evidence.id])
        self.assertEqual(
            [(item["evidence_id"], item["status"], item["current_evidence_eligible"])
             for item in relationship["evidence_freshness"]],
            [(fresh_evidence.id, "fresh", True), (stale_evidence.id, "stale", False)],
        )
        self.assertEqual(
            [(item["provenance"][0]["reason"], item["provenance"][0]["checked_at"])
             for item in relationship["evidence_freshness"]],
            [("revision-match", checks[0]["checked_at"]), ("revision-mismatch", checks[1]["checked_at"])],
        )
        self.assertEqual(
            [item["evidence_id"] for item in support["evidence_freshness"]],
            support["evidence_ids"],
        )
        self.assertTrue(all("current_evidence_eligible" in item for item in support["evidence_freshness"]))
        self.assertEqual([item["id"] for item in relationship["provenance"]],
                         sorted((fresh_provenance.id, stale_provenance.id)))

    def test_traceability_defaults_each_support_to_unknown_in_original_order(self):
        change, _, _, graph = _graph()
        result = EngineeringKgQuery.from_snapshot(graph).get_traceability(change.id)
        self.assertEqual([item["edge_id"] for item in result["relationships"]], ["trace"])
        self.assertEqual([item["edge_id"] for item in result["support_records"]], ["assertion"])
        trace = next(item for item in result["relationships"] if item["edge_id"] == "trace")
        self.assertTrue({"edge_id", "evidence_ids", "kind", "properties", "source_id", "target_id", "provenance"}
                        .issubset(trace))
        self.assertEqual(trace["evidence_ids"], sorted(trace["evidence_ids"]))
        self.assertEqual([item["evidence_id"] for item in trace["evidence_freshness"]], trace["evidence_ids"])
        self.assertTrue(all(item["status"] == "unknown" for item in trace["evidence_freshness"]))
        self.assertTrue(all(not item["current_evidence_eligible"] for item in trace["evidence_freshness"]))
        assertion = result["support_records"][0]
        self.assertEqual([item["evidence_id"] for item in assertion["evidence_freshness"]], assertion["evidence_ids"])

    def test_freshness_does_not_promote_cross_graph_trust_projection(self):
        subject, graph, external, _ = _cross_graph_fixture()
        identity = external.source_artifact_identity
        checked = {"source_type": identity.source_type, "source_identity": identity.source_identity,
                   "artifact_type": identity.artifact_type, "stable_locator": identity.stable_locator,
                   "revision_or_version": identity.revision_or_version, "checked_at": "2026-01-03T00:00:00+00:00"}
        result = EngineeringKgQuery.from_snapshot(graph).get_traceability(subject.id, checked_revisions=[checked])
        link = result["cross_graph_links"][0]
        self.assertFalse(link["trusted_projection"])
        self.assertEqual(link["observations"][0]["evidence_freshness"][0]["status"], "fresh")

    def test_freshness_is_not_serialized_and_readback_ids_and_bytes_stay_unchanged(self):
        _, _, node, snapshot = _graph()
        evidence = next(item for item in snapshot.evidence if item.id in node.evidence_ids)
        item = next(item for item in snapshot.provenance if item.id in evidence.provenance_ids)
        identity = item.source_artifact_identity
        checked = {"source_type": identity.source_type, "source_identity": identity.source_identity,
                   "artifact_type": identity.artifact_type, "stable_locator": identity.stable_locator,
                   "revision_or_version": identity.revision_or_version, "checked_at": "2026-01-03T00:00:00+00:00"}
        before = serialize_snapshot(snapshot, CATALOG_REVISION)
        with tempfile.TemporaryDirectory() as directory:
            store = initialize_ladybugdb_store(Path(directory) / "store")
            stored = store.write_snapshot(snapshot)
            persisted_bytes = store._graph_file.read_bytes()
            assessed = EngineeringKgQuery.from_store(store.path).list_requirements(checked_revisions=[checked])
            self.assertEqual(store._graph_file.read_bytes(), persisted_bytes)
            self.assertIn(node.id, [item.id for item in stored.nodes])
        after = serialize_snapshot(deserialize_snapshot(before), CATALOG_REVISION)
        self.assertEqual(CURRENT_SCHEMA_VERSION, 1)
        self.assertEqual(before, after)
        self.assertEqual(assessed[0]["id"], node.id)
        self.assertEqual(assessed[0]["evidence_ids"], [evidence.id])
        self.assertEqual(assessed[0]["provenance"][0]["id"], item.id)
        self.assertTrue(assessed[0]["evidence_freshness"])
        self.assertEqual(assessed[0]["evidence_freshness"][0]["status"], "fresh")
        self.assertEqual(assessed, EngineeringKgQuery.from_snapshot(snapshot).list_requirements(checked_revisions=[checked, checked]))


if __name__ == "__main__":
    unittest.main()
