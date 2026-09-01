from __future__ import annotations

import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
FIXTURES = REPO_ROOT / "tests" / "fixtures"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from engineering_kg.ontology import (
    CodeLocator,
    ConfluencePageRef,
    Edge,
    EdgeKind,
    Evidence,
    GraphSnapshot,
    Node,
    NodeKind,
    OpenSpecLocator,
    ProvenanceRecord,
    SourceArtifactIdentity,
    SourceArtifactLocator,
    stable_id,
)
from engineering_kg.persistence import (
    MIGRATION_BACKUP_FILE_NAME,
    PersistenceInitializationError,
    PersistenceIntegrityError,
    PersistenceWriteError,
    initialize_ladybugdb_store,
    migrate_graph_snapshot,
)
from engineering_kg.project import load_workspace_registry


class LadybugDbPersistenceTest(unittest.TestCase):
    def test_repeated_canonical_writes_merge_evidence(self) -> None:
        node_id = stable_id("node", NodeKind.SPECIFICATION, "requirements", "payments")
        node = lambda evidence_id: Node(
            node_id,
            NodeKind.SPECIFICATION,
            "payments",
            {"repository_id": "requirements", "capability": "payments"},
            (evidence_id,),
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "ladybugdb")
            store.write_snapshot(GraphSnapshot(nodes=(node("first"),), evidence=(Evidence("first", "fixture", "one"),)))
            result = store.write_snapshot(GraphSnapshot(nodes=(node("second"),), evidence=(Evidence("second", "fixture", "two"),)))
        self.assertEqual(result.nodes[0].evidence_ids, ("first", "second"))

    def test_migrates_legacy_openspec_records_and_preserves_backup(self) -> None:
        legacy_spec = Node("legacy-spec", "openspec-spec", "Payments", {"capability": "payments", "repository_id": "requirements"}, ("spec-evidence",))
        legacy_requirement = Node("legacy-requirement", "openspec-requirement", "Payment is submitted", {"capability": "payments"}, ("requirement-evidence",))
        legacy_edge = Edge("legacy-edge", "openspec-spec-contains-requirement", legacy_spec.id, legacy_requirement.id, evidence_ids=("requirement-evidence",))
        snapshot = GraphSnapshot((legacy_spec, legacy_requirement), (legacy_edge,), (Evidence("spec-evidence", "fixture", "spec.md"), Evidence("requirement-evidence", "fixture", "spec.md")))
        migrated = migrate_graph_snapshot(snapshot)
        self.assertTrue(migrated.migrated)
        self.assertEqual({node.kind for node in migrated.snapshot.nodes}, {NodeKind.SPECIFICATION, NodeKind.REQUIREMENT})
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "ladybugdb")
            store._write_raw({"node_order": [item.id for item in snapshot.nodes], "nodes": {item.id: item.as_dict() for item in snapshot.nodes}, "edge_order": [legacy_edge.id], "edges": {legacy_edge.id: legacy_edge.as_dict()}, "evidence_order": [item.id for item in snapshot.evidence], "evidence": {item.id: item.as_dict() for item in snapshot.evidence}})
            self.assertEqual(store.read_snapshot().node_count, 2)
            self.assertTrue((store.path / MIGRATION_BACKUP_FILE_NAME).is_file())

    def test_migrates_sufficient_legacy_openspec_evidence_and_rewrites_references(self) -> None:
        node = Node("node", NodeKind.OPENSPEC_ACTIVE_CHANGE, "change", evidence_ids=("legacy-evidence",))
        legacy = Evidence(
            "legacy-evidence", "openspec",
            OpenSpecLocator("openspec/changes/change/proposal.md", "openspec-artifact", "active-change:change"),
            {"source_artifact_identity": {
                "source_type": "openspec", "source_identity": "requirements",
                "artifact_type": "openspec-artifact", "revision_or_version": "a" * 40,
                "stable_locator": "openspec/changes/change/proposal.md",
            }, "provenance": _legacy_external_provenance()},
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "ladybugdb")
            store._write_raw({"node_order": [node.id], "nodes": {node.id: node.as_dict()}, "edge_order": [], "edges": {}, "evidence_order": [legacy.id], "evidence": {legacy.id: legacy.as_dict()}})
            result = store.migrate_persisted_snapshot()
        self.assertTrue(result.migrated)
        self.assertEqual(result.snapshot.nodes[0].id, node.id)
        self.assertNotEqual(result.snapshot.nodes[0].evidence_ids, node.evidence_ids)
        self.assertIsNotNone(result.snapshot.evidence[0].locator.source_artifact_identity)

    def test_migrates_sufficient_legacy_non_openspec_authoritative_evidence(self) -> None:
        identity_fields = {
            "source_type": "bitbucket", "source_identity": "payments",
            "artifact_type": "pull-request", "revision_or_version": "abc123",
            "stable_locator": "pull-requests/7",
        }
        node = Node("canonical-node", NodeKind.REPOSITORY, "payments", evidence_ids=("legacy",))
        edge = Edge("canonical-edge", EdgeKind.CONTAINS, node.id, node.id, evidence_ids=("legacy",))
        legacy = Evidence("legacy", "bitbucket", "legacy-pr-7", {
            "source_artifact_identity": identity_fields,
            "provenance": _legacy_external_provenance(),
        })

        migrated = migrate_graph_snapshot(
            GraphSnapshot((node,), (edge,), (legacy,), allow_legacy_evidence=True)
        ).snapshot

        identity = SourceArtifactIdentity(**identity_fields)
        evidence = migrated.evidence[0]
        self.assertEqual(evidence.id, stable_id("evidence", identity.id))
        self.assertEqual(evidence.locator, SourceArtifactLocator(identity))
        self.assertEqual(migrated.nodes[0].id, node.id)
        self.assertEqual(migrated.edges[0].id, edge.id)
        self.assertEqual(migrated.nodes[0].evidence_ids, (evidence.id,))
        self.assertEqual(migrated.edges[0].evidence_ids, (evidence.id,))

    def test_complete_legacy_migration_retains_only_provenance_association_on_readback(self) -> None:
        identity_fields = {
            "source_type": "bitbucket", "source_identity": "payments",
            "artifact_type": "pull-request", "revision_or_version": "abc123",
            "stable_locator": "pull-requests/7",
        }
        legacy = Evidence("legacy", "bitbucket", "legacy-pr-7", {
            "source_artifact_identity": identity_fields,
            "provenance": _legacy_external_provenance(),
        })
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "ladybugdb")
            store._write_raw({
                "node_order": [], "nodes": {}, "edge_order": [], "edges": {},
                "evidence_order": [legacy.id], "evidence": {legacy.id: legacy.as_dict()},
            })
            readback = store.read_snapshot()
            persisted = store._graph_file.read_text(encoding="utf-8")

        self.assertEqual(readback.evidence[0].properties, {})
        self.assertEqual(readback.evidence[0].provenance_ids, (readback.provenance[0].id,))
        persisted_evidence = json.loads(persisted)["evidence"][readback.evidence[0].id]
        self.assertEqual(persisted_evidence["properties"], {})
        self.assertNotIn("provenance", persisted_evidence)
        self.assertNotIn("legacy-pr-7", persisted)

    def test_coalesces_equivalent_legacy_evidence_with_the_same_migrated_id(self) -> None:
        identity_fields = {
            "source_type": "openspec", "source_identity": "requirements",
            "artifact_type": "openspec-artifact", "revision_or_version": "a" * 40,
            "stable_locator": "openspec/changes/change/proposal.md",
        }
        first = Evidence(
            "legacy-first", "openspec",
            OpenSpecLocator("openspec/changes/change/proposal.md", "openspec-artifact", "active-change:change"),
            {"source_artifact_identity": identity_fields, "provenance": _legacy_external_provenance()},
        )
        second = Evidence(
            "legacy-second", "openspec",
            OpenSpecLocator("openspec/changes/change/proposal.md", "openspec-artifact", "active-change:change"),
            {"source_artifact_identity": identity_fields, "provenance": _legacy_external_provenance()},
        )
        node = Node("node", NodeKind.OPENSPEC_ACTIVE_CHANGE, "change", evidence_ids=(first.id, second.id))
        edge = Edge("edge", EdgeKind.CONTAINS, node.id, node.id, evidence_ids=(second.id, first.id))

        migrated = migrate_graph_snapshot(
            GraphSnapshot((node,), (edge,), (second, first), allow_legacy_evidence=True)
        ).snapshot
        reverse_migrated = migrate_graph_snapshot(
            GraphSnapshot((node,), (edge,), (first, second), allow_legacy_evidence=True)
        ).snapshot

        self.assertEqual(migrated.evidence_count, 1)
        migrated_evidence_id = migrated.evidence[0].id
        self.assertEqual(migrated.nodes[0].evidence_ids, (migrated_evidence_id,))
        self.assertEqual(migrated.edges[0].evidence_ids, (migrated_evidence_id,))
        self.assertEqual(migrated.as_json(), reverse_migrated.as_json())

    def test_rejects_ambiguous_legacy_openspec_evidence_without_path_inference(self) -> None:
        snapshot = GraphSnapshot(evidence=(
            Evidence("legacy", "openspec", OpenSpecLocator("/tmp/spec.md", "openspec-spec", "durable:payments")),
        ), allow_legacy_evidence=True)
        with self.assertRaisesRegex(PersistenceIntegrityError, "legacy-source-artifact-identity"):
            migrate_graph_snapshot(snapshot)

    def test_rejects_legacy_evidence_without_retained_provenance(self) -> None:
        identity_fields = {
            "source_type": "openspec", "source_identity": "requirements",
            "artifact_type": "openspec-spec", "revision_or_version": "a" * 40,
            "stable_locator": "openspec/specs/payments/spec.md",
        }
        legacy = Evidence(
            "legacy", "openspec",
            OpenSpecLocator("openspec/specs/payments/spec.md", "openspec-spec", "durable:payments"),
            {"source_artifact_identity": identity_fields},
        )
        with self.assertRaisesRegex(PersistenceIntegrityError, "legacy-provenance"):
            migrate_graph_snapshot(GraphSnapshot(evidence=(legacy,), allow_legacy_evidence=True))

    def test_readback_rejects_openspec_locator_identity_disagreement(self) -> None:
        identity = SourceArtifactIdentity(
            "openspec", "requirements", "openspec-spec", "a" * 40,
            "openspec/specs/payments/spec.md",
        )
        raw_evidence = {
            "id": stable_id("evidence", identity.id, "durable:payments"),
            "source": "openspec",
            "locator": {
                "artifact_type": "openspec-change",
                "openspec_identity": "durable:payments",
                "relative_file_path": identity.stable_locator,
                "source_artifact_identity": identity.as_dict(),
            },
            "properties": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "ladybugdb")
            store._write_raw({
                "node_order": [], "nodes": {}, "edge_order": [], "edges": {},
                "evidence_order": [raw_evidence["id"]],
                "evidence": {raw_evidence["id"]: raw_evidence},
            })
            with self.assertRaisesRegex(PersistenceIntegrityError, "artifact_type does not match"):
                store.read_snapshot()

    def test_readback_rejects_unknown_or_payload_fields_in_openspec_locator_mappings(self) -> None:
        identity = SourceArtifactIdentity(
            "openspec", "requirements", "openspec-spec", "a" * 40,
            "openspec/specs/payments/spec.md",
        )
        evidence = Evidence(
            stable_id("evidence", identity.id, "durable:payments"), "openspec",
            OpenSpecLocator(
                identity.stable_locator, identity.artifact_type, "durable:payments",
                source_artifact_identity=identity,
            ),
        )
        for mapping_name, field in (
            ("locator", "content"),
            ("locator", "provider_payload"),
            ("source_artifact_identity", "content"),
            ("source_artifact_identity", "provider_payload"),
        ):
            raw_evidence = evidence.as_dict()
            target = raw_evidence["locator"]
            if mapping_name == "source_artifact_identity":
                target = target[mapping_name]
            target[field] = "unretained source body"
            with self.subTest(mapping=mapping_name, field=field), tempfile.TemporaryDirectory() as tmp:
                store = initialize_ladybugdb_store(Path(tmp) / "ladybugdb")
                store._write_raw({
                    "node_order": [], "nodes": {}, "edge_order": [], "edges": {},
                    "evidence_order": [evidence.id], "evidence": {evidence.id: raw_evidence},
                })
                with self.assertRaisesRegex(
                    PersistenceIntegrityError,
                    f"{mapping_name if mapping_name == 'locator' else f'locator.{mapping_name}'}\\.{field} is not allowed",
                ):
                    store.read_snapshot()

    def test_migration_rewrites_derived_traceability_input_ids_and_is_idempotent(self) -> None:
        legacy_spec = Node("legacy-spec", "openspec-spec", "Payments", {"capability": "payments", "repository_id": "requirements"}, ("e",))
        change = Node("change", NodeKind.OPENSPEC_ACTIVE_CHANGE, "change")
        assertion = Edge("legacy-assertion", "openspec-change-touches-spec", change.id, legacy_spec.id, evidence_ids=("e",))
        trace = Edge("legacy-trace", "openspec-change-traces-to-spec", change.id, legacy_spec.id, {"derived": True, "input_edge_ids": (assertion.id,), "rule_id": "openspec-change-to-durable-spec"}, ("e",))
        migrated = migrate_graph_snapshot(GraphSnapshot((change, legacy_spec), (assertion, trace), (Evidence("e", "fixture", "fixture"),)))
        migrated_assertion = next(edge for edge in migrated.snapshot.edges if edge.kind == EdgeKind.ASSERTS)
        migrated_trace = next(edge for edge in migrated.snapshot.edges if edge.kind == EdgeKind.TRACES_TO)
        self.assertEqual(migrated_trace.properties["input_edge_ids"], (migrated_assertion.id,))
        self.assertFalse(migrate_graph_snapshot(migrated.snapshot).migrated)

    def test_legacy_evidence_migration_preserves_canonical_node_and_edge_ids(self) -> None:
        identity_fields = {
            "source_type": "openspec", "source_identity": "requirements",
            "artifact_type": "openspec-spec", "revision_or_version": "a" * 40,
            "stable_locator": "openspec/specs/payments/spec.md",
        }
        node = Node("canonical-node", NodeKind.REPOSITORY, "requirements", evidence_ids=("legacy",))
        edge = Edge("canonical-edge", EdgeKind.CONTAINS, node.id, node.id, evidence_ids=("legacy",))
        legacy = Evidence(
            "legacy", "openspec",
            OpenSpecLocator("openspec/specs/payments/spec.md", "openspec-spec", "durable:payments"),
            {"source_artifact_identity": identity_fields, "provenance": _legacy_external_provenance()},
        )
        migrated = migrate_graph_snapshot(
            GraphSnapshot((node,), (edge,), (legacy,), allow_legacy_evidence=True)
        ).snapshot
        self.assertEqual(migrated.nodes[0].id, node.id)
        self.assertEqual(migrated.edges[0].id, edge.id)

    def test_migrated_legacy_graph_matches_clean_canonical_rebuild(self) -> None:
        legacy_spec = Node("legacy-spec", "openspec-spec", "Payments", {"capability": "payments", "repository_id": "requirements"}, ("spec-evidence",))
        legacy_requirement = Node("legacy-requirement", "openspec-requirement", "Payment is submitted", {"capability": "payments"}, ("requirement-evidence",))
        legacy_scenario = Node("legacy-scenario", "openspec-scenario", "Valid payment", {"capability": "payments"}, ("scenario-evidence",))
        change = Node("change", NodeKind.OPENSPEC_ACTIVE_CHANGE, "add-payments", {"change_identity": "add-payments"}, ("change-evidence",))
        legacy_assertion = Edge("legacy-assertion", "openspec-change-touches-spec", change.id, legacy_spec.id, evidence_ids=("spec-evidence",))
        legacy_graph = GraphSnapshot(
            (legacy_spec, legacy_requirement, legacy_scenario, change),
            (
                Edge("legacy-contains-requirement", "openspec-spec-contains-requirement", legacy_spec.id, legacy_requirement.id, evidence_ids=("requirement-evidence",)),
                Edge("legacy-contains-scenario", "openspec-requirement-contains-scenario", legacy_requirement.id, legacy_scenario.id, evidence_ids=("scenario-evidence",)),
                legacy_assertion,
            ),
            tuple(Evidence(item, "fixture", "fixture") for item in ("spec-evidence", "requirement-evidence", "scenario-evidence", "change-evidence")),
        )
        migrated = migrate_graph_snapshot(legacy_graph).snapshot
        specification = next(node for node in migrated.nodes if node.kind == NodeKind.SPECIFICATION)
        requirement = next(node for node in migrated.nodes if node.kind == NodeKind.REQUIREMENT)
        scenario = next(node for node in migrated.nodes if node.kind == NodeKind.SCENARIO)
        clean_rebuild = GraphSnapshot(
            (specification, requirement, scenario, change),
            (
                Edge(stable_id("edge", EdgeKind.CONTAINS, specification.id, requirement.id, "spec-requirement", "specification-requirement"), EdgeKind.CONTAINS, specification.id, requirement.id, evidence_ids=("requirement-evidence",)),
                Edge(stable_id("edge", EdgeKind.CONTAINS, requirement.id, scenario.id, "requirement-scenario", "requirement-scenario"), EdgeKind.CONTAINS, requirement.id, scenario.id, evidence_ids=("scenario-evidence",)),
                Edge(stable_id("edge", EdgeKind.ASSERTS, change.id, specification.id, "openspec-change-specification", "add-payments", "payments"), EdgeKind.ASSERTS, change.id, specification.id, evidence_ids=("spec-evidence",)),
            ),
            legacy_graph.evidence,
        )
        self.assertEqual(migrated.as_json(), clean_rebuild.as_json())

    def test_migration_rejects_conflicting_canonical_records(self) -> None:
        legacy_spec = Node("legacy-spec", "openspec-spec", "Payments", {"capability": "payments", "repository_id": "requirements"})
        conflicting = Node(
            stable_id("node", NodeKind.SPECIFICATION, "requirements", "payments"),
            NodeKind.REQUIREMENT,
            "Conflicting requirement",
        )
        with self.assertRaises(PersistenceIntegrityError):
            migrate_graph_snapshot(GraphSnapshot(nodes=(legacy_spec, conflicting)))

    def test_migration_write_failure_preserves_graph_and_backup(self) -> None:
        legacy_spec = Node("legacy-spec", "openspec-spec", "Payments", {"capability": "payments", "repository_id": "requirements"}, ("e",))
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "ladybugdb")
            store._write_raw({"node_order": [legacy_spec.id], "nodes": {legacy_spec.id: legacy_spec.as_dict()}, "edge_order": [], "edges": {}, "evidence_order": ["e"], "evidence": {"e": Evidence("e", "fixture", "fixture").as_dict()}})
            original = store._graph_file.read_text(encoding="utf-8")
            with mock.patch("engineering_kg.persistence.os.replace", side_effect=OSError("disk full")):
                with self.assertRaises(PersistenceWriteError):
                    store.migrate_persisted_snapshot()
            self.assertEqual(store._graph_file.read_text(encoding="utf-8"), original)
            self.assertTrue((store.path / MIGRATION_BACKUP_FILE_NAME).is_file())

    def test_invalid_migration_preserves_original_snapshot(self) -> None:
        legacy_spec = Node(
            "legacy-spec",
            "openspec-spec",
            "Payments",
            {"capability": "payments", "repository_id": "requirements"},
            ("e",),
        )
        repository = Node("repository", NodeKind.REPOSITORY, "requirements")
        assertion = Edge("assertion", EdgeKind.ASSERTS, repository.id, legacy_spec.id, evidence_ids=("e",))
        snapshot = GraphSnapshot(
            (legacy_spec, repository),
            (assertion,),
            (Evidence("e", "fixture", "fixture"),),
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "ladybugdb")
            store._write_raw({
                "node_order": [item.id for item in snapshot.nodes],
                "nodes": {item.id: item.as_dict() for item in snapshot.nodes},
                "edge_order": [item.id for item in snapshot.edges],
                "edges": {item.id: item.as_dict() for item in snapshot.edges},
                "evidence_order": [item.id for item in snapshot.evidence],
                "evidence": {item.id: item.as_dict() for item in snapshot.evidence},
            })
            original = store._graph_file.read_text(encoding="utf-8")
            with self.assertRaises(PersistenceIntegrityError):
                store.migrate_persisted_snapshot()
            self.assertEqual(store._graph_file.read_text(encoding="utf-8"), original)
            self.assertFalse((store.path / MIGRATION_BACKUP_FILE_NAME).exists())

    def test_empty_store_initializes_and_reads_empty_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "ladybugdb")

            snapshot = store.read_snapshot()

        self.assertEqual(snapshot.as_dict(), GraphSnapshot().as_dict())

    def test_registry_graph_snapshot_persists_and_reads_back(self) -> None:
        registry = load_workspace_registry(FIXTURES / "repo-index.yaml")
        graph = registry.to_graph_snapshot()

        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "ladybugdb")
            readback = store.write_snapshot(graph)

            self.assertEqual(readback.as_dict(), graph.as_dict())
            self.assertEqual(store.read_snapshot().as_dict(), graph.as_dict())

    def test_repeated_writes_do_not_duplicate_graph_objects(self) -> None:
        graph = load_workspace_registry(FIXTURES / "repo-index.yaml").to_graph_snapshot()

        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "ladybugdb")
            first = store.write_snapshot(graph).as_dict()
            second = store.write_snapshot(graph).as_dict()

        self.assertEqual(second, first)
        self.assertEqual(second["node_count"], graph.node_count)
        self.assertEqual(second["edge_count"], graph.edge_count)
        self.assertEqual(second["evidence_count"], graph.evidence_count)

    def test_evidence_locators_persist_and_read_back(self) -> None:
        node = Node(
            id=stable_id("node", NodeKind.REPOSITORY, "payment-service"),
            kind=NodeKind.REPOSITORY,
            name="payment-service",
        )
        edge = Edge(
            id=stable_id("edge", EdgeKind.REFERENCES_CODE, node.id, "create_payment"),
            kind=EdgeKind.REFERENCES_CODE,
            source_id=node.id,
            target_id=node.id,
        )
        confluence_identity = SourceArtifactIdentity(
            "confluence", "engineering-wiki", "page", "123", "pages/123456789"
        )
        confluence_provenance = _external_provenance(confluence_identity)
        evidence = (
            Evidence(
                id=stable_id("evidence", "repo-index", "payment-service"),
                source="repo-index",
                locator="repo-index.yaml",
            ),
            Evidence(
                id=stable_id("evidence", "openlore", "payment-service", "create_payment"),
                source="openlore",
                locator=CodeLocator(
                    repository="payment-service",
                    revision="abc123",
                    file="src/app.py",
                    symbol="create_payment",
                ),
            ),
            Evidence(
                id=stable_id("evidence", confluence_identity.id),
                source="confluence",
                locator=SourceArtifactLocator(confluence_identity),
                provenance_ids=(confluence_provenance.id,),
            ),
        )
        graph = GraphSnapshot(nodes=(node,), edges=(edge,), evidence=evidence, provenance=(confluence_provenance,))

        with tempfile.TemporaryDirectory() as tmp:
            readback = initialize_ladybugdb_store(Path(tmp) / "ladybugdb").write_snapshot(graph)

        self.assertEqual(readback.as_dict(), graph.as_dict())

    def test_persistence_rejects_forbidden_external_payload_fields(self) -> None:
        graph = GraphSnapshot(
            nodes=(
                Node(
                    id=stable_id("node", NodeKind.REPOSITORY, "payment-service"),
                    kind=NodeKind.REPOSITORY,
                    name="payment-service",
                    properties={"source_code": "def create_payment(): pass"},
                ),
            )
        )

        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "ladybugdb")
            with self.assertRaises(PersistenceIntegrityError):
                store.write_snapshot(graph)

    def test_persistence_readback_rejects_source_evidence_body_metadata(self) -> None:
        identity = SourceArtifactIdentity(
            "bitbucket", "payments", "pull-request", "abc", "pull-requests/7"
        )
        evidence = Evidence(
            stable_id("evidence", identity.id), "bitbucket", SourceArtifactLocator(identity)
        )
        raw_evidence = evidence.as_dict()
        raw_evidence["properties"] = {"provider_payload": "full provider response body"}
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "ladybugdb")
            store._write_raw({
                "node_order": [], "nodes": {}, "edge_order": [], "edges": {},
                "evidence_order": [evidence.id], "evidence": {evidence.id: raw_evidence},
            })
            with self.assertRaisesRegex(PersistenceIntegrityError, "invalid-source-artifact-identity"):
                store.read_snapshot()

    def test_persistence_readback_rejects_payload_body_and_content_identity_values(self) -> None:
        identity = SourceArtifactIdentity(
            "bitbucket", "payments", "pull-request", "abc", "pull-requests/7"
        )
        evidence = Evidence(
            stable_id("evidence", identity.id), "bitbucket", SourceArtifactLocator(identity)
        )
        for unsafe_value in ("provider payload", "full source body", "artifact content"):
            for field in (
                "source_type", "source_identity", "artifact_type", "revision_or_version", "stable_locator"
            ):
                raw_evidence = evidence.as_dict()
                raw_evidence["locator"]["source_artifact_identity"][field] = unsafe_value
                with self.subTest(field=field, value=unsafe_value), tempfile.TemporaryDirectory() as tmp:
                    store = initialize_ladybugdb_store(Path(tmp) / "ladybugdb")
                    store._write_raw({
                        "node_order": [], "nodes": {}, "edge_order": [], "edges": {},
                        "evidence_order": [evidence.id], "evidence": {evidence.id: raw_evidence},
                    })
                    with self.assertRaisesRegex(
                        PersistenceIntegrityError, f"{field} contains unsafe content"
                    ):
                        store.read_snapshot()

    def test_persistence_coalesces_equivalent_external_evidence_and_rejects_identityless_external_evidence(self) -> None:
        identity = SourceArtifactIdentity("bitbucket", "payments", "pull-request", "abc", "pull-requests/7")
        provenance = _external_provenance(identity)
        evidence = Evidence(stable_id("evidence", identity.id), "bitbucket", SourceArtifactLocator(identity), provenance_ids=(provenance.id,))
        conflicting = Evidence(
            evidence.id, "bitbucket", SourceArtifactLocator(identity, {"pull_request_id": "other"}), provenance_ids=(provenance.id,)
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "ladybugdb")
            first = store.write_snapshot(GraphSnapshot(evidence=(evidence,), provenance=(provenance,)))
            second = store.write_snapshot(GraphSnapshot(evidence=(evidence,), provenance=(provenance,)))
            self.assertEqual(second.as_dict(), first.as_dict())
            with self.assertRaisesRegex(ValueError, "explicit source-artifact identity"):
                store.write_snapshot(GraphSnapshot(evidence=(Evidence("external", "confluence", "123"),)))
        for first, second in ((evidence, conflicting), (conflicting, evidence)):
            with tempfile.TemporaryDirectory() as tmp:
                store = initialize_ladybugdb_store(Path(tmp) / "ladybugdb")
                store.write_snapshot(GraphSnapshot(evidence=(first,), provenance=(provenance,)))
                with self.assertRaisesRegex(PersistenceIntegrityError, "Conflicting graph record values"):
                    store.write_snapshot(GraphSnapshot(evidence=(second,), provenance=(provenance,)))

    def test_persisted_readback_excludes_code_and_external_payloads(self) -> None:
        confluence_identity = SourceArtifactIdentity(
            "confluence", "engineering-wiki", "page", "123", "pages/123456789"
        )
        confluence_provenance = _external_provenance(confluence_identity)
        graph = GraphSnapshot(
            evidence=(
                Evidence(
                    id=stable_id("evidence", "openlore", "payment-service", "create_payment"),
                    source="openlore",
                    locator=CodeLocator(
                        repository="payment-service",
                        revision="abc123",
                        file="src/app.py",
                        symbol="create_payment",
                    ),
                ),
                Evidence(
                    id=stable_id("evidence", confluence_identity.id),
                    source="confluence",
                    locator=SourceArtifactLocator(confluence_identity),
                    provenance_ids=(confluence_provenance.id,),
                ),
            ), provenance=(confluence_provenance,)
        )

        with tempfile.TemporaryDirectory() as tmp:
            readback = initialize_ladybugdb_store(Path(tmp) / "ladybugdb").write_snapshot(graph)

        serialized = str(readback.as_dict())
        for forbidden in (
            "source_code",
            "call_graph",
            "dependency_graph",
            "class_body",
            "function_body",
            "page_content",
            "credentials",
            "token",
            "api_response",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_invalid_storage_path_fails_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "not-a-directory"
            file_path.write_text("not a directory", encoding="utf-8")

            with self.assertRaises(PersistenceInitializationError):
                initialize_ladybugdb_store(file_path)


if __name__ == "__main__":
    unittest.main()


def _legacy_external_provenance() -> dict[str, str]:
    return {
        "observed_at": "2026-01-02T03:04:05+00:00",
        "content_hash_algorithm": "sha256",
        "content_hash": "a" * 64,
        "extractor_id": "legacy-test-extractor",
        "extractor_version": "1",
    }


def _external_provenance(identity: SourceArtifactIdentity) -> ProvenanceRecord:
    return ProvenanceRecord(
        "external", "2026-01-02T03:04:05+00:00", "sha256", "a" * 64,
        "test-extractor", "1", identity,
    )
