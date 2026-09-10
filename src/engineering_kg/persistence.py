"""Local persistence boundary for canonical Engineering KG graph snapshots.

The confirmed local LadybugDB dependency is the Node package
``@ladybugdb/core``. The Python runner keeps persistence isolated so a Node
bridge or Python binding can replace this local adapter without changing
pipeline stages or scripts.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engineering_kg.ontology import (
    CodeLocator,
    ConfluencePageRef,
    CrossGraphLinkClaim,
    CrossGraphLinkEvidence,
    CrossGraphLinkLifecycle,
    Edge,
    Evidence,
    GraphSnapshot,
    Node,
    OpenSpecLocator,
    ProvenanceRecord,
    SourceArtifactIdentity,
    SourceArtifactLocator,
    PullRequestImplementationEvidence,
    PullRequestDeclaredAssociation,
    PullRequestObservedRepositoryRelation,
    ProvenanceKind,
    evidence_requires_source_artifact_identity,
    source_artifact_identity_error,
    EdgeKind,
    NodeKind,
    openspec_requirement_id,
    openspec_scenario_id,
    openspec_specification_id,
    stable_id,
)
from engineering_kg.validation import validate_graph_integrity
from engineering_kg.relationship_vocabulary import CATALOG_BY_KIND, CATALOG_REVISION


GRAPH_FILE_NAME = "graph.json"
MIGRATION_BACKUP_FILE_NAME = "graph.pre-canonical-migration.json"

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
class OntologyMigrationResult:
    """Deterministic summary of one persisted ontology migration."""

    snapshot: GraphSnapshot
    migrated_node_count: int = 0
    migrated_edge_count: int = 0
    status: str | None = None
    diagnostics: tuple[str, ...] = ()

    @property
    def migrated(self) -> bool:
        return bool(self.migrated_node_count or self.migrated_edge_count)

    def as_dict(self) -> dict[str, Any]:
        return {
            "diagnostics": list(self.diagnostics),
            "graph_counts": {
                "edge_count": self.snapshot.edge_count,
                "evidence_count": self.snapshot.evidence_count,
                "node_count": self.snapshot.node_count,
            },
            "migrated_edge_count": self.migrated_edge_count,
            "migrated_node_count": self.migrated_node_count,
            "status": self.status or ("migrated" if self.migrated else "not-needed"),
        }


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
            current = _snapshot_from_data(
                self._migrate_raw_if_needed(self._read_raw())
            )
            try:
                prospective = current.merged_with(snapshot)
            except ValueError as exc:
                raise PersistenceIntegrityError(str(exc)) from exc
            # Validate the full prospective graph, including constraints that
            # apply across writes, before replacing the persisted snapshot.
            _validate_snapshot(prospective)
            self._write_raw(_snapshot_data(prospective))
            return self.read_snapshot()
        except PersistenceError:
            raise
        except OSError as exc:
            raise PersistenceWriteError(f"Cannot write graph snapshot: {exc}") from exc

    def read_snapshot(self) -> GraphSnapshot:
        try:
            data = self._migrate_raw_if_needed(self._read_raw())
            return _snapshot_from_data(data)
        except PersistenceError:
            raise
        except OSError as exc:
            raise PersistenceReadError(f"Cannot read graph snapshot: {exc}") from exc

    def migrate_persisted_snapshot(self) -> OntologyMigrationResult:
        """Read and verify the only supported canonical persisted format."""

        try:
            data = self._read_raw()
            _require_current_catalog_revision(data)
            return OntologyMigrationResult(_snapshot_from_data(data))
        except PersistenceError:
            raise
        except OSError as exc:
            raise PersistenceWriteError(f"Cannot migrate persisted graph snapshot: {exc}") from exc

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
        _require_current_catalog_revision(data)
        return data


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
                f"legacy-evidence-migration-unsupported: {item.id}: {error}"
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
    return OntologyMigrationResult(canonical)


def _reject_legacy_relationship_migration(snapshot: GraphSnapshot) -> None:
    """Keep the retained domain migration from converting relationship aliases."""

    for edge in sorted(snapshot.edges, key=lambda item: item.id):
        kind = _value(edge.kind)
        if kind != EdgeKind.ASSERTS.value and kind not in CATALOG_BY_KIND:
            raise PersistenceIntegrityError(
                f"legacy-relationship-migration-unsupported: {edge.id}: {kind}"
            )


def _require_current_catalog_revision(data: dict[str, Any]) -> None:
    """Reject historical formats rather than converting them on readback."""
    revision = data.get("catalog_revision")
    if revision == CATALOG_REVISION:
        legacy_candidates = any(
            isinstance(record, dict)
            and record.get("strategy_id") == "pr-code-candidate-extraction"
            for record in (data.get("cross_graph_link_evidence") or {}).values()
            if isinstance(data.get("cross_graph_link_evidence") or {}, dict)
        )
        if legacy_candidates and "pull_request_evidence" not in data:
            raise PersistenceIntegrityError(
                "legacy-pr-candidate-unsupported: missing base/head revisions and explicit association"
            )
        return
    if revision is None:
        raise PersistenceIntegrityError("missing-catalog-revision")
    raise PersistenceIntegrityError(f"unsupported-catalog-revision: {revision!r}")


def _migrate_legacy_evidence(snapshot: GraphSnapshot) -> tuple[GraphSnapshot, int]:
    """Reject retired evidence records; persisted-data migration is unsupported."""

    raise PersistenceIntegrityError("legacy-evidence-migration-unsupported")

    evidence_ids: dict[str, str] = {}
    evidence_by_id: dict[str, Evidence] = {}
    provenance: list[ProvenanceRecord] = list(snapshot.provenance)
    migrated = 0
    for item in snapshot.evidence:
        locator = item.locator
        if isinstance(locator, OpenSpecLocator) and locator.source_artifact_identity is not None:
            _coalesce_migrated_evidence(evidence_by_id, item)
            continue
        if isinstance(locator, SourceArtifactLocator):
            _coalesce_migrated_evidence(evidence_by_id, item)
            continue
        if not evidence_requires_source_artifact_identity(item):
            _coalesce_migrated_evidence(evidence_by_id, item)
            continue
        fields = item.properties.get("source_artifact_identity")
        if not isinstance(fields, dict):
            raise PersistenceIntegrityError(
                "legacy-source-artifact-identity: authoritative evidence lacks sufficient authoritative identity fields"
            )
        try:
            identity = SourceArtifactIdentity(
                _expect_string(fields.get("source_type"), "legacy source_type"),
                _expect_string(fields.get("source_identity"), "legacy source_identity"),
                _expect_string(fields.get("artifact_type"), "legacy artifact_type"),
                _expect_string(fields.get("revision_or_version"), "legacy revision_or_version"),
                _expect_string(fields.get("stable_locator"), "legacy stable_locator"),
            )
        except (PersistenceIntegrityError, ValueError) as exc:
            raise PersistenceIntegrityError(
                "legacy-source-artifact-identity: authoritative evidence lacks sufficient authoritative identity fields"
            ) from exc
        if isinstance(locator, OpenSpecLocator):
            if identity.artifact_type != locator.artifact_type or identity.stable_locator != locator.relative_file_path:
                raise PersistenceIntegrityError(
                    "legacy-source-artifact-identity: retained identity conflicts with OpenSpec locator"
                )
            migrated_locator = OpenSpecLocator(
                locator.relative_file_path, locator.artifact_type,
                locator.openspec_identity, locator.heading_name,
                locator.line_start, locator.line_end, identity,
            )
            new_id = stable_id("evidence", identity.id, locator.openspec_identity)
        else:
            migrated_locator = SourceArtifactLocator(identity)
            new_id = stable_id("evidence", identity.id)
        evidence_ids[item.id] = new_id
        properties = dict(item.properties)
        properties.pop("source_artifact_identity")
        provenance_fields = properties.pop("provenance", None)
        if not isinstance(provenance_fields, dict):
            raise PersistenceIntegrityError("legacy-provenance: authoritative evidence lacks complete retained provenance fields")
        try:
            record = ProvenanceRecord(
                ProvenanceKind.EXTERNAL,
                _expect_string(provenance_fields.get("observed_at"), "legacy provenance.observed_at"),
                _expect_string(provenance_fields.get("content_hash_algorithm"), "legacy provenance.content_hash_algorithm"),
                _expect_string(provenance_fields.get("content_hash"), "legacy provenance.content_hash"),
                _expect_string(provenance_fields.get("extractor_id"), "legacy provenance.extractor_id"),
                _expect_string(provenance_fields.get("extractor_version"), "legacy provenance.extractor_version"),
                identity,
            )
        except (PersistenceIntegrityError, ValueError) as exc:
            raise PersistenceIntegrityError("legacy-provenance: authoritative evidence lacks complete retained provenance fields") from exc
        provenance.append(record)
        _coalesce_migrated_evidence(evidence_by_id, Evidence(
            new_id, item.source, migrated_locator, properties, (record.id,),
        ))
        migrated += 1
    if not migrated:
        return snapshot, 0
    rewrite = lambda ids: tuple(sorted({evidence_ids.get(item, item) for item in ids}))
    return GraphSnapshot(
        nodes=tuple(Node(item.id, item.kind, item.name, item.properties, rewrite(item.evidence_ids)) for item in snapshot.nodes),
        edges=tuple(Edge(item.id, item.kind, item.source_id, item.target_id, item.properties,
                         rewrite(item.evidence_ids), item.confidence) for item in snapshot.edges),
        evidence=tuple(evidence_by_id[item_id] for item_id in sorted(evidence_by_id)),
        cross_graph_link_claims=snapshot.cross_graph_link_claims,
        cross_graph_link_evidence=tuple(CrossGraphLinkEvidence(
            item.claim_id, item.strategy_id, item.observation_id,
            evidence_ids.get(item.provenance_evidence_id, item.provenance_evidence_id),
            item.origin, item.status, item.confidence, item.trust_disposition,
            item.pull_request_evidence_id, item.declared_association_id,
        ) for item in snapshot.cross_graph_link_evidence),
        cross_graph_link_lifecycle=tuple(CrossGraphLinkLifecycle(
            item.claim_id, item.revision, item.state,
            evidence_ids.get(item.provenance_evidence_id, item.provenance_evidence_id)
        ) for item in snapshot.cross_graph_link_lifecycle),
        provenance=tuple(sorted({item.id: item for item in provenance}.values(), key=lambda item: item.id)),
        pull_request_evidence=snapshot.pull_request_evidence,
        pull_request_declared_associations=snapshot.pull_request_declared_associations,
        pull_request_observed_repository_relations=snapshot.pull_request_observed_repository_relations,
    ), migrated


def _coalesce_migrated_evidence(
    evidence_by_id: dict[str, Evidence], item: Evidence
) -> None:
    """Retain one equivalent migrated record or reject conflicting provenance."""

    existing = evidence_by_id.get(item.id)
    if existing is None:
        evidence_by_id[item.id] = item
        return
    if existing.as_dict() != item.as_dict():
        raise PersistenceIntegrityError("legacy-source-artifact-identity: conflicting migrated evidence")


def _repository_for_legacy_requirement(
    nodes: tuple[Node, ...], requirement: Node, capability: str
) -> str:
    for node in nodes:
        if _value(node.kind) != "openspec-spec":
            continue
        if node.properties.get("capability") == capability:
            repository_id = node.properties.get("repository_id")
            if isinstance(repository_id, str) and repository_id:
                return repository_id
    raise PersistenceIntegrityError(
        f"Cannot migrate legacy requirement without a specification repository: {requirement.id}"
    )


def _legacy_requirement_for_scenario(
    edges: tuple[Edge, ...], nodes: tuple[Node, ...], scenario_id: str
) -> Node:
    nodes_by_id = {node.id: node for node in nodes}
    for edge in edges:
        if edge.target_id == scenario_id and _value(edge.kind) == "openspec-requirement-contains-scenario":
            requirement = nodes_by_id.get(edge.source_id)
            if requirement is not None and _value(requirement.kind) == "openspec-requirement":
                return requirement
    raise PersistenceIntegrityError(
        f"Cannot migrate legacy scenario without its containing requirement: {scenario_id}"
    )


def _normalized(value: object) -> str:
    return " ".join(str(value).strip().lower().split())


def _migrated_edge_id(
    edge: Edge,
    kind: EdgeKind | str,
    source_id: str,
    target_id: str,
    properties: dict[str, Any],
    nodes_by_id: dict[str, Node],
) -> str:
    if _value(edge.kind) == _value(kind):
        return edge.id
    if _value(edge.kind) == "openspec-spec-contains-requirement":
        return stable_id(
            "edge", kind, source_id, target_id, "spec-requirement", "specification-requirement"
        )
    if _value(edge.kind) == "openspec-requirement-contains-scenario":
        return stable_id(
            "edge", kind, source_id, target_id, "requirement-scenario", "requirement-scenario"
        )
    if _value(edge.kind) == "openspec-change-touches-spec":
        change = nodes_by_id[source_id]
        specification = nodes_by_id[target_id]
        return stable_id(
            "edge",
            kind,
            source_id,
            target_id,
            "openspec-change-specification",
            change.properties.get("change_identity", change.name),
            specification.properties["capability"],
        )
    if _value(edge.kind) == "openspec-change-traces-to-spec":
        return stable_id(
            "edge",
            kind,
            properties["rule_id"],
            source_id,
            target_id,
            *properties.get("input_edge_ids", ()),
        )
    if _value(edge.kind) == "openspec-related-spec":
        source = nodes_by_id[source_id]
        return stable_id(
            "edge",
            kind,
            source_id,
            target_id,
            "related-spec",
            source.properties["capability"],
            properties["related_title"],
        )
    return stable_id("edge", kind, source_id, target_id, *sorted(properties.items()))


def _value(value: object) -> object:
    return getattr(value, "value", value)


def _empty_graph_data() -> dict[str, dict[str, Any]]:
    return {
        "catalog_revision": CATALOG_REVISION,
        "edge_order": [],
        "edges": {},
        "evidence": {},
        "evidence_order": [],
        "provenance": {},
        "provenance_order": [],
        "cross_graph_link_claims": {},
        "cross_graph_link_claim_order": [],
        "cross_graph_link_evidence": {},
        "cross_graph_link_evidence_order": [],
        "cross_graph_link_lifecycle": {},
        "cross_graph_link_lifecycle_order": [],
        "pull_request_evidence": {},
        "pull_request_evidence_order": [],
        "pull_request_declared_associations": {},
        "pull_request_declared_association_order": [],
        "pull_request_observed_repository_relations": {},
        "pull_request_observed_repository_relation_order": [],
        "node_order": [],
        "nodes": {},
    }


def _merge_snapshot(data: dict[str, Any], snapshot: GraphSnapshot) -> dict[str, Any]:
    try:
        merged_snapshot = _snapshot_from_data(data).merged_with(snapshot)
    except ValueError as exc:
        raise PersistenceIntegrityError(str(exc)) from exc
    return _snapshot_data(merged_snapshot)


def _snapshot_data(snapshot: GraphSnapshot) -> dict[str, Any]:
    """Serialize an already validated canonical snapshot for persistence."""

    merged = {
        "catalog_revision": CATALOG_REVISION,
        "edge_order": [],
        "edges": {},
        "evidence": {},
        "evidence_order": [],
        "provenance": {},
        "provenance_order": [],
        "cross_graph_link_claims": {},
        "cross_graph_link_claim_order": [],
        "cross_graph_link_evidence": {},
        "cross_graph_link_evidence_order": [],
        "cross_graph_link_lifecycle": {},
        "cross_graph_link_lifecycle_order": [],
        "pull_request_evidence": {},
        "pull_request_evidence_order": [],
        "pull_request_declared_associations": {},
        "pull_request_declared_association_order": [],
        "pull_request_observed_repository_relations": {},
        "pull_request_observed_repository_relation_order": [],
        "node_order": [],
        "nodes": {},
    }

    for node in snapshot.nodes:
        merged["nodes"][node.id] = node.as_dict()
        merged["node_order"].append(node.id)
    for edge in snapshot.edges:
        merged["edges"][edge.id] = edge.as_dict()
        merged["edge_order"].append(edge.id)
    for evidence in snapshot.evidence:
        merged["evidence"][evidence.id] = evidence.as_dict()
        merged["evidence_order"].append(evidence.id)
    for provenance in snapshot.provenance:
        merged["provenance"][provenance.id] = provenance.as_dict()
        merged["provenance_order"].append(provenance.id)
    for claim in snapshot.cross_graph_link_claims:
        merged["cross_graph_link_claims"][claim.id] = claim.as_dict()
        merged["cross_graph_link_claim_order"].append(claim.id)
    for observation in snapshot.cross_graph_link_evidence:
        merged["cross_graph_link_evidence"][observation.id] = observation.as_dict()
        merged["cross_graph_link_evidence_order"].append(observation.id)
    for lifecycle in snapshot.cross_graph_link_lifecycle:
        merged["cross_graph_link_lifecycle"][lifecycle.id] = lifecycle.as_dict()
        merged["cross_graph_link_lifecycle_order"].append(lifecycle.id)
    for item in snapshot.pull_request_evidence:
        merged["pull_request_evidence"][item.id] = item.as_dict()
        merged["pull_request_evidence_order"].append(item.id)
    for item in snapshot.pull_request_declared_associations:
        merged["pull_request_declared_associations"][item.id] = item.as_dict()
        merged["pull_request_declared_association_order"].append(item.id)
    for item in snapshot.pull_request_observed_repository_relations:
        merged["pull_request_observed_repository_relations"][item.id] = item.as_dict()
        merged["pull_request_observed_repository_relation_order"].append(item.id)

    return merged


def _snapshot_from_data(data: dict[str, Any], allow_legacy_evidence: bool = False) -> GraphSnapshot:
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
        _evidence_from_dict(item, allow_legacy_evidence)
        for item in _ordered_records(
            _expect_mapping(data.get("evidence", {}), "evidence"),
            _expect_string_tuple(data.get("evidence_order", []), "evidence_order"),
        )
    )
    provenance = tuple(
        _provenance_from_dict(item)
        for item in _ordered_records(
            _expect_mapping(data.get("provenance", {}), "provenance"),
            _expect_string_tuple(data.get("provenance_order", []), "provenance_order"),
        )
    )
    claims = tuple(
        _cross_graph_link_claim_from_dict(item)
        for item in _ordered_records(
            _expect_mapping(data.get("cross_graph_link_claims", {}), "cross_graph_link_claims"),
            _expect_string_tuple(data.get("cross_graph_link_claim_order", []), "cross_graph_link_claim_order"),
        )
    )
    observations = tuple(
        _cross_graph_link_evidence_from_dict(item)
        for item in _ordered_records(
            _expect_mapping(data.get("cross_graph_link_evidence", {}), "cross_graph_link_evidence"),
            _expect_string_tuple(data.get("cross_graph_link_evidence_order", []), "cross_graph_link_evidence_order"),
        )
    )
    lifecycle = tuple(
        _cross_graph_link_lifecycle_from_dict(item)
        for item in _ordered_records(
            _expect_mapping(data.get("cross_graph_link_lifecycle", {}), "cross_graph_link_lifecycle"),
            _expect_string_tuple(data.get("cross_graph_link_lifecycle_order", []), "cross_graph_link_lifecycle_order"),
        )
    )
    pull_request_evidence = tuple(
        _pull_request_evidence_from_dict(item)
        for item in _ordered_records(
            _expect_mapping(data.get("pull_request_evidence", {}), "pull_request_evidence"),
            _expect_string_tuple(data.get("pull_request_evidence_order", []), "pull_request_evidence_order"),
        )
    )
    associations = tuple(
        _pull_request_association_from_dict(item)
        for item in _ordered_records(
            _expect_mapping(data.get("pull_request_declared_associations", {}), "pull_request_declared_associations"),
            _expect_string_tuple(data.get("pull_request_declared_association_order", []), "pull_request_declared_association_order"),
        )
    )
    repository_relations = tuple(
        _pull_request_repository_relation_from_dict(item)
        for item in _ordered_records(
            _expect_mapping(data.get("pull_request_observed_repository_relations", {}), "pull_request_observed_repository_relations"),
            _expect_string_tuple(data.get("pull_request_observed_repository_relation_order", []), "pull_request_observed_repository_relation_order"),
        )
    )
    snapshot = GraphSnapshot(
        nodes, edges, evidence, claims, observations, lifecycle, provenance,
        pull_request_evidence, associations, repository_relations,
        allow_legacy_evidence=allow_legacy_evidence,
    )
    if not allow_legacy_evidence:
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
        confidence=_expect_optional_string(data.get("confidence"), "edge.confidence"),
    )


def _evidence_from_dict(data: dict[str, Any], allow_legacy_evidence: bool = False) -> Evidence:
    try:
        record = Evidence(
            id=_expect_string(data.get("id"), "evidence.id"),
            source=_expect_string(data.get("source"), "evidence.source"),
            locator=_locator_from_value(data.get("locator")),
            properties=dict(_expect_mapping(data.get("properties", {}), "evidence.properties")),
            provenance_ids=tuple(_expect_string_tuple(data.get("provenance_ids", []), "evidence.provenance_ids")),
        )
    except ValueError as exc:
        raise PersistenceIntegrityError(str(exc)) from exc
    if not allow_legacy_evidence and (error := source_artifact_identity_error(record)):
        raise PersistenceIntegrityError(
            f"invalid-source-artifact-identity: {error}"
        )
    return record


def _provenance_from_dict(data: dict[str, Any]) -> ProvenanceRecord:
    allowed = {"id", "kind", "observed_at", "content_hash_algorithm", "content_hash", "extractor_id", "extractor_version", "source_artifact_identity", "derivation_rule_id", "input_provenance_ids"}
    _expect_allowed_locator_keys(set(data), allowed, "provenance")
    identity_data = data.get("source_artifact_identity")
    try:
        record = ProvenanceRecord(
            _expect_string(data.get("kind"), "provenance.kind"),
            _expect_string(data.get("observed_at"), "provenance.observed_at"),
            _expect_string(data.get("content_hash_algorithm"), "provenance.content_hash_algorithm"),
            _expect_string(data.get("content_hash"), "provenance.content_hash"),
            _expect_string(data.get("extractor_id"), "provenance.extractor_id"),
            _expect_string(data.get("extractor_version"), "provenance.extractor_version"),
            _source_artifact_identity_from_mapping(identity_data) if identity_data is not None else None,
            _expect_optional_string(data.get("derivation_rule_id"), "provenance.derivation_rule_id"),
            tuple(_expect_string_tuple(data.get("input_provenance_ids", []), "provenance.input_provenance_ids")),
        )
    except ValueError as exc:
        raise PersistenceIntegrityError(str(exc)) from exc
    _expect_record_id(data, record.id, "provenance")
    return record


def _cross_graph_link_claim_from_dict(data: dict[str, Any]) -> CrossGraphLinkClaim:
    target = _locator_from_value(data.get("target"))
    if not isinstance(target, CodeLocator):
        raise PersistenceIntegrityError("cross_graph_link_claim.target must be a CodeLocator")
    try:
        record = CrossGraphLinkClaim(
            _expect_string(data.get("subject_id"), "cross_graph_link_claim.subject_id"),
            _expect_string(data.get("relation_kind"), "cross_graph_link_claim.relation_kind"), target,
        )
    except ValueError as exc:
        raise PersistenceIntegrityError(str(exc)) from exc
    _expect_record_id(data, record.id, "cross_graph_link_claim")
    return record


def _cross_graph_link_evidence_from_dict(data: dict[str, Any]) -> CrossGraphLinkEvidence:
    if data.get("strategy_id") == "pr-code-candidate-extraction" and (
        data.get("pull_request_evidence_id") is None
        or data.get("declared_association_id") is None
    ):
        raise PersistenceIntegrityError(
            "legacy-pr-candidate-readback-unsupported: PR candidate lacks explicit PR evidence and association"
        )
    try:
        record = CrossGraphLinkEvidence(
            _expect_string(data.get("claim_id"), "cross_graph_link_evidence.claim_id"),
            _expect_string(data.get("strategy_id"), "cross_graph_link_evidence.strategy_id"),
            _expect_string(data.get("observation_id"), "cross_graph_link_evidence.observation_id"),
            _expect_string(data.get("provenance_evidence_id"), "cross_graph_link_evidence.provenance_evidence_id"),
            _expect_string(data.get("origin"), "cross_graph_link_evidence.origin"),
            _expect_string(data.get("status"), "cross_graph_link_evidence.status"),
            _expect_string(data.get("confidence"), "cross_graph_link_evidence.confidence"),
            _expect_string(data.get("trust_disposition"), "cross_graph_link_evidence.trust_disposition"),
            _expect_optional_string(data.get("pull_request_evidence_id"), "cross_graph_link_evidence.pull_request_evidence_id"),
            _expect_optional_string(data.get("declared_association_id"), "cross_graph_link_evidence.declared_association_id"),
        )
    except ValueError as exc:
        raise PersistenceIntegrityError(str(exc)) from exc
    _expect_record_id(data, record.id, "cross_graph_link_evidence")
    return record


def _cross_graph_link_lifecycle_from_dict(data: dict[str, Any]) -> CrossGraphLinkLifecycle:
    revision = data.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int):
        raise PersistenceIntegrityError("cross_graph_link_lifecycle.revision must be an integer")
    try:
        record = CrossGraphLinkLifecycle(
            _expect_string(data.get("claim_id"), "cross_graph_link_lifecycle.claim_id"), revision,
            _expect_string(data.get("state"), "cross_graph_link_lifecycle.state"),
            _expect_string(data.get("provenance_evidence_id"), "cross_graph_link_lifecycle.provenance_evidence_id"),
            _expect_string(data.get("origin"), "cross_graph_link_lifecycle.origin"),
            _expect_string(data.get("status"), "cross_graph_link_lifecycle.status"),
            _expect_string(data.get("confidence"), "cross_graph_link_lifecycle.confidence"),
            _expect_string(data.get("trust_disposition"), "cross_graph_link_lifecycle.trust_disposition"),
        )
    except ValueError as exc:
        raise PersistenceIntegrityError(str(exc)) from exc
    _expect_record_id(data, record.id, "cross_graph_link_lifecycle")
    return record


def _pull_request_evidence_from_dict(data: dict[str, Any]) -> PullRequestImplementationEvidence:
    try:
        record = PullRequestImplementationEvidence(
            _expect_string(data.get("pull_request_id"), "pull_request_evidence.pull_request_id"),
            _expect_string(data.get("repository_id"), "pull_request_evidence.repository_id"),
            _expect_string(data.get("base_revision"), "pull_request_evidence.base_revision"),
            _expect_string(data.get("head_revision"), "pull_request_evidence.head_revision"),
            data.get("merged"),
            _expect_string(data.get("source_evidence_id"), "pull_request_evidence.source_evidence_id"),
            _expect_string(data.get("provenance_evidence_id"), "pull_request_evidence.provenance_evidence_id"),
        )
    except ValueError as exc:
        raise PersistenceIntegrityError(str(exc)) from exc
    _expect_record_id(data, record.id, "pull_request_evidence")
    if data.get("node_id") != record.node_id:
        raise PersistenceIntegrityError("pull_request_evidence.node_id does not match its stable identity")
    return record


def _pull_request_association_from_dict(data: dict[str, Any]) -> PullRequestDeclaredAssociation:
    try:
        record = PullRequestDeclaredAssociation(
            _expect_string(data.get("pull_request_evidence_id"), "pull_request_declared_association.pull_request_evidence_id"),
            _expect_string(data.get("intended_change_id"), "pull_request_declared_association.intended_change_id"),
            _expect_string(data.get("source_evidence_id"), "pull_request_declared_association.source_evidence_id"),
            _expect_string(data.get("provenance_evidence_id"), "pull_request_declared_association.provenance_evidence_id"),
        )
    except ValueError as exc:
        raise PersistenceIntegrityError(str(exc)) from exc
    _expect_record_id(data, record.id, "pull_request_declared_association")
    if data.get("origin") != "declared":
        raise PersistenceIntegrityError("pull_request_declared_association.origin must be declared")
    return record


def _pull_request_repository_relation_from_dict(data: dict[str, Any]) -> PullRequestObservedRepositoryRelation:
    try:
        record = PullRequestObservedRepositoryRelation(
            _expect_string(data.get("pull_request_evidence_id"), "pull_request_observed_repository_relation.pull_request_evidence_id"),
            _expect_string(data.get("repository_id"), "pull_request_observed_repository_relation.repository_id"),
            _expect_string(data.get("source_evidence_id"), "pull_request_observed_repository_relation.source_evidence_id"),
            _expect_string(data.get("provenance_evidence_id"), "pull_request_observed_repository_relation.provenance_evidence_id"),
        )
    except ValueError as exc:
        raise PersistenceIntegrityError(str(exc)) from exc
    _expect_record_id(data, record.id, "pull_request_observed_repository_relation")
    if data.get("origin") != "observed":
        raise PersistenceIntegrityError("pull_request_observed_repository_relation.origin must be observed")
    return record


def _expect_record_id(data: dict[str, Any], expected: str, context: str) -> None:
    if data.get("id") != expected:
        raise PersistenceIntegrityError(f"{context}.id does not match its stable identity")


def _locator_from_value(
    value: Any,
) -> str | CodeLocator | ConfluencePageRef | OpenSpecLocator | SourceArtifactLocator:
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
    if keys == {"navigation_detail", "source_artifact_identity"}:
        try:
            identity = _source_artifact_identity_from_mapping(data["source_artifact_identity"])
            locator = SourceArtifactLocator(
                identity,
                dict(_expect_mapping(data["navigation_detail"], "locator.navigation_detail")),
            )
        except ValueError as exc:
            raise PersistenceIntegrityError(str(exc)) from exc
        return locator
    if {"artifact_type", "openspec_identity", "relative_file_path"}.issubset(keys):
        allowed_keys = {
            "artifact_type", "heading_name", "line_end", "line_start",
            "openspec_identity", "relative_file_path", "source_artifact_identity",
        }
        _expect_allowed_locator_keys(keys, allowed_keys)
        identity_value = data.get("source_artifact_identity")
        identity = None
        if identity_value is not None:
            try:
                identity = _source_artifact_identity_from_mapping(identity_value)
            except ValueError as exc:
                raise PersistenceIntegrityError(str(exc)) from exc
        return OpenSpecLocator(
            relative_file_path=_expect_string(data["relative_file_path"], "locator.relative_file_path"),
            artifact_type=_expect_string(data["artifact_type"], "locator.artifact_type"),
            openspec_identity=_expect_string(data["openspec_identity"], "locator.openspec_identity"),
            heading_name=_expect_optional_string(data.get("heading_name", ""), "locator.heading_name") or "",
            line_start=_expect_optional_int(data.get("line_start"), "locator.line_start"),
            line_end=_expect_optional_int(data.get("line_end"), "locator.line_end"),
            source_artifact_identity=identity,
        )
    raise PersistenceIntegrityError(f"Unsupported evidence locator shape: {sorted(keys)}")


def _source_artifact_identity_from_mapping(value: Any) -> SourceArtifactIdentity:
    """Deserialize the complete persisted identity without dropping unknown fields."""

    identity_data = _expect_mapping(value, "locator.source_artifact_identity")
    _expect_allowed_locator_keys(
        set(identity_data),
        {"artifact_type", "id", "revision_or_version", "source_identity", "source_type", "stable_locator"},
        "locator.source_artifact_identity",
    )
    identity = SourceArtifactIdentity(
        _expect_string(identity_data.get("source_type"), "source_artifact_identity.source_type"),
        _expect_string(identity_data.get("source_identity"), "source_artifact_identity.source_identity"),
        _expect_string(identity_data.get("artifact_type"), "source_artifact_identity.artifact_type"),
        _expect_string(identity_data.get("revision_or_version"), "source_artifact_identity.revision_or_version"),
        _expect_string(identity_data.get("stable_locator"), "source_artifact_identity.stable_locator"),
    )
    _expect_record_id(identity_data, identity.id, "source_artifact_identity")
    return identity


def _expect_allowed_locator_keys(
    keys: set[str], allowed_keys: set[str], context: str = "locator",
) -> None:
    unknown_keys = sorted(keys - allowed_keys)
    if unknown_keys:
        raise PersistenceIntegrityError(
            f"invalid-source-artifact-identity: {context}.{unknown_keys[0]} is not allowed"
        )


def _validate_snapshot(snapshot: GraphSnapshot) -> None:
    _reject_forbidden_fields(snapshot.as_dict())
    validation = validate_graph_integrity(snapshot)
    errors = [item for item in validation.metadata.diagnostics if item.severity == "error"]
    if errors:
        raise PersistenceIntegrityError(errors[0].message)


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


def _expect_optional_string(value: Any, context: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PersistenceIntegrityError(f"{context} must be a string")
    return value


def _expect_optional_int(value: Any, context: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int):
        raise PersistenceIntegrityError(f"{context} must be an integer")
    return value


def _expect_string_tuple(value: Any, context: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise PersistenceIntegrityError(f"{context} must be a list")
    return tuple(_expect_string(item, f"{context}[]") for item in value)
