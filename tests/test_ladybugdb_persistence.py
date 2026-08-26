from __future__ import annotations

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
            store.write_snapshot(GraphSnapshot(nodes=(node("first"),), evidence=(Evidence("first", "openspec", "one"),)))
            result = store.write_snapshot(GraphSnapshot(nodes=(node("second"),), evidence=(Evidence("second", "openspec", "two"),)))
        self.assertEqual(result.nodes[0].evidence_ids, ("first", "second"))

    def test_migrates_legacy_openspec_records_and_preserves_backup(self) -> None:
        legacy_spec = Node("legacy-spec", "openspec-spec", "Payments", {"capability": "payments", "repository_id": "requirements"}, ("spec-evidence",))
        legacy_requirement = Node("legacy-requirement", "openspec-requirement", "Payment is submitted", {"capability": "payments"}, ("requirement-evidence",))
        legacy_edge = Edge("legacy-edge", "openspec-spec-contains-requirement", legacy_spec.id, legacy_requirement.id, evidence_ids=("requirement-evidence",))
        snapshot = GraphSnapshot((legacy_spec, legacy_requirement), (legacy_edge,), (Evidence("spec-evidence", "openspec", "spec.md"), Evidence("requirement-evidence", "openspec", "spec.md")))
        migrated = migrate_graph_snapshot(snapshot)
        self.assertTrue(migrated.migrated)
        self.assertEqual({node.kind for node in migrated.snapshot.nodes}, {NodeKind.SPECIFICATION, NodeKind.REQUIREMENT})
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "ladybugdb")
            store._write_raw({"node_order": [item.id for item in snapshot.nodes], "nodes": {item.id: item.as_dict() for item in snapshot.nodes}, "edge_order": [legacy_edge.id], "edges": {legacy_edge.id: legacy_edge.as_dict()}, "evidence_order": [item.id for item in snapshot.evidence], "evidence": {item.id: item.as_dict() for item in snapshot.evidence}})
            self.assertEqual(store.read_snapshot().node_count, 2)
            self.assertTrue((store.path / MIGRATION_BACKUP_FILE_NAME).is_file())

    def test_migration_rewrites_derived_traceability_input_ids_and_is_idempotent(self) -> None:
        legacy_spec = Node("legacy-spec", "openspec-spec", "Payments", {"capability": "payments", "repository_id": "requirements"}, ("e",))
        change = Node("change", NodeKind.OPENSPEC_ACTIVE_CHANGE, "change")
        assertion = Edge("legacy-assertion", "openspec-change-touches-spec", change.id, legacy_spec.id, evidence_ids=("e",))
        trace = Edge("legacy-trace", "openspec-change-traces-to-spec", change.id, legacy_spec.id, {"derived": True, "input_edge_ids": (assertion.id,), "rule_id": "openspec-change-to-durable-spec"}, ("e",))
        migrated = migrate_graph_snapshot(GraphSnapshot((change, legacy_spec), (assertion, trace), (Evidence("e", "openspec", "fixture"),)))
        migrated_assertion = next(edge for edge in migrated.snapshot.edges if edge.kind == EdgeKind.ASSERTS)
        migrated_trace = next(edge for edge in migrated.snapshot.edges if edge.kind == EdgeKind.TRACES_TO)
        self.assertEqual(migrated_trace.properties["input_edge_ids"], (migrated_assertion.id,))
        self.assertFalse(migrate_graph_snapshot(migrated.snapshot).migrated)

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
            tuple(Evidence(item, "openspec", "fixture") for item in ("spec-evidence", "requirement-evidence", "scenario-evidence", "change-evidence")),
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
            store._write_raw({"node_order": [legacy_spec.id], "nodes": {legacy_spec.id: legacy_spec.as_dict()}, "edge_order": [], "edges": {}, "evidence_order": ["e"], "evidence": {"e": Evidence("e", "openspec", "fixture").as_dict()}})
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
            (Evidence("e", "openspec", "fixture"),),
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
                id=stable_id("evidence", "confluence", "123456789"),
                source="confluence",
                locator=ConfluencePageRef(page_id="123456789"),
            ),
        )
        graph = GraphSnapshot(nodes=(node,), edges=(edge,), evidence=evidence)

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

    def test_persisted_readback_excludes_code_and_external_payloads(self) -> None:
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
                    id=stable_id("evidence", "confluence", "123456789"),
                    source="confluence",
                    locator=ConfluencePageRef(page_id="123456789"),
                ),
            )
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
