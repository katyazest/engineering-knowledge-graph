"""Local persistence boundary for canonical Engineering KG graph snapshots.

The confirmed local LadybugDB dependency is the Node package
``@ladybugdb/core``. The Python runner keeps persistence isolated so a Node
bridge or Python binding can replace this local adapter without changing
pipeline stages or scripts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engineering_kg.ontology import (
    CodeLocator,
    ConfluencePageRef,
    Edge,
    Evidence,
    GraphSnapshot,
    Node,
)


GRAPH_FILE_NAME = "graph.json"

FORBIDDEN_PERSISTENCE_FIELDS = frozenset(
    {
        "api_response",
        "attachments",
        "call_graph",
        "class_body",
        "comments",
        "content",
        "credentials",
        "dependency_graph",
        "external_api_response",
        "function_body",
        "openlore_analysis",
        "page_content",
        "page_url",
        "source_code",
        "token",
        "tokens",
        "url",
    }
)


class PersistenceError(RuntimeError):
    """Base class for local Engineering KG persistence failures."""


class PersistenceInitializationError(PersistenceError):
    """Raised when a local graph store cannot be created or opened."""


class PersistenceWriteError(PersistenceError):
    """Raised when a canonical graph snapshot cannot be written."""


class PersistenceReadError(PersistenceError):
    """Raised when a local graph store cannot be read."""


class PersistenceIntegrityError(PersistenceError):
    """Raised when persisted graph data cannot be reconstructed safely."""


@dataclass(frozen=True)
class LadybugDbStore:
    """Adapter-shaped local graph store for canonical Engineering KG snapshots."""

    path: Path

    @classmethod
    def initialize(cls, path: str | Path) -> "LadybugDbStore":
        store_path = Path(path).expanduser().resolve()
        try:
            if store_path.exists() and not store_path.is_dir():
                raise PersistenceInitializationError(
                    f"Persistence path is not a directory: {store_path}"
                )
            store_path.mkdir(parents=True, exist_ok=True)
            store = cls(path=store_path)
            if not store._graph_file.exists():
                store._write_raw(_empty_graph_data())
            return store
        except PersistenceInitializationError:
            raise
        except OSError as exc:
            raise PersistenceInitializationError(
                f"Cannot initialize persistence store at {store_path}: {exc}"
            ) from exc

    @property
    def _graph_file(self) -> Path:
        return self.path / GRAPH_FILE_NAME

    def write_snapshot(self, snapshot: GraphSnapshot) -> GraphSnapshot:
        try:
            _validate_snapshot(snapshot)
            current = self._read_raw()
            merged = _merge_snapshot(current, snapshot)
            self._write_raw(merged)
            return self.read_snapshot()
        except PersistenceError:
            raise
        except OSError as exc:
            raise PersistenceWriteError(f"Cannot write graph snapshot: {exc}") from exc

    def read_snapshot(self) -> GraphSnapshot:
        try:
            return _snapshot_from_data(self._read_raw())
        except PersistenceError:
            raise
        except OSError as exc:
            raise PersistenceReadError(f"Cannot read graph snapshot: {exc}") from exc

    def _read_raw(self) -> dict[str, Any]:
        if not self._graph_file.exists():
            return _empty_graph_data()
        with self._graph_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise PersistenceIntegrityError("Persisted graph root must be a mapping")
        return data

    def _write_raw(self, data: dict[str, Any]) -> None:
        with self._graph_file.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")


def initialize_ladybugdb_store(path: str | Path) -> LadybugDbStore:
    """Initialize the local Engineering KG persistence store."""

    return LadybugDbStore.initialize(path)


def persist_graph_snapshot(path: str | Path, snapshot: GraphSnapshot) -> GraphSnapshot:
    """Persist a canonical graph snapshot and return deterministic readback."""

    return initialize_ladybugdb_store(path).write_snapshot(snapshot)


def read_graph_snapshot(path: str | Path) -> GraphSnapshot:
    """Read a persisted canonical graph snapshot from local storage."""

    return initialize_ladybugdb_store(path).read_snapshot()


def _empty_graph_data() -> dict[str, dict[str, Any]]:
    return {
        "edge_order": [],
        "edges": {},
        "evidence": {},
        "evidence_order": [],
        "node_order": [],
        "nodes": {},
    }


def _merge_snapshot(data: dict[str, Any], snapshot: GraphSnapshot) -> dict[str, Any]:
    merged = {
        "edge_order": list(_expect_string_tuple(data.get("edge_order", []), "edge_order")),
        "edges": dict(_expect_mapping(data.get("edges", {}), "edges")),
        "evidence": dict(_expect_mapping(data.get("evidence", {}), "evidence")),
        "evidence_order": list(
            _expect_string_tuple(data.get("evidence_order", []), "evidence_order")
        ),
        "node_order": list(_expect_string_tuple(data.get("node_order", []), "node_order")),
        "nodes": dict(_expect_mapping(data.get("nodes", {}), "nodes")),
    }

    for node in snapshot.nodes:
        merged["nodes"][node.id] = node.as_dict()
        if node.id not in merged["node_order"]:
            merged["node_order"].append(node.id)
    for edge in snapshot.edges:
        merged["edges"][edge.id] = edge.as_dict()
        if edge.id not in merged["edge_order"]:
            merged["edge_order"].append(edge.id)
    for evidence in snapshot.evidence:
        merged["evidence"][evidence.id] = evidence.as_dict()
        if evidence.id not in merged["evidence_order"]:
            merged["evidence_order"].append(evidence.id)

    return merged


def _snapshot_from_data(data: dict[str, Any]) -> GraphSnapshot:
    nodes = tuple(
        _node_from_dict(item)
        for item in _ordered_records(
            _expect_mapping(data.get("nodes", {}), "nodes"),
            _expect_string_tuple(data.get("node_order", []), "node_order"),
        )
    )
    edges = tuple(
        _edge_from_dict(item)
        for item in _ordered_records(
            _expect_mapping(data.get("edges", {}), "edges"),
            _expect_string_tuple(data.get("edge_order", []), "edge_order"),
        )
    )
    evidence = tuple(
        _evidence_from_dict(item)
        for item in _ordered_records(
            _expect_mapping(data.get("evidence", {}), "evidence"),
            _expect_string_tuple(data.get("evidence_order", []), "evidence_order"),
        )
    )
    snapshot = GraphSnapshot(nodes=nodes, edges=edges, evidence=evidence)
    _validate_snapshot(snapshot)
    return snapshot


def _ordered_records(records: dict[str, Any], order: tuple[str, ...]) -> list[dict[str, Any]]:
    if not order:
        order = tuple(sorted(records))
    missing = set(records) - set(order)
    if missing:
        order = (*order, *tuple(sorted(missing)))
    values = []
    for record_id in order:
        if record_id not in records:
            raise PersistenceIntegrityError(f"Persisted record order references unknown id: {record_id}")
        record = _expect_mapping(records[record_id], record_id)
        if record.get("id") != record_id:
            raise PersistenceIntegrityError(f"Persisted record id mismatch: {record_id}")
        values.append(record)
    return values


def _node_from_dict(data: dict[str, Any]) -> Node:
    return Node(
        id=_expect_string(data.get("id"), "node.id"),
        kind=_expect_string(data.get("kind"), "node.kind"),
        name=_expect_string(data.get("name"), "node.name"),
        properties=dict(_expect_mapping(data.get("properties", {}), "node.properties")),
        evidence_ids=tuple(_expect_string_tuple(data.get("evidence_ids", []), "node.evidence_ids")),
    )


def _edge_from_dict(data: dict[str, Any]) -> Edge:
    return Edge(
        id=_expect_string(data.get("id"), "edge.id"),
        kind=_expect_string(data.get("kind"), "edge.kind"),
        source_id=_expect_string(data.get("source_id"), "edge.source_id"),
        target_id=_expect_string(data.get("target_id"), "edge.target_id"),
        properties=dict(_expect_mapping(data.get("properties", {}), "edge.properties")),
        evidence_ids=tuple(_expect_string_tuple(data.get("evidence_ids", []), "edge.evidence_ids")),
    )


def _evidence_from_dict(data: dict[str, Any]) -> Evidence:
    return Evidence(
        id=_expect_string(data.get("id"), "evidence.id"),
        source=_expect_string(data.get("source"), "evidence.source"),
        locator=_locator_from_value(data.get("locator")),
        properties=dict(_expect_mapping(data.get("properties", {}), "evidence.properties")),
    )


def _locator_from_value(value: Any) -> str | CodeLocator | ConfluencePageRef:
    if isinstance(value, str):
        return value
    data = _expect_mapping(value, "evidence.locator")
    keys = set(data)
    if keys == {"file", "repository", "revision", "symbol"}:
        return CodeLocator(
            repository=_expect_string(data["repository"], "locator.repository"),
            revision=_expect_string(data["revision"], "locator.revision"),
            file=_expect_string(data["file"], "locator.file"),
            symbol=_expect_string(data["symbol"], "locator.symbol"),
        )
    if keys == {"page_id"}:
        return ConfluencePageRef(page_id=_expect_string(data["page_id"], "locator.page_id"))
    raise PersistenceIntegrityError(f"Unsupported evidence locator shape: {sorted(keys)}")


def _validate_snapshot(snapshot: GraphSnapshot) -> None:
    _reject_forbidden_fields(snapshot.as_dict())


def _reject_forbidden_fields(value: Any, path: str = "graph") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_PERSISTENCE_FIELDS:
                raise PersistenceIntegrityError(f"{path}.{key_text} is not allowed in persistence")
            _reject_forbidden_fields(nested, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_forbidden_fields(item, f"{path}[{index}]")


def _expect_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PersistenceIntegrityError(f"{context} must be a mapping")
    return value


def _expect_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersistenceIntegrityError(f"{context} must be a non-empty string")
    return value


def _expect_string_tuple(value: Any, context: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise PersistenceIntegrityError(f"{context} must be a list")
    return tuple(_expect_string(item, f"{context}[]") for item in value)
