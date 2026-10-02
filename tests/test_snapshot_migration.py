from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from engineering_kg.ontology import (
    CodeLocator, CrossGraphLinkClaim, CrossGraphLinkEvidence, CrossGraphLinkLifecycle,
    Edge, Evidence, GraphSnapshot, Node, NodeKind, OpenSpecLocator,
    ProvenanceRecord, PullRequestDeclaredAssociation, PullRequestImplementationEvidence,
    PullRequestObservedRepositoryRelation, SourceArtifactIdentity,
    openspec_specification_id, stable_id,
)
from engineering_kg.persistence import PersistenceIntegrityError, initialize_ladybugdb_store
from engineering_kg.ingest.pr_code_candidates import extract_pr_code_candidates, normalize_pull_request_evidence
from engineering_kg.pipeline import run_pipeline
from engineering_kg.relationship_vocabulary import CATALOG_REVISION
from engineering_kg.snapshot_codec import SnapshotCodecError, deserialize_snapshot, empty_document, serialize_snapshot
from engineering_kg.snapshot_migration import (
    SnapshotMigrationError,
    SnapshotMigrationRegistry,
    SnapshotMigrationTransition,
    SnapshotSourceDescriptor,
    migrate_snapshot_document,
    parse_schema_version,
)
from engineering_kg.validation import validate_graph_integrity


