from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.ontology import (
    CodeLocator,
    CrossGraphLinkClaim,
    CrossGraphLinkEvidence,
    CrossGraphLinkLifecycle,
    GraphSnapshot,
    Evidence,
    Node,
    NodeKind,
)
from engineering_kg.persistence import PersistenceIntegrityError, initialize_ladybugdb_store
from engineering_kg.validation import validate_graph_integrity


class CrossGraphLinkEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.subject = Node("requirement-1", NodeKind.REQUIREMENT, "Requirement")
        self.provenance = Evidence("provenance-1", "fixture", "fixture.md")
        self.target = CodeLocator("payments", "abc123", "src/payments.py", "submit")
        self.claim = CrossGraphLinkClaim(self.subject.id, "implements", self.target)

    def snapshot(self, state: str = "candidate", observations: tuple[CrossGraphLinkEvidence, ...] = ()) -> GraphSnapshot:
        return GraphSnapshot(
            nodes=(self.subject,), evidence=(self.provenance,),
            cross_graph_link_claims=(self.claim,),
            cross_graph_link_evidence=observations,
            cross_graph_link_lifecycle=(CrossGraphLinkLifecycle(self.claim.id, 1, state, self.provenance.id),),
        )

    def test_claim_identity_is_stable_and_requires_complete_locator(self) -> None:
        self.assertEqual(self.claim.id, CrossGraphLinkClaim("requirement-1", "implements", self.target).id)
        for field in ("repository", "revision", "file", "symbol"):
            values = self.target.as_dict()
            values[field] = "other"
            self.assertNotEqual(self.claim.id, CrossGraphLinkClaim("requirement-1", "implements", CodeLocator(**values)).id)
        for field in ("repository", "revision", "file", "symbol"):
            values = self.target.as_dict()
            values[field] = values[field].swapcase()
            self.assertNotEqual(
                self.claim.id,
                CrossGraphLinkClaim(
                    "requirement-1", "implements", CodeLocator(**values)
                ).id,
            )
        with self.assertRaises(ValueError):
            CrossGraphLinkClaim("requirement-1", "implements", CodeLocator("", "rev", "file", "symbol"))
        with self.assertRaises(ValueError):
            CrossGraphLinkEvidence(self.claim.id, "", "observation", self.provenance.id)

    def test_merge_is_idempotent_and_accumulates_attributable_observations(self) -> None:
        first = CrossGraphLinkEvidence(self.claim.id, "manual", "one", self.provenance.id)
        second = CrossGraphLinkEvidence(self.claim.id, "heuristic", "two", self.provenance.id)
        merged = self.snapshot(observations=(first,)).merged_with(self.snapshot(observations=(second,)))
        self.assertEqual(tuple(item.id for item in merged.cross_graph_link_evidence), tuple(sorted((first.id, second.id))))
        self.assertEqual(merged.merged_with(merged).as_json(), merged.as_json())

    def test_merge_rejects_evidence_that_references_an_absent_claim(self) -> None:
        dangling = CrossGraphLinkEvidence("missing-claim", "manual", "one", self.provenance.id)

        with self.assertRaisesRegex(
            ValueError, "Cross-graph evidence references an absent claim: missing-claim"
        ):
            GraphSnapshot(cross_graph_link_evidence=(dangling,)).merged_with(GraphSnapshot())

    def test_merge_rejects_claim_with_an_absent_subject(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "Cross-graph claim subject_id does not reference an existing node: requirement-1",
        ):
            GraphSnapshot(
                cross_graph_link_claims=(self.claim,),
            ).merged_with(GraphSnapshot())

    def test_merge_rejects_records_that_reference_absent_provenance_evidence(self) -> None:
        observation = CrossGraphLinkEvidence(self.claim.id, "manual", "one", "missing-evidence")
        lifecycle = CrossGraphLinkLifecycle(self.claim.id, 1, "candidate", "missing-evidence")

        with self.assertRaisesRegex(
            ValueError,
            "Cross-graph evidence references absent provenance evidence: missing-evidence",
        ):
            GraphSnapshot(
                nodes=(self.subject,),
                cross_graph_link_claims=(self.claim,),
                cross_graph_link_evidence=(observation,),
            ).merged_with(GraphSnapshot())

        with self.assertRaisesRegex(
            ValueError,
            "Cross-graph lifecycle references absent provenance evidence: missing-evidence",
        ):
            GraphSnapshot(
                nodes=(self.subject,),
                cross_graph_link_claims=(self.claim,),
                cross_graph_link_lifecycle=(lifecycle,),
            ).merged_with(GraphSnapshot())

    def test_only_explicit_highest_trusted_lifecycle_is_projected(self) -> None:
        observation = CrossGraphLinkEvidence(self.claim.id, "confidence-0.99", "one", self.provenance.id)
        candidate = self.snapshot(observations=(observation,))
        self.assertEqual(candidate.trusted_cross_graph_links, ())
        trusted = GraphSnapshot(
            nodes=candidate.nodes, evidence=candidate.evidence,
            cross_graph_link_claims=candidate.cross_graph_link_claims,
            cross_graph_link_evidence=candidate.cross_graph_link_evidence,
            cross_graph_link_lifecycle=(
                CrossGraphLinkLifecycle(self.claim.id, 1, "candidate", self.provenance.id),
                CrossGraphLinkLifecycle(self.claim.id, 2, "trusted", self.provenance.id),
            ),
        )
        link = trusted.trusted_cross_graph_links[0]
        self.assertEqual(link.supporting_evidence_ids, (observation.id,))
        self.assertEqual(link.supporting_provenance_evidence_ids, (self.provenance.id,))
        self.assertEqual(self.snapshot("rejected").trusted_cross_graph_links, ())
        self.assertEqual(self.snapshot("superseded").trusted_cross_graph_links, ())

    def test_validation_reports_dangling_records_and_missing_lifecycle(self) -> None:
        dangling = CrossGraphLinkEvidence("missing-claim", "manual", "one", "missing-evidence")
        result = validate_graph_integrity(GraphSnapshot(cross_graph_link_evidence=(dangling,)))
        self.assertEqual(result.status, "invalid")
        self.assertEqual(
            {item.rule_id for item in result.metadata.diagnostics},
            {"cross-graph-claim-exists", "cross-graph-provenance-exists"},
        )
        self.assertEqual(validate_graph_integrity(GraphSnapshot(nodes=(self.subject,), cross_graph_link_claims=(self.claim,))).status, "invalid")

    def test_validation_rejects_unknown_state_and_conflicting_lifecycle_revision(self) -> None:
        unsupported = object.__new__(CrossGraphLinkLifecycle)
        object.__setattr__(unsupported, "claim_id", self.claim.id)
        object.__setattr__(unsupported, "revision", 1)
        object.__setattr__(unsupported, "state", "automatic")
        object.__setattr__(unsupported, "provenance_evidence_id", self.provenance.id)
        conflicting = CrossGraphLinkLifecycle(self.claim.id, 1, "trusted", self.provenance.id)
        result = validate_graph_integrity(GraphSnapshot(
            nodes=(self.subject,), evidence=(self.provenance,), cross_graph_link_claims=(self.claim,),
            cross_graph_link_lifecycle=(unsupported, conflicting),
        ))
        self.assertEqual(result.status, "invalid")
        self.assertTrue({"cross-graph-lifecycle-state", "cross-graph-lifecycle-revision-conflict"}.issubset(
            {item.rule_id for item in result.metadata.diagnostics}
        ))

    def test_persistence_round_trip_legacy_compatibility_and_malformed_rejection(self) -> None:
        observation = CrossGraphLinkEvidence(self.claim.id, "manual", "one", self.provenance.id)
        graph = self.snapshot("trusted", (observation,))
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "store")
            self.assertEqual(store.write_snapshot(graph).as_dict(), graph.as_dict())
            store._write_raw({"nodes": {}, "node_order": [], "edges": {}, "edge_order": [], "evidence": {}, "evidence_order": []})
            legacy = store.read_snapshot()
            self.assertEqual(legacy.cross_graph_link_claims, ())
            malformed = graph.as_dict()["cross_graph_link_evidence"][0]
            store._write_raw({
                "nodes": {self.subject.id: self.subject.as_dict()}, "node_order": [self.subject.id],
                "edges": {}, "edge_order": [], "evidence": {self.provenance.id: self.provenance.as_dict()}, "evidence_order": [self.provenance.id],
                "cross_graph_link_claims": {}, "cross_graph_link_claim_order": [],
                "cross_graph_link_evidence": {observation.id: malformed}, "cross_graph_link_evidence_order": [observation.id],
                "cross_graph_link_lifecycle": {}, "cross_graph_link_lifecycle_order": [],
            })
            with self.assertRaises(PersistenceIntegrityError):
                store.read_snapshot()

    def test_persistence_merges_incremental_observation_with_persisted_claim(self) -> None:
        observation = CrossGraphLinkEvidence(
            self.claim.id, "manual", "one", self.provenance.id
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "store")
            store.write_snapshot(self.snapshot())

            readback = store.write_snapshot(
                GraphSnapshot(
                    evidence=(self.provenance,),
                    cross_graph_link_evidence=(observation,),
                )
            )

        self.assertEqual(readback.cross_graph_link_evidence, (observation,))


if __name__ == "__main__":
    unittest.main()
