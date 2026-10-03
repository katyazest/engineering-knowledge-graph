from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from engineering_kg.ontology import (
    CodeLocator, CrossGraphLinkClaim, CrossGraphLinkEvidence, CrossGraphLinkLifecycle,
    CrossGraphEvidenceStatus, Evidence, GraphSnapshot, Node, NodeKind, ProvenanceRecord, SourceArtifactIdentity,
    normalized_support_classification,
)
from engineering_kg.persistence import PersistenceIntegrityError, initialize_ladybugdb_store
from engineering_kg.mcp.factmcp_server import register_query_tools
from engineering_kg.query import EngineeringKgQuery, GraphQueryValidationError
from engineering_kg.relationship_vocabulary import CATALOG_REVISION
from engineering_kg.validation import validate_graph_integrity


class CrossGraphLinkEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.subject = Node("story", NodeKind.JIRA_STORY, "story")
        identity = SourceArtifactIdentity("fixture", "cross-graph", "record", "1", "fixtures/cross-graph")
        self.external = ProvenanceRecord("external", "2026-01-02T03:04:05+00:00", "sha256", "a" * 64, "test", "1", identity)
        self.derived = ProvenanceRecord("derived", "2026-01-02T03:04:06+00:00", "sha256", "b" * 64, "test", "1", None, "test-rule", (self.external.id,))
        self.external_evidence = Evidence("external-evidence", "fixture", "fixture", provenance_ids=(self.external.id,))
        self.derived_evidence = Evidence("derived-evidence", "fixture", "fixture", provenance_ids=(self.derived.id,))
        self.claim = CrossGraphLinkClaim(self.subject.id, "implements", CodeLocator("repo", "rev", "a.py", "a.b"))

    def support(self, *, origin="declared", status="authoritative", confidence="explicit", trust="trusted", observation=True):
        evidence = self.external_evidence if status == "authoritative" else self.derived_evidence
        if observation:
            return CrossGraphLinkEvidence(self.claim.id, "manual", f"{origin}-{status}-{trust}", evidence.id, origin, status, confidence, trust)
        return CrossGraphLinkLifecycle(self.claim.id, 1, "trusted", evidence.id, origin, status, confidence, trust)

    def snapshot(self, observations=(), lifecycle=None):
        lifecycle = lifecycle or CrossGraphLinkLifecycle(self.claim.id, 1, "candidate", self.derived_evidence.id, "observed", "derived", "candidate", "untrusted")
        return GraphSnapshot(nodes=(self.subject,), evidence=(self.external_evidence, self.derived_evidence), provenance=(self.external, self.derived), cross_graph_link_claims=(self.claim,), cross_graph_link_evidence=observations, cross_graph_link_lifecycle=(lifecycle,))

    def support_conflict_snapshot(self, evidence_records):
        return GraphSnapshot(
            nodes=(self.subject,),
            evidence=(*evidence_records, self.derived_evidence),
            provenance=(self.external, self.derived),
            cross_graph_link_claims=(self.claim,),
            cross_graph_link_evidence=(self.support(),),
            cross_graph_link_lifecycle=(self.support(observation=False),),
            allow_legacy_evidence=True,
        )

    def test_cross_graph_evidence_use_retains_conflicting_support_reason_in_both_orders(self) -> None:
        conflicting_evidence = Evidence(
            self.external_evidence.id, "conflicting-fixture", self.external_evidence.locator,
            self.external_evidence.properties, self.external_evidence.provenance_ids,
        )
        for evidence_records in (
            (self.external_evidence, conflicting_evidence),
            (conflicting_evidence, self.external_evidence),
        ):
            with self.subTest(first=evidence_records[0].source):
                graph = self.support_conflict_snapshot(evidence_records)
                self.assertEqual(graph.trusted_cross_graph_links, ())
                link = EngineeringKgQuery.from_snapshot(graph).get_traceability(
                    self.subject.id
                )["cross_graph_links"][0]
                self.assertFalse(link["trusted_projection"])
                self.assertEqual(link["evidence_use"]["disposition"], "unresolved")
                self.assertIn("conflicting", link["evidence_use"]["reason_codes"])

    def test_registered_mcp_preserves_cross_graph_conflict_reason_in_both_orders(self) -> None:
        conflicting_evidence = Evidence(
            self.external_evidence.id, "conflicting-fixture", self.external_evidence.locator,
            self.external_evidence.properties, self.external_evidence.provenance_ids,
        )

        class Server:
            def __init__(self):
                self.tools = {}

            def tool(self):
                def register(function):
                    self.tools[function.__name__] = function
                    return function
                return register

        for evidence_records in (
            (self.external_evidence, conflicting_evidence),
            (conflicting_evidence, self.external_evidence),
        ):
            with self.subTest(first=evidence_records[0].source):
                graph = self.support_conflict_snapshot(evidence_records)
                server = Server()
                register_query_tools(
                    server, graph_store_path=".",
                    query_factory=lambda _, graph=graph: EngineeringKgQuery.from_snapshot(graph),
                )
                result = server.tools["get_traceability"](self.subject.id)
                self.assertTrue(result["ok"])
                link = result["result"]["cross_graph_links"][0]
                self.assertFalse(link["trusted_projection"])
                self.assertEqual(link["evidence_use"]["disposition"], "unresolved")
                self.assertIn("conflicting", link["evidence_use"]["reason_codes"])

    def test_candidate_lifecycle_without_observations_is_unknown_locally_and_through_mcp(self) -> None:
        graph = self.snapshot()
        query = EngineeringKgQuery.from_snapshot(graph)

        local = query.get_traceability(self.subject.id)["cross_graph_links"][0]

        self.assertEqual(local["current_lifecycle_disposition"], "candidate")
        self.assertEqual(local["evidence_use"]["disposition"], "unresolved")
        self.assertEqual(local["evidence_use"]["reason_codes"], ["candidate", "unknown"])
        self.assertEqual(local["evidence_use"]["evidence_ids"], [])
        self.assertEqual(local["evidence_use"]["provenance_ids"], [])
        self.assertFalse(local["trusted_projection"])
        self.assertEqual(local["observations"], [])

        class Server:
            def __init__(self):
                self.tools = {}

            def tool(self):
                def register(function):
                    self.tools[function.__name__] = function
                    return function
                return register

        server = Server()
        register_query_tools(
            server, graph_store_path=".",
            query_factory=lambda _, query=query: query,
        )
        result = server.tools["get_traceability"](self.subject.id)

        self.assertTrue(result["ok"])
        forwarded = result["result"]["cross_graph_links"][0]
        self.assertEqual(forwarded["evidence_use"], local["evidence_use"])
        self.assertEqual(forwarded["evidence_use"]["reason_codes"], ["candidate", "unknown"])
        self.assertEqual(forwarded["evidence_use"]["evidence_ids"], [])
        self.assertEqual(forwarded["evidence_use"]["provenance_ids"], [])
        self.assertFalse(forwarded["trusted_projection"])

    def test_classification_is_required_payload_safe_and_part_of_identity(self) -> None:
        with self.assertRaisesRegex(TypeError, "required positional"):
            CrossGraphLinkEvidence(self.claim.id, "manual", "one", self.external_evidence.id)
        for field, value in (
            ("strategy_id", ""),
            ("observation_id", ""),
            ("provenance_evidence_id", ""),
        ):
            with self.subTest(field=field):
                arguments = {
                    "claim_id": self.claim.id,
                    "strategy_id": "manual",
                    "observation_id": "one",
                    "provenance_evidence_id": self.external_evidence.id,
                    "origin": "declared",
                    "status": "authoritative",
                    "confidence": "explicit",
                    "trust_disposition": "trusted",
                }
                arguments[field] = value
                with self.assertRaisesRegex(ValueError, f"{field} must be a non-empty string"):
                    CrossGraphLinkEvidence(**arguments)
        for confidence in ("", " payload", "source body", "https://unsafe"):
            with self.subTest(confidence=confidence):
                with self.assertRaisesRegex(ValueError, "invalid-cross-graph-confidence"):
                    self.support(confidence=confidence)
        for field in ("origin", "status", "trust_disposition"):
            for value in (f"unknown-{field}", "https://payload"):
                with self.subTest(field=field, value=value):
                    arguments = {
                        "claim_id": self.claim.id,
                        "strategy_id": "manual",
                        "observation_id": "one",
                        "provenance_evidence_id": self.external_evidence.id,
                        "origin": "declared",
                        "status": "authoritative",
                        "confidence": "explicit",
                        "trust_disposition": "trusted",
                    }
                    arguments[field] = value
                    with self.assertRaisesRegex(ValueError, "invalid-cross-graph-classification"):
                        CrossGraphLinkEvidence(**arguments)
        declared = self.support(origin="declared")
        observed = self.support(origin="observed", trust="untrusted")
        self.assertNotEqual(declared.id, observed.id)
        self.assertEqual(self.claim.id, CrossGraphLinkClaim(self.subject.id, "implements", self.claim.target).id)

    def test_payload_bearing_observation_identifiers_are_rejected_before_boundaries(self) -> None:
        for field, value in (
            ("strategy_id", "provider payload"),
            ("strategy_id", "https://provider.example/strategy"),
            ("observation_id", "token:secret"),
            ("observation_id", "custom:/provider.example/observation"),
        ):
            with self.subTest(field=field, value=value):
                arguments = {
                    "claim_id": self.claim.id,
                    "strategy_id": "manual",
                    "observation_id": "observation-1",
                    "provenance_evidence_id": self.external_evidence.id,
                    "origin": "declared",
                    "status": "authoritative",
                    "confidence": "explicit",
                    "trust_disposition": "trusted",
                }
                arguments[field] = value
                with self.assertRaisesRegex(
                    ValueError, f"invalid-cross-graph-opaque-identifier: {field}"
                ):
                    CrossGraphLinkEvidence(**arguments)

        bypassed = self.support()
        object.__setattr__(bypassed, "observation_id", "https://provider.example/payload")
        with self.assertRaisesRegex(ValueError, "invalid-cross-graph-opaque-identifier"):
            bypassed.as_dict()
        with self.assertRaisesRegex(ValueError, "invalid-cross-graph-opaque-identifier"):
            self.snapshot((bypassed,))

        graph = self.snapshot((self.support(),), self.support(observation=False))
        object.__setattr__(graph.cross_graph_link_evidence[0], "strategy_id", "provider payload")
        with self.assertRaisesRegex(ValueError, "invalid-cross-graph-opaque-identifier"):
            EngineeringKgQuery.from_snapshot(graph).get_traceability(self.subject.id)
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "store")
            record = self.support().as_dict()
            record["strategy_id"] = "https://provider.example/payload"
            store._write_raw({
                "catalog_revision": CATALOG_REVISION,
                "nodes": {}, "node_order": [], "edges": {}, "edge_order": [],
                "evidence": {}, "evidence_order": [], "provenance": {}, "provenance_order": [],
                "cross_graph_link_claims": {}, "cross_graph_link_claim_order": [],
                "cross_graph_link_evidence": {record["id"]: record},
                "cross_graph_link_evidence_order": [record["id"]],
                "cross_graph_link_lifecycle": {}, "cross_graph_link_lifecycle_order": [],
            })
            with self.assertRaisesRegex(
                PersistenceIntegrityError, "invalid-cross-graph-opaque-identifier: strategy_id"
            ):
                store.read_snapshot()

    def test_opaque_uri_identifiers_persist_and_are_queryable_as_identifiers(self) -> None:
        observation = CrossGraphLinkEvidence(
            self.claim.id, "urn:ekg:strategy-42", "urn:example.org/observation-42",
            self.external_evidence.id, "declared", "authoritative", "explicit", "trusted",
        )
        graph = self.snapshot((observation,), self.support(observation=False))
        with tempfile.TemporaryDirectory() as tmp:
            readback = initialize_ladybugdb_store(Path(tmp) / "store").write_snapshot(graph)
        result = EngineeringKgQuery.from_snapshot(readback).get_traceability(self.subject.id)
        returned = result["cross_graph_links"][0]["observations"][0]
        self.assertEqual(returned["strategy_id"], "urn:ekg:strategy-42")
        self.assertEqual(returned["observation_id"], "urn:example.org/observation-42")

    def test_declared_authoritative_support_with_explicit_trusted_lifecycle_projects(self) -> None:
        graph = self.snapshot((self.support(),), self.support(observation=False))
        self.assertEqual(validate_graph_integrity(graph).status, "valid")
        self.assertEqual([item.claim_id for item in graph.trusted_cross_graph_links], [self.claim.id])

    def test_trusted_cross_graph_projection_is_supported_with_resolvable_path(self) -> None:
        graph = self.snapshot((self.support(),), self.support(observation=False))
        self.assertEqual(validate_graph_integrity(graph).status, "valid")
        self.assertTrue(graph.trusted_cross_graph_links)

        link = EngineeringKgQuery.from_snapshot(graph).get_traceability(self.subject.id)["cross_graph_links"][0]

        self.assertEqual(link["evidence_use"]["disposition"], "supported")
        self.assertEqual(link["evidence_use"]["reason_codes"], [])
        self.assertEqual(link["evidence_use"]["claim_id"], self.claim.id)
        self.assertEqual(link["evidence_use"]["evidence_ids"], [self.external_evidence.id])
        self.assertEqual(link["evidence_use"]["provenance_ids"], [self.external.id])

    def test_cross_graph_claim_and_link_attach_evidence_use(self) -> None:
        graph = self.snapshot((self.support(),), self.support(observation=False))

        link = EngineeringKgQuery.from_snapshot(graph).get_traceability(self.subject.id)["cross_graph_links"][0]

        self.assertIn("evidence_use", link)
        self.assertIn("evidence_use", link["claim"])
        self.assertEqual(link["claim"]["evidence_use"], link["evidence_use"])
        self.assertEqual(link["claim"]["id"], self.claim.id)

    def test_trusted_projection_is_blocked_by_generic_canonical_conflict(self) -> None:
        conflicting_subject = Node(self.subject.id, NodeKind.JIRA_STORY, "conflicting subject")
        graph = GraphSnapshot(
            nodes=(self.subject, conflicting_subject),
            evidence=(self.external_evidence, self.derived_evidence),
            provenance=(self.external, self.derived),
            cross_graph_link_claims=(self.claim,),
            cross_graph_link_evidence=(self.support(),),
            cross_graph_link_lifecycle=(self.support(observation=False),),
        )

        self.assertEqual(graph.trusted_cross_graph_links, ())
        result = validate_graph_integrity(graph)
        self.assertEqual(result.status, "invalid")
        self.assertIn(
            "duplicate-identity-conflict",
            [item.rule_id for item in result.metadata.diagnostics],
        )

    def test_same_lifecycle_revision_conflict_is_not_resolved_by_state_order(self) -> None:
        candidate = CrossGraphLinkLifecycle(
            self.claim.id, 1, "candidate", self.external_evidence.id,
            "declared", "authoritative", "explicit", "trusted",
        )
        trusted = CrossGraphLinkLifecycle(
            self.claim.id, 1, "trusted", self.external_evidence.id,
            "declared", "authoritative", "explicit", "trusted",
        )
        for first, second in ((candidate, trusted), (trusted, candidate)):
            with self.subTest(first=first.state, second=second.state):
                with self.assertRaisesRegex(ValueError, "Conflicting graph record values"):
                    GraphSnapshot(cross_graph_link_lifecycle=(first,)).merged_with(
                        GraphSnapshot(cross_graph_link_lifecycle=(second,))
                    )

    def test_observed_and_inferred_implementation_never_project(self) -> None:
        lifecycle = self.support(origin="observed", trust="trusted", observation=False)
        observed = self.snapshot((self.support(origin="observed", trust="untrusted"),), lifecycle)
        inferred = self.snapshot((self.support(origin="inferred", status="derived", trust="untrusted"),), CrossGraphLinkLifecycle(self.claim.id, 1, "trusted", self.derived_evidence.id, "inferred", "derived", "llm", "trusted"))
        for graph in (observed, inferred):
            with self.subTest(graph=graph.as_json()):
                self.assertEqual(graph.trusted_cross_graph_links, ())
                self.assertIn("cross-graph-implementation-trust", [item.rule_id for item in validate_graph_integrity(graph).metadata.diagnostics])

    def test_declared_observation_with_observed_lifecycle_support_never_projects(self) -> None:
        declared_observation = self.support()
        observed_candidate = CrossGraphLinkLifecycle(
            self.claim.id, 1, "candidate", self.external_evidence.id,
            "observed", "authoritative", "pr-file", "untrusted",
        )
        declared_trusted = CrossGraphLinkLifecycle(
            self.claim.id, 2, "trusted", self.external_evidence.id,
            "declared", "authoritative", "explicit", "trusted",
        )
        graph = GraphSnapshot(
            nodes=(self.subject,),
            evidence=(self.external_evidence, self.derived_evidence),
            provenance=(self.external, self.derived),
            cross_graph_link_claims=(self.claim,),
            cross_graph_link_evidence=(declared_observation,),
            cross_graph_link_lifecycle=(observed_candidate, declared_trusted),
        )

        self.assertEqual(graph.trusted_cross_graph_links, ())
        self.assertIn(
            "cross-graph-implementation-trust",
            [item.rule_id for item in validate_graph_integrity(graph).metadata.diagnostics],
        )

    def test_declared_observation_with_inferred_lifecycle_support_never_projects_or_persists(self) -> None:
        inferred_candidate = CrossGraphLinkLifecycle(
            self.claim.id, 1, "candidate", self.derived_evidence.id,
            "inferred", "derived", "llm", "untrusted",
        )
        declared_trusted = CrossGraphLinkLifecycle(
            self.claim.id, 2, "trusted", self.external_evidence.id,
            "declared", "authoritative", "explicit", "trusted",
        )
        graph = GraphSnapshot(
            nodes=(self.subject,),
            evidence=(self.external_evidence, self.derived_evidence),
            provenance=(self.external, self.derived),
            cross_graph_link_claims=(self.claim,),
            cross_graph_link_evidence=(self.support(),),
            cross_graph_link_lifecycle=(inferred_candidate, declared_trusted),
        )

        self.assertEqual(graph.trusted_cross_graph_links, ())
        self.assertIn(
            "cross-graph-implementation-trust",
            [item.rule_id for item in validate_graph_integrity(graph).metadata.diagnostics],
        )
        with self.assertRaises(GraphQueryValidationError):
            EngineeringKgQuery.from_snapshot(graph).get_traceability(
                self.subject.id, require_validation=True,
            )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(PersistenceIntegrityError, "authoritative declared support"):
                initialize_ladybugdb_store(Path(tmp) / "store").write_snapshot(graph)

    def test_declared_support_with_observed_observation_never_projects_or_persists(self) -> None:
        observed_pr_file = CrossGraphLinkEvidence(
            self.claim.id, "merged-pr-changed-symbol", "merged-pr-file",
            self.external_evidence.id, "observed", "authoritative", "pr-file", "untrusted",
        )
        graph = self.snapshot(
            (self.support(), observed_pr_file), self.support(observation=False),
        )

        self.assertEqual(graph.trusted_cross_graph_links, ())
        self.assertIn(
            "cross-graph-implementation-trust",
            [item.rule_id for item in validate_graph_integrity(graph).metadata.diagnostics],
        )
        with self.assertRaises(GraphQueryValidationError):
            EngineeringKgQuery.from_snapshot(graph).get_traceability(
                self.subject.id, require_validation=True,
            )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(PersistenceIntegrityError, "authoritative declared support"):
                initialize_ladybugdb_store(Path(tmp) / "store").write_snapshot(graph)

    def test_declared_support_with_inferred_observation_never_projects(self) -> None:
        inferred_llm = CrossGraphLinkEvidence(
            self.claim.id, "llm-inference", "inferred-observation",
            self.derived_evidence.id, "inferred", "derived", "llm", "untrusted",
        )
        graph = self.snapshot(
            (self.support(), inferred_llm), self.support(observation=False),
        )

        self.assertEqual(graph.trusted_cross_graph_links, ())
        self.assertIn(
            "cross-graph-implementation-trust",
            [item.rule_id for item in validate_graph_integrity(graph).metadata.diagnostics],
        )

    def test_conflicting_valid_support_is_retained_and_repeated_support_coalesces(self) -> None:
        declared = self.support()
        observed = self.support(origin="observed", trust="untrusted")
        inferred = self.support(origin="inferred", status="derived", trust="untrusted")
        graph = self.snapshot((declared, observed, inferred), self.support(observation=False))
        merged = graph.merged_with(graph)
        self.assertEqual(tuple(item.id for item in merged.cross_graph_link_evidence), tuple(sorted((declared.id, observed.id, inferred.id))))
        self.assertEqual(merged.as_json(), merged.merged_with(merged).as_json())

    def test_provenance_status_and_normalized_source_admission_fail_closed(self) -> None:
        bad_support = CrossGraphLinkEvidence(self.claim.id, "manual", "bad", self.external_evidence.id, "inferred", "derived", "opaque", "untrusted")
        bad = self.snapshot((bad_support,), self.support(observation=False))
        self.assertIn("cross-graph-classification-provenance", [item.rule_id for item in validate_graph_integrity(bad).metadata.diagnostics])
        self.assertEqual(normalized_support_classification("declared-authoritative")[0], "declared")
        with self.assertRaisesRegex(ValueError, "unsupported-cross-graph-source-category"):
            normalized_support_classification("provider-implements")

    def test_derived_provenance_cannot_project_authoritative_support_or_default_query_output(self) -> None:
        invalid_authoritative = CrossGraphLinkEvidence(
            self.claim.id, "manual", "declared-derived", self.derived_evidence.id,
            "declared", "authoritative", "explicit", "trusted",
        )
        graph = self.snapshot((invalid_authoritative,), self.support(observation=False))

        self.assertEqual(graph.trusted_cross_graph_links, ())
        self.assertIn(
            "cross-graph-classification-provenance",
            [item.rule_id for item in validate_graph_integrity(graph).metadata.diagnostics],
        )
        link = EngineeringKgQuery.from_snapshot(graph).get_traceability(self.subject.id)["cross_graph_links"][0]
        self.assertFalse(link["trusted_projection"])

    def test_inferred_authoritative_support_is_rejected_at_admission_and_validation(self) -> None:
        for support_type in (CrossGraphLinkEvidence, CrossGraphLinkLifecycle):
            with self.subTest(support_type=support_type.__name__):
                arguments = (
                    (self.claim.id, "manual", "inferred-authoritative", self.external_evidence.id)
                    if support_type is CrossGraphLinkEvidence
                    else (self.claim.id, 1, "candidate", self.external_evidence.id)
                )
                with self.assertRaisesRegex(ValueError, "invalid-cross-graph-classification-consistency"):
                    support_type(*arguments, "inferred", "authoritative", "opaque", "untrusted")

        bypassed = CrossGraphLinkEvidence(
            self.claim.id, "manual", "bypassed", self.external_evidence.id,
            "inferred", "derived", "opaque", "untrusted",
        )
        graph = self.snapshot((bypassed,), self.support(observation=False))
        object.__setattr__(bypassed, "status", CrossGraphEvidenceStatus.AUTHORITATIVE)
        with self.assertRaisesRegex(ValueError, "invalid-cross-graph-classification-consistency"):
            bypassed.as_dict()
        with self.assertRaisesRegex(ValueError, "invalid-cross-graph-classification-consistency"):
            EngineeringKgQuery.from_snapshot(graph).get_traceability(self.subject.id)
        self.assertIn(
            "cross-graph-classification-valid",
            [item.rule_id for item in validate_graph_integrity(graph).metadata.diagnostics],
        )

    def test_frozen_bypassed_lifecycle_classification_is_rejected_at_all_boundaries(self) -> None:
        lifecycle = self.support(observation=False)
        object.__setattr__(lifecycle, "origin", "unknown-origin")

        with self.assertRaisesRegex(ValueError, "invalid-cross-graph-classification"):
            GraphSnapshot(
                nodes=(self.subject,), evidence=(self.external_evidence, self.derived_evidence),
                provenance=(self.external, self.derived),
                cross_graph_link_claims=(self.claim,),
                cross_graph_link_lifecycle=(lifecycle,),
            )
        with self.assertRaisesRegex(ValueError, "invalid-cross-graph-classification"):
            lifecycle.as_dict()

        graph = self.snapshot((self.support(),), self.support(observation=False))
        object.__setattr__(graph.cross_graph_link_lifecycle[0], "origin", "unknown-origin")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(PersistenceIntegrityError, "invalid-cross-graph-classification"):
                initialize_ladybugdb_store(Path(tmp) / "store").write_snapshot(graph)
        with self.assertRaisesRegex(ValueError, "invalid-cross-graph-classification"):
            EngineeringKgQuery.from_snapshot(graph).get_traceability(self.subject.id)

    def test_persistence_round_trip_and_missing_classification_rejection(self) -> None:
        graph = self.snapshot((self.support(),), self.support(observation=False))
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "store")
            self.assertEqual(store.write_snapshot(graph).as_json(), graph.as_json())
            for field in ("origin", "status", "confidence", "trust_disposition"):
                with self.subTest(field=field):
                    record = self.support().as_dict()
                    record.pop(field)
                    store._write_raw({"catalog_revision": CATALOG_REVISION, "nodes": {}, "node_order": [], "edges": {}, "edge_order": [], "evidence": {}, "evidence_order": [], "provenance": {}, "provenance_order": [], "cross_graph_link_claims": {}, "cross_graph_link_claim_order": [], "cross_graph_link_evidence": {record["id"]: record}, "cross_graph_link_evidence_order": [record["id"]], "cross_graph_link_lifecycle": {}, "cross_graph_link_lifecycle_order": []})
                    with self.assertRaisesRegex(PersistenceIntegrityError, f"cross_graph_link_evidence.{field}"):
                        store.read_snapshot()
            for field in ("origin", "status", "confidence", "trust_disposition"):
                with self.subTest(record_type="lifecycle", field=field):
                    record = self.support(observation=False).as_dict()
                    record.pop(field)
                    store._write_raw({"catalog_revision": CATALOG_REVISION, "nodes": {}, "node_order": [], "edges": {}, "edge_order": [], "evidence": {}, "evidence_order": [], "provenance": {}, "provenance_order": [], "cross_graph_link_claims": {}, "cross_graph_link_claim_order": [], "cross_graph_link_evidence": {}, "cross_graph_link_evidence_order": [], "cross_graph_link_lifecycle": {record["id"]: record}, "cross_graph_link_lifecycle_order": [record["id"]]})
                    with self.assertRaisesRegex(PersistenceIntegrityError, f"cross_graph_link_lifecycle.{field}"):
                        store.read_snapshot()

    def test_invalid_implementation_trust_is_rejected_by_validation_required_query_and_persistence(self) -> None:
        graph = self.snapshot((self.support(origin="observed", trust="untrusted"),), self.support(origin="observed", trust="trusted", observation=False))
        with self.assertRaises(GraphQueryValidationError):
            EngineeringKgQuery.from_snapshot(graph).get_traceability(self.subject.id, require_validation=True)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(PersistenceIntegrityError, "authoritative declared support"):
                initialize_ladybugdb_store(Path(tmp) / "store").write_snapshot(graph)


if __name__ == "__main__":
    unittest.main()