class SnapshotMigrationTest(unittest.TestCase):
    def test_current_document_is_noop_and_marker_upgrade_is_migrated(self) -> None:
        current = empty_document(CATALOG_REVISION)
        result = migrate_snapshot_document(current)
        self.assertEqual(result.status, "not-needed")
        self.assertEqual(result.source_version, 1)
        self.assertEqual(result.target_version, 1)
        self.assertEqual(result.applied_migration_ids, ())

        versionless = copy.deepcopy(current)
        versionless.pop("ontology_schema_version")
        result = migrate_snapshot_document(versionless)
        self.assertEqual(result.status, "migrated")
        self.assertEqual(result.applied_migration_ids, ("unversioned-current-canonical-v4",))
        self.assertEqual(result.document["ontology_schema_version"], 1)

    def test_populated_versionless_document_is_upgraded_only_with_version_marker(self) -> None:
        snapshot = GraphSnapshot(
            nodes=(Node("repository", NodeKind.REPOSITORY, "payments"),),
            evidence=(Evidence("evidence", "fixture", "fixture.json"),),
        )
        versionless = serialize_snapshot(snapshot, CATALOG_REVISION)
        versionless.pop("ontology_schema_version")
        expected = {**copy.deepcopy(versionless), "ontology_schema_version": 1}

        pure = migrate_snapshot_document(versionless)
        self.assertEqual(pure.document, expected)

        with tempfile.TemporaryDirectory() as temporary:
            store = initialize_ladybugdb_store(Path(temporary) / "graph")
            store._write_raw(versionless)
            adapter = store.migrate_persisted_snapshot()
            persisted = store._read_raw()

        self.assertEqual(persisted, expected)
        self.assertEqual(adapter.status, pure.status)
        self.assertEqual(adapter.applied_migration_ids, ("unversioned-current-canonical-v4",))

    def test_registered_migration_rejects_legacy_requirement_without_unique_specification(self) -> None:
        requirement = Node(
            "legacy-requirement", "openspec-requirement", "Payment is submitted",
            {"capability": "payments"},
        )
        document = {
            "catalog_revision": CATALOG_REVISION,
            "nodes": {requirement.id: requirement.as_dict()},
            "node_order": [requirement.id],
            "edges": {}, "edge_order": [],
        }
        original = copy.deepcopy(document)

        with self.assertRaises(SnapshotMigrationError) as raised:
            migrate_snapshot_document(document)

        self.assertEqual(raised.exception.code, "legacy-identity-insufficient")
        self.assertEqual(document, original)

    def test_version_parser_is_strict(self) -> None:
        for value in (True, False, "1", 0, -1, 1.0, None):
            with self.subTest(value=value), self.assertRaises(SnapshotMigrationError):
                parse_schema_version(value)

    def test_codec_rejects_current_document_catalog_mismatch(self) -> None:
        document = empty_document(CATALOG_REVISION)
        document["catalog_revision"] = "retired"
        with self.assertRaisesRegex(SnapshotCodecError, "unsupported-catalog-revision"):
            deserialize_snapshot(document)

    def test_unsupported_prior_and_unrecognized_versionless_documents_fail_closed(self) -> None:
        prior = empty_document(CATALOG_REVISION)
        prior["ontology_schema_version"] = 0
        with self.assertRaises(SnapshotMigrationError):
            migrate_snapshot_document(prior)
        unrecognized = empty_document(CATALOG_REVISION)
        unrecognized.pop("ontology_schema_version")
        unrecognized["nodes"] = {"x": {"id": "x"}}
        original = copy.deepcopy(unrecognized)
        with self.assertRaises(SnapshotMigrationError):
            migrate_snapshot_document(unrecognized)
        self.assertEqual(unrecognized, original)

    def test_future_and_catalog_versions_fail_without_mutating_input(self) -> None:
        document = empty_document(CATALOG_REVISION)
        document["ontology_schema_version"] = 2
        original = copy.deepcopy(document)
        with self.assertRaisesRegex(SnapshotMigrationError, "unsupported ontology schema version"):
            migrate_snapshot_document(document)
        self.assertEqual(document, original)

        document = empty_document("old")
        with self.assertRaisesRegex(SnapshotMigrationError, "unsupported-catalog-revision"):
            migrate_snapshot_document(document)

    def test_registry_rejects_ambiguous_descriptors_and_transition_gaps(self) -> None:
        descriptor = SnapshotSourceDescriptor("one", lambda value: True, transform=lambda value: (dict(value), 0, 0))
        ambiguous = SnapshotMigrationRegistry(descriptors=(descriptor, SnapshotSourceDescriptor("two", lambda value: True, transform=descriptor.transform)))
        unversioned = empty_document(CATALOG_REVISION)
        unversioned.pop("ontology_schema_version")
        with self.assertRaisesRegex(SnapshotMigrationError, "ambiguous legacy"):
            ambiguous.migrate(unversioned)

        gap = SnapshotMigrationRegistry(
            descriptors=(), current_version=3,
            transitions=(SnapshotMigrationTransition("one-to-three", 1, 3, lambda value: (dict(value), 0, 0)),),
        )
        document = empty_document(CATALOG_REVISION)
        document["ontology_schema_version"] = 1
        with self.assertRaisesRegex(SnapshotMigrationError, "adjacent"):
            gap.migrate(document)

    def test_openspec_prefixed_document_migrates_to_canonical_records(self) -> None:
        identity = SourceArtifactIdentity("openspec", "requirements", "openspec-spec", "a" * 40, "openspec/specs/payments/spec.md")
        provenance = ProvenanceRecord("external", "2026-01-02T03:04:05+00:00", "sha256", "a" * 64, "test", "1", identity)
        spec_evidence = Evidence(stable_id("evidence", identity.id, "durable:payments"), "openspec", OpenSpecLocator(identity.stable_locator, identity.artifact_type, "durable:payments", source_artifact_identity=identity), provenance_ids=(provenance.id,))
        requirement_identity = SourceArtifactIdentity("openspec", "requirements", "openspec-requirement", "a" * 40, "openspec/specs/payments/spec.md")
        requirement_provenance = ProvenanceRecord("external", "2026-01-02T03:04:05+00:00", "sha256", "b" * 64, "test", "1", requirement_identity)
        requirement_evidence = Evidence(stable_id("evidence", requirement_identity.id, "durable:payments:requirement:Payment is submitted"), "openspec", OpenSpecLocator(requirement_identity.stable_locator, requirement_identity.artifact_type, "durable:payments:requirement:Payment is submitted", source_artifact_identity=requirement_identity), provenance_ids=(requirement_provenance.id,))
        spec = Node("legacy-spec", "openspec-spec", "Payments", {"capability": "payments", "repository_id": "requirements"}, (spec_evidence.id,))
        requirement = Node("legacy-requirement", "openspec-requirement", "Payment is submitted", {"capability": "payments"}, (requirement_evidence.id,))
        edge = Edge("legacy-edge", "openspec-spec-contains-requirement", spec.id, requirement.id, evidence_ids=(requirement_evidence.id,))
        document = {
            "catalog_revision": CATALOG_REVISION,
            "nodes": {item.id: item.as_dict() for item in (spec, requirement)},
            "node_order": [spec.id, requirement.id],
            "edges": {edge.id: edge.as_dict()},
            "edge_order": [edge.id],
            "evidence": {item.id: item.as_dict() for item in (spec_evidence, requirement_evidence)},
            "evidence_order": [spec_evidence.id, requirement_evidence.id],
            "provenance": {item.id: item.as_dict() for item in (provenance, requirement_provenance)},
            "provenance_order": [provenance.id, requirement_provenance.id],
        }
        result = migrate_snapshot_document(document)
        snapshot = deserialize_snapshot(result.document)
        self.assertEqual({item.kind for item in snapshot.nodes}, {"specification", "requirement"})
        self.assertEqual(snapshot.edges[0].kind, "contains")
        self.assertEqual(result.status, "migrated")

    def test_registered_openspec_migration_covers_scenarios_assertions_traces_and_related(self) -> None:
        document = _legacy_openspec_document(include_scenario=True, include_trace=True, include_related=True)
        result = migrate_snapshot_document(document)
        snapshot = deserialize_snapshot(result.document)
        self.assertEqual({node.kind for node in snapshot.nodes if node.kind in {"specification", "requirement", "scenario"}}, {"specification", "requirement", "scenario"})
        edges = {edge.kind: edge for edge in snapshot.edges}
        self.assertEqual(sum(edge.kind == "contains" for edge in snapshot.edges), 2)
        self.assertEqual(edges["asserts"].source_id, "change-1")
        self.assertEqual(edges["traces_to"].properties["input_edge_ids"], [edges["asserts"].id])
        self.assertTrue(edges["traces_to"].properties["derived"])
        self.assertNotEqual(edges["asserts"].id, edges["traces_to"].id)
        self.assertFalse({"source_scope", "target_scope", "via_spec_id"} & set(edges["traces_to"].properties))
        related = next(edge for edge in snapshot.edges if edge.kind == "references")
        self.assertEqual(related.confidence, "non-confident")
        self.assertEqual(related.properties["related_title"], "Other")
        self.assertFalse(any(edge.properties.get("related_title") == "Unresolved title" for edge in snapshot.edges))
        related_evidence = next(item for item in snapshot.evidence if item.id in snapshot.nodes[0].evidence_ids)
        self.assertIn("Unresolved title", related_evidence.properties["related"])
        specification = next(node for node in snapshot.nodes if node.kind == NodeKind.SPECIFICATION)
        self.assertEqual(specification.id, openspec_specification_id("requirements", "payments"))
        self.assertEqual(related_evidence.properties["specification_id"], specification.id)
        diagnostics = validate_graph_integrity(snapshot).metadata.diagnostics
        self.assertIn("unresolved-non-confident-related-spec", [item.rule_id for item in diagnostics])

    def test_migrated_related_metadata_is_associated_and_matched_title_has_no_warning(self) -> None:
        document = _legacy_openspec_document(include_related=True)
        evidence = document["evidence"][document["evidence_order"][0]]
        evidence["properties"]["related"] = ["Other"]

        snapshot = deserialize_snapshot(migrate_snapshot_document(document).document)
        specification = next(node for node in snapshot.nodes if node.kind == NodeKind.SPECIFICATION and node.name == "payments")
        references = [edge for edge in snapshot.edges if edge.kind == "references"]
        self.assertEqual(len(references), 1)
        self.assertEqual(references[0].source_id, specification.id)
        migrated_evidence = next(item for item in snapshot.evidence if item.id == evidence["id"])
        self.assertEqual(migrated_evidence.properties["specification_id"], specification.id)
        self.assertNotIn(
            "unresolved-non-confident-related-spec",
            [item.rule_id for item in validate_graph_integrity(snapshot).metadata.diagnostics],
        )

    def test_unresolvable_evidence_specification_id_is_preserved(self) -> None:
        document = _legacy_openspec_document()
        evidence = document["evidence"][document["evidence_order"][0]]
        evidence["properties"]["specification_id"] = "unknown-specification"

        snapshot = deserialize_snapshot(migrate_snapshot_document(document).document)
        migrated_evidence = next(item for item in snapshot.evidence if item.id == evidence["id"])
        self.assertEqual(migrated_evidence.properties["specification_id"], "unknown-specification")
        self.assertNotIn("unknown-specification", {node.id for node in snapshot.nodes})

    def test_registered_migration_carries_canonical_pr_candidate_without_relabeling(self) -> None:
        document = _legacy_openspec_document(include_trace=True)
        subject = Node("change-1", NodeKind.OPENSPEC_ACTIVE_CHANGE, "change")
        repository = Node(stable_id("node", NodeKind.REPOSITORY, "payments"), NodeKind.REPOSITORY, "payments")
        pr_input = normalize_pull_request_evidence({
            "pull_request_id": "bitbucket:pr-1", "repository_node_id": repository.id,
            "base_revision": "a" * 40, "head_revision": "b" * 40, "merged": True,
            "observed_at": "2026-01-02T03:04:05+00:00",
            "provenance": {"pr": "complete", "association": "complete", "repository": "complete"},
            "pr_source_reference": "urn:example.org/pr-42", "repository_source_reference": "urn:example.org/repository-42",
            "association": {"id": "association-42", "intended_change_id": subject.id, "source_reference": "urn:example.org/association-42", "intended_change_kind": "openspec-active-change"},
            "mappings": [{"id": "graphify:mapping-42", "file": "src/a.py", "symbol": "pkg.a", "outcome": "resolved", "repository": repository.id, "revision": "b" * 40}],
        })
        snapshot = GraphSnapshot(nodes=(subject, repository)).merged_with(extract_pr_code_candidates((pr_input,), GraphSnapshot(nodes=(subject, repository))).graph)
        self.assertEqual(len(snapshot.cross_graph_link_claims), 1)
        claim = snapshot.cross_graph_link_claims[0]
        support_id = snapshot.cross_graph_link_evidence[0].provenance_evidence_id
        snapshot = GraphSnapshot(
            nodes=snapshot.nodes, edges=snapshot.edges, evidence=snapshot.evidence,
            provenance=snapshot.provenance, cross_graph_link_claims=snapshot.cross_graph_link_claims,
            cross_graph_link_evidence=snapshot.cross_graph_link_evidence,
            cross_graph_link_lifecycle=(
                *snapshot.cross_graph_link_lifecycle,
                CrossGraphLinkLifecycle(claim.id, 2, "rejected", support_id, "observed", "authoritative", "reviewed", "untrusted"),
                CrossGraphLinkLifecycle(claim.id, 3, "superseded", support_id, "observed", "authoritative", "reviewed", "untrusted"),
            ), pull_request_evidence=snapshot.pull_request_evidence,
            pull_request_declared_associations=snapshot.pull_request_declared_associations,
            pull_request_observed_repository_relations=snapshot.pull_request_observed_repository_relations,
        )
        current = serialize_snapshot(snapshot, CATALOG_REVISION)
        for collection, order_key in (("nodes", "node_order"), ("edges", "edge_order")):
            document[collection].update(current[collection])
            document[order_key].extend(item for item in current[order_key] if item not in document[order_key])
        order_keys = {
            "cross_graph_link_claims": "cross_graph_link_claim_order",
            "cross_graph_link_evidence": "cross_graph_link_evidence_order",
            "cross_graph_link_lifecycle": "cross_graph_link_lifecycle_order",
            "pull_request_evidence": "pull_request_evidence_order",
            "pull_request_declared_associations": "pull_request_declared_association_order",
            "pull_request_observed_repository_relations": "pull_request_observed_repository_relation_order",
        }
        for collection, order_key in order_keys.items():
            document[collection] = current[collection]
            document[order_key] = current[order_key]
        for collection, order_key in (("evidence", "evidence_order"), ("provenance", "provenance_order")):
            document[collection].update(current[collection])
            document[order_key].extend(item for item in current[order_key] if item not in document[order_key])
        migrated = deserialize_snapshot(migrate_snapshot_document(document).document)
        self.assertEqual(migrated.cross_graph_link_claims[0].relation_kind, "touches")
        self.assertEqual(migrated.cross_graph_link_lifecycle[0].state, "candidate")
        self.assertEqual(migrated.cross_graph_link_lifecycle[0].trust_disposition, "untrusted")
        self.assertEqual({item.state for item in migrated.cross_graph_link_lifecycle}, {"candidate", "rejected", "superseded"})
        self.assertEqual(migrated.trusted_cross_graph_links, ())
        self.assertEqual(migrated.cross_graph_link_evidence[0].pull_request_evidence_id, snapshot.pull_request_evidence[0].id)
        self.assertEqual(migrated.cross_graph_link_evidence[0].declared_association_id, snapshot.pull_request_declared_associations[0].id)
        self.assertEqual(migrated.pull_request_observed_repository_relations[0].pull_request_evidence_id, snapshot.pull_request_evidence[0].id)

    def test_registered_migration_rejects_incomplete_pr_and_verification_data(self) -> None:
        base = _legacy_openspec_document()
        for incomplete_pr in (True, False):
            with self.subTest(incomplete_pr=incomplete_pr):
                document = copy.deepcopy(base)
                if incomplete_pr:
                    collection, record_name = "pull_request_evidence", "pr"
                    record = {"id": "pr", "pull_request_id": "bitbucket:pr-1", "repository_id": "repo", "base_revision": "a" * 40, "merged": True, "source_evidence_id": "missing", "provenance_evidence_id": "missing"}
                    document[collection] = {record_name: record}
                else:
                    node = Node("verification", "test_case", "test", {"test_case_key": "case"})
                    document["nodes"][node.id] = node.as_dict()
                    document["node_order"].append(node.id)
                original = copy.deepcopy(document)
                with self.assertRaises(SnapshotMigrationError):
                    migrate_snapshot_document(document)
                self.assertEqual(document, original)

        missing_provenance = _legacy_openspec_document()
        missing_provenance["provenance"] = {}
        missing_provenance["provenance_order"] = []
        with self.assertRaisesRegex(SnapshotMigrationError, "legacy snapshot cannot be migrated deterministically"):
            migrate_snapshot_document(missing_provenance)

    def test_legacy_evidence_rejects_conflicting_retained_provenance(self) -> None:
        conflicting = _legacy_document_with_embedded_provenance(conflict=True)
        unresolved = _legacy_document_with_embedded_provenance()
        evidence = unresolved["evidence"][unresolved["evidence_order"][0]]
        unresolved_id = evidence["provenance_ids"][0]
        del unresolved["provenance"][unresolved_id]
        unresolved["provenance_order"].remove(unresolved_id)

        for label, document in (("different retained record", conflicting), ("missing retained record", unresolved)):
            with self.subTest(label=label), self.assertRaises(SnapshotMigrationError) as raised:
                migrate_snapshot_document(document)
            self.assertEqual(raised.exception.code, "legacy-provenance-conflict")

    def test_legacy_evidence_reuses_identical_retained_provenance(self) -> None:
        document = _legacy_document_with_embedded_provenance()
        retained_provenance_id = document["evidence"][document["evidence_order"][0]]["provenance_ids"][0]
        original_provenance_count = len(document["provenance"])

        result = migrate_snapshot_document(document)
        snapshot = deserialize_snapshot(result.document)
        converted_evidence = next(
            evidence for evidence in snapshot.evidence
            if evidence.properties.get("specification_id") == openspec_specification_id("requirements", "payments")
        )

        self.assertEqual(converted_evidence.provenance_ids, (retained_provenance_id,))
        self.assertEqual(len(snapshot.provenance), original_provenance_count)
        self.assertIn(retained_provenance_id, {record.id for record in snapshot.provenance})
        self.assertEqual(
            {record_id for evidence in snapshot.evidence for record_id in evidence.provenance_ids},
            {record.id for record in snapshot.provenance},
        )

    def test_legacy_embedded_provenance_migrates_without_retained_association(self) -> None:
        document = _legacy_document_with_embedded_provenance(retain_association=False)

        result = migrate_snapshot_document(document)
        snapshot = deserialize_snapshot(result.document)
        converted_evidence = next(
            evidence for evidence in snapshot.evidence
            if evidence.properties.get("specification_id") == openspec_specification_id("requirements", "payments")
        )

        self.assertEqual(len(converted_evidence.provenance_ids), 1)
        self.assertIn(converted_evidence.provenance_ids[0], {record.id for record in snapshot.provenance})

    def test_adapter_rejection_preserves_conflicting_provenance_source_without_backup(self) -> None:
        document = _legacy_document_with_embedded_provenance(conflict=True)
        with tempfile.TemporaryDirectory() as temporary:
            store = initialize_ladybugdb_store(Path(temporary) / "graph")
            store._write_raw(document)
            original_bytes = store._graph_file.read_bytes()

            with self.assertRaisesRegex(PersistenceIntegrityError, "legacy-provenance-conflict"):
                store.migrate_persisted_snapshot()

            self.assertEqual(store._graph_file.read_bytes(), original_bytes)
            self.assertEqual(tuple(store.path.glob("graph.pre-ontology-migration.*.json")), ())

    def test_registered_migration_conflict_and_invalid_target_fail_before_result(self) -> None:
        document = _legacy_openspec_document()
        conflict = copy.deepcopy(document)
        canonical = Node(stable_id("node", "specification", "requirements", "payments"), "requirement", "wrong")
        conflict["nodes"][canonical.id] = canonical.as_dict()
        conflict["node_order"].append(canonical.id)
        with self.assertRaises(SnapshotMigrationError):
            migrate_snapshot_document(conflict)

        invalid_registry = SnapshotMigrationRegistry(
            descriptors=(SnapshotSourceDescriptor("supported-invalid-target", lambda value: True, transform=lambda value: ({**_legacy_openspec_document(), "ontology_schema_version": 1, "edges": {"dangling": {"id": "dangling", "kind": "contains", "source_id": "absent", "target_id": "absent", "properties": {}, "evidence_ids": [], "confidence": "explicit"}}, "edge_order": ["dangling"]}, 0, 0)),),
        )
        with self.assertRaisesRegex(SnapshotMigrationError, "edge-source-exists"):
            invalid_registry.migrate(_legacy_openspec_document())

    def test_registered_migration_is_idempotent_for_canonicalized_openspec_source(self) -> None:
        first = migrate_snapshot_document(_legacy_openspec_document())
        second = migrate_snapshot_document(first.document)
        self.assertEqual(second.status, "not-needed")
        self.assertEqual(second.applied_migration_ids, ())
        self.assertEqual(second.document, first.document)
        self.assertEqual(second.graph_counts, first.graph_counts)

    def test_registered_migration_rejects_ambiguous_relationship_variants_without_guessing(self) -> None:
        for label, source_kind in (
            ("alias", "owns"),
            ("reversed", "owned_by"),
            ("endpoint", "owned_by"),
            ("unmapped", "openspec-unmapped"),
        ):
            with self.subTest(label=label):
                document = _legacy_openspec_document()
                target_id = "legacy-spec" if label == "reversed" else "legacy-requirement"
                edge = Edge(f"bad-{label}", source_kind, "legacy-spec", target_id)
                document["edges"][edge.id] = edge.as_dict()
                document["edge_order"].append(edge.id)
                original = copy.deepcopy(document)
                with self.assertRaises(SnapshotMigrationError) as raised:
                    migrate_snapshot_document(document)
                with self.assertRaises(SnapshotMigrationError) as repeated:
                    migrate_snapshot_document(document)
                self.assertTrue(raised.exception.code)
                self.assertEqual(raised.exception.as_dict(), repeated.exception.as_dict())
                self.assertEqual(document, original)

        unclassified = _legacy_openspec_document()
        unclassified["cross_graph_link_lifecycle"] = {"bad": {"id": "bad", "claim_id": "missing", "revision": 1, "state": "candidate", "provenance_evidence_id": "missing", "origin": "observed", "status": "derived", "confidence": "unknown", "trust_disposition": "unknown"}}
        unclassified["cross_graph_link_lifecycle_order"] = ["bad"]
        with self.assertRaises(SnapshotMigrationError):
            migrate_snapshot_document(unclassified)

    def test_persistence_creates_qualified_backup_only_for_real_migration(self) -> None:
        document = empty_document(CATALOG_REVISION)
        document.pop("ontology_schema_version")
        with tempfile.TemporaryDirectory() as temporary:
            store = initialize_ladybugdb_store(Path(temporary) / "graph")
            store._write_raw(document)
            original = store._graph_file.read_bytes()
            store.migrate_persisted_snapshot()
            backups = tuple(store.path.glob("graph.pre-ontology-migration.*.json"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original)
            store.migrate_persisted_snapshot()
            self.assertEqual(tuple(store.path.glob("graph.pre-ontology-migration.*.json")), backups)

    def test_core_and_local_adapter_return_identical_marker_migration(self) -> None:
        document = empty_document(CATALOG_REVISION)
        document.pop("ontology_schema_version")
        pure = migrate_snapshot_document(document)
        with tempfile.TemporaryDirectory() as temporary:
            store = initialize_ladybugdb_store(Path(temporary) / "graph")
            store._write_raw(document)
            adapter = store.migrate_persisted_snapshot()
            persisted = store._read_raw()
        self.assertEqual(persisted, pure.document)
        self.assertEqual(adapter.status, pure.status)
        self.assertEqual(adapter.applied_migration_ids, pure.applied_migration_ids)

    def test_core_and_local_adapter_return_identical_openspec_migration(self) -> None:
        document = _legacy_openspec_document(include_scenario=True, include_trace=True, include_related=True)
        pure = migrate_snapshot_document(document)
        with tempfile.TemporaryDirectory() as temporary:
            store = initialize_ladybugdb_store(Path(temporary) / "graph")
            store._write_raw(document)
            adapter = store.migrate_persisted_snapshot()
            persisted = store._read_raw()
        self.assertEqual(persisted, pure.document)
        self.assertEqual(adapter.status, pure.status)
        self.assertEqual(adapter.source_descriptor, pure.source_descriptor)
        self.assertEqual(adapter.applied_migration_ids, pure.applied_migration_ids)
        self.assertEqual(adapter.graph_counts, pure.graph_counts)

    def test_pipeline_serializes_safe_migration_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            graph_path = Path(temporary) / "graph"
            store = initialize_ladybugdb_store(graph_path)
            document = empty_document(CATALOG_REVISION)
            document.pop("ontology_schema_version")
            store._write_raw(document)
            result = run_pipeline(persistence_path=graph_path).as_dict()
        migration = result["ontology_migration"]
        self.assertEqual(migration["status"], "migrated")
        self.assertEqual(migration["source_descriptor"], "unversioned-current-canonical-v4")
        self.assertEqual(migration["target_version"], 1)
        self.assertEqual(migration["applied_migration_ids"], ["unversioned-current-canonical-v4"])
        self.assertNotIn("graph.json", str(migration))

    def test_pipeline_migration_diagnostics_exclude_catalog_revision_values(self) -> None:
        sentinels = (
            {"credentials": "hunter2-catalog-secret"},
            "Bearer catalog-secret-token-123",
        )
        for catalog_revision in sentinels:
            with self.subTest(catalog_revision_type=type(catalog_revision).__name__), tempfile.TemporaryDirectory() as temporary:
                graph_path = Path(temporary) / "graph"
                store = initialize_ladybugdb_store(graph_path)
                document = empty_document(CATALOG_REVISION)
                document["catalog_revision"] = catalog_revision
                store._write_raw(document)

                result = run_pipeline(persistence_path=graph_path).as_dict()

            diagnostics = result["ontology_migration"]["diagnostics"]
            self.assertEqual(
                diagnostics,
                ["unsupported-catalog-revision: unsupported-catalog-revision"],
            )
            self.assertNotIn("hunter2-catalog-secret", str(diagnostics))
            self.assertNotIn("catalog-secret-token-123", str(diagnostics))


if __name__ == "__main__":
    unittest.main()


def _legacy_openspec_document(*, include_scenario=False, include_trace=False, include_related=False):
    identity = SourceArtifactIdentity("openspec", "requirements", "openspec-spec", "a" * 40, "openspec/specs/payments/spec.md")
    provenance = ProvenanceRecord("external", "2026-01-02T03:04:05+00:00", "sha256", "a" * 64, "test", "1", identity)
    evidence = Evidence(stable_id("evidence", identity.id, "durable:payments"), "openspec", OpenSpecLocator(identity.stable_locator, identity.artifact_type, "durable:payments", source_artifact_identity=identity), {"related": ["Unresolved title"], "specification_id": "legacy-spec"}, provenance_ids=(provenance.id,))
    req_identity = SourceArtifactIdentity("openspec", "requirements", "openspec-requirement", "a" * 40, identity.stable_locator)
    req_provenance = ProvenanceRecord("external", "2026-01-02T03:04:05+00:00", "sha256", "b" * 64, "test", "1", req_identity)
    req_evidence = Evidence(stable_id("evidence", req_identity.id, "durable:payments:requirement:Payment is submitted"), "openspec", OpenSpecLocator(req_identity.stable_locator, req_identity.artifact_type, "durable:payments:requirement:Payment is submitted", source_artifact_identity=req_identity), provenance_ids=(req_provenance.id,))
    spec = Node("legacy-spec", "openspec-spec", "Payments", {"capability": "payments", "repository_id": "requirements"}, (evidence.id,))
    requirement = Node("legacy-requirement", "openspec-requirement", "Payment is submitted", {"capability": "payments"}, (req_evidence.id,))
    nodes = [spec, requirement]
    edges = [Edge("legacy-hierarchy", "openspec-spec-contains-requirement", spec.id, requirement.id, evidence_ids=(req_evidence.id,))]
    evidences = [evidence, req_evidence]
    provenances = [provenance, req_provenance]
    if include_scenario:
        scenario_identity = SourceArtifactIdentity("openspec", "requirements", "openspec-scenario", "a" * 40, identity.stable_locator)
        scenario_provenance = ProvenanceRecord("external", "2026-01-02T03:04:05+00:00", "sha256", "c" * 64, "test", "1", scenario_identity)
        scenario_evidence = Evidence(stable_id("evidence", scenario_identity.id, "scenario"), "openspec", OpenSpecLocator(scenario_identity.stable_locator, scenario_identity.artifact_type, "scenario", source_artifact_identity=scenario_identity), provenance_ids=(scenario_provenance.id,))
        scenario = Node("legacy-scenario", "openspec-scenario", "Valid payment", {"capability": "payments"}, (scenario_evidence.id,))
        nodes.append(scenario)
        edges.append(Edge("legacy-scenario-edge", "openspec-requirement-contains-scenario", requirement.id, scenario.id, evidence_ids=(scenario_evidence.id,)))
        evidences.append(scenario_evidence)
        provenances.append(scenario_provenance)
    if include_trace:
        change = Node("change-1", NodeKind.OPENSPEC_ACTIVE_CHANGE, "change", {"change_identity": "change"})
        nodes.append(change)
        edges.append(Edge("legacy-assertion", "openspec-change-touches-spec", change.id, spec.id, evidence_ids=(evidence.id,)))
        edges.append(Edge("legacy-trace", "openspec-change-traces-to-spec", change.id, spec.id, {"derived": True, "rule_id": "openspec-change-to-durable-spec", "input_edge_ids": ("legacy-assertion",), "source_scope": "legacy", "target_scope": "legacy", "via_spec_id": spec.id}, evidence_ids=(evidence.id,)))
    if include_related:
        other_identity = SourceArtifactIdentity("openspec", "requirements", "openspec-spec", "d" * 40, "openspec/specs/other/spec.md")
        other_prov = ProvenanceRecord("external", "2026-01-02T03:04:05+00:00", "sha256", "d" * 64, "test", "1", other_identity)
        other_evidence = Evidence(stable_id("evidence", other_identity.id, "durable:other"), "openspec", OpenSpecLocator(other_identity.stable_locator, other_identity.artifact_type, "durable:other", source_artifact_identity=other_identity), provenance_ids=(other_prov.id,))
        other = Node("other-spec", "openspec-spec", "Other", {"capability": "other", "repository_id": "requirements"}, (other_evidence.id,))
        nodes.append(other)
        evidences.append(other_evidence)
        provenances.append(other_prov)
        edges.append(Edge("legacy-related", "openspec-related-spec", spec.id, other.id, {"related_title": "Other"}, evidence_ids=(evidence.id,)))
    return {
        "catalog_revision": CATALOG_REVISION,
        "nodes": {item.id: item.as_dict() for item in nodes}, "node_order": [item.id for item in nodes],
        "edges": {item.id: item.as_dict() for item in edges}, "edge_order": [item.id for item in edges],
        "evidence": {item.id: item.as_dict() for item in evidences}, "evidence_order": [item.id for item in evidences],
        "provenance": {item.id: item.as_dict() for item in provenances}, "provenance_order": [item.id for item in provenances],
    }


def _legacy_document_with_embedded_provenance(*, retain_association=True, conflict=False):
    document = _legacy_openspec_document()
    evidence_id = document["evidence_order"][0]
    evidence = document["evidence"][evidence_id]
    provenance_id = evidence["provenance_ids"][0]
    provenance = document["provenance"][provenance_id]
    identity = provenance["source_artifact_identity"]
    evidence["locator"].pop("source_artifact_identity")
    evidence["properties"].update({
        "source_artifact_identity": identity,
        "provenance": {
            "observed_at": provenance["observed_at"],
            "content_hash_algorithm": provenance["content_hash_algorithm"],
            "content_hash": "c" * 64 if conflict else provenance["content_hash"],
            "extractor_id": provenance["extractor_id"],
            "extractor_version": provenance["extractor_version"],
        },
    })
    if not retain_association:
        evidence["provenance_ids"] = []
        del document["provenance"][provenance_id]
        document["provenance_order"].remove(provenance_id)
    return document
