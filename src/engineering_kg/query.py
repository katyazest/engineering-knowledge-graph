"""Deterministic local query API for Engineering KG graph snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engineering_kg.ontology import (
    Edge,
    EdgeKind,
    Evidence,
    GraphSnapshot,
    Node,
    NodeKind,
)
from engineering_kg.persistence import read_graph_snapshot
from engineering_kg.validation import GraphValidationResult, validate_graph_integrity


QUERY_FORBIDDEN_FIELDS = frozenset(
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
        "generated_graph_records",
        "jira_payload",
        "bitbucket_payload",
        "confluence_content",
        "openlore_analysis",
        "page_content",
        "page_url",
        "source_code",
        "symbol_body",
        "token",
        "tokens",
        "url",
    }
)


class GraphQueryError(ValueError):
    """Base class for Engineering KG query failures."""

    code = "graph-query-error"

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
        }


class GraphObjectNotFoundError(GraphQueryError):
    """Raised when a query references a missing graph object."""

    code = "graph-object-not-found"

    def __init__(self, object_id: str) -> None:
        self.object_id = object_id
        super().__init__(f"Graph object not found: {object_id}")

    def as_dict(self) -> dict[str, Any]:
        data = super().as_dict()
        data["object_id"] = self.object_id
        return data


class GraphQueryValidationError(GraphQueryError):
    """Raised when a query requires a valid graph but validation fails."""

    code = "graph-validation-failed"

    def __init__(self, validation: GraphValidationResult) -> None:
        self.validation = validation
        super().__init__("Graph integrity validation failed")

    def as_dict(self) -> dict[str, Any]:
        data = super().as_dict()
        data["validation"] = self.validation.as_dict()
        return data


@dataclass(frozen=True)
class QueryNodeResult:
    """Serializable graph node query result."""

    id: str
    kind: str
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
    locators: tuple[dict[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_ids": list(self.evidence_ids),
            "id": self.id,
            "kind": self.kind,
            "locators": [dict(item) for item in self.locators],
            "name": self.name,
            "properties": _sanitize_value(self.properties),
        }


@dataclass(frozen=True)
class TraceabilityResult:
    """Serializable graph traceability query result."""

    object_id: str
    relationships: tuple[dict[str, Any], ...] = ()
    missing: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "missing": self.missing,
            "object_id": self.object_id,
            "relationships": [_sanitize_value(item) for item in self.relationships],
        }


class EngineeringKgQuery:
    """Reusable query facade over canonical Engineering KG graph snapshots."""

    def __init__(
        self,
        snapshot: GraphSnapshot,
        validation: GraphValidationResult | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.validation = validation
        self._nodes_by_id = {node.id: node for node in snapshot.nodes}
        self._evidence_by_id = {item.id: item for item in snapshot.evidence}

    @classmethod
    def from_snapshot(
        cls,
        snapshot: GraphSnapshot,
        validation: GraphValidationResult | None = None,
    ) -> "EngineeringKgQuery":
        return cls(snapshot=snapshot, validation=validation)

    @classmethod
    def from_store(
        cls,
        path: str | Path,
        validation: GraphValidationResult | None = None,
        require_validation: bool = False,
    ) -> "EngineeringKgQuery":
        snapshot = read_graph_snapshot(path)
        validation_result = validation
        if require_validation and validation_result is None:
            validation_result = validate_graph_integrity(snapshot)
            _raise_if_invalid(validation_result)
        return cls(snapshot=snapshot, validation=validation_result)

    def list_requirements(
        self,
        *,
        capability: str | None = None,
        service: str | None = None,
        change: str | None = None,
        evidence_ref: str | None = None,
    ) -> list[dict[str, Any]]:
        nodes = [
            node
            for node in self.snapshot.nodes
            if _value(node.kind) in {NodeKind.REQUIREMENT.value, NodeKind.OPENSPEC_REQUIREMENT.value}
        ]
        if capability:
            nodes = [node for node in nodes if self._node_related_to_property(node, "capability", capability)]
        if service:
            nodes = [node for node in nodes if self._node_related_to_kind_name(node, NodeKind.SERVICE, service)]
        if change:
            nodes = [
                node
                for node in nodes
                if self._node_related_to_change(node, change)
            ]
        if evidence_ref:
            nodes = [node for node in nodes if self._node_has_evidence_ref(node, evidence_ref)]
        return [self._node_result(node).as_dict() for node in _sort_nodes(nodes)]

    def list_services(self) -> list[dict[str, Any]]:
        services = [node for node in self.snapshot.nodes if _value(node.kind) == NodeKind.SERVICE.value]
        return [self._service_result(node).as_dict() for node in _sort_nodes(services)]

    def list_changes(self) -> list[dict[str, Any]]:
        changes = [
            node
            for node in self.snapshot.nodes
            if _value(node.kind)
            in {NodeKind.OPENSPEC_ACTIVE_CHANGE.value, NodeKind.OPENSPEC_ARCHIVED_CHANGE.value}
        ]
        return [self._change_result(node).as_dict() for node in _sort_nodes(changes)]

    def get_traceability(
        self,
        object_id: str,
        *,
        require_validation: bool = False,
        missing_ok: bool = True,
    ) -> dict[str, Any]:
        if require_validation:
            validation = self.validation or validate_graph_integrity(self.snapshot)
            _raise_if_invalid(validation)
        if object_id not in self._nodes_by_id:
            if missing_ok:
                return TraceabilityResult(object_id=object_id, missing=True).as_dict()
            raise GraphObjectNotFoundError(object_id)

        relationships = tuple(
            self._edge_result(edge)
            for edge in _sort_edges(
                edge
                for edge in self.snapshot.edges
                if edge.source_id == object_id or edge.target_id == object_id
            )
        )
        return TraceabilityResult(object_id=object_id, relationships=relationships).as_dict()

    def _node_result(self, node: Node) -> QueryNodeResult:
        return QueryNodeResult(
            id=node.id,
            kind=str(_value(node.kind)),
            name=node.name,
            properties=dict(node.properties),
            evidence_ids=tuple(sorted(node.evidence_ids)),
            locators=self._locators_for(node.evidence_ids),
        )

    def _service_result(self, node: Node) -> QueryNodeResult:
        repositories = [
            self._nodes_by_id[edge.target_id].id
            for edge in self.snapshot.edges
            if edge.source_id == node.id
            and _value(edge.kind) in {EdgeKind.OWNS.value, EdgeKind.CONTAINS.value}
            and edge.target_id in self._nodes_by_id
            and _value(self._nodes_by_id[edge.target_id].kind) == NodeKind.REPOSITORY.value
        ]
        properties = dict(node.properties)
        if repositories:
            properties["repository_ids"] = sorted(repositories)
        return QueryNodeResult(
            id=node.id,
            kind=str(_value(node.kind)),
            name=node.name,
            properties=properties,
            evidence_ids=tuple(sorted(node.evidence_ids)),
            locators=self._locators_for(node.evidence_ids),
        )

    def _change_result(self, node: Node) -> QueryNodeResult:
        properties = dict(node.properties)
        properties["artifact_ids"] = self._targets_for(node.id, EdgeKind.OPENSPEC_CHANGE_HAS_ARTIFACT)
        touched = self._targets_for(node.id, EdgeKind.OPENSPEC_CHANGE_TOUCHES_SPEC)
        traced = self._targets_for(node.id, EdgeKind.OPENSPEC_CHANGE_TRACES_TO_SPEC)
        properties["touched_spec_ids"] = touched
        properties["traceability_spec_ids"] = traced
        properties["missing_durable_spec_links"] = [
            item for item in touched if item not in set(traced)
        ]
        return QueryNodeResult(
            id=node.id,
            kind=str(_value(node.kind)),
            name=node.name,
            properties=properties,
            evidence_ids=tuple(sorted(node.evidence_ids)),
            locators=self._locators_for(node.evidence_ids),
        )

    def _edge_result(self, edge: Edge) -> dict[str, Any]:
        data: dict[str, Any] = {
            "edge_id": edge.id,
            "evidence_ids": sorted(edge.evidence_ids),
            "kind": str(_value(edge.kind)),
            "properties": _sanitize_value(edge.properties),
            "source_id": edge.source_id,
            "target_id": edge.target_id,
        }
        if edge.confidence is not None:
            data["confidence"] = edge.confidence
        locators = self._locators_for(edge.evidence_ids)
        if locators:
            data["locators"] = [dict(item) for item in locators]
        return data

    def _targets_for(self, source_id: str, kind: EdgeKind) -> list[str]:
        return sorted(
            edge.target_id
            for edge in self.snapshot.edges
            if edge.source_id == source_id and _value(edge.kind) == kind.value
        )

    def _locators_for(self, evidence_ids: tuple[str, ...]) -> tuple[dict[str, Any], ...]:
        locators: list[dict[str, Any]] = []
        for evidence_id in sorted(evidence_ids):
            evidence = self._evidence_by_id.get(evidence_id)
            if evidence is None:
                continue
            locators.append(_evidence_locator(evidence))
        return tuple(locators)

    def _node_has_evidence_ref(self, node: Node, evidence_ref: str) -> bool:
        if evidence_ref in node.evidence_ids:
            return True
        for edge in self._edges_touching(node.id):
            if evidence_ref in edge.evidence_ids:
                return True
        return False

    def _node_related_to_change(self, node: Node, change: str) -> bool:
        for related_id in self._reachable_ids(node.id):
            related = self._nodes_by_id.get(related_id)
            if related is None:
                continue
            if _value(related.kind) in {
                NodeKind.OPENSPEC_ACTIVE_CHANGE.value,
                NodeKind.OPENSPEC_ARCHIVED_CHANGE.value,
            } and (related.id == change or related.name == change):
                return True
        return False

    def _node_related_to_kind_name(self, node: Node, kind: NodeKind, name: str) -> bool:
        for related_id in self._reachable_ids(node.id):
            related = self._nodes_by_id.get(related_id)
            if related and _value(related.kind) == kind.value and (related.id == name or related.name == name):
                return True
        return False

    def _node_related_to_property(self, node: Node, key: str, expected: str) -> bool:
        if node.properties.get(key) == expected:
            return True
        for related_id in self._reachable_ids(node.id):
            related = self._nodes_by_id.get(related_id)
            if related and related.properties.get(key) == expected:
                return True
        return False

    def _reachable_ids(self, node_id: str) -> set[str]:
        related = {node_id}
        changed = True
        while changed:
            changed = False
            for edge in self.snapshot.edges:
                if self._is_workspace(edge.source_id) or self._is_workspace(edge.target_id):
                    continue
                if edge.source_id in related and edge.target_id not in related:
                    related.add(edge.target_id)
                    changed = True
                if edge.target_id in related and edge.source_id not in related:
                    related.add(edge.source_id)
                    changed = True
        return related

    def _is_workspace(self, node_id: str) -> bool:
        node = self._nodes_by_id.get(node_id)
        return node is not None and _value(node.kind) == NodeKind.WORKSPACE.value

    def _edges_touching(self, node_id: str) -> tuple[Edge, ...]:
        return tuple(
            edge for edge in self.snapshot.edges if edge.source_id == node_id or edge.target_id == node_id
        )


def _raise_if_invalid(validation: GraphValidationResult) -> None:
    if validation.status != "valid":
        raise GraphQueryValidationError(validation)


def _sort_nodes(nodes: list[Node]) -> tuple[Node, ...]:
    return tuple(sorted(nodes, key=lambda item: (item.id, str(_value(item.kind)), item.name)))


def _sort_edges(edges: Any) -> tuple[Edge, ...]:
    return tuple(sorted(edges, key=lambda item: (item.id, str(_value(item.kind)), item.source_id, item.target_id)))


def _evidence_locator(evidence: Evidence) -> dict[str, Any]:
    locator = evidence.locator.as_dict() if hasattr(evidence.locator, "as_dict") else evidence.locator
    return {
        "evidence_id": evidence.id,
        "locator": _sanitize_value(locator),
        "source": evidence.source,
    }


def _sanitize_value(value: Any) -> Any:
    if hasattr(value, "as_dict"):
        value = value.as_dict()
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key in sorted(value, key=lambda item: str(item)):
            key_text = str(key)
            if key_text in QUERY_FORBIDDEN_FIELDS:
                continue
            sanitized[key_text] = _sanitize_value(value[key])
        return sanitized
    if isinstance(value, tuple):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _value(value: object) -> object:
    return getattr(value, "value", value)
