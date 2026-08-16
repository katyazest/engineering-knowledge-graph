"""Deterministic graph relationship derivation for Engineering KG snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engineering_kg.ontology import Edge, EdgeKind, GraphSnapshot, Node, NodeKind, stable_id


OPENSPEC_CHANGE_TO_DURABLE_SPEC_RULE = "openspec-change-to-durable-spec"


@dataclass(frozen=True)
class GraphDerivationDiagnostic:
    """Deterministic diagnostic for a derivation input that did not create output."""

    rule_id: str
    affected_object_id: str
    message: str
    severity: str = "info"

    def as_dict(self) -> dict[str, str]:
        return {
            "affected_object_id": self.affected_object_id,
            "message": self.message,
            "rule_id": self.rule_id,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class GraphDerivationMetadata:
    """Serializable metadata for one graph derivation run."""

    status: str
    rule_counts: dict[str, int] = field(default_factory=dict)
    derived_edge_count: int = 0
    skipped_input_count: int = 0
    unresolved_input_count: int = 0
    graph_counts: dict[str, int] = field(default_factory=dict)
    diagnostics: tuple[GraphDerivationDiagnostic, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "derived_edge_count": self.derived_edge_count,
            "diagnostics": [item.as_dict() for item in self.diagnostics],
            "graph_counts": dict(sorted(self.graph_counts.items())),
            "rule_counts": dict(sorted(self.rule_counts.items())),
            "skipped_input_count": self.skipped_input_count,
            "status": self.status,
            "unresolved_input_count": self.unresolved_input_count,
        }


@dataclass(frozen=True)
class GraphDerivationResult:
    """Canonical graph plus deterministic derivation metadata."""

    graph: GraphSnapshot
    metadata: GraphDerivationMetadata

    def as_dict(self) -> dict[str, Any]:
        return {
            "graph": self.graph.as_dict(),
            "metadata": self.metadata.as_dict(),
        }


def derive_graph_relationships(snapshot: GraphSnapshot) -> GraphDerivationResult:
    """Derive deterministic relationships from a canonical graph snapshot."""

    nodes_by_id = {node.id: node for node in snapshot.nodes}
    durable_specs_by_capability = _durable_specs_by_capability(snapshot.nodes)
    derived_edges: list[Edge] = []
    diagnostics: list[GraphDerivationDiagnostic] = []
    seen_change_spec_inputs: set[tuple[str, str, str]] = set()

    for edge in sorted(snapshot.edges, key=lambda item: item.id):
        if _value(edge.kind) != EdgeKind.OPENSPEC_CHANGE_TOUCHES_SPEC.value:
            continue
        change_node = nodes_by_id.get(edge.source_id)
        change_scoped_spec = nodes_by_id.get(edge.target_id)
        if change_node is None or change_scoped_spec is None:
            diagnostics.append(
                GraphDerivationDiagnostic(
                    rule_id=OPENSPEC_CHANGE_TO_DURABLE_SPEC_RULE,
                    affected_object_id=edge.id,
                    message="Cannot derive OpenSpec traceability because the change-to-spec edge has a missing endpoint.",
                    severity="warning",
                )
            )
            continue
        capability = str(change_scoped_spec.properties.get("capability", ""))
        scope = str(change_scoped_spec.properties.get("scope", ""))
        input_key = (change_node.id, change_scoped_spec.id, capability)
        if input_key in seen_change_spec_inputs:
            continue
        seen_change_spec_inputs.add(input_key)

        durable_spec = durable_specs_by_capability.get(capability)
        if durable_spec is None:
            diagnostics.append(
                GraphDerivationDiagnostic(
                    rule_id=OPENSPEC_CHANGE_TO_DURABLE_SPEC_RULE,
                    affected_object_id=change_scoped_spec.id,
                    message=f"No durable OpenSpec spec exists for capability: {capability}",
                    severity="info",
                )
            )
            continue
        derived_edges.append(
            Edge(
                id=stable_id(
                    "edge",
                    EdgeKind.OPENSPEC_CHANGE_TRACES_TO_SPEC,
                    OPENSPEC_CHANGE_TO_DURABLE_SPEC_RULE,
                    change_node.id,
                    durable_spec.id,
                    capability,
                ),
                kind=EdgeKind.OPENSPEC_CHANGE_TRACES_TO_SPEC,
                source_id=change_node.id,
                target_id=durable_spec.id,
                properties={
                    "capability": capability,
                    "derived": True,
                    "rule_id": OPENSPEC_CHANGE_TO_DURABLE_SPEC_RULE,
                    "source_scope": scope,
                    "target_scope": str(durable_spec.properties.get("scope", "")),
                    "via_spec_id": change_scoped_spec.id,
                },
                evidence_ids=edge.evidence_ids,
            )
        )

    derived_graph = GraphSnapshot(edges=tuple(sorted(derived_edges, key=lambda item: item.id)))
    graph = snapshot.merged_with(derived_graph)
    diagnostics_tuple = tuple(sorted(diagnostics, key=_diagnostic_sort_key))
    metadata = GraphDerivationMetadata(
        status="completed",
        rule_counts={OPENSPEC_CHANGE_TO_DURABLE_SPEC_RULE: len(derived_edges)},
        derived_edge_count=len(derived_edges),
        skipped_input_count=len(diagnostics_tuple),
        unresolved_input_count=len(diagnostics_tuple),
        graph_counts={
            "edge_count": graph.edge_count,
            "evidence_count": graph.evidence_count,
            "node_count": graph.node_count,
        },
        diagnostics=diagnostics_tuple,
    )
    return GraphDerivationResult(graph=graph, metadata=metadata)


def _durable_specs_by_capability(nodes: tuple[Node, ...]) -> dict[str, Node]:
    durable_specs: dict[str, Node] = {}
    for node in sorted(nodes, key=lambda item: item.id):
        if _value(node.kind) != NodeKind.OPENSPEC_SPEC.value:
            continue
        if node.properties.get("scope") != "durable":
            continue
        capability = str(node.properties.get("capability", ""))
        if capability and capability not in durable_specs:
            durable_specs[capability] = node
    return durable_specs


def _diagnostic_sort_key(item: GraphDerivationDiagnostic) -> tuple[str, str, str, str]:
    return (item.severity, item.rule_id, item.affected_object_id, item.message)


def _value(value: object) -> object:
    return getattr(value, "value", value)
