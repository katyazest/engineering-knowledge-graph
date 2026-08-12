"""OpenSpec store source validation for Engineering KG."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from engineering_kg.ontology import (
    Edge,
    EdgeKind,
    Evidence,
    GraphSnapshot,
    Node,
    NodeKind,
    OpenSpecLocator,
    stable_id,
)
from engineering_kg.project import RepositoryEntry, WorkspaceRegistry


class OpenSpecStoreSourceValidationError(ValueError):
    """Raised when the OpenSpec store source cannot be validated."""


class OpenSpecGraphExtractionError(ValueError):
    """Raised when OpenSpec graph extraction cannot run safely."""


@dataclass(frozen=True)
class RegisteredOpenSpecStore:
    """Structured metadata for one locally registered OpenSpec store."""

    id: str
    path: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "path": str(self.path),
        }


@dataclass(frozen=True)
class OpenSpecStoreSourceValidationResult:
    """Deterministic result for OpenSpec store source validation."""

    status: str
    selection_source: str
    repository_id: str
    repository_role: str
    repository_path: Path
    openspec_root_path: Path
    specs_path: Path
    changes_path: Path
    store_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        data = {
            "changes_path": str(self.changes_path),
            "openspec_root_path": str(self.openspec_root_path),
            "repository_id": self.repository_id,
            "repository_path": str(self.repository_path),
            "repository_role": self.repository_role,
            "selection_source": self.selection_source,
            "specs_path": str(self.specs_path),
            "status": self.status,
        }
        if self.store_id:
            data["store_id"] = self.store_id
        return data


@dataclass(frozen=True)
class OpenSpecExtractionMetadata:
    """Serializable status metadata for one OpenSpec graph extraction run."""

    status: str
    store_id: str
    repository_id: str
    durable_spec_count: int
    active_change_count: int
    archived_change_count: int
    requirement_count: int
    scenario_count: int
    artifact_count: int
    unresolved_related_spec_references: tuple[dict[str, str], ...] = ()
    graph_counts: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "active_change_count": self.active_change_count,
            "archived_change_count": self.archived_change_count,
            "artifact_count": self.artifact_count,
            "durable_spec_count": self.durable_spec_count,
            "graph_counts": dict(sorted(self.graph_counts.items())),
            "repository_id": self.repository_id,
            "requirement_count": self.requirement_count,
            "scenario_count": self.scenario_count,
            "status": self.status,
            "store_id": self.store_id,
            "unresolved_related_spec_references": [
                dict(sorted(item.items())) for item in self.unresolved_related_spec_references
            ],
        }


@dataclass(frozen=True)
class OpenSpecExtractionResult:
    """Canonical graph plus metadata extracted from OpenSpec source files."""

    graph: GraphSnapshot
    metadata: OpenSpecExtractionMetadata

    def as_dict(self) -> dict[str, Any]:
        return {
            "graph": self.graph.as_dict(),
            "metadata": self.metadata.as_dict(),
        }


@dataclass(frozen=True)
class _ParsedSpec:
    scope: str
    capability: str
    path: Path
    node: Node
    evidence: Evidence
    title: str
    related: tuple[str, ...]
    requirements: tuple[Node, ...]
    scenarios: tuple[Node, ...]
    edges: tuple[Edge, ...]
    evidence_items: tuple[Evidence, ...]


_REQUIREMENT_RE = re.compile(r"^### Requirement:\s*(.+?)\s*$")
_SCENARIO_RE = re.compile(r"^#### Scenario:\s*(.+?)\s*$")
_JIRA_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")
_PLANNING_ARTIFACTS = (".openspec.yaml", "proposal.md", "design.md", "tasks.md")


def discover_registered_openspec_stores() -> tuple[RegisteredOpenSpecStore, ...]:
    """Read locally registered OpenSpec stores through the OpenSpec CLI."""

    completed = subprocess.run(
        ["openspec", "store", "list", "--json"],
        text=True,
        capture_output=True,
        check=True,
    )
    return parse_registered_openspec_stores(json.loads(completed.stdout))


def parse_registered_openspec_stores(raw: Any) -> tuple[RegisteredOpenSpecStore, ...]:
    """Parse structured OpenSpec store list/config data into stable store records."""

    stores = raw.get("stores", raw) if isinstance(raw, dict) else raw
    if stores is None:
        stores = []
    if not isinstance(stores, list):
        raise OpenSpecStoreSourceValidationError("OpenSpec store discovery must be a list")

    parsed: list[RegisteredOpenSpecStore] = []
    for index, item in enumerate(stores):
        if not isinstance(item, dict):
            raise OpenSpecStoreSourceValidationError(
                f"OpenSpec store discovery entry {index} must be a mapping"
            )
        store_id = _store_id(item, index)
        store_path = _store_path(item, store_id)
        parsed.append(RegisteredOpenSpecStore(id=store_id, path=store_path))

    return tuple(parsed)


def validate_openspec_store_source(
    registry: WorkspaceRegistry,
    registered_stores: Iterable[RegisteredOpenSpecStore | dict[str, Any]] | None = None,
    selected_store_id: str | None = None,
) -> OpenSpecStoreSourceValidationResult:
    """Validate the OpenSpec store source without reading spec or change bodies."""

    requirements_repo = _requirements_repository(registry)
    stores = _normalized_registered_stores(registered_stores)

    if selected_store_id:
        selected = _select_explicit_store(stores, selected_store_id)
    elif stores:
        selected = _select_matching_registered_store(stores, requirements_repo)
    else:
        return _validate_selected_store(
            selection_source="registry-fallback",
            repository=requirements_repo,
            store_path=requirements_repo.resolved_path,
        )

    _require_matching_path(selected.path, requirements_repo)
    return _validate_selected_store(
        selection_source="registered-store",
        repository=requirements_repo,
        store_path=selected.path,
        store_id=selected.id,
    )


def extract_openspec_graph(
    store_source: OpenSpecStoreSourceValidationResult,
) -> OpenSpecExtractionResult:
    """Extract deterministic canonical graph facts from a validated OpenSpec store."""

    if store_source.status != "valid":
        raise OpenSpecGraphExtractionError("OpenSpec store source must be valid before extraction")
    if not store_source.specs_path.is_dir() or not store_source.changes_path.is_dir():
        raise OpenSpecGraphExtractionError("Validated OpenSpec specs and changes paths must exist")

    nodes: list[Node] = []
    edges: list[Edge] = []
    evidence: list[Evidence] = []
    durable_specs: list[_ParsedSpec] = []
    active_change_count = 0
    archived_change_count = 0
    artifact_count = 0

    for spec_file in sorted(store_source.specs_path.glob("*/spec.md")):
        parsed = _parse_spec_file(store_source, spec_file, "durable", None)
        durable_specs.append(parsed)
        _extend_spec(nodes, edges, evidence, parsed)

    for change_dir in _active_change_dirs(store_source.changes_path):
        active_change_count += 1
        artifact_count += _extract_change_scope(
            store_source,
            change_dir,
            archived=False,
            nodes=nodes,
            edges=edges,
            evidence=evidence,
        )

    archive_dir = store_source.changes_path / "archive"
    if archive_dir.is_dir():
        for change_dir in sorted(item for item in archive_dir.iterdir() if item.is_dir()):
            archived_change_count += 1
            artifact_count += _extract_change_scope(
                store_source,
                change_dir,
                archived=True,
                nodes=nodes,
                edges=edges,
                evidence=evidence,
            )

    related_edges, unresolved = _related_spec_edges(durable_specs)
    edges.extend(related_edges)

    graph = _snapshot(nodes, edges, evidence)
    metadata = OpenSpecExtractionMetadata(
        status="completed",
        store_id=store_source.store_id,
        repository_id=store_source.repository_id,
        durable_spec_count=len(durable_specs),
        active_change_count=active_change_count,
        archived_change_count=archived_change_count,
        requirement_count=sum(len(spec.requirements) for spec in durable_specs),
        scenario_count=sum(len(spec.scenarios) for spec in durable_specs),
        artifact_count=artifact_count,
        unresolved_related_spec_references=tuple(unresolved),
        graph_counts={
            "edge_count": graph.edge_count,
            "evidence_count": graph.evidence_count,
            "node_count": graph.node_count,
        },
    )
    return OpenSpecExtractionResult(graph=graph, metadata=metadata)


def _requirements_repository(registry: WorkspaceRegistry) -> RepositoryEntry:
    matches = [
        repo for repo in registry.repositories if repo.id == registry.engineering_kg.store_repository
    ]
    if len(matches) != 1:
        raise OpenSpecStoreSourceValidationError(
            "engineering_kg.store_repository must resolve to exactly one repository entry"
        )
    repository = matches[0]
    if repository.role != "requirements":
        raise OpenSpecStoreSourceValidationError(
            "engineering_kg.store_repository must reference a repository with role requirements"
        )
    return repository


def _normalized_registered_stores(
    stores: Iterable[RegisteredOpenSpecStore | dict[str, Any]] | None,
) -> tuple[RegisteredOpenSpecStore, ...]:
    if stores is None:
        return discover_registered_openspec_stores()

    normalized: list[RegisteredOpenSpecStore] = []
    for index, store in enumerate(stores):
        if isinstance(store, RegisteredOpenSpecStore):
            normalized.append(
                RegisteredOpenSpecStore(id=store.id, path=Path(store.path).expanduser().resolve())
            )
        elif isinstance(store, dict):
            normalized.append(RegisteredOpenSpecStore(id=_store_id(store, index), path=_store_path(store, str(index))))
        else:
            raise OpenSpecStoreSourceValidationError(
                f"OpenSpec store discovery entry {index} must be a registered store or mapping"
            )
    return tuple(normalized)


def _select_explicit_store(
    stores: tuple[RegisteredOpenSpecStore, ...],
    selected_store_id: str,
) -> RegisteredOpenSpecStore:
    for store in stores:
        if store.id == selected_store_id:
            return store
    raise OpenSpecStoreSourceValidationError(
        f"selected OpenSpec store id is not registered: {selected_store_id}"
    )


def _select_matching_registered_store(
    stores: tuple[RegisteredOpenSpecStore, ...],
    requirements_repo: RepositoryEntry,
) -> RegisteredOpenSpecStore:
    matches = [store for store in stores if _same_path(store.path, requirements_repo.resolved_path)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise OpenSpecStoreSourceValidationError(
            "multiple registered OpenSpec stores match the requirements repository; "
            "explicit store selection is required"
        )
    raise OpenSpecStoreSourceValidationError(
        "registered OpenSpec stores do not match the requirements repository; "
        "explicit store selection is required"
    )


def _require_matching_path(store_path: Path, requirements_repo: RepositoryEntry) -> None:
    if not _same_path(store_path, requirements_repo.resolved_path):
        raise OpenSpecStoreSourceValidationError(
            "registered OpenSpec store does not match the requirements repository; "
            "explicit store selection is required"
        )


def _validate_selected_store(
    selection_source: str,
    repository: RepositoryEntry,
    store_path: Path,
    store_id: str = "",
) -> OpenSpecStoreSourceValidationResult:
    resolved_store_path = Path(store_path).expanduser().resolve()
    if not resolved_store_path.is_dir():
        raise OpenSpecStoreSourceValidationError(
            f"OpenSpec store repository path must exist as a directory: {resolved_store_path}"
        )

    openspec_root = resolved_store_path / "openspec"
    if not openspec_root.is_dir():
        raise OpenSpecStoreSourceValidationError(
            f"OpenSpec root directory is missing: {openspec_root}"
        )

    specs_path = openspec_root / "specs"
    if not specs_path.is_dir():
        raise OpenSpecStoreSourceValidationError(
            f"OpenSpec specs directory is missing: {specs_path}"
        )

    changes_path = openspec_root / "changes"
    if not changes_path.is_dir():
        raise OpenSpecStoreSourceValidationError(
            f"OpenSpec changes directory is missing: {changes_path}"
        )

    return OpenSpecStoreSourceValidationResult(
        status="valid",
        selection_source=selection_source,
        store_id=store_id,
        repository_id=repository.id,
        repository_role=repository.role,
        repository_path=repository.resolved_path,
        openspec_root_path=openspec_root,
        specs_path=specs_path,
        changes_path=changes_path,
    )


def _store_id(item: dict[str, Any], index: int) -> str:
    value = item.get("id", item.get("name"))
    if not isinstance(value, str) or not value.strip():
        raise OpenSpecStoreSourceValidationError(
            f"OpenSpec store discovery entry {index} must contain a non-empty id"
        )
    return value


def _store_path(item: dict[str, Any], store_id: str) -> Path:
    value = (
        item.get("path")
        or item.get("root")
        or item.get("storePath")
        or item.get("store_path")
        or item.get("location")
    )
    if not isinstance(value, str) or not value.strip():
        raise OpenSpecStoreSourceValidationError(
            f"OpenSpec store discovery entry {store_id} must contain a non-empty path"
        )
    return Path(value).expanduser().resolve()


def _same_path(left: Path, right: Path) -> bool:
    return Path(left).expanduser().resolve() == Path(right).expanduser().resolve()


def _extend_spec(
    nodes: list[Node],
    edges: list[Edge],
    evidence: list[Evidence],
    parsed: _ParsedSpec,
) -> None:
    nodes.append(parsed.node)
    nodes.extend(parsed.requirements)
    nodes.extend(parsed.scenarios)
    edges.extend(parsed.edges)
    evidence.append(parsed.evidence)
    evidence.extend(parsed.evidence_items)


def _extract_change_scope(
    store_source: OpenSpecStoreSourceValidationResult,
    change_dir: Path,
    archived: bool,
    nodes: list[Node],
    edges: list[Edge],
    evidence: list[Evidence],
) -> int:
    scope = "archived-change" if archived else "active-change"
    change_node, change_evidence = _change_node(store_source, change_dir, archived)
    nodes.append(change_node)
    evidence.append(change_evidence)
    artifact_nodes, artifact_edges, artifact_evidence = _change_artifacts(
        store_source, change_dir, change_node.id, scope
    )
    nodes.extend(artifact_nodes)
    edges.extend(artifact_edges)
    evidence.extend(artifact_evidence)
    for spec_file in sorted((change_dir / "specs").glob("*/spec.md")):
        parsed = _parse_spec_file(store_source, spec_file, scope, change_dir.name)
        _extend_spec(nodes, edges, evidence, parsed)
        edges.append(
            _edge(
                EdgeKind.OPENSPEC_CHANGE_TOUCHES_SPEC,
                change_node.id,
                parsed.node.id,
                f"{scope}-spec",
                change_dir.name,
                parsed.capability,
                evidence_ids=(parsed.evidence.id,),
            )
        )
    return len(artifact_nodes)


def _parse_spec_file(
    store_source: OpenSpecStoreSourceValidationResult,
    spec_file: Path,
    scope: str,
    change_identity: str | None,
) -> _ParsedSpec:
    capability = spec_file.parent.name
    relative_path = _relative_path(store_source.repository_path, spec_file)
    identity_parts = (scope, change_identity or "current", capability)
    openspec_identity = ":".join(identity_parts)
    source_text = spec_file.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(source_text)
    title = _optional_string(frontmatter.get("title")) or capability
    related = _related_values(frontmatter.get("related"))
    supported_frontmatter = {
        key: _frontmatter_value(value)
        for key in ("repo", "created", "updated", "title", "related")
        if (value := frontmatter.get(key)) is not None
    }
    evidence_id = stable_id("evidence", "openspec", relative_path, openspec_identity)
    spec_node = Node(
        id=stable_id("node", NodeKind.OPENSPEC_SPEC, *identity_parts),
        kind=NodeKind.OPENSPEC_SPEC,
        name=title,
        properties={
            "capability": capability,
            "change_identity": change_identity or "",
            "frontmatter": supported_frontmatter,
            "openspec_identity": openspec_identity,
            "repository_id": store_source.repository_id,
            "scope": scope,
        },
        evidence_ids=(evidence_id,),
    )
    spec_evidence = _evidence(
        evidence_id,
        relative_path,
        "openspec-spec",
        openspec_identity,
    )

    requirement_nodes: list[Node] = []
    scenario_nodes: list[Node] = []
    edges: list[Edge] = []
    evidence_items: list[Evidence] = []
    current_requirement: Node | None = None
    for line_number, line in enumerate(body.splitlines(), start=1):
        requirement_match = _REQUIREMENT_RE.match(line)
        if requirement_match:
            requirement_name = requirement_match.group(1).strip()
            requirement_identity = f"{openspec_identity}:requirement:{requirement_name}"
            requirement_evidence_id = stable_id(
                "evidence", "openspec", relative_path, requirement_identity
            )
            current_requirement = Node(
                id=stable_id("node", NodeKind.OPENSPEC_REQUIREMENT, requirement_identity),
                kind=NodeKind.OPENSPEC_REQUIREMENT,
                name=requirement_name,
                properties={
                    "capability": capability,
                    "change_identity": change_identity or "",
                    "openspec_identity": requirement_identity,
                    "scope": scope,
                },
                evidence_ids=(requirement_evidence_id,),
            )
            requirement_nodes.append(current_requirement)
            evidence_items.append(
                _evidence(
                    requirement_evidence_id,
                    relative_path,
                    "openspec-requirement",
                    requirement_identity,
                    heading_name=requirement_name,
                    line_start=line_number,
                )
            )
            edges.append(
                _edge(
                    EdgeKind.OPENSPEC_SPEC_CONTAINS_REQUIREMENT,
                    spec_node.id,
                    current_requirement.id,
                    "spec-requirement",
                    openspec_identity,
                    requirement_name,
                    evidence_ids=(requirement_evidence_id,),
                )
            )
            continue

        scenario_match = _SCENARIO_RE.match(line)
        if scenario_match and current_requirement is not None:
            scenario_name = scenario_match.group(1).strip()
            scenario_identity = (
                f"{current_requirement.properties['openspec_identity']}:scenario:{scenario_name}"
            )
            scenario_evidence_id = stable_id(
                "evidence", "openspec", relative_path, scenario_identity
            )
            scenario_node = Node(
                id=stable_id("node", NodeKind.OPENSPEC_SCENARIO, scenario_identity),
                kind=NodeKind.OPENSPEC_SCENARIO,
                name=scenario_name,
                properties={
                    "capability": capability,
                    "change_identity": change_identity or "",
                    "openspec_identity": scenario_identity,
                    "scope": scope,
                },
                evidence_ids=(scenario_evidence_id,),
            )
            scenario_nodes.append(scenario_node)
            evidence_items.append(
                _evidence(
                    scenario_evidence_id,
                    relative_path,
                    "openspec-scenario",
                    scenario_identity,
                    heading_name=scenario_name,
                    line_start=line_number,
                )
            )
            edges.append(
                _edge(
                    EdgeKind.OPENSPEC_REQUIREMENT_CONTAINS_SCENARIO,
                    current_requirement.id,
                    scenario_node.id,
                    "requirement-scenario",
                    current_requirement.id,
                    scenario_name,
                    evidence_ids=(scenario_evidence_id,),
                )
            )

    return _ParsedSpec(
        scope=scope,
        capability=capability,
        path=spec_file,
        node=spec_node,
        evidence=spec_evidence,
        title=title,
        related=related,
        requirements=tuple(requirement_nodes),
        scenarios=tuple(scenario_nodes),
        edges=tuple(edges),
        evidence_items=tuple(evidence_items),
    )


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            raw = "\n".join(lines[1:index])
            parsed = yaml.safe_load(raw) or {}
            body = "\n".join(lines[index + 1 :])
            return (parsed if isinstance(parsed, dict) else {}), body
    return {}, text


def _active_change_dirs(changes_path: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            item
            for item in changes_path.iterdir()
            if item.is_dir() and item.name != "archive"
        )
    )


def _change_node(
    store_source: OpenSpecStoreSourceValidationResult,
    change_dir: Path,
    archived: bool,
) -> tuple[Node, Evidence]:
    kind = NodeKind.OPENSPEC_ARCHIVED_CHANGE if archived else NodeKind.OPENSPEC_ACTIVE_CHANGE
    artifact_type = "openspec-archived-change" if archived else "openspec-active-change"
    relative_path = _relative_path(store_source.repository_path, change_dir)
    evidence_id = stable_id("evidence", "openspec", relative_path, change_dir.name)
    node = Node(
        id=stable_id("node", kind, change_dir.name),
        kind=kind,
        name=change_dir.name,
        properties={
            "archive_state": "archived" if archived else "active",
            "change_identity": change_dir.name,
            "jira_reference_hints": tuple(_JIRA_TOKEN_RE.findall(change_dir.name)),
        },
        evidence_ids=(evidence_id,),
    )
    return node, _evidence(evidence_id, relative_path, artifact_type, change_dir.name)


def _change_artifacts(
    store_source: OpenSpecStoreSourceValidationResult,
    change_dir: Path,
    change_node_id: str,
    scope: str,
) -> tuple[list[Node], list[Edge], list[Evidence]]:
    nodes: list[Node] = []
    edges: list[Edge] = []
    evidence: list[Evidence] = []
    for artifact_name in _PLANNING_ARTIFACTS:
        path = change_dir / artifact_name
        if not path.is_file():
            continue
        relative_path = _relative_path(store_source.repository_path, path)
        identity = f"{scope}:{change_dir.name}:artifact:{artifact_name}"
        evidence_id = stable_id("evidence", "openspec", relative_path, identity)
        node = Node(
            id=stable_id("node", NodeKind.OPENSPEC_ARTIFACT, identity),
            kind=NodeKind.OPENSPEC_ARTIFACT,
            name=artifact_name,
            properties={
                "artifact_type": artifact_name,
                "change_identity": change_dir.name,
                "scope": scope,
            },
            evidence_ids=(evidence_id,),
        )
        nodes.append(node)
        evidence.append(_evidence(evidence_id, relative_path, "openspec-artifact", identity))
        edges.append(
            _edge(
                EdgeKind.OPENSPEC_CHANGE_HAS_ARTIFACT,
                change_node_id,
                node.id,
                "change-artifact",
                change_dir.name,
                artifact_name,
                evidence_ids=(evidence_id,),
            )
        )
    return nodes, edges, evidence


def _related_spec_edges(durable_specs: list[_ParsedSpec]) -> tuple[list[Edge], list[dict[str, str]]]:
    title_index: dict[str, list[_ParsedSpec]] = {}
    for spec in durable_specs:
        title_index.setdefault(spec.title, []).append(spec)

    edges: list[Edge] = []
    unresolved: list[dict[str, str]] = []
    for spec in durable_specs:
        for related_title in spec.related:
            matches = [item for item in title_index.get(related_title, []) if item.node.id != spec.node.id]
            if len(matches) == 1:
                target = matches[0]
                edges.append(
                    _edge(
                        EdgeKind.OPENSPEC_RELATED_SPEC,
                        spec.node.id,
                        target.node.id,
                        "related-spec",
                        spec.capability,
                        related_title,
                        confidence="non-confident",
                        properties={"related_title": related_title},
                    )
                )
            else:
                unresolved.append(
                    {
                        "capability": spec.capability,
                        "reason": "ambiguous" if len(matches) > 1 else "missing",
                        "related_title": related_title,
                    }
                )
    return edges, unresolved


def _edge(
    kind: EdgeKind,
    source_id: str,
    target_id: str,
    *identity_parts: object,
    evidence_ids: tuple[str, ...] = (),
    confidence: str | None = None,
    properties: dict[str, Any] | None = None,
) -> Edge:
    return Edge(
        id=stable_id("edge", kind, source_id, target_id, *identity_parts),
        kind=kind,
        source_id=source_id,
        target_id=target_id,
        properties=properties or {},
        evidence_ids=evidence_ids,
        confidence=confidence,
    )


def _evidence(
    evidence_id: str,
    relative_path: str,
    artifact_type: str,
    openspec_identity: str,
    heading_name: str = "",
    line_start: int | None = None,
) -> Evidence:
    return Evidence(
        id=evidence_id,
        source="openspec",
        locator=OpenSpecLocator(
            relative_file_path=relative_path,
            artifact_type=artifact_type,
            openspec_identity=openspec_identity,
            heading_name=heading_name,
            line_start=line_start,
        ),
    )


def _snapshot(nodes: list[Node], edges: list[Edge], evidence: list[Evidence]) -> GraphSnapshot:
    return GraphSnapshot(
        nodes=tuple({item.id: item for item in sorted(nodes, key=lambda item: item.id)}.values()),
        edges=tuple({item.id: item for item in sorted(edges, key=lambda item: item.id)}.values()),
        evidence=tuple(
            {item.id: item for item in sorted(evidence, key=lambda item: item.id)}.values()
        ),
    )


def _relative_path(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _optional_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _related_values(value: Any) -> tuple[str, ...]:
    if isinstance(value, str) and value.strip():
        return (value.strip(),)
    if isinstance(value, list):
        return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
    return ()


def _frontmatter_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_frontmatter_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _frontmatter_value(nested) for key, nested in sorted(value.items())}
    return str(value)
