"""Storage-neutral codec for the logical Engineering KG snapshot envelope.

The codec deliberately deals in JSON-compatible mappings.  It has no knowledge
of a storage adapter; adapters are responsible for loading and committing the
mapping.
"""

from __future__ import annotations

from typing import Any, Mapping

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
    PullRequestDeclaredAssociation,
    PullRequestImplementationEvidence,
    PullRequestObservedRepositoryRelation,
    SourceArtifactIdentity,
    SourceArtifactLocator,
)
from engineering_kg.relationship_vocabulary import CATALOG_REVISION


CURRENT_SCHEMA_VERSION = 1


class SnapshotCodecError(ValueError):
    """The logical document cannot be decoded as the current format."""


def empty_document(catalog_revision: str) -> dict[str, Any]:
    return _document({}, catalog_revision)


def serialize_snapshot(snapshot: GraphSnapshot, catalog_revision: str) -> dict[str, Any]:
    """Serialize a validated current snapshot to deterministic record maps."""
    result = _document({}, catalog_revision)
    for collection, order_key, records in (
        ("nodes", "node_order", snapshot.nodes),
        ("edges", "edge_order", snapshot.edges),
        ("evidence", "evidence_order", snapshot.evidence),
        ("provenance", "provenance_order", snapshot.provenance),
        ("cross_graph_link_claims", "cross_graph_link_claim_order", snapshot.cross_graph_link_claims),
        ("cross_graph_link_evidence", "cross_graph_link_evidence_order", snapshot.cross_graph_link_evidence),
        ("cross_graph_link_lifecycle", "cross_graph_link_lifecycle_order", snapshot.cross_graph_link_lifecycle),
        ("pull_request_evidence", "pull_request_evidence_order", snapshot.pull_request_evidence),
        ("pull_request_declared_associations", "pull_request_declared_association_order", snapshot.pull_request_declared_associations),
        ("pull_request_observed_repository_relations", "pull_request_observed_repository_relation_order", snapshot.pull_request_observed_repository_relations),
    ):
        result[collection] = {record.id: record.as_dict() for record in records}
        result[order_key] = [record.id for record in records]
    reject_forbidden_fields(result)
    return result


def deserialize_snapshot(document: Mapping[str, Any], *, allow_legacy_evidence: bool = False) -> GraphSnapshot:
    """Decode one current logical document and run model-level validation."""
    data = dict(document)
    reject_forbidden_fields(data)
    if data.get("catalog_revision") != CATALOG_REVISION:
        raise SnapshotCodecError("unsupported-catalog-revision")
    nodes = tuple(_node(item) for item in _ordered(data, "nodes", "node_order"))
    edges = tuple(_edge(item) for item in _ordered(data, "edges", "edge_order"))
    evidence = tuple(_evidence(item, allow_legacy_evidence) for item in _ordered(data, "evidence", "evidence_order"))
    provenance = tuple(_provenance(item) for item in _ordered(data, "provenance", "provenance_order"))
    claims = tuple(_claim(item) for item in _ordered(data, "cross_graph_link_claims", "cross_graph_link_order"))
    observations = tuple(_observation(item) for item in _ordered(data, "cross_graph_link_evidence", "cross_graph_link_evidence_order"))
    lifecycle = tuple(_lifecycle(item) for item in _ordered(data, "cross_graph_link_lifecycle", "cross_graph_link_lifecycle_order"))
    prs = tuple(_pr(item) for item in _ordered(data, "pull_request_evidence", "pull_request_evidence_order"))
    associations = tuple(_association(item) for item in _ordered(data, "pull_request_declared_associations", "pull_request_declared_association_order"))
    relations = tuple(_relation(item) for item in _ordered(data, "pull_request_observed_repository_relations", "pull_request_observed_repository_relation_order"))
    try:
        return GraphSnapshot(
            nodes, edges, evidence, claims, observations, lifecycle, provenance,
            prs, associations, relations, allow_legacy_evidence=allow_legacy_evidence,
        )
    except (TypeError, ValueError) as exc:
        raise SnapshotCodecError(str(exc)) from exc


