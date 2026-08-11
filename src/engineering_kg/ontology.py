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
    OPENSPEC_CHANGE = "openspec_change"
    JIRA_STORY = "jira_story"
    PULL_REQUEST = "pull_request"
    CONTRACT = "contract"
    EXTERNAL_SYSTEM = "external_system"
    BUSINESS_PROCESS = "business_process"
    ADR = "adr"


class EdgeKind(StrEnum):
    CONTAINS = "contains"
    DEPENDS_ON = "depends_on"
    IMPLEMENTS = "implements"
    IMPLEMENTS_CHANGE = "implements_change"
    TRACES_TO = "traces_to"
    REFERENCES_CODE = "references_code"
    OWNS = "owns"


def stable_id(object_kind: str, *identity_parts: object) -> str:
    """Return a deterministic ID from an object kind and explicit identity parts."""

    normalized_parts = [
        _normalize_identity_part(object_kind),
        *(_normalize_identity_part(part) for part in identity_parts),
    ]
    raw_identity = "\x1f".join(normalized_parts)
    digest = hashlib.sha256(raw_identity.encode("utf-8")).hexdigest()[:16]
    return f"{normalized_parts[0]}:{digest}"


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
class Evidence:
    id: str
    source: str
    locator: str | CodeLocator | ConfluencePageRef
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

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_ids": list(self.evidence_ids),
            "id": self.id,
            "kind": _serialize_value(self.kind),
            "properties": _serialize_value(self.properties),
            "source_id": self.source_id,
            "target_id": self.target_id,
        }


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
