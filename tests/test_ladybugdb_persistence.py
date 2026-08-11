from __future__ import annotations

import tempfile
import unittest
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
    PersistenceInitializationError,
    PersistenceIntegrityError,
    initialize_ladybugdb_store,
)
from engineering_kg.project import load_workspace_registry


class LadybugDbPersistenceTest(unittest.TestCase):
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