def reject_forbidden_fields(value: Any, path: str = "graph") -> None:
    forbidden = {
        "api_response", "attachments", "call_graph", "class_body", "comments",
        "content", "credentials", "dependency_graph", "external_api_response",
        "framework", "function_body", "log", "logs", "openlore_analysis",
        "outcome", "page_content", "page_url", "source_code", "test_output",
        "token", "tokens", "url", "coverage", "provider_payload", "ci_payload",
    }
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).casefold().replace("-", "_") in forbidden:
                raise SnapshotCodecError(f"{path}.{key} is not allowed in persistence")
            reject_forbidden_fields(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            reject_forbidden_fields(nested, f"{path}[{index}]")


def _document(records: dict[str, Any], catalog_revision: str) -> dict[str, Any]:
    return {
        "catalog_revision": catalog_revision,
        "ontology_schema_version": CURRENT_SCHEMA_VERSION,
        "edge_order": [], "edges": {}, "evidence": {}, "evidence_order": [],
        "provenance": {}, "provenance_order": [],
        "cross_graph_link_claims": {}, "cross_graph_link_claim_order": [],
        "cross_graph_link_evidence": {}, "cross_graph_link_evidence_order": [],
        "cross_graph_link_lifecycle": {}, "cross_graph_link_lifecycle_order": [],
        "pull_request_evidence": {}, "pull_request_evidence_order": [],
        "pull_request_declared_associations": {}, "pull_request_declared_association_order": [],
        "pull_request_observed_repository_relations": {}, "pull_request_observed_repository_relation_order": [],
        "node_order": [], "nodes": {}, **records,
    }


def _ordered(data: Mapping[str, Any], collection: str, order_key: str) -> list[dict[str, Any]]:
    records = data.get(collection, {})
    order = data.get(order_key, [])
    if not isinstance(records, dict) or not isinstance(order, list):
        raise SnapshotCodecError(f"{collection} and {order_key} must be mappings and lists")
    ids = list(order) if order else sorted(records)
    ids.extend(item for item in sorted(records) if item not in ids)
    result = []
    for record_id in ids:
        if record_id not in records or not isinstance(records[record_id], dict):
            raise SnapshotCodecError(f"Persisted record order references unknown id: {record_id}")
        record = records[record_id]
        if record.get("id") != record_id:
            raise SnapshotCodecError(f"Persisted record id mismatch: {record_id}")
        result.append(record)
    return result


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SnapshotCodecError(f"{name} must be a non-empty string")
    return value


def _optional_text(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SnapshotCodecError(f"{name} must be a string")
    return value


def _texts(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise SnapshotCodecError(f"{name} must be a list")
    return tuple(_text(item, f"{name}[]") for item in value)


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SnapshotCodecError(f"{name} must be a mapping")
    return dict(value)


def _allowed(item: dict[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(item) - allowed)
    if unknown:
        raise SnapshotCodecError(f"{context}.{unknown[0]} is not allowed")


def _node(item: dict[str, Any]) -> Node:
    _allowed(item, {"evidence_ids", "id", "kind", "name", "properties"}, "node")
    return Node(_text(item.get("id"), "node.id"), _text(item.get("kind"), "node.kind"), _text(item.get("name"), "node.name"), _mapping(item.get("properties", {}), "node.properties"), _texts(item.get("evidence_ids", []), "node.evidence_ids"))


def _edge(item: dict[str, Any]) -> Edge:
    _allowed(item, {"confidence", "evidence_ids", "id", "kind", "properties", "source_id", "target_id"}, "edge")
    return Edge(_text(item.get("id"), "edge.id"), _text(item.get("kind"), "edge.kind"), _text(item.get("source_id"), "edge.source_id"), _text(item.get("target_id"), "edge.target_id"), _mapping(item.get("properties", {}), "edge.properties"), _texts(item.get("evidence_ids", []), "edge.evidence_ids"), _optional_text(item.get("confidence"), "edge.confidence"))


def _evidence(item: dict[str, Any], allow_legacy: bool) -> Evidence:
    _allowed(item, {"id", "source", "locator", "properties", "provenance_ids"}, "evidence")
    try:
        return Evidence(_text(item.get("id"), "evidence.id"), _text(item.get("source"), "evidence.source"), _locator(item.get("locator")), _mapping(item.get("properties", {}), "evidence.properties"), _texts(item.get("provenance_ids", []), "evidence.provenance_ids"))
    except (TypeError, ValueError) as exc:
        raise SnapshotCodecError(str(exc)) from exc


def _identity(value: Any) -> SourceArtifactIdentity:
    item = _mapping(value, "source_artifact_identity")
    _allowed(item, {"artifact_type", "id", "revision_or_version", "source_identity", "source_type", "stable_locator"}, "source_artifact_identity")
    try:
        return SourceArtifactIdentity(_text(item.get("source_type"), "source_artifact_identity.source_type"), _text(item.get("source_identity"), "source_artifact_identity.source_identity"), _text(item.get("artifact_type"), "source_artifact_identity.artifact_type"), _text(item.get("revision_or_version"), "source_artifact_identity.revision_or_version"), _text(item.get("stable_locator"), "source_artifact_identity.stable_locator"))
    except ValueError as exc:
        raise SnapshotCodecError(str(exc)) from exc


def _locator(value: Any) -> Any:
    if isinstance(value, str):
        return value
    item = _mapping(value, "evidence.locator")
    keys = set(item)
    try:
        if keys == {"file", "repository", "revision", "symbol"}:
            return CodeLocator(_text(item["repository"], "locator.repository"), _text(item["revision"], "locator.revision"), _text(item["file"], "locator.file"), _text(item["symbol"], "locator.symbol"))
        if keys == {"page_id"}:
            return ConfluencePageRef(_text(item["page_id"], "locator.page_id"))
        if keys == {"navigation_detail", "source_artifact_identity"}:
            return SourceArtifactLocator(_identity(item["source_artifact_identity"]), _mapping(item["navigation_detail"], "locator.navigation_detail"))
        if {"artifact_type", "openspec_identity", "relative_file_path"}.issubset(keys):
            _allowed(item, {"artifact_type", "heading_name", "line_end", "line_start", "openspec_identity", "relative_file_path", "source_artifact_identity"}, "locator")
            identity = _identity(item["source_artifact_identity"]) if item.get("source_artifact_identity") is not None else None
            return OpenSpecLocator(_text(item["relative_file_path"], "locator.relative_file_path"), _text(item["artifact_type"], "locator.artifact_type"), _text(item["openspec_identity"], "locator.openspec_identity"), _optional_text(item.get("heading_name", ""), "locator.heading_name") or "", item.get("line_start"), item.get("line_end"), identity)
    except (TypeError, ValueError) as exc:
        raise SnapshotCodecError(str(exc)) from exc
    raise SnapshotCodecError(f"Unsupported evidence locator shape: {sorted(keys)}")


def _provenance(item: dict[str, Any]) -> ProvenanceRecord:
    try:
        record = ProvenanceRecord(_text(item.get("kind"), "provenance.kind"), _text(item.get("observed_at"), "provenance.observed_at"), _text(item.get("content_hash_algorithm"), "provenance.content_hash_algorithm"), _text(item.get("content_hash"), "provenance.content_hash"), _text(item.get("extractor_id"), "provenance.extractor_id"), _text(item.get("extractor_version"), "provenance.extractor_version"), _identity(item["source_artifact_identity"]) if item.get("source_artifact_identity") is not None else None, _optional_text(item.get("derivation_rule_id"), "provenance.derivation_rule_id"), _texts(item.get("input_provenance_ids", []), "provenance.input_provenance_ids"))
    except (TypeError, ValueError) as exc:
        raise SnapshotCodecError(str(exc)) from exc
    if item.get("id") != record.id:
        raise SnapshotCodecError("provenance.id does not match its stable identity")
    return record


def _claim(item: dict[str, Any]) -> CrossGraphLinkClaim:
    try:
        target = _locator(item.get("target"))
        return CrossGraphLinkClaim(_text(item.get("subject_id"), "claim.subject_id"), _text(item.get("relation_kind"), "claim.relation_kind"), target)
    except (TypeError, ValueError) as exc:
        raise SnapshotCodecError(str(exc)) from exc


def _observation(item: dict[str, Any]) -> CrossGraphLinkEvidence:
    try:
        for field in ("claim_id", "strategy_id", "observation_id", "provenance_evidence_id", "origin", "status", "confidence", "trust_disposition"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise SnapshotCodecError(f"cross_graph_link_evidence.{field} must be a non-empty string")
        if item.get("strategy_id") == "pr-code-candidate-extraction" and (item.get("pull_request_evidence_id") is None or item.get("declared_association_id") is None):
            raise SnapshotCodecError("legacy-pr-candidate-readback-unsupported: PR candidate lacks explicit PR evidence and association")
        return CrossGraphLinkEvidence(_text(item.get("claim_id"), "observation.claim_id"), _text(item.get("strategy_id"), "observation.strategy_id"), _text(item.get("observation_id"), "observation.observation_id"), _text(item.get("provenance_evidence_id"), "observation.provenance_evidence_id"), _text(item.get("origin"), "observation.origin"), _text(item.get("status"), "observation.status"), _text(item.get("confidence"), "observation.confidence"), _text(item.get("trust_disposition"), "observation.trust_disposition"), _optional_text(item.get("pull_request_evidence_id"), "observation.pull_request_evidence_id"), _optional_text(item.get("declared_association_id"), "observation.declared_association_id"), _optional_text(item.get("verification_evidence_id"), "observation.verification_evidence_id"))
    except (TypeError, ValueError) as exc:
        raise SnapshotCodecError(str(exc)) from exc


def _lifecycle(item: dict[str, Any]) -> CrossGraphLinkLifecycle:
    try:
        for field in ("claim_id", "state", "provenance_evidence_id", "origin", "status", "confidence", "trust_disposition"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise SnapshotCodecError(f"cross_graph_link_lifecycle.{field} must be a non-empty string")
        return CrossGraphLinkLifecycle(_text(item.get("claim_id"), "lifecycle.claim_id"), item.get("revision"), _text(item.get("state"), "lifecycle.state"), _text(item.get("provenance_evidence_id"), "lifecycle.provenance_evidence_id"), _text(item.get("origin"), "lifecycle.origin"), _text(item.get("status"), "lifecycle.status"), _text(item.get("confidence"), "lifecycle.confidence"), _text(item.get("trust_disposition"), "lifecycle.trust_disposition"))
    except (TypeError, ValueError) as exc:
        raise SnapshotCodecError(str(exc)) from exc


def _pr(item: dict[str, Any]) -> PullRequestImplementationEvidence:
    try:
        return PullRequestImplementationEvidence(_text(item.get("pull_request_id"), "pr.pull_request_id"), _text(item.get("repository_id"), "pr.repository_id"), _text(item.get("base_revision"), "pr.base_revision"), _text(item.get("head_revision"), "pr.head_revision"), item.get("merged"), _text(item.get("source_evidence_id"), "pr.source_evidence_id"), _text(item.get("provenance_evidence_id"), "pr.provenance_evidence_id"))
    except (TypeError, ValueError) as exc:
        raise SnapshotCodecError(str(exc)) from exc


def _association(item: dict[str, Any]) -> PullRequestDeclaredAssociation:
    try:
        return PullRequestDeclaredAssociation(_text(item.get("pull_request_evidence_id"), "association.pull_request_evidence_id"), _text(item.get("intended_change_id"), "association.intended_change_id"), _text(item.get("source_evidence_id"), "association.source_evidence_id"), _text(item.get("provenance_evidence_id"), "association.provenance_evidence_id"))
    except (TypeError, ValueError) as exc:
        raise SnapshotCodecError(str(exc)) from exc


def _relation(item: dict[str, Any]) -> PullRequestObservedRepositoryRelation:
    try:
        return PullRequestObservedRepositoryRelation(_text(item.get("pull_request_evidence_id"), "relation.pull_request_evidence_id"), _text(item.get("repository_id"), "relation.repository_id"), _text(item.get("source_evidence_id"), "relation.source_evidence_id"), _text(item.get("provenance_evidence_id"), "relation.provenance_evidence_id"))
    except (TypeError, ValueError) as exc:
        raise SnapshotCodecError(str(exc)) from exc
