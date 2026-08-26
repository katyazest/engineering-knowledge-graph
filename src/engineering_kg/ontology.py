"""Canonical in-memory ontology models for the Engineering KG MVP."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class NodeKind(StrEnum):
    WORKSPACE = "workspace"
    SERVICE = "service"
    REPOSITORY = "repository"
    SPECIFICATION = "specification"
    REQUIREMENT = "requirement"
    SCENARIO = "scenario"
    OPENSPEC_CHANGE = "openspec_change"
    JIRA_STORY = "jira_story"
    PULL_REQUEST = "pull_request"
    CONTRACT = "contract"
    EXTERNAL_SYSTEM = "external_system"
    BUSINESS_PROCESS = "business_process"
    ADR = "adr"
    OPENSPEC_ACTIVE_CHANGE = "openspec-active-change"
    OPENSPEC_ARCHIVED_CHANGE = "openspec-archived-change"
    OPENSPEC_ARTIFACT = "openspec-artifact"


class EdgeKind(StrEnum):
    CONTAINS = "contains"
    DEPENDS_ON = "depends_on"
    IMPLEMENTS = "implements"
    IMPLEMENTS_CHANGE = "implements_change"
    TRACES_TO = "traces_to"
    REFERENCES_CODE = "references_code"
    OWNS = "owns"
    OPENSPEC_CHANGE_HAS_ARTIFACT = "openspec-change-has-artifact"
    ASSERTS = "asserts"
    RELATED_TO = "related_to"


def stable_id(object_kind: str, *identity_parts: object) -> str:
    """Return a deterministic ID from an object kind and explicit identity parts."""

    normalized_parts = [
        _normalize_identity_part(object_kind),
        *(_normalize_identity_part(part) for part in identity_parts),
    ]
    raw_identity = "\x1f".join(normalized_parts)
    digest = hashlib.sha256(raw_identity.encode("utf-8")).hexdigest()[:16]
    return f"{normalized_parts[0]}:{digest}"


def openspec_specification_id(repository_id: str, capability: str) -> str:
    """Return the source-independent ID for an OpenSpec-backed specification."""

    return stable_id("node", NodeKind.SPECIFICATION, repository_id, capability)


def openspec_requirement_id(specification_id: str, requirement_key: str) -> str:
    """Return the source-independent ID for an OpenSpec-backed requirement."""

    return stable_id("node", NodeKind.REQUIREMENT, specification_id, requirement_key)


def openspec_scenario_id(requirement_id: str, scenario_key: str) -> str:
    """Return the source-independent ID for an OpenSpec-backed scenario."""

    return stable_id("node", NodeKind.SCENARIO, requirement_id, scenario_key)


def _normalize_identity_part(part: object) -> str:
    if isinstance(part, StrEnum):
        part = part.value
    text = str(part).strip().lower()
    return " ".join(text.split())


def _serialize_value(value: Any) -> Any:
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _serialize_value(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    return value


@dataclass(frozen=True)
class CodeLocator:
    repository: str
    revision: str
    file: str
    symbol: str

    def as_dict(self) -> dict[str, str]:
        return {
            "file": self.file,
            "repository": self.repository,
            "revision": self.revision,
            "symbol": self.symbol,
        }


@dataclass(frozen=True)
class ConfluencePageRef:
    page_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            "page_id": self.page_id,
        }


@dataclass(frozen=True)
class OpenSpecLocator:
    relative_file_path: str
    artifact_type: str
    openspec_identity: str
    heading_name: str = ""
    line_start: int | None = None
    line_end: int | None = None

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "artifact_type": self.artifact_type,
            "openspec_identity": self.openspec_identity,
            "relative_file_path": self.relative_file_path,
        }
        if self.heading_name:
            data["heading_name"] = self.heading_name
        if self.line_start is not None:
            data["line_start"] = self.line_start
        if self.line_end is not None:
            data["line_end"] = self.line_end
        return data


@dataclass(frozen=True)
class Evidence:
    id: str
    source: str
    locator: str | CodeLocator | ConfluencePageRef | OpenSpecLocator
    properties: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "locator": _serialize_value(self.locator),
            "properties": _serialize_value(self.properties),
            "source": self.source,
        }


@dataclass(frozen=True)
class Node:
    id: str
    kind: NodeKind | str
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_ids": list(self.evidence_ids),
            "id": self.id,
            "kind": _serialize_value(self.kind),
            "name": self.name,
            "properties": _serialize_value(self.properties),
        }


@dataclass(frozen=True)
class Edge:
    id: str
    kind: EdgeKind | str
    source_id: str
    target_id: str
    properties: dict[str, Any] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
    confidence: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = {
            "evidence_ids": list(self.evidence_ids),
            "id": self.id,
            "kind": _serialize_value(self.kind),
            "properties": _serialize_value(self.properties),
            "source_id": self.source_id,
            "target_id": self.target_id,
        }
        if self.confidence is not None:
            data["confidence"] = self.confidence
        return data


@dataclass(frozen=True)
class GraphSnapshot:
    nodes: tuple[Node, ...] = ()
    edges: tuple[Edge, ...] = ()
    evidence: tuple[Evidence, ...] = ()

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)

    def as_dict(self) -> dict[str, Any]:
        return {
            "edge_count": self.edge_count,
            "edges": [_serialize_value(edge) for edge in self.edges],
            "evidence": [_serialize_value(item) for item in self.evidence],
            "evidence_count": self.evidence_count,
            "node_count": self.node_count,
            "nodes": [_serialize_value(node) for node in self.nodes],
        }

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True)

    def merged_with(self, other: "GraphSnapshot") -> "GraphSnapshot":
        nodes = _merge_records(self.nodes, other.nodes)
        edges = _merge_records(self.edges, other.edges)
        evidence = _merge_records(self.evidence, other.evidence)
        return GraphSnapshot(nodes=nodes, edges=edges, evidence=evidence)


def _merge_records(left: tuple[Any, ...], right: tuple[Any, ...]) -> tuple[Any, ...]:
    records: dict[str, Any] = {}
    order: list[str] = []
    for item in (*left, *right):
        existing = records.get(item.id)
        if existing is None:
            records[item.id] = item
            order.append(item.id)
        else:
            records[item.id] = _merge_record(existing, item)
    return tuple(records[item_id] for item_id in order)


def _merge_record(left: Any, right: Any) -> Any:
    if type(left) is not type(right):
        raise ValueError(f"Conflicting graph record types for ID: {left.id}")
    if isinstance(left, (Node, Edge)):
        left_data = left.as_dict()
        right_data = right.as_dict()
        left_data.pop("evidence_ids")
        right_data.pop("evidence_ids")
        if isinstance(left, Node):
            left_data.pop("name")
            right_data.pop("name")
        if left_data != right_data:
            raise ValueError(f"Conflicting graph record values for ID: {left.id}")
        evidence_ids = tuple(sorted(set(left.evidence_ids) | set(right.evidence_ids)))
        if isinstance(left, Node):
            return dataclass_replace(left, name=min(left.name, right.name), evidence_ids=evidence_ids)
        return dataclass_replace(left, evidence_ids=evidence_ids)
    if left.as_dict() != right.as_dict():
        raise ValueError(f"Conflicting graph record values for ID: {left.id}")
    return left


def dataclass_replace(value: Any, **changes: Any) -> Any:
    """Avoid exposing dataclasses.replace at the graph model boundary."""

    from dataclasses import replace

    return replace(value, **changes)
