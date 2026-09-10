from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from engineering_kg.ingest.pr_code_candidates import (
    normalize_pull_request_evidence,
    extract_pr_code_candidates,
)
from engineering_kg.ontology import GraphSnapshot, Node, NodeKind, stable_id
from engineering_kg.ontology import (
    CrossGraphEvidenceOrigin,
    CrossGraphTrustDisposition,
    CrossGraphLinkEvidence,
    PullRequestImplementationEvidence,
    PullRequestDeclaredAssociation,
    SourceArtifactIdentity,
    SourceArtifactLocator,
    Evidence,
    ProvenanceRecord,
    cross_graph_link_evidence_id,
    pull_request_projection_edge,
)
from engineering_kg.persistence import PersistenceIntegrityError, initialize_ladybugdb_store
from engineering_kg.query import EngineeringKgQuery
from engineering_kg.validation import validate_graph_integrity
from engineering_kg.relationship_vocabulary import relationship_error


class PullRequestImplementationEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Node(stable_id("node", NodeKind.REPOSITORY, "payments"), NodeKind.REPOSITORY, "payments")
        self.change = Node("change-1", NodeKind.OPENSPEC_ACTIVE_CHANGE, "add-payments")
        self.raw = {
            "pull_request_id": "bitbucket:pr-42",
            "repository_node_id": self.repository.id,
            "base_revision": "a" * 40,
            "head_revision": "b" * 40,
            "merged": True,
            "observed_at": "2026-09-01T12:00:00+00:00",
            "provenance": {"pr": "complete", "association": "complete", "repository": "complete"},
            "pr_source_reference": "urn:example.org/pr-42",
            "repository_source_reference": "urn:example.org/repository-42",
            "association": {
                "id": "association-42",
                "intended_change_id": self.change.id,
                "source_reference": "urn:example.org/association-42",
                "intended_change_kind": "openspec-active-change",
            },
            "mappings": [{
                "id": "graphify:mapping-42",
                "file": "src/payments.py",
                "symbol": "payments.submit",
                "outcome": "resolved",
                "repository": self.repository.id,
                "revision": "b" * 40,
            }],
        }

    def test_enriched_evidence_projects_scoped_observation_without_trust(self) -> None:
        normalized = normalize_pull_request_evidence(self.raw)
        graph = GraphSnapshot(nodes=(self.repository, self.change))
        result = extract_pr_code_candidates((normalized,), graph)
        merged = graph.merged_with(result.graph)

        self.assertEqual(len(merged.pull_request_evidence), 1)
        self.assertEqual(len(merged.pull_request_declared_associations), 1)
        self.assertEqual(len(merged.pull_request_observed_repository_relations), 1)
        self.assertEqual(len(merged.cross_graph_link_claims), 1)
        observation = merged.cross_graph_link_evidence[0]
        self.assertEqual(observation.pull_request_evidence_id, normalized.pull_request.id)
        self.assertEqual(observation.declared_association_id, normalized.association.id)
        self.assertEqual(merged.trusted_cross_graph_links, ())
        self.assertEqual(validate_graph_integrity(merged).status, "valid")
        self.assertNotIn("provider_payload", merged.as_json())

    def test_repeated_complete_evidence_coalesces_pr_relations_and_candidates(self) -> None:
        normalized = normalize_pull_request_evidence(self.raw)
        graph = GraphSnapshot(nodes=(self.repository, self.change))
        result = extract_pr_code_candidates((normalized, normalized), graph)
        merged = graph.merged_with(result.graph)
        self.assertEqual(len(merged.pull_request_evidence), 1)
        self.assertEqual(len(merged.pull_request_declared_associations), 1)
        self.assertEqual(len(merged.pull_request_observed_repository_relations), 1)
        self.assertEqual(len(merged.cross_graph_link_claims), 1)
        self.assertEqual(len(merged.cross_graph_link_evidence), 1)

    def test_distinct_associations_for_one_pr_merge_readback_and_query_isolate_candidates(self) -> None:
        second_change = Node("change-2", NodeKind.OPENSPEC_ARCHIVED_CHANGE, "add-refunds")
        first = normalize_pull_request_evidence(self.raw)
        second = normalize_pull_request_evidence({
            **self.raw,
            "association": {
                **self.raw["association"],
                "intended_change_id": second_change.id,
                "source_reference": "urn:example.org/association-43",
                "intended_change_kind": "openspec-archived-change",
            },
            "mappings": [{
                **self.raw["mappings"][0],
                "id": "graphify:mapping-43",
                "file": "src/refunds.py",
                "symbol": "refunds.refund",
            }],
        })
        source = GraphSnapshot(nodes=(self.repository, self.change, second_change))
        result = extract_pr_code_candidates((first, second), source)
        merged = source.merged_with(result.graph)

        self.assertEqual(len(merged.pull_request_evidence), 1)
        self.assertEqual(len(merged.pull_request_declared_associations), 2)
        self.assertEqual(len(merged.cross_graph_link_claims), 2)
        with tempfile.TemporaryDirectory() as temporary:
            readback = initialize_ladybugdb_store(Path(temporary) / "store").write_snapshot(merged)
        query = EngineeringKgQuery.from_snapshot(readback)
        first_result = query.list_pull_request_implementation_evidence(
            intended_change_id=self.change.id,
        )[0]
        second_result = query.list_pull_request_implementation_evidence(
            intended_change_id=second_change.id,
        )[0]
        self.assertEqual(
            [item["target"]["file"] for item in first_result["observed_candidates"]],
            ["src/payments.py"],
        )
        self.assertEqual(
            [item["target"]["file"] for item in second_result["observed_candidates"]],
            ["src/refunds.py"],
        )

    def test_conflicting_duplicate_source_mapping_id_is_not_admitted(self) -> None:
        conflicting = {
            **self.raw["mappings"][0],
            "file": "src/refunds.py",
            "symbol": "refunds.refund",
        }
        retained = {
            **self.raw["mappings"][0],
            "id": "graphify:mapping-43",
            "file": "src/settlements.py",
            "symbol": "settlements.close",
        }
        normalized = normalize_pull_request_evidence({
            **self.raw,
            "mappings": [self.raw["mappings"][0], conflicting, retained],
        })
        result = extract_pr_code_candidates(
            (normalized,), GraphSnapshot(nodes=(self.repository, self.change)),
        )

        self.assertEqual(len(result.graph.cross_graph_link_claims), 1)
        self.assertEqual(
            result.graph.cross_graph_link_claims[0].target.file,
            "src/settlements.py",
        )
        self.assertEqual(
            result.metadata.skipped_reason_counts,
            {"conflicting-source-mapping-identity": 1},
        )
        self.assertNotIn("src/refunds.py", result.graph.as_json())

    def test_round_trip_and_query_separate_declared_and_observed_evidence(self) -> None:
        normalized = normalize_pull_request_evidence(self.raw)
        source = GraphSnapshot(nodes=(self.repository, self.change))
        graph = source.merged_with(extract_pr_code_candidates((normalized,), source).graph)
        with tempfile.TemporaryDirectory() as temporary:
            readback = initialize_ladybugdb_store(Path(temporary) / "store").write_snapshot(graph)
        result = EngineeringKgQuery.from_snapshot(readback).list_pull_request_implementation_evidence()
        self.assertEqual(result[0]["base_revision"], "a" * 40)
        self.assertEqual(result[0]["head_revision"], "b" * 40)
        self.assertEqual(result[0]["declared_associations"][0]["origin"], "declared")
        self.assertEqual(result[0]["observed_repository_relations"][0]["origin"], "observed")
        self.assertEqual(result[0]["observed_candidates"][0]["trust_disposition"], "untrusted")
        self.assertNotIn("url", str(result).lower())

    def test_legacy_pr_candidate_readback_shape_is_rejected(self) -> None:
        normalized = normalize_pull_request_evidence(self.raw)
        source = GraphSnapshot(nodes=(self.repository, self.change))
        graph = source.merged_with(extract_pr_code_candidates((normalized,), source).graph)
        with tempfile.TemporaryDirectory() as temporary:
            store = initialize_ladybugdb_store(Path(temporary) / "store")
            store.write_snapshot(graph)
            raw = store._read_raw()
            observation = graph.cross_graph_link_evidence[0]
            legacy = dict(raw["cross_graph_link_evidence"][observation.id])
            legacy.pop("pull_request_evidence_id")
            legacy.pop("declared_association_id")
            legacy["id"] = cross_graph_link_evidence_id(
                observation.claim_id, observation.strategy_id, observation.observation_id,
                observation.provenance_evidence_id, observation.origin, observation.status,
                observation.confidence, observation.trust_disposition,
            )
            del raw["cross_graph_link_evidence"][observation.id]
            raw["cross_graph_link_evidence"][legacy["id"]] = legacy
            raw["cross_graph_link_evidence_order"] = [legacy["id"]]
            store._write_raw(raw)
            with self.assertRaisesRegex(PersistenceIntegrityError, "legacy-pr-candidate-readback-unsupported"):
                store.read_snapshot()

    def test_legacy_merged_revision_only_adapter_input_is_rejected_by_new_boundary(self) -> None:
        with self.assertRaisesRegex(ValueError, "merged_revision-only"):
            normalize_pull_request_evidence({**self.raw, "head_revision": None, "merged_revision": "b" * 40})

    def test_legacy_candidate_object_is_rejected_before_graph_mutation(self) -> None:
        graph = GraphSnapshot(nodes=(self.repository, self.change))
        legacy = object()
        with self.assertRaisesRegex(ValueError, "legacy merged-revision-only"):
            extract_pr_code_candidates((legacy,), graph)  # type: ignore[arg-type]
        self.assertEqual(graph.pull_request_evidence, ())
        self.assertEqual(graph.cross_graph_link_claims, ())

    def test_unmerged_pr_is_rejected_before_graph_emission(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be merged"):
            normalize_pull_request_evidence({**self.raw, "merged": False})

    def test_pull_request_identity_must_be_source_qualified_at_model_and_adapter(self) -> None:
        with self.assertRaisesRegex(ValueError, "source-qualified"):
            PullRequestImplementationEvidence(
                "pr-42", self.repository.id, "a" * 40, "b" * 40, True,
                "source-evidence", "provenance-evidence",
            )
        with self.assertRaisesRegex(ValueError, "source-qualified"):
            normalize_pull_request_evidence({**self.raw, "pull_request_id": "pr-42"})

    def test_pr_candidate_observation_requires_scope_at_construction_merge_and_validation(self) -> None:
        normalized = normalize_pull_request_evidence(self.raw)
        source = GraphSnapshot(nodes=(self.repository, self.change))
        graph = source.merged_with(extract_pr_code_candidates((normalized,), source).graph)
        observation = graph.cross_graph_link_evidence[0]

        with self.assertRaisesRegex(ValueError, "explicit PR evidence and association"):
            CrossGraphLinkEvidence(
                observation.claim_id, "pr-code-candidate-extraction", observation.observation_id,
                observation.provenance_evidence_id, observation.origin, observation.status,
                observation.confidence, observation.trust_disposition,
            )

        object.__setattr__(observation, "pull_request_evidence_id", None)
        object.__setattr__(observation, "declared_association_id", None)
        with self.assertRaisesRegex(ValueError, "lacks explicit PR scope"):
            GraphSnapshot().merged_with(graph)
        validation = validate_graph_integrity(graph)
        self.assertEqual(validation.status, "invalid")
        self.assertTrue(any(item.rule_id == "pr-observation-scope" for item in validation.metadata.diagnostics))

    def test_pr_relation_provenance_must_bind_to_source_artifact_for_both_relation_types(self) -> None:
        normalized = normalize_pull_request_evidence(self.raw)
        source = GraphSnapshot(nodes=(self.repository, self.change))
        graph = source.merged_with(extract_pr_code_candidates((normalized,), source).graph)

        for relation_name in ("association", "repository_relation"):
            with self.subTest(relation_name=relation_name):
                relation = (
                    graph.pull_request_declared_associations[0]
                    if relation_name == "association"
                    else graph.pull_request_observed_repository_relations[0]
                )
                source_evidence = next(
                    item for item in graph.evidence if item.id == relation.source_evidence_id
                )
                identity = source_evidence.locator.source_artifact_identity
                wrong_identity = SourceArtifactIdentity(
                    identity.source_type, identity.source_identity, identity.artifact_type,
                    "c" * 40, identity.stable_locator,
                )
                wrong_provenance = ProvenanceRecord(
                    "external", "2026-09-01T12:00:00+00:00", "sha256", "e" * 64,
                    "pr-code-candidate-extraction", "2", wrong_identity,
                )
                tampered_evidence = replace(source_evidence, provenance_ids=(wrong_provenance.id,))
                tampered_relation = replace(relation, provenance_evidence_id=wrong_provenance.id)
                tampered = GraphSnapshot(
                    nodes=graph.nodes,
                    edges=graph.edges,
                    evidence=tuple(
                        tampered_evidence if item.id == source_evidence.id else item
                        for item in graph.evidence
                    ),
                    cross_graph_link_claims=graph.cross_graph_link_claims,
                    cross_graph_link_evidence=graph.cross_graph_link_evidence,
                    cross_graph_link_lifecycle=graph.cross_graph_link_lifecycle,
                    provenance=(*graph.provenance, wrong_provenance),
                    pull_request_evidence=graph.pull_request_evidence,
                    pull_request_declared_associations=(
                        (tampered_relation,)
                        if relation_name == "association"
                        else graph.pull_request_declared_associations
                    ),
                    pull_request_observed_repository_relations=(
                        (tampered_relation,)
                        if relation_name == "repository_relation"
                        else graph.pull_request_observed_repository_relations
                    ),
                )
                with self.assertRaisesRegex(ValueError, "provenance binding invalid"):
                    GraphSnapshot().merged_with(tampered)
                validation = validate_graph_integrity(tampered)
                self.assertEqual(validation.status, "invalid")
                expected_rule = (
                    "pr-association-provenance-binding"
                    if relation_name == "association"
                    else "pr-relation-provenance-binding"
                )
                self.assertTrue(any(item.rule_id == expected_rule for item in validation.metadata.diagnostics))

    def test_missing_or_unknown_repository_and_intended_change_are_not_admitted(self) -> None:
        normalized = normalize_pull_request_evidence(self.raw)
        for repository_id, graph in (
            (self.repository.id, GraphSnapshot(nodes=(self.change,))),
            ("repository-unknown", GraphSnapshot(nodes=(self.change,))),
        ):
            with self.subTest(repository_id=repository_id):
                candidate = normalize_pull_request_evidence({**self.raw, "repository_node_id": repository_id})
                result = extract_pr_code_candidates((candidate,), graph)
                self.assertEqual(result.graph.pull_request_evidence, ())
                self.assertEqual(result.metadata.skipped_reason_counts, {"missing-repository": 1})

        for intended_change_id, graph in (
            (self.change.id, GraphSnapshot(nodes=(self.repository,))),
            ("change-unknown", GraphSnapshot(nodes=(self.repository,))),
        ):
            with self.subTest(intended_change_id=intended_change_id):
                candidate = normalize_pull_request_evidence({
                    **self.raw,
                    "association": {**self.raw["association"], "intended_change_id": intended_change_id},
                })
                result = extract_pr_code_candidates((candidate,), graph)
                self.assertEqual(result.graph.pull_request_evidence, ())
                self.assertEqual(result.metadata.skipped_reason_counts, {"missing-intended-change": 1})

    def test_merge_rejects_dangling_or_ineligible_pr_endpoints_without_partial_snapshot(self) -> None:
        normalized = normalize_pull_request_evidence(self.raw)
        source = GraphSnapshot(nodes=(self.repository, self.change))
        graph = source.merged_with(extract_pr_code_candidates((normalized,), source).graph)
        association = graph.pull_request_declared_associations[0]

        association_cases = (
            (
                "dangling intended-change endpoint",
                replace(association, intended_change_id="change-missing"),
            ),
            (
                "ineligible intended-change endpoint",
                replace(association, intended_change_id=self.repository.id),
            ),
        )
        for label, tampered_association in association_cases:
            with self.subTest(label=label):
                tampered = replace(
                    graph,
                    pull_request_declared_associations=(tampered_association,),
                )
                with self.assertRaisesRegex(ValueError, "intended-change endpoint"):
                    GraphSnapshot().merged_with(tampered)

        for label, tampered_nodes in (
            (
                "dangling repository endpoint",
                tuple(node for node in graph.nodes if node.id != self.repository.id),
            ),
            (
                "ineligible repository endpoint",
                tuple(
                    replace(node, kind=NodeKind.WORKSPACE)
                    if node.id == self.repository.id else node
                    for node in graph.nodes
                ),
            ),
        ):
            with self.subTest(label=label):
                tampered = replace(graph, nodes=tampered_nodes)
                with self.assertRaisesRegex(ValueError, "repository endpoint"):
                    GraphSnapshot().merged_with(tampered)

        pr_node_id = graph.pull_request_evidence[0].node_id
        for label, tampered_nodes in (
            (
                "dangling PR-node endpoint",
                tuple(node for node in graph.nodes if node.id != pr_node_id),
            ),
            (
                "ineligible PR-node endpoint",
                tuple(
                    replace(node, kind=NodeKind.WORKSPACE)
                    if node.id == pr_node_id else node
                    for node in graph.nodes
                ),
            ),
        ):
            with self.subTest(label=label):
                tampered = replace(graph, nodes=tampered_nodes)
                with self.assertRaisesRegex(ValueError, "PR-node endpoint"):
                    GraphSnapshot().merged_with(tampered)

    def test_conflicting_immutable_pr_identity_is_not_admitted(self) -> None:
        first = normalize_pull_request_evidence(self.raw)
        second = normalize_pull_request_evidence({**self.raw, "base_revision": "c" * 40})
        graph = GraphSnapshot(nodes=(self.repository, self.change))
        result = extract_pr_code_candidates((first, second), graph)
        self.assertEqual(result.graph.pull_request_evidence, ())
        self.assertEqual(result.graph.cross_graph_link_claims, ())
        self.assertEqual(result.metadata.skipped_reason_counts, {"conflicting-pr-evidence-identity": 1})

    def test_unresolved_mapping_emits_no_partial_candidate(self) -> None:
        normalized = normalize_pull_request_evidence({
            **self.raw,
            "mappings": [{"id": "graphify:unresolved", "file": "src/payments.py", "outcome": "unresolved"}],
        })
        result = extract_pr_code_candidates((normalized,), GraphSnapshot(nodes=(self.repository, self.change)))
        self.assertEqual(result.graph.cross_graph_link_claims, ())
        self.assertEqual(result.graph.cross_graph_link_evidence, ())
        self.assertEqual(result.graph.cross_graph_link_lifecycle, ())
        self.assertEqual(result.metadata.skipped_reason_counts, {"unresolved-symbol": 1})

    def test_pr_scoped_evidence_rejects_scope_mismatch_and_non_observed_trust(self) -> None:
        normalized = normalize_pull_request_evidence(self.raw)
        observation = extract_pr_code_candidates(
            (normalized,), GraphSnapshot(nodes=(self.repository, self.change))
        ).graph.cross_graph_link_evidence[0]
        with self.assertRaisesRegex(ValueError, "observed and untrusted"):
            CrossGraphLinkEvidence(
                observation.claim_id, observation.strategy_id, observation.observation_id,
                observation.provenance_evidence_id, CrossGraphEvidenceOrigin.DECLARED,
                observation.status, observation.confidence, CrossGraphTrustDisposition.UNTRUSTED,
                observation.pull_request_evidence_id, observation.declared_association_id,
            )

        mismatched = CrossGraphLinkEvidence(
            observation.claim_id, observation.strategy_id, "graphify:mismatch",
            observation.provenance_evidence_id, observation.origin, observation.status,
            observation.confidence, observation.trust_disposition,
            observation.pull_request_evidence_id,
            PullRequestDeclaredAssociation(
                observation.pull_request_evidence_id, "change-other",
                normalized.association.source_evidence_id,
                normalized.association.provenance_evidence_id,
            ).id,
        )
        base = extract_pr_code_candidates(
            (normalized,), GraphSnapshot(nodes=(self.repository, self.change))
        ).graph
        wrong_association = PullRequestDeclaredAssociation(
            observation.pull_request_evidence_id, "change-other",
            normalized.association.source_evidence_id,
            normalized.association.provenance_evidence_id,
        )
        other_change = Node("change-other", NodeKind.OPENSPEC_ACTIVE_CHANGE, "other-change")
        with self.assertRaisesRegex(ValueError, "intended-change scope mismatch"):
            GraphSnapshot(nodes=(self.repository, self.change, other_change)).merged_with(GraphSnapshot(
                nodes=base.nodes,
                edges=(*base.edges, pull_request_projection_edge(
                    base.pull_request_evidence[0], wrong_association,
                )),
                cross_graph_link_claims=base.cross_graph_link_claims,
                cross_graph_link_evidence=(mismatched,),
                cross_graph_link_lifecycle=base.cross_graph_link_lifecycle,
                evidence=base.evidence,
                provenance=base.provenance,
                pull_request_evidence=base.pull_request_evidence,
                pull_request_declared_associations=(*base.pull_request_declared_associations, wrong_association),
                pull_request_observed_repository_relations=base.pull_request_observed_repository_relations,
            ))

    def test_typed_pr_relations_require_exact_projection_edges_at_all_graph_boundaries(self) -> None:
        normalized = normalize_pull_request_evidence(self.raw)
        source = GraphSnapshot(nodes=(self.repository, self.change))
        graph = source.merged_with(extract_pr_code_candidates((normalized,), source).graph)

        relations = (
            ("association", graph.pull_request_declared_associations[0]),
            ("repository", graph.pull_request_observed_repository_relations[0]),
        )
        for relation_name, relation in relations:
            expected = pull_request_projection_edge(graph.pull_request_evidence[0], relation)
            cases = (
                (
                    "missing",
                    tuple(edge for edge in graph.edges if edge.id != expected.id),
                ),
                (
                    "mismatched source evidence",
                    tuple(
                        replace(edge, evidence_ids=("source-evidence-mismatch",))
                        if edge.id == expected.id else edge
                        for edge in graph.edges
                    ),
                ),
            )
            for case_name, edges in cases:
                with self.subTest(relation=relation_name, case=case_name):
                    tampered = replace(graph, edges=edges)
                    validation = validate_graph_integrity(tampered)
                    self.assertEqual(validation.status, "invalid")
                    expected_rule = (
                        "pr-declared-association-projection"
                        if relation_name == "association"
                        else "pr-observed-repository-projection"
                    )
                    self.assertTrue(any(
                        item.rule_id == expected_rule
                        for item in validation.metadata.diagnostics
                    ))
                    with self.assertRaisesRegex(ValueError, "projected edge"):
                        GraphSnapshot().merged_with(tampered)
                    with tempfile.TemporaryDirectory() as temporary:
                        with self.assertRaisesRegex(PersistenceIntegrityError, "projected edge"):
                            initialize_ladybugdb_store(Path(temporary) / "store").write_snapshot(tampered)

    def test_typed_pr_relation_sources_require_explicit_identity_and_external_provenance(self) -> None:
        normalized = normalize_pull_request_evidence(self.raw)
        source = GraphSnapshot(nodes=(self.repository, self.change))
        graph = source.merged_with(extract_pr_code_candidates((normalized,), source).graph)
        derived = ProvenanceRecord(
            "derived", "2026-09-01T12:00:00+00:00", "sha256", "f" * 64,
            "test-derived", "1", None, "test-derivation", (graph.provenance[0].id,),
        )

        relations = (
            ("association", graph.pull_request_declared_associations[0]),
            ("repository", graph.pull_request_observed_repository_relations[0]),
        )
        for relation_name, relation in relations:
            source_evidence = next(
                item for item in graph.evidence if item.id == relation.source_evidence_id
            )
            cases = (
                (
                    "generic locator",
                    replace(source_evidence, locator="generic-locator"),
                    relation,
                    "explicit source-artifact identity",
                ),
                (
                    "derived provenance",
                    replace(source_evidence, provenance_ids=(derived.id,)),
                    replace(relation, provenance_evidence_id=derived.id),
                    "derived provenance",
                ),
            )
            for case_name, tampered_evidence, tampered_relation, expected_text in cases:
                with self.subTest(relation=relation_name, case=case_name):
                    tampered = replace(
                        graph,
                        evidence=tuple(
                            tampered_evidence if item.id == source_evidence.id else item
                            for item in graph.evidence
                        ),
                        provenance=(*graph.provenance, derived),
                        pull_request_declared_associations=(
                            (tampered_relation,)
                            if relation_name == "association"
                            else graph.pull_request_declared_associations
                        ),
                        pull_request_observed_repository_relations=(
                            (tampered_relation,)
                            if relation_name == "repository"
                            else graph.pull_request_observed_repository_relations
                        ),
                    )
                    validation = validate_graph_integrity(tampered)
                    self.assertEqual(validation.status, "invalid")
                    expected_rule = (
                        "pr-association-provenance-binding"
                        if relation_name == "association"
                        else "pr-relation-provenance-binding"
                    )
                    self.assertTrue(any(
                        item.rule_id == expected_rule and expected_text in item.message
                        for item in validation.metadata.diagnostics
                    ))
                    with self.assertRaisesRegex(ValueError, "provenance binding invalid"):
                        GraphSnapshot().merged_with(tampered)
                    with tempfile.TemporaryDirectory() as temporary:
                        with self.assertRaisesRegex(PersistenceIntegrityError, "provenance binding"):
                            initialize_ladybugdb_store(Path(temporary) / "store").write_snapshot(tampered)

    def test_revision_mismatch_is_not_admitted(self) -> None:
        normalized = normalize_pull_request_evidence({
            **self.raw,
            "mappings": [{**self.raw["mappings"][0], "revision": "c" * 40}],
        })
        graph = GraphSnapshot(nodes=(self.repository, self.change))
        result = extract_pr_code_candidates((normalized,), graph)
        self.assertEqual(result.graph.cross_graph_link_claims, ())
        self.assertEqual(result.metadata.skipped_reason_counts, {"revision-mismatch": 1})

    def test_payload_unsafe_and_incomplete_inputs_are_rejected_before_graph_emission(self) -> None:
        for key, value, reason in (
            ("pr_source_reference", "https://provider.example/pr/42", "URL-like"),
            ("pr_source_reference", {"source_identity": "pr", "provider_payload": "body"}, "raw source reference"),
            ("provenance", {}, "provenance input"),
        ):
            raw = {**self.raw, key: value}
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, reason):
                    normalize_pull_request_evidence(raw)

    def test_mutable_or_abbreviated_revisions_are_rejected(self) -> None:
        for field in ("base_revision", "head_revision"):
            for revision in ("main", "v1.2.3", "deadbee"):
                with self.subTest(field=field, revision=revision):
                    with self.assertRaisesRegex(ValueError, "immutable"):
                        normalize_pull_request_evidence({**self.raw, field: revision})

    def test_differing_pr_source_artifact_revision_is_invalid_at_integrity_and_persistence(self) -> None:
        normalized = normalize_pull_request_evidence(self.raw)
        source = GraphSnapshot(nodes=(self.repository, self.change))
        graph = source.merged_with(extract_pr_code_candidates((normalized,), source).graph)
        original_evidence = next(
            item for item in graph.evidence
            if item.id == normalized.pull_request.source_evidence_id
        )
        original_identity = original_evidence.locator.source_artifact_identity
        wrong_identity = SourceArtifactIdentity(
            original_identity.source_type,
            original_identity.source_identity,
            original_identity.artifact_type,
            "c" * 40,
            original_identity.stable_locator,
        )
        wrong_provenance = ProvenanceRecord(
            "external", "2026-09-01T12:00:00+00:00", "sha256", "d" * 64,
            "pr-code-candidate-extraction", "2", wrong_identity,
        )
        wrong_evidence = Evidence(
            stable_id("evidence", wrong_identity.id),
            "pr-code-candidate-extraction",
            SourceArtifactLocator(wrong_identity),
            {"pull_request_id": normalized.pull_request.pull_request_id, "repository": self.repository.id},
            (wrong_provenance.id,),
        )
        wrong_pr = type(normalized.pull_request)(
            normalized.pull_request.pull_request_id,
            normalized.pull_request.repository_id,
            normalized.pull_request.base_revision,
            normalized.pull_request.head_revision,
            normalized.pull_request.merged,
            wrong_evidence.id,
            wrong_provenance.id,
        )
        tampered = GraphSnapshot(
            nodes=graph.nodes,
            edges=graph.edges,
            evidence=tuple(item for item in graph.evidence if item.id != normalized.pull_request.source_evidence_id) + (wrong_evidence,),
            cross_graph_link_claims=graph.cross_graph_link_claims,
            cross_graph_link_evidence=graph.cross_graph_link_evidence,
            cross_graph_link_lifecycle=graph.cross_graph_link_lifecycle,
            provenance=tuple(item for item in graph.provenance if item.id != normalized.pull_request.provenance_evidence_id) + (wrong_provenance,),
            pull_request_evidence=(wrong_pr,),
            pull_request_declared_associations=graph.pull_request_declared_associations,
            pull_request_observed_repository_relations=graph.pull_request_observed_repository_relations,
        )
        validation = validate_graph_integrity(tampered)
        self.assertEqual(validation.status, "invalid")
        self.assertTrue(any(item.rule_id == "pr-source-artifact-binding" for item in validation.metadata.diagnostics))
        with self.assertRaisesRegex(ValueError, "source artifact invalid"):
            GraphSnapshot().merged_with(tampered)
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(PersistenceIntegrityError, "source artifact"):
                initialize_ladybugdb_store(Path(temporary) / "store").write_snapshot(tampered)

    def test_association_is_never_inferred_without_an_explicit_source_reference(self) -> None:
        raw = {**self.raw, "association": {**self.raw["association"], "source_reference": None}}
        with self.assertRaisesRegex(ValueError, "source reference is required"):
            normalize_pull_request_evidence(raw)

    def test_catalog_rejects_pr_implementation_and_reversed_pr_endpoints(self) -> None:
        from engineering_kg.ontology import Node

        pr = Node("pr-node", NodeKind.PULL_REQUEST, "pr")
        repo = self.repository
        self.assertEqual(relationship_error("implements", pr, repo), "relationship-endpoint-contract")
        self.assertEqual(relationship_error("references", pr, repo), "pr-declared-association-endpoint-contract")

    def test_multiple_symbols_remain_observed_candidates_without_implementation_projection(self) -> None:
        raw = {
            **self.raw,
            "mappings": [
                self.raw["mappings"][0],
                {**self.raw["mappings"][0], "id": "graphify:mapping-43", "file": "src/refunds.py", "symbol": "refunds.refund"},
            ],
        }
        normalized = normalize_pull_request_evidence(raw)
        graph = GraphSnapshot(nodes=(self.repository, self.change))
        result = extract_pr_code_candidates((normalized,), graph)
        merged = graph.merged_with(result.graph)
        self.assertEqual(len(merged.cross_graph_link_claims), 2)
        self.assertFalse(any(edge.kind == "implements" for edge in merged.edges))
        self.assertEqual(merged.trusted_cross_graph_links, ())

    def test_openspec_requirements_do_not_receive_fanout_from_pr_candidates(self) -> None:
        requirement = Node("requirement-1", NodeKind.REQUIREMENT, "must submit payment")
        normalized = normalize_pull_request_evidence(self.raw)
        source = GraphSnapshot(nodes=(self.repository, self.change, requirement))
        result = extract_pr_code_candidates((normalized,), source)
        merged = source.merged_with(result.graph)
        self.assertEqual(len(merged.cross_graph_link_claims), 1)
        self.assertEqual(merged.cross_graph_link_claims[0].subject_id, self.change.id)
        self.assertFalse(any(claim.subject_id == requirement.id for claim in merged.cross_graph_link_claims))
        self.assertFalse(any(edge.kind == "implements" for edge in merged.edges))
        self.assertEqual(merged.trusted_cross_graph_links, ())

    def test_reordered_equivalent_input_is_deterministic(self) -> None:
        first_raw = {
            **self.raw,
            "mappings": [self.raw["mappings"][0], {**self.raw["mappings"][0], "id": "graphify:mapping-43", "file": "src/refunds.py", "symbol": "refunds.refund"}],
        }
        second_raw = {**first_raw, "mappings": list(reversed(first_raw["mappings"]))}
        first = normalize_pull_request_evidence(first_raw)
        second = normalize_pull_request_evidence(second_raw)
        graph = GraphSnapshot(nodes=(self.repository, self.change))
        first_result = extract_pr_code_candidates((first,), graph)
        second_result = extract_pr_code_candidates((second,), graph)
        self.assertEqual(first_result.graph.as_json(), second_result.graph.as_json())


if __name__ == "__main__":
    unittest.main()
