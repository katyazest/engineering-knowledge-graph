"""Pure, forward-only migration of logical ontology snapshot documents."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from engineering_kg.ontology import (
    Edge,
    Evidence,
    CrossGraphLinkEvidence,
    CrossGraphLinkLifecycle,
    EdgeKind,
    GraphSnapshot,
    Node,
    NodeKind,
    OpenSpecLocator,
    ProvenanceKind,
    ProvenanceRecord,
    PullRequestImplementationEvidence,
    PullRequestDeclaredAssociation,
    PullRequestObservedRepositoryRelation,
    SourceArtifactIdentity,
    SourceArtifactLocator,
    evidence_requires_source_artifact_identity,
    source_artifact_identity_error,
    openspec_requirement_id,
    openspec_scenario_id,
    openspec_specification_id,
    stable_id,
)
from engineering_kg.relationship_vocabulary import CATALOG_REVISION
from engineering_kg.snapshot_codec import (
    CURRENT_SCHEMA_VERSION,
    SnapshotCodecError,
    deserialize_snapshot,
    serialize_snapshot,
)
from engineering_kg.validation import validate_graph_integrity


class SnapshotMigrationError(ValueError):
    """A safe, deterministic migration diagnostic."""

    def __init__(self, code: str, message: str | None = None, *, identifiers: tuple[str, ...] = ()) -> None:
        self.code = code
        self.identifiers = tuple(identifiers)
        detail = f" ({', '.join(self.identifiers)})" if self.identifiers else ""
        super().__init__((message or code) + detail)

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "identifiers": list(self.identifiers), "message": str(self)}


@dataclass(frozen=True)
class SnapshotMigrationResult:
    document: dict[str, Any] | None
    source_version: int | None
    source_descriptor: str | None
    target_version: int
    applied_migration_ids: tuple[str, ...] = ()
    status: str = "not-needed"
    migrated_node_count: int = 0
    migrated_edge_count: int = 0
    diagnostics: tuple[str, ...] = ()
    graph_counts: dict[str, int] | None = None

    @property
    def target_document(self) -> dict[str, Any] | None:
        return self.document

    @property
    def migrated(self) -> bool:
        return self.status == "migrated"

    def as_dict(self) -> dict[str, Any]:
        return {
            "applied_migration_ids": list(self.applied_migration_ids),
            "diagnostics": list(self.diagnostics),
            "graph_counts": dict(sorted((self.graph_counts or {}).items())),
            "migrated_edge_count": self.migrated_edge_count,
            "migrated_node_count": self.migrated_node_count,
            "source_descriptor": self.source_descriptor,
            "source_version": self.source_version,
            "status": self.status,
            "target_version": self.target_version,
        }


Transform = Callable[[Mapping[str, Any]], tuple[dict[str, Any], int, int]]
Matcher = Callable[[Mapping[str, Any]], bool]

_SAFE_CODEC_DIAGNOSTIC_IDS = (
    "unsupported-catalog-revision",
    "legacy-pr-candidate-readback-unsupported",
    "Persisted record id mismatch",
    "Persisted record order references unknown id",
    "invalid-cross-graph-opaque-identifier",
    "invalid-source-artifact-identity",
    "invalid-provenance",
    "forbidden-persistence-field",
    "invalid-record-shape",
)


def _safe_record_id(value: str) -> str:
    """Expose only generated stable IDs in operational diagnostics."""
    return value if re.fullmatch(r"[a-z][a-z0-9-]*:[0-9a-f]{16}", value) else "record-id-redacted"


def _safe_codec_diagnostic_id(error: SnapshotCodecError) -> str:
    """Retain a stable codec rule ID without forwarding document values."""
    message = str(error)
    for rule_id in _SAFE_CODEC_DIAGNOSTIC_IDS:
        if message.startswith(rule_id):
            if rule_id in {"invalid-source-artifact-identity", "invalid-provenance"}:
                safe_detail = next(
                    (
                        phrase
                        for phrase in (
                            "authoritative external evidence lacks a complete explicit source-artifact identity",
                            "OpenSpec locator artifact_type does not match source-artifact identity",
                            "derived provenance cannot contain source_artifact_identity",
                            *(f"{field} contains unsafe content" for field in (
                                "source_type", "source_identity", "artifact_type",
                                "revision_or_version", "stable_locator",
                            )),
                        )
                        if phrase in message
                    ),
                    "invalid source-artifact identity",
                )
                return f"{rule_id}: {safe_detail}"
            if rule_id == "invalid-cross-graph-opaque-identifier":
                field = message.partition(": ")[2]
                if field in {"strategy_id", "observation_id", "origin", "status", "confidence", "trust_disposition"}:
                    return f"{rule_id}: {field}"
            return rule_id
        for record_type in ("cross_graph_link_evidence", "cross_graph_link_lifecycle"):
            prefix = f"{record_type}."
            if message.startswith(prefix) and message.endswith(" must be a non-empty string"):
                field = message[len(prefix):].partition(" ")[0]
                if field in {"claim_id", "strategy_id", "observation_id", "provenance_evidence_id", "origin", "status", "confidence", "trust_disposition", "state"}:
                    return f"{record_type}.{field} must be a non-empty string"
        if " is not allowed in persistence" in message:
            return "forbidden-persistence-field"
        if message.endswith(" is not allowed"):
            return "invalid-record-shape"
    return "snapshot-codec-invalid"


@dataclass(frozen=True)
class SnapshotSourceDescriptor:
    id: str
    matcher: Matcher
    source_version: int | None = None
    target_version: int = CURRENT_SCHEMA_VERSION
    transform: Transform | None = None


@dataclass(frozen=True)
class SnapshotMigrationTransition:
    id: str
    source_version: int
    target_version: int
    transform: Transform
    expected_catalog_revision: str = CATALOG_REVISION


class SnapshotMigrationRegistry:
    """Registry resolving descriptors and adjacent version transitions."""

    def __init__(
        self,
        descriptors: tuple[SnapshotSourceDescriptor, ...] | None = None,
        transitions: tuple[SnapshotMigrationTransition, ...] = (),
        *, current_version: int = CURRENT_SCHEMA_VERSION,
        catalog_revision: str = CATALOG_REVISION,
    ) -> None:
        self.current_version = current_version
        self.catalog_revision = catalog_revision
        self.descriptors = BUILTIN_DESCRIPTORS if descriptors is None else descriptors
        self.transitions = transitions

    def migrate(self, document: Mapping[str, Any]) -> SnapshotMigrationResult:
        if not isinstance(document, Mapping):
            raise SnapshotMigrationError("invalid-snapshot-document")
        raw = deepcopy(dict(document))
        if "ontology_schema_version" in raw:
            source_version = parse_schema_version(raw["ontology_schema_version"])
            if source_version > self.current_version:
                raise SnapshotMigrationError("unsupported-ontology-schema-version", "unsupported ontology schema version", identifiers=(str(source_version),))
            if source_version == self.current_version:
                target = self._validate_current(raw)
                return _result(target, source_version, None, (), "not-needed", 0, 0, self.current_version)
            target, ids, node_count, edge_count = self._apply_chain(raw, source_version)
            return _result(target, source_version, None, ids, "migrated", node_count, edge_count, self.current_version)

        if "catalog_revision" not in raw:
            raise SnapshotMigrationError("missing-catalog-revision", "logical snapshot lacks catalog revision")
        if raw.get("catalog_revision") != self.catalog_revision:
            raise SnapshotMigrationError("unsupported-catalog-revision")
        matches = tuple(descriptor for descriptor in self.descriptors if descriptor.matcher(raw))
        if len(matches) != 1:
            if len(matches) > 1:
                raise SnapshotMigrationError("ambiguous-legacy-descriptor", "ambiguous legacy snapshot descriptor", identifiers=tuple(item.id for item in matches))
            # Preserve the current codec's safe field-level diagnostic when a
            # document resembles current storage but is malformed.  It is
            # still rejected as an unregistered legacy format; no descriptor
            # is selected from that partial shape.
            try:
                deserialize_snapshot(raw)
            except SnapshotCodecError as exc:
                # Codec detail may include document-controlled keys, paths, or
                # record identifiers. Keep only the stable migration rule ID.
                raise SnapshotMigrationError(
                    "unsupported-legacy-format", _safe_codec_diagnostic_id(exc)
                ) from exc
            raise SnapshotMigrationError("unsupported-legacy-format", "unsupported legacy snapshot format")
        descriptor = matches[0]
        if descriptor.transform is None:
            raise SnapshotMigrationError("unsupported-legacy-format", "legacy descriptor has no migration transition", identifiers=(descriptor.id,))
        try:
            target, nodes, edges = descriptor.transform(raw)
        except SnapshotMigrationError:
            raise
        except (KeyError, TypeError, ValueError, SnapshotCodecError) as exc:
            raise SnapshotMigrationError("legacy-transform-failed", "legacy snapshot cannot be migrated deterministically", identifiers=(descriptor.id,)) from exc
        target, ids, chain_nodes, chain_edges = self._apply_chain(target, descriptor.target_version)
        target["ontology_schema_version"] = self.current_version
        return _result(target, descriptor.source_version, descriptor.id, (descriptor.id, *ids), "migrated", nodes + chain_nodes, edges + chain_edges, self.current_version)

    def _apply_chain(self, document: dict[str, Any], source_version: int) -> tuple[dict[str, Any], tuple[str, ...], int, int]:
        current = source_version
        target = document
        ids: list[str] = []
        nodes = edges = 0
        while current < self.current_version:
            candidates = tuple(item for item in self.transitions if item.source_version == current)
            if len(candidates) != 1:
                raise SnapshotMigrationError("unsupported-ontology-schema-version", "no unique adjacent ontology migration transition", identifiers=(str(current),))
            transition = candidates[0]
            if transition.target_version != current + 1:
                raise SnapshotMigrationError("unsupported-ontology-schema-version", "ontology migration transition is not adjacent", identifiers=(transition.id,))
            if target.get("catalog_revision") != transition.expected_catalog_revision:
                raise SnapshotMigrationError("unsupported-catalog-revision", "unsupported-catalog-revision", identifiers=(transition.id,))
            target, changed_nodes, changed_edges = transition.transform(target)
            ids.append(transition.id)
            nodes += changed_nodes
            edges += changed_edges
            current = transition.target_version
        target["ontology_schema_version"] = self.current_version
        return target, tuple(ids), nodes, edges

    def _validate_current(self, document: dict[str, Any]) -> dict[str, Any]:
        if document.get("catalog_revision") != self.catalog_revision:
            raise SnapshotMigrationError("unsupported-catalog-revision")
        try:
            snapshot = deserialize_snapshot(document)
        except SnapshotCodecError as exc:
            raise SnapshotMigrationError(
                "current-document-invalid",
                _safe_codec_diagnostic_id(exc),
                identifiers=("schema-v1",),
            ) from exc
        _validate_snapshot(snapshot)
        return deepcopy(document)


def parse_schema_version(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SnapshotMigrationError("invalid-ontology-schema-version", "ontology schema version must be a positive integer")
    return value


def migrate_snapshot_document(document: Mapping[str, Any], registry: SnapshotMigrationRegistry | None = None) -> SnapshotMigrationResult:
    return (registry or DEFAULT_REGISTRY).migrate(document)


def _result(document: dict[str, Any], source_version: int | None, descriptor: str | None, ids: tuple[str, ...], status: str, nodes: int, edges: int, target_version: int = CURRENT_SCHEMA_VERSION) -> SnapshotMigrationResult:
    try:
        snapshot = deserialize_snapshot(document)
    except SnapshotCodecError as exc:
        raise SnapshotMigrationError("target-document-invalid", "migrated ontology snapshot is not decodable", identifiers=ids) from exc
    _validate_snapshot(snapshot)
    return SnapshotMigrationResult(
        document=deepcopy(document), source_version=source_version, source_descriptor=descriptor,
        target_version=target_version, applied_migration_ids=ids, status=status,
        migrated_node_count=nodes, migrated_edge_count=edges,
        graph_counts={
            "edge_count": snapshot.edge_count, "evidence_count": snapshot.evidence_count,
            "node_count": snapshot.node_count, "provenance_count": snapshot.provenance_count,
            "cross_graph_link_claim_count": snapshot.cross_graph_link_claim_count,
            "cross_graph_link_evidence_count": snapshot.cross_graph_link_evidence_count,
            "cross_graph_link_lifecycle_count": snapshot.cross_graph_link_lifecycle_count,
            "pull_request_evidence_count": snapshot.pull_request_evidence_count,
            "pull_request_declared_association_count": snapshot.pull_request_declared_association_count,
            "pull_request_observed_repository_relation_count": snapshot.pull_request_observed_repository_relation_count,
        },
    )


def _validate_snapshot(snapshot: GraphSnapshot) -> None:
    validation = validate_graph_integrity(snapshot)
    errors = tuple(item for item in validation.metadata.diagnostics if item.severity == "error")
    if errors:
        raise SnapshotMigrationError("target-integrity-invalid", "migrated ontology snapshot failed graph integrity validation", identifiers=(errors[0].rule_id, _safe_record_id(errors[0].affected_object_id)))


def _catalog_document(document: Mapping[str, Any]) -> bool:
    return document.get("ontology_schema_version") is None and document.get("catalog_revision") == CATALOG_REVISION


def _current_descriptor(document: Mapping[str, Any]) -> bool:
    if not _catalog_document(document):
        return False
    retired = {"openspec-spec", "openspec-requirement", "openspec-scenario"}
    for collection in ("nodes", "edges"):
        records = document.get(collection, {})
        if not isinstance(records, dict):
            return False
        if any(record.get("kind") in retired or str(record.get("kind", "")).startswith("openspec-") and collection == "edges" for record in records.values() if isinstance(record, dict)):
            return False
    try:
        _validate_snapshot(deserialize_snapshot(document))
    except (SnapshotCodecError, SnapshotMigrationError):
        return False
    return True


def _legacy_descriptor(document: Mapping[str, Any]) -> bool:
    if not _catalog_document(document):
        return False
    nodes = document.get("nodes", {})
    edges = document.get("edges", {})
    return isinstance(nodes, dict) and isinstance(edges, dict) and (
        any(isinstance(item, dict) and item.get("kind") in {"openspec-spec", "openspec-requirement", "openspec-scenario"} for item in nodes.values())
        or any(isinstance(item, dict) and str(item.get("kind", "")).startswith("openspec-") and item.get("kind") not in {"contains"} for item in edges.values())
    )


def _legacy_transform(document: Mapping[str, Any]) -> tuple[dict[str, Any], int, int]:
    """Canonicalize the retained pre-v1 OpenSpec-prefixed logical shape."""
    source = _migrate_legacy_evidence(deserialize_snapshot(document, allow_legacy_evidence=True))
    node_map: dict[str, str] = {}
    new_nodes: list[Node] = []
    new_nodes_by_id: dict[str, Node] = {}
    nodes_by_id = {item.id: item for item in source.nodes}
    specs = [item for item in source.nodes if item.kind == "openspec-spec"]

    def text(value: Any, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise SnapshotMigrationError("legacy-identity-insufficient", "legacy source lacks a required canonical identity field", identifiers=(name,))
        return value

    for item in source.nodes:
        kind = getattr(item.kind, "value", item.kind)
        if kind == "openspec-spec":
            capability = text(item.properties.get("capability"), "capability")
            repository = text(item.properties.get("repository_id"), "repository_id")
            node_id = openspec_specification_id(repository, capability)
            node_map[item.id] = node_id
            converted = Node(node_id, NodeKind.SPECIFICATION, capability, {"capability": capability, "repository_id": repository}, item.evidence_ids)
        elif kind == "openspec-requirement":
            capability = text(item.properties.get("capability"), "capability")
            matches = [spec for spec in specs if spec.properties.get("capability") == capability]
            if not matches or len({spec.properties.get("repository_id") for spec in matches}) != 1:
                raise SnapshotMigrationError("legacy-identity-insufficient", "legacy requirement has no unique containing specification", identifiers=(_safe_record_id(item.id),))
            spec = matches[0]
            repository = text(spec.properties.get("repository_id"), "repository_id")
            specification_id = openspec_specification_id(repository, capability)
            node_id = openspec_requirement_id(specification_id, item.name)
            node_map[item.id] = node_id
            converted = Node(node_id, NodeKind.REQUIREMENT, item.name, {"capability": capability, "requirement_key": " ".join(item.name.strip().lower().split()), "specification_id": specification_id}, item.evidence_ids)
        elif kind == "openspec-scenario":
            parents = [edge.source_id for edge in source.edges if edge.target_id == item.id and edge.kind == "openspec-requirement-contains-scenario"]
            requirements = [nodes_by_id[parent] for parent in parents if parent in nodes_by_id and nodes_by_id[parent].kind == "openspec-requirement"]
            if not requirements or len({(requirement.name, requirement.properties.get("capability")) for requirement in requirements}) != 1:
                raise SnapshotMigrationError("legacy-identity-insufficient", "legacy scenario has no unique containing requirement", identifiers=(_safe_record_id(item.id),))
            requirement = requirements[0]
            capability = text(requirement.properties.get("capability"), "capability")
            specs_for_requirement = [spec for spec in specs if spec.properties.get("capability") == capability]
            if not specs_for_requirement or len({spec.properties.get("repository_id") for spec in specs_for_requirement}) != 1:
                raise SnapshotMigrationError("legacy-identity-insufficient", "legacy scenario has no unique specification", identifiers=(_safe_record_id(item.id),))
            repository = text(specs_for_requirement[0].properties.get("repository_id"), "repository_id")
            requirement_id = openspec_requirement_id(openspec_specification_id(repository, capability), requirement.name)
            node_id = openspec_scenario_id(requirement_id, item.name)
            node_map[item.id] = node_id
            converted = Node(node_id, NodeKind.SCENARIO, item.name, {"capability": capability, "requirement_id": requirement_id, "scenario_key": " ".join(item.name.strip().lower().split())}, item.evidence_ids)
        else:
            node_map[item.id] = item.id
            converted = item
        existing = new_nodes_by_id.get(converted.id)
        if existing is not None:
            if (existing.kind, existing.name, existing.properties) != (converted.kind, converted.name, converted.properties):
                raise SnapshotMigrationError("legacy-identity-conflict", "legacy records conflict on a canonical identity", identifiers=(_safe_record_id(converted.id),))
            converted = Node(converted.id, converted.kind, converted.name, converted.properties, tuple(sorted(set(existing.evidence_ids) | set(converted.evidence_ids))))
            new_nodes_by_id[converted.id] = converted
            new_nodes[next(index for index, item in enumerate(new_nodes) if item.id == converted.id)] = converted
            continue
        new_nodes_by_id[converted.id] = converted
        new_nodes.append(converted)

    edge_map: dict[str, str] = {}
    new_edges: list[tuple[Any, Any, str, str, dict[str, Any]]] = []
    mappings = {
        "openspec-spec-contains-requirement": EdgeKind.CONTAINS,
        "openspec-requirement-contains-scenario": EdgeKind.CONTAINS,
        "openspec-change-touches-spec": EdgeKind.ASSERTS,
        "openspec-change-traces-to-spec": EdgeKind.TRACES_TO,
        "openspec-related-spec": EdgeKind.REFERENCES,
    }
    for edge in source.edges:
        kind = getattr(edge.kind, "value", edge.kind)
        new_kind = mappings.get(kind, edge.kind)
        if kind.startswith("openspec-") and kind not in mappings:
            raise SnapshotMigrationError("legacy-relationship-unsupported", "legacy relationship mapping is not registered", identifiers=(_safe_record_id(edge.id),))
        source_id, target_id = node_map.get(edge.source_id), node_map.get(edge.target_id)
        if source_id is None or target_id is None:
            raise SnapshotMigrationError("legacy-relationship-endpoint", "legacy relationship endpoint cannot be reconstructed", identifiers=(_safe_record_id(edge.id),))
        properties = dict(edge.properties)
        if kind == "openspec-change-traces-to-spec":
            for field in ("source_scope", "target_scope", "via_spec_id"):
                properties.pop(field, None)
        confidence = edge.confidence
        if kind == "openspec-related-spec":
            if not isinstance(properties.get("related_title"), str) or not properties["related_title"].strip():
                raise SnapshotMigrationError("legacy-relationship-insufficient", "legacy related-spec mapping lacks its retained title", identifiers=(_safe_record_id(edge.id),))
            confidence = "non-confident"
        identity_parts: tuple[Any, ...]
        if kind in {"openspec-spec-contains-requirement", "openspec-requirement-contains-scenario"}:
            identity_parts = ("spec-requirement", "specification-requirement") if kind.startswith("openspec-spec") else ("requirement-scenario", "requirement-scenario")
        elif kind == "openspec-change-touches-spec":
            change, specification = nodes_by_id[edge.source_id], nodes_by_id[edge.target_id]
            identity_parts = ("openspec-change-specification", change.properties.get("change_identity", change.name), nodes_by_id[edge.target_id].properties.get("capability"))
        elif kind == "openspec-change-traces-to-spec":
            identity_parts = (properties.get("rule_id"), source_id, target_id, *properties.get("input_edge_ids", ()))
        elif kind == "openspec-related-spec":
            identity_parts = ("related-spec", new_nodes[[item.id for item in new_nodes].index(source_id)].properties.get("capability"), properties["related_title"])
        else:
            identity_parts = tuple(sorted(properties.items()))
        if kind in mappings and "input_edge_ids" not in properties:
            new_id = stable_id("edge", new_kind, source_id, target_id, *identity_parts)
            edge_map[edge.id] = new_id
        elif "input_edge_ids" not in properties:
            # Unaffected canonical relationships are carried through byte-for-
            # byte, including identities referenced by typed PR relations.
            edge_map[edge.id] = edge.id
        new_edges.append((edge, new_kind, source_id, target_id, properties))

    edges = []
    for original, kind, source_id, target_id, properties in new_edges:
        if "input_edge_ids" in properties:
            inputs = properties["input_edge_ids"]
            if not isinstance(inputs, (tuple, list)) or any(item not in edge_map for item in inputs):
                raise SnapshotMigrationError("legacy-relationship-input-insufficient", "derived legacy relationship references an unknown input edge", identifiers=(_safe_record_id(original.id),))
            rewritten_inputs = tuple(edge_map[item] for item in inputs)
            properties["input_edge_ids"] = rewritten_inputs
            identity = stable_id("edge", kind, properties.get("rule_id"), source_id, target_id, *rewritten_inputs)
            edge_map[original.id] = identity
        kind_value = getattr(kind, "value", kind)
        identity = edge_map[original.id]
        converted_edge = (identity, kind_value, source_id, target_id, properties, original.evidence_ids, confidence)
        existing_edge = next((existing for existing in edges if existing[0] == identity), None)
        if existing_edge is not None:
            if existing_edge[1:5] != converted_edge[1:5] or existing_edge[6] != converted_edge[6]:
                raise SnapshotMigrationError("legacy-relationship-conflict", "legacy relationships conflict on a canonical identity", identifiers=(_safe_record_id(identity),))
            merged_edge = (*converted_edge[:5], tuple(sorted(set(existing_edge[5]) | set(converted_edge[5]))), converted_edge[6])
            edges[edges.index(existing_edge)] = merged_edge
        else:
            edges.append(converted_edge)

    migrated_evidence = []
    for item in source.evidence:
        properties = dict(item.properties)
        specification_id = properties.get("specification_id")
        if isinstance(specification_id, str) and specification_id in node_map:
            properties["specification_id"] = node_map[specification_id]
        migrated_evidence.append(Evidence(item.id, item.source, item.locator, properties, item.provenance_ids))

    target = serialize_snapshot(GraphSnapshot(tuple(new_nodes), tuple(Edge(*edge) for edge in edges), tuple(migrated_evidence), source.cross_graph_link_claims, source.cross_graph_link_evidence, source.cross_graph_link_lifecycle, source.provenance, source.pull_request_evidence, source.pull_request_declared_associations, source.pull_request_observed_repository_relations), CATALOG_REVISION)
    return target, sum(getattr(item.kind, "value", item.kind) in {"openspec-spec", "openspec-requirement", "openspec-scenario"} for item in source.nodes), sum(getattr(item.kind, "value", item.kind) in mappings for item in source.edges)


def _migrate_legacy_evidence(snapshot: GraphSnapshot) -> GraphSnapshot:
    """Recover an old embedded identity/provenance envelope without inference."""
    evidence_ids: dict[str, str] = {}
    migrated: dict[str, Any] = {}
    provenance = {item.id: item for item in snapshot.provenance}
    for item in snapshot.evidence:
        if not evidence_requires_source_artifact_identity(item) or source_artifact_identity_error(item) is None:
            existing = migrated.get(item.id)
            if existing is not None and existing.as_dict() != item.as_dict():
                raise SnapshotMigrationError("legacy-evidence-conflict", "legacy evidence records conflict after coalescing", identifiers=(_safe_record_id(item.id),))
            migrated[item.id] = item
            continue
        fields = item.properties.get("source_artifact_identity")
        legacy_provenance = item.properties.get("provenance")
        if not isinstance(fields, dict) or not isinstance(legacy_provenance, dict):
            raise SnapshotMigrationError("legacy-provenance-insufficient", "legacy evidence lacks complete retained identity or provenance", identifiers=(_safe_record_id(item.id),))
        try:
            identity = SourceArtifactIdentity(
                _legacy_text(fields.get("source_type"), "source_type"),
                _legacy_text(fields.get("source_identity"), "source_identity"),
                _legacy_text(fields.get("artifact_type"), "artifact_type"),
                _legacy_text(fields.get("revision_or_version"), "revision_or_version"),
                _legacy_text(fields.get("stable_locator"), "stable_locator"),
            )
            provenance_record = ProvenanceRecord(
                ProvenanceKind.EXTERNAL,
                _legacy_text(legacy_provenance.get("observed_at"), "observed_at"),
                _legacy_text(legacy_provenance.get("content_hash_algorithm"), "content_hash_algorithm"),
                _legacy_text(legacy_provenance.get("content_hash"), "content_hash"),
                _legacy_text(legacy_provenance.get("extractor_id"), "extractor_id"),
                _legacy_text(legacy_provenance.get("extractor_version"), "extractor_version"),
                identity,
            )
            locator = item.locator
            if isinstance(locator, OpenSpecLocator):
                if locator.artifact_type != identity.artifact_type or locator.relative_file_path != identity.stable_locator:
                    raise SnapshotMigrationError("legacy-provenance-conflict", "legacy evidence identity conflicts with its locator", identifiers=(_safe_record_id(item.id),))
                migrated_locator = OpenSpecLocator(locator.relative_file_path, locator.artifact_type, locator.openspec_identity, locator.heading_name, locator.line_start, locator.line_end, identity)
                new_id = stable_id("evidence", identity.id, locator.openspec_identity)
            else:
                migrated_locator = SourceArtifactLocator(identity)
                new_id = stable_id("evidence", identity.id)
            properties = dict(item.properties)
            properties.pop("source_artifact_identity", None)
            properties.pop("provenance", None)
            if item.provenance_ids:
                retained_records = tuple(provenance.get(record_id) for record_id in item.provenance_ids)
                if any(record is None or record != provenance_record for record in retained_records):
                    raise SnapshotMigrationError(
                        "legacy-provenance-conflict",
                        "legacy evidence retained provenance conflicts with its embedded provenance",
                        identifiers=(_safe_record_id(item.id),),
                    )
                provenance_ids = item.provenance_ids
            else:
                provenance_ids = (provenance_record.id,)
            converted = Evidence(new_id, item.source, migrated_locator, properties, provenance_ids)
            migrated.pop(item.id, None)
            existing = migrated.get(new_id)
            if existing is not None and existing.as_dict() != converted.as_dict():
                raise SnapshotMigrationError("legacy-evidence-conflict", "legacy evidence records conflict after coalescing", identifiers=(_safe_record_id(new_id),))
            migrated[new_id] = converted
            evidence_ids[item.id] = new_id
            provenance[provenance_record.id] = provenance_record
        except SnapshotMigrationError:
            raise
        except (TypeError, ValueError) as exc:
            raise SnapshotMigrationError("legacy-provenance-insufficient", "legacy evidence lacks complete retained identity or provenance", identifiers=(_safe_record_id(item.id),)) from exc

    if not evidence_ids:
        return snapshot
    remap = lambda ids: tuple(sorted({evidence_ids.get(item, item) for item in ids}))
    nodes = tuple(Node(item.id, item.kind, item.name, item.properties, remap(item.evidence_ids)) for item in snapshot.nodes)
    edges = tuple(Edge(item.id, item.kind, item.source_id, item.target_id, item.properties, remap(item.evidence_ids), item.confidence) for item in snapshot.edges)
    observations = tuple(CrossGraphLinkEvidence(item.claim_id, item.strategy_id, item.observation_id, evidence_ids.get(item.provenance_evidence_id, item.provenance_evidence_id), item.origin, item.status, item.confidence, item.trust_disposition, item.pull_request_evidence_id, item.declared_association_id, item.verification_evidence_id) for item in snapshot.cross_graph_link_evidence)
    lifecycle = tuple(CrossGraphLinkLifecycle(item.claim_id, item.revision, item.state, evidence_ids.get(item.provenance_evidence_id, item.provenance_evidence_id), item.origin, item.status, item.confidence, item.trust_disposition) for item in snapshot.cross_graph_link_lifecycle)
    prs = tuple(PullRequestImplementationEvidence(item.pull_request_id, item.repository_id, item.base_revision, item.head_revision, item.merged, evidence_ids.get(item.source_evidence_id, item.source_evidence_id), evidence_ids.get(item.provenance_evidence_id, item.provenance_evidence_id)) for item in snapshot.pull_request_evidence)
    associations = tuple(PullRequestDeclaredAssociation(item.pull_request_evidence_id, item.intended_change_id, evidence_ids.get(item.source_evidence_id, item.source_evidence_id), evidence_ids.get(item.provenance_evidence_id, item.provenance_evidence_id)) for item in snapshot.pull_request_declared_associations)
    relations = tuple(PullRequestObservedRepositoryRelation(item.pull_request_evidence_id, item.repository_id, evidence_ids.get(item.source_evidence_id, item.source_evidence_id), evidence_ids.get(item.provenance_evidence_id, item.provenance_evidence_id)) for item in snapshot.pull_request_observed_repository_relations)
    return GraphSnapshot(nodes, edges, tuple(migrated.values()), snapshot.cross_graph_link_claims, observations, lifecycle, tuple(provenance.values()), prs, associations, relations, allow_legacy_evidence=True)


def _legacy_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SnapshotMigrationError("legacy-provenance-insufficient", "legacy provenance contains a missing required field", identifiers=(field,))
    return value


BUILTIN_DESCRIPTORS = (
    SnapshotSourceDescriptor("unversioned-current-canonical-v4", _current_descriptor, None, CURRENT_SCHEMA_VERSION, lambda document: ({**deepcopy(dict(document)), "ontology_schema_version": CURRENT_SCHEMA_VERSION}, 0, 0)),
    SnapshotSourceDescriptor("unversioned-openspec-prefixed-canonicalization", _legacy_descriptor, None, CURRENT_SCHEMA_VERSION, _legacy_transform),
)
DEFAULT_REGISTRY = SnapshotMigrationRegistry()
