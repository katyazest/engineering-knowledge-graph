"""Graph integrity validation for canonical Engineering KG snapshots."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from engineering_kg.ontology import (
    CROSS_GRAPH_LINK_LIFECYCLE_STATES,
    CodeLocator,
    CrossGraphLinkClaim,
    CrossGraphLinkEvidence,
    CrossGraphLinkLifecycle,
    Edge,
    EdgeKind,
    GraphSnapshot,
    Node,
    NodeKind,
    OpenSpecLocator,
    SourceArtifactLocator,
    source_artifact_identity_error,
    openspec_requirement_id,
    openspec_scenario_id,
    openspec_specification_id,
    stable_id,
)


SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
OPENSPEC_CHANGE_TRACEABILITY_KINDS = {EdgeKind.ASSERTS.value, EdgeKind.TRACES_TO.value}
RETIRED_OPENSPEC_DOMAIN_KINDS = {
    "openspec-spec",
    "openspec-requirement",
    "openspec-scenario",
    "openspec-spec-contains-requirement",
    "openspec-requirement-contains-scenario",
    "openspec-change-touches-spec",
    "openspec-change-traces-to-spec",
    "openspec-related-spec",
}


class GraphIntegrityValidationError(ValueError):
    """Raised when graph integrity validation fails during pipeline execution."""

    def __init__(self, result: "GraphValidationResult") -> None:
        self.result = result
        super().__init__("graph-integrity-validation failed with invalid graph status")


@dataclass(frozen=True)
class GraphValidationDiagnostic:
    """One deterministic graph integrity diagnostic."""

    severity: str
    rule_id: str
    affected_object_id: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "affected_object_id": self.affected_object_id,
            "message": self.message,
            "rule_id": self.rule_id,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class GraphValidationMetadata:
    """Serializable metadata for graph integrity validation."""

    status: str
    diagnostics: tuple[GraphValidationDiagnostic, ...] = ()
    severity_counts: dict[str, int] = field(default_factory=dict)
    duplicate_counts: dict[str, int] = field(default_factory=dict)
    graph_counts: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "diagnostics": [item.as_dict() for item in self.diagnostics],
            "duplicate_counts": dict(sorted(self.duplicate_counts.items())),
            "graph_counts": dict(sorted(self.graph_counts.items())),
            "severity_counts": dict(sorted(self.severity_counts.items())),
            "status": self.status,
        }


@dataclass(frozen=True)
class GraphValidationResult:
    """Graph integrity validation result."""

    status: str
    metadata: GraphValidationMetadata

    def as_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.as_dict(),
            "status": self.status,
        }


def validate_graph_integrity(snapshot: GraphSnapshot) -> GraphValidationResult:
    """Validate graph references, identity conflicts, and traceability shape."""

    diagnostics: list[GraphValidationDiagnostic] = []
    duplicate_counts = _duplicate_counts(snapshot)
    diagnostics.extend(_duplicate_conflict_diagnostics("node", snapshot.nodes))
    diagnostics.extend(_duplicate_conflict_diagnostics("edge", snapshot.edges))
    diagnostics.extend(_duplicate_conflict_diagnostics("evidence", snapshot.evidence))
    diagnostics.extend(_duplicate_conflict_diagnostics("cross-graph-link-claim", snapshot.cross_graph_link_claims))
    diagnostics.extend(_duplicate_conflict_diagnostics("cross-graph-link-evidence", snapshot.cross_graph_link_evidence))
    diagnostics.extend(_duplicate_conflict_diagnostics("cross-graph-link-lifecycle", snapshot.cross_graph_link_lifecycle))

    nodes_by_id = {node.id: node for node in snapshot.nodes}
    evidence_by_id = {item.id: item for item in snapshot.evidence}
    diagnostics.extend(_edge_endpoint_diagnostics(snapshot.edges, nodes_by_id))
    diagnostics.extend(_evidence_reference_diagnostics(snapshot, evidence_by_id))
    diagnostics.extend(_retired_vocabulary_diagnostics(snapshot))
    diagnostics.extend(_canonical_identity_diagnostics(snapshot.nodes))
    diagnostics.extend(_traceability_shape_diagnostics(snapshot.edges, nodes_by_id))
    diagnostics.extend(_unresolved_related_spec_diagnostics(snapshot.nodes, snapshot.edges, snapshot.evidence))
    diagnostics.extend(_cross_graph_link_diagnostics(snapshot, nodes_by_id, evidence_by_id))
    diagnostics.extend(_source_artifact_identity_diagnostics(snapshot))

    sorted_diagnostics = tuple(sorted(diagnostics, key=_diagnostic_sort_key))
    severity_counts = Counter(item.severity for item in sorted_diagnostics)
    status = "invalid" if severity_counts.get("error", 0) else "valid"
    metadata = GraphValidationMetadata(
        status=status,
        diagnostics=sorted_diagnostics,
        severity_counts=dict(severity_counts),
        duplicate_counts=duplicate_counts,
        graph_counts={
            "edge_count": snapshot.edge_count,
            "evidence_count": snapshot.evidence_count,
            "cross_graph_link_claim_count": snapshot.cross_graph_link_claim_count,
            "cross_graph_link_evidence_count": snapshot.cross_graph_link_evidence_count,
            "cross_graph_link_lifecycle_count": snapshot.cross_graph_link_lifecycle_count,
            "node_count": snapshot.node_count,
        },
    )
    return GraphValidationResult(status=status, metadata=metadata)


def _source_artifact_identity_diagnostics(snapshot: GraphSnapshot) -> list[GraphValidationDiagnostic]:
    """Verify explicit provenance IDs without treating navigation detail as identity."""

    diagnostics: list[GraphValidationDiagnostic] = []
    for evidence in snapshot.evidence:
        locator = evidence.locator
        missing_identity_error = source_artifact_identity_error(evidence)
        if missing_identity_error:
            diagnostics.append(
                GraphValidationDiagnostic(
                    "error", "source-artifact-identity-missing", evidence.id,
                    missing_identity_error + ".",
                )
            )
            continue
        if isinstance(locator, SourceArtifactLocator):
            expected = stable_id("evidence", locator.source_artifact_identity.id)
        elif isinstance(locator, OpenSpecLocator):
            if locator.source_artifact_identity is None:
                diagnostics.append(
                    GraphValidationDiagnostic(
                        "error", "source-artifact-identity-missing", evidence.id,
                        "OpenSpec evidence lacks an explicit source-artifact identity.",
                    )
                )
                continue
            expected = stable_id("evidence", locator.source_artifact_identity.id, locator.openspec_identity)
        else:
            continue
        if evidence.id != expected:
            diagnostics.append(
                GraphValidationDiagnostic(
                    "error", "source-artifact-evidence-identity", evidence.id,
                    "Evidence ID does not match its source-artifact identity and retained locator detail.",
                )
            )
    return diagnostics


def _edge_endpoint_diagnostics(
    edges: tuple[Edge, ...],
    nodes_by_id: dict[str, Node],
) -> list[GraphValidationDiagnostic]:
    diagnostics: list[GraphValidationDiagnostic] = []
    for edge in edges:
        if edge.source_id not in nodes_by_id:
            diagnostics.append(
                GraphValidationDiagnostic(
                    severity="error",
                    rule_id="edge-source-exists",
                    affected_object_id=edge.id,
                    message=f"Edge source_id does not reference an existing node: {edge.source_id}",
                )
            )
        if edge.target_id not in nodes_by_id:
            diagnostics.append(
                GraphValidationDiagnostic(
                    severity="error",
                    rule_id="edge-target-exists",
                    affected_object_id=edge.id,
                    message=f"Edge target_id does not reference an existing node: {edge.target_id}",
                )
            )
    return diagnostics


def _evidence_reference_diagnostics(
    snapshot: GraphSnapshot,
    evidence_by_id: dict[str, object],
) -> list[GraphValidationDiagnostic]:
    diagnostics: list[GraphValidationDiagnostic] = []
    for collection, items in (("node", snapshot.nodes), ("edge", snapshot.edges)):
        for item in items:
            for evidence_id in item.evidence_ids:
                if evidence_id not in evidence_by_id:
                    diagnostics.append(
                        GraphValidationDiagnostic(
                            severity="error",
                            rule_id="evidence-reference-exists",
                            affected_object_id=item.id,
                            message=(
                                f"{collection} evidence_id does not reference an existing "
                                f"evidence record: {evidence_id}"
                            ),
                        )
                    )
    return diagnostics


def _duplicate_counts(snapshot: GraphSnapshot) -> dict[str, int]:
    return {
        "edge": _duplicate_id_count(snapshot.edges),
        "evidence": _duplicate_id_count(snapshot.evidence),
        "node": _duplicate_id_count(snapshot.nodes),
        "cross_graph_link_claim": _duplicate_id_count(snapshot.cross_graph_link_claims),
        "cross_graph_link_evidence": _duplicate_id_count(snapshot.cross_graph_link_evidence),
        "cross_graph_link_lifecycle": _duplicate_id_count(snapshot.cross_graph_link_lifecycle),
    }


def _duplicate_id_count(items: tuple[Any, ...]) -> int:
    counts = Counter(item.id for item in items)
    return sum(count - 1 for count in counts.values() if count > 1)


def _duplicate_conflict_diagnostics(
    collection: str,
    items: tuple[Any, ...],
) -> list[GraphValidationDiagnostic]:
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        serialized = item.as_dict()
        if collection in {"node", "edge"}:
            serialized.pop("evidence_ids")
        if collection == "node" and _value(item.kind) in {
            NodeKind.SPECIFICATION.value,
            NodeKind.REQUIREMENT.value,
            NodeKind.SCENARIO.value,
        }:
            serialized.pop("name")
        by_id[item.id].append(serialized)

    diagnostics: list[GraphValidationDiagnostic] = []
    for item_id, serialized_items in sorted(by_id.items()):
        unique_items = {
            repr(_canonical_dict(serialized_item)) for serialized_item in serialized_items
        }
        if len(unique_items) > 1:
            diagnostics.append(
                GraphValidationDiagnostic(
                    severity="error",
                    rule_id="duplicate-identity-conflict",
                    affected_object_id=item_id,
                    message=f"{collection} ID has conflicting serialized values: {item_id}",
                )
            )
    return diagnostics


def _cross_graph_link_diagnostics(
    snapshot: GraphSnapshot, nodes_by_id: dict[str, Node], evidence_by_id: dict[str, object]
) -> list[GraphValidationDiagnostic]:
    diagnostics: list[GraphValidationDiagnostic] = []
    claims_by_id = {item.id: item for item in snapshot.cross_graph_link_claims}
    for claim in snapshot.cross_graph_link_claims:
        if claim.subject_id not in nodes_by_id:
            diagnostics.append(_cross_error("cross-graph-subject-exists", claim.id, "Cross-graph claim subject_id does not reference an existing node."))
        if not _complete_code_locator(claim.target):
            diagnostics.append(_cross_error("cross-graph-target-complete", claim.id, "Cross-graph claim target must be a complete CodeLocator."))
    for observation in snapshot.cross_graph_link_evidence:
        if observation.claim_id not in claims_by_id:
            diagnostics.append(_cross_error("cross-graph-claim-exists", observation.id, "Cross-graph evidence references an absent claim."))
        if observation.provenance_evidence_id not in evidence_by_id:
            diagnostics.append(_cross_error("cross-graph-provenance-exists", observation.id, "Cross-graph evidence references absent provenance evidence."))
    revisions: dict[tuple[str, int], CrossGraphLinkLifecycle] = {}
    lifecycle_claims: set[str] = set()
    for entry in snapshot.cross_graph_link_lifecycle:
        lifecycle_claims.add(entry.claim_id)
        if entry.claim_id not in claims_by_id:
            diagnostics.append(_cross_error("cross-graph-claim-exists", entry.id, "Cross-graph lifecycle references an absent claim."))
        if entry.provenance_evidence_id not in evidence_by_id:
            diagnostics.append(_cross_error("cross-graph-provenance-exists", entry.id, "Cross-graph lifecycle references absent provenance evidence."))
        if not isinstance(entry.revision, int) or isinstance(entry.revision, bool) or entry.revision <= 0:
            diagnostics.append(_cross_error("cross-graph-lifecycle-revision", entry.id, "Cross-graph lifecycle revision must be a positive integer."))
        if _value(entry.state) not in CROSS_GRAPH_LINK_LIFECYCLE_STATES:
            diagnostics.append(_cross_error("cross-graph-lifecycle-state", entry.id, "Cross-graph lifecycle state is unsupported."))
        key = (entry.claim_id, entry.revision)
        previous = revisions.get(key)
        if previous is not None and previous.as_dict() != entry.as_dict():
            diagnostics.append(_cross_error("cross-graph-lifecycle-revision-conflict", entry.id, "Cross-graph lifecycle revision has conflicting values."))
        revisions[key] = entry
    for claim in snapshot.cross_graph_link_claims:
        if claim.id not in lifecycle_claims:
            diagnostics.append(_cross_error("cross-graph-lifecycle-current", claim.id, "Cross-graph claim has no determinable current lifecycle revision."))
    return diagnostics


def _complete_code_locator(value: object) -> bool:
    return isinstance(value, CodeLocator) and all(
        isinstance(getattr(value, field), str) and getattr(value, field).strip()
        for field in ("repository", "revision", "file", "symbol")
    )


def _cross_error(rule_id: str, object_id: str, message: str) -> GraphValidationDiagnostic:
    return GraphValidationDiagnostic("error", rule_id, object_id, message)


def _traceability_shape_diagnostics(
    edges: tuple[Edge, ...],
    nodes_by_id: dict[str, Node],
) -> list[GraphValidationDiagnostic]:
    diagnostics: list[GraphValidationDiagnostic] = []
    for edge in edges:
        is_openspec_trace = (
            _value(edge.kind) == EdgeKind.ASSERTS.value
            or (
                _value(edge.kind) == EdgeKind.TRACES_TO.value
                and edge.properties.get("rule_id") == "openspec-change-to-durable-spec"
            )
        )
        if not is_openspec_trace:
            continue
        source = nodes_by_id.get(edge.source_id)
        target = nodes_by_id.get(edge.target_id)
        if source is None or target is None:
            continue
        source_valid = _value(source.kind) in {
            NodeKind.OPENSPEC_ACTIVE_CHANGE.value,
            NodeKind.OPENSPEC_ARCHIVED_CHANGE.value,
        }
        target_valid = _value(target.kind) == NodeKind.SPECIFICATION.value
        if not source_valid:
            diagnostics.append(
                GraphValidationDiagnostic(
                    severity="error",
                    rule_id="openspec-traceability-source-kind",
                    affected_object_id=edge.id,
                    message="OpenSpec traceability source endpoint has an invalid kind or scope.",
                )
            )
        if not target_valid:
            diagnostics.append(
                GraphValidationDiagnostic(
                    severity="error",
                    rule_id="openspec-traceability-target-kind",
                    affected_object_id=edge.id,
                    message="OpenSpec traceability target endpoint must be a canonical specification.",
                )
            )
    return diagnostics


def _unresolved_related_spec_diagnostics(
    nodes: tuple[Node, ...],
    edges: tuple[Edge, ...],
    evidence: tuple[Any, ...],
) -> list[GraphValidationDiagnostic]:
    related_edges_by_source: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if _value(edge.kind) != EdgeKind.RELATED_TO.value:
            continue
        related_title = edge.properties.get("related_title")
        if isinstance(related_title, str):
            related_edges_by_source[edge.source_id].add(related_title)

    related_by_specification: dict[str, set[str]] = defaultdict(set)
    for item in evidence:
        related = item.properties.get("related", ())
        specification_id = item.properties.get("specification_id")
        if isinstance(specification_id, str):
            related_by_specification[specification_id].update(_related_titles(related))

    diagnostics: list[GraphValidationDiagnostic] = []
    for node in nodes:
        if _value(node.kind) != NodeKind.SPECIFICATION.value:
            continue
        for related_title in sorted(related_by_specification.get(node.id, ())):
            if related_title in related_edges_by_source.get(node.id, set()):
                continue
            diagnostics.append(
                GraphValidationDiagnostic(
                    severity="warning",
                    rule_id="unresolved-non-confident-related-spec",
                    affected_object_id=node.id,
                    message=f"Non-confident related spec reference is unresolved: {related_title}",
                )
            )
    return diagnostics


def _canonical_identity_diagnostics(nodes: tuple[Node, ...]) -> list[GraphValidationDiagnostic]:
    diagnostics: list[GraphValidationDiagnostic] = []
    for node in nodes:
        kind = _value(node.kind)
        properties = node.properties
        if kind == NodeKind.SPECIFICATION.value:
            expected = _specification_id(properties)
        elif kind == NodeKind.REQUIREMENT.value:
            expected = _requirement_id(properties)
        elif kind == NodeKind.SCENARIO.value:
            expected = _scenario_id(properties)
        else:
            continue
        if expected is None or node.id != expected:
            diagnostics.append(
                GraphValidationDiagnostic(
                    severity="error",
                    rule_id="canonical-natural-key-identity",
                    affected_object_id=node.id,
                    message="Canonical node ID does not match its required natural-key properties.",
                )
            )
    return diagnostics


def _specification_id(properties: dict[str, Any]) -> str | None:
    repository_id = properties.get("repository_id")
    capability = properties.get("capability")
    if isinstance(repository_id, str) and isinstance(capability, str):
        return openspec_specification_id(repository_id, capability)
    return None


def _requirement_id(properties: dict[str, Any]) -> str | None:
    specification_id = properties.get("specification_id")
    requirement_key = properties.get("requirement_key")
    if isinstance(specification_id, str) and isinstance(requirement_key, str):
        return openspec_requirement_id(specification_id, requirement_key)
    return None


def _scenario_id(properties: dict[str, Any]) -> str | None:
    requirement_id = properties.get("requirement_id")
    scenario_key = properties.get("scenario_key")
    if isinstance(requirement_id, str) and isinstance(scenario_key, str):
        return openspec_scenario_id(requirement_id, scenario_key)
    return None


def _retired_vocabulary_diagnostics(snapshot: GraphSnapshot) -> list[GraphValidationDiagnostic]:
    diagnostics: list[GraphValidationDiagnostic] = []
    for item in (*snapshot.nodes, *snapshot.edges):
        if _value(item.kind) in RETIRED_OPENSPEC_DOMAIN_KINDS:
            diagnostics.append(
                GraphValidationDiagnostic(
                    severity="error",
                    rule_id="retired-openspec-domain-vocabulary",
                    affected_object_id=item.id,
                    message="Retired OpenSpec-prefixed domain vocabulary is not valid in a canonical graph.",
                )
            )
    return diagnostics


def _related_titles(value: object) -> tuple[str, ...]:
    if isinstance(value, str) and value.strip():
        return (value.strip(),)
    if isinstance(value, list):
        return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
    if isinstance(value, tuple):
        return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
    return ()


def _canonical_dict(value: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple((key, _canonical_value(value[key])) for key in sorted(value))


def _canonical_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _canonical_dict(value)
    if isinstance(value, list):
        return tuple(_canonical_value(item) for item in value)
    return value


def _diagnostic_sort_key(item: GraphValidationDiagnostic) -> tuple[int, str, str, str]:
    return (
        SEVERITY_ORDER.get(item.severity, 99),
        item.rule_id,
        item.affected_object_id,
        item.message,
    )


def _value(value: object) -> object:
    return getattr(value, "value", value)
