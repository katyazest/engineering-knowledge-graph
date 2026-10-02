"""Local persistence boundary for canonical Engineering KG graph snapshots.

The confirmed local LadybugDB dependency is the Node package
``@ladybugdb/core``. The Python runner keeps persistence isolated so a Node
bridge or Python binding can replace this local adapter without changing
pipeline stages or scripts.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engineering_kg.ontology import (
    GraphSnapshot,
    source_artifact_identity_error,
    verification_payload_error,
    GraphMergeConflict,
    GraphMergeConflictError,
)
from engineering_kg.validation import validate_graph_integrity
from engineering_kg.relationship_vocabulary import CATALOG_REVISION
from engineering_kg.snapshot_codec import (
    CURRENT_SCHEMA_VERSION,
    SnapshotCodecError,
    deserialize_snapshot,
    empty_document,
    serialize_snapshot,
)
from engineering_kg.snapshot_migration import (
    SnapshotMigrationError,
    SnapshotMigrationResult,
    _safe_codec_diagnostic_id,
    _safe_record_id,
    migrate_snapshot_document,
)


GRAPH_FILE_NAME = "graph.json"
ONTOLOGY_SCHEMA_VERSION = CURRENT_SCHEMA_VERSION

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
        "framework",
        "function_body",
        "log",
        "logs",
        "openlore_analysis",
        "outcome",
        "page_content",
        "page_url",
        "source_code",
        "test_output",
        "token",
        "tokens",
        "url",
        "coverage",
        "provider_payload",
        "ci_payload",
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

    def __init__(
        self, message: str, conflicts: tuple[GraphMergeConflict, ...] = ()
    ) -> None:
        self.conflicts = tuple(conflicts)
        super().__init__(message)

    def as_dict(self) -> dict[str, Any]:
        return {
            "conflicts": [
                {
                    **item.as_dict(),
                    "canonical_id": _safe_record_id(item.canonical_id),
                    "contributor_record_ids": [_safe_record_id(value) for value in item.contributor_record_ids],
                    "contributor_evidence_ids": [_safe_record_id(value) for value in item.contributor_evidence_ids],
                    "contributor_provenance_ids": [_safe_record_id(value) for value in item.contributor_provenance_ids],
                }
                for item in self.conflicts
            ],
            "message": str(self),
        }


@dataclass(frozen=True)
class OntologyMigrationResult:
    """Deterministic summary of one persisted ontology migration."""

    snapshot: GraphSnapshot
    migrated_node_count: int = 0
    migrated_edge_count: int = 0
    status: str | None = None
    diagnostics: tuple[str, ...] = ()
    source_version: int | None = None
    source_descriptor: str | None = None
    target_version: int = ONTOLOGY_SCHEMA_VERSION
    applied_migration_ids: tuple[str, ...] = ()
    graph_counts: dict[str, int] | None = None

    @property
    def migrated(self) -> bool:
        return self.status == "migrated" or bool(self.migrated_node_count or self.migrated_edge_count)

    def as_dict(self) -> dict[str, Any]:
        data = {
            "diagnostics": list(self.diagnostics),
            "graph_counts": {
                "edge_count": self.snapshot.edge_count,
                "evidence_count": self.snapshot.evidence_count,
                "node_count": self.snapshot.node_count,
            },
            "migrated_edge_count": self.migrated_edge_count,
            "migrated_node_count": self.migrated_node_count,
            "source_version": self.source_version,
            "source_descriptor": self.source_descriptor,
            "target_version": self.target_version,
            "applied_migration_ids": list(self.applied_migration_ids),
            "status": self.status or ("migrated" if self.migrated else "not-needed"),
        }
        if self.graph_counts is not None:
            data["graph_counts"] = dict(sorted(self.graph_counts.items()))
        return data


@dataclass(frozen=True)
class LadybugDbStore:
    """Adapter-shaped local graph store for canonical Engineering KG snapshots."""

    path: Path

    @classmethod
    def initialize(cls, path: str | Path) -> "LadybugDbStore":
        store_path = Path(path).expanduser().resolve()
        try:
            if store_path.exists() and not store_path.is_dir():
                raise PersistenceInitializationError("Persistence path is not a directory")
            store_path.mkdir(parents=True, exist_ok=True)
            store = cls(path=store_path)
            if not store._graph_file.exists():
                store._write_raw(_empty_graph_data())
            return store
        except PersistenceInitializationError:
            raise
        except OSError as exc:
            raise PersistenceInitializationError("Cannot initialize persistence store") from exc

    @property
    def _graph_file(self) -> Path:
        return self.path / GRAPH_FILE_NAME

    def write_snapshot(self, snapshot: GraphSnapshot) -> GraphSnapshot:
        try:
            if verification_payload_error(snapshot):
                raise PersistenceIntegrityError("verification-payload-boundary")
            source_data = self._read_raw()
            migration = self._run_migration(source_data)
            current_data = migration.document or source_data
            current = _snapshot_from_data(current_data)
            try:
                prospective = current.merged_with(snapshot)
            except GraphMergeConflictError as exc:
                raise PersistenceIntegrityError("Conflicting graph record values: graph-merge-conflict", exc.conflicts) from exc
            except ValueError as exc:
                raise PersistenceIntegrityError(_safe_merge_diagnostic(exc)) from exc
            # Validate the full prospective graph, including constraints that
            # apply across writes, before replacing the persisted snapshot.
            _validate_snapshot(prospective)
            target_data = _snapshot_data(prospective)
            if migration.status == "migrated":
                self._backup_source(source_data, migration)
            self._write_raw(target_data)
            return _snapshot_from_data(target_data)
        except PersistenceError:
            raise
        except OSError as exc:
            raise PersistenceWriteError("Cannot write graph snapshot") from exc

    def read_snapshot(self) -> GraphSnapshot:
        try:
            data = self._migrate_raw_if_needed(self._read_raw())
            return _snapshot_from_data(data)
        except PersistenceError:
            raise
        except OSError as exc:
            raise PersistenceReadError("Cannot read graph snapshot") from exc

    def migrate_persisted_snapshot(self) -> OntologyMigrationResult:
        """Migrate and atomically commit the logical snapshot when required."""

        try:
            data = self._read_raw()
            migration = self._run_migration(data)
            if migration.status == "migrated":
                self._backup_source(data, migration)
                self._write_raw(migration.document or data)
            snapshot = _snapshot_from_data(migration.document or data)
            return _persistence_migration_result(snapshot, migration)
        except PersistenceError:
            raise
        except OSError as exc:
            raise PersistenceWriteError("Cannot migrate persisted graph snapshot") from exc

    def _read_raw(self) -> dict[str, Any]:
        if not self._graph_file.exists():
            return _empty_graph_data()
        with self._graph_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise PersistenceIntegrityError("Persisted graph root must be a mapping")
        return data

    def _write_raw(self, data: dict[str, Any]) -> None:
        temporary = self.path / f"{GRAPH_FILE_NAME}.tmp"
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, self._graph_file)

    def _migrate_raw_if_needed(self, data: dict[str, Any]) -> dict[str, Any]:
        migration = self._run_migration(data)
        if migration.status == "migrated":
            self._backup_source(data, migration)
            self._write_raw(migration.document or data)
        return migration.document or data

    def _run_migration(self, data: dict[str, Any]) -> SnapshotMigrationResult:
        try:
            return migrate_snapshot_document(data)
        except SnapshotMigrationError as exc:
            raise PersistenceIntegrityError(f"{exc.code}: {exc}") from exc

    def _backup_source(self, data: dict[str, Any], result: SnapshotMigrationResult) -> None:
        descriptor = result.source_descriptor or f"v{result.source_version}"
        safe_descriptor = "".join(char if char.isalnum() or char in "._-" else "_" for char in descriptor)
        backup = self.path / f"graph.pre-ontology-migration.{safe_descriptor}.json"
        with self._graph_file.open("rb") as source:
            source_bytes = source.read()
        if backup.exists():
            if backup.read_bytes() != source_bytes:
                raise PersistenceWriteError("Cannot overwrite non-equivalent ontology migration backup")
            return
        temporary = self.path / f"{backup.name}.tmp"
        try:
            temporary.write_bytes(source_bytes)
            os.replace(temporary, backup)
        except OSError as exc:
            if temporary.exists():
                temporary.unlink()
            raise PersistenceWriteError("Cannot create ontology migration backup") from exc


def initialize_ladybugdb_store(path: str | Path) -> LadybugDbStore:
    """Initialize the local Engineering KG persistence store."""

    return LadybugDbStore.initialize(path)


def persist_graph_snapshot(path: str | Path, snapshot: GraphSnapshot) -> GraphSnapshot:
    """Persist a canonical graph snapshot and return deterministic readback."""

    return initialize_ladybugdb_store(path).write_snapshot(snapshot)


def read_graph_snapshot(path: str | Path) -> GraphSnapshot:
    """Read a persisted canonical graph snapshot from local storage."""

    return initialize_ladybugdb_store(path).read_snapshot()


def migrate_graph_snapshot(snapshot: GraphSnapshot) -> OntologyMigrationResult:
    """Verify a current canonical snapshot; historical records are not migrated."""

    for item in snapshot.evidence:
        if error := source_artifact_identity_error(item):
            raise PersistenceIntegrityError(
                f"legacy-evidence-migration-unsupported: {_safe_record_id(item.id)}: {error}"
            )
    try:
        canonical = GraphSnapshot(
            snapshot.nodes, snapshot.edges, snapshot.evidence,
            snapshot.cross_graph_link_claims, snapshot.cross_graph_link_evidence,
            snapshot.cross_graph_link_lifecycle, snapshot.provenance,
            snapshot.pull_request_evidence,
            snapshot.pull_request_declared_associations,
            snapshot.pull_request_observed_repository_relations,
        )
    except ValueError as exc:
        raise PersistenceIntegrityError(str(exc)) from exc
    _validate_snapshot(canonical)
    return OntologyMigrationResult(
        snapshot=canonical,
        status="not-needed",
        source_version=ONTOLOGY_SCHEMA_VERSION,
        target_version=ONTOLOGY_SCHEMA_VERSION,
        graph_counts={
            "edge_count": canonical.edge_count,
            "evidence_count": canonical.evidence_count,
            "node_count": canonical.node_count,
            "provenance_count": canonical.provenance_count,
        },
    )


def _persistence_migration_result(
    snapshot: GraphSnapshot, result: SnapshotMigrationResult,
) -> OntologyMigrationResult:
    return OntologyMigrationResult(
        snapshot=snapshot,
        migrated_node_count=result.migrated_node_count,
        migrated_edge_count=result.migrated_edge_count,
        status=result.status,
        diagnostics=result.diagnostics,
        source_version=result.source_version,
        source_descriptor=result.source_descriptor,
        target_version=result.target_version,
        applied_migration_ids=result.applied_migration_ids,
        graph_counts=result.graph_counts,
    )


def _empty_graph_data() -> dict[str, dict[str, Any]]:
    return empty_document(CATALOG_REVISION)


def _snapshot_data(snapshot: GraphSnapshot) -> dict[str, Any]:
    """Serialize an already validated canonical snapshot for persistence."""

    return serialize_snapshot(snapshot, CATALOG_REVISION)


def _validate_snapshot(snapshot: GraphSnapshot) -> None:
    if verification_payload_error(snapshot):
        raise PersistenceIntegrityError("verification-payload-boundary")
    try:
        serialized = snapshot.as_dict()
    except ValueError as exc:
        raise PersistenceIntegrityError("snapshot-serialization-invalid") from exc
    _reject_forbidden_fields(serialized)
    validation = validate_graph_integrity(snapshot)
    errors = [item for item in validation.metadata.diagnostics if item.severity == "error"]
    if errors:
        diagnostic = errors[0]
        safe_summaries = {
            "cross-graph-implementation-trust": "requires authoritative declared support",
            "relationship-vocabulary-kind": "canonical relationship catalog violation",
            "retired-openspec-domain-vocabulary": "Retired OpenSpec-prefixed domain vocabulary",
        }
        summary = safe_summaries.get(diagnostic.rule_id, "graph integrity validation failed")
        raise PersistenceIntegrityError(
            f"{diagnostic.rule_id}: {summary} ({_safe_record_id(diagnostic.affected_object_id)})"
        )


def _reject_forbidden_fields(value: Any, path: str = "graph") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            if _is_forbidden_persistence_field(key_text):
                raise PersistenceIntegrityError("forbidden-persistence-field")
            _reject_forbidden_fields(nested, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_forbidden_fields(item, f"{path}[{index}]")


def _is_forbidden_persistence_field(key: str) -> bool:
    """Reject provider/framework/CI payload containers, including variants."""
    folded = key.casefold().replace("-", "_")
    normalized = "".join(
        f"_{character.lower()}" if character.isupper() else character
        for character in key
    ).replace("-", "_").casefold()
    tokens = set(folded.split("_")) | set(normalized.split("_"))
    return folded in {field.casefold() for field in FORBIDDEN_PERSISTENCE_FIELDS}


def _safe_merge_diagnostic(error: ValueError) -> str:
    """Retain known validation rules while dropping record values from errors."""
    message = str(error)
    for prefix in (
        "invalid-cross-graph-classification",
        "Pull-request source artifact invalid",
        "Pull-request association provenance binding invalid",
        "Pull-request repository relation provenance binding invalid",
        "Pull-request typed relation lacks its exact projected edge",
        "Pull-request projected edge does not match its typed relation",
    ):
        if message.startswith(prefix):
            return prefix
    return "snapshot-merge-invalid"


def _snapshot_from_data(data: dict[str, Any], allow_legacy_evidence: bool = False) -> GraphSnapshot:
    """Decode through the shared logical codec and map errors at the adapter boundary."""
    try:
        return deserialize_snapshot(data, allow_legacy_evidence=allow_legacy_evidence)
    except SnapshotCodecError as exc:
        raise PersistenceIntegrityError(_safe_codec_diagnostic_id(exc)) from exc
