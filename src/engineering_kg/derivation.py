"""Deterministic graph relationship derivation for Engineering KG snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any

from engineering_kg.ontology import Edge, EdgeKind, Evidence, GraphSnapshot, Node, NodeKind, ProvenanceKind, ProvenanceRecord, has_complete_resolvable_provenance, stable_id
from engineering_kg.relationship_vocabulary import relationship_error


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
    derived_edges: list[Edge] = []
    diagnostics: list[GraphDerivationDiagnostic] = []
    evidence_ids = {item.id for item in snapshot.evidence}
    evidence_by_id = {item.id: item for item in snapshot.evidence}
    provenance_by_id = {item.id: item for item in snapshot.provenance}
    derived_evidence: list[Evidence] = []
    derived_provenance: list[ProvenanceRecord] = []
    seen_inputs: set[str] = set()

    for edge in sorted(snapshot.edges, key=lambda item: item.id):
        if _value(edge.kind) != EdgeKind.ASSERTS.value:
            continue
        change_node = nodes_by_id.get(edge.source_id)
        change_scoped_spec = nodes_by_id.get(edge.target_id)
        if change_node is None or change_scoped_spec is None:
            diagnostics.append(
                GraphDerivationDiagnostic(
                    rule_id=OPENSPEC_CHANGE_TO_DURABLE_SPEC_RULE,
                    affected_object_id=edge.id,
                    message="Cannot derive OpenSpec traceability because the asserted edge has a missing endpoint.",
                    severity="warning",
                )
            )
            continue
        if edge.id in seen_inputs:
            continue
        seen_inputs.add(edge.id)
        if _value(change_node.kind) not in {
            NodeKind.OPENSPEC_ACTIVE_CHANGE.value,
            NodeKind.OPENSPEC_ARCHIVED_CHANGE.value,
        }:
            diagnostics.append(
                GraphDerivationDiagnostic(
                    rule_id=OPENSPEC_CHANGE_TO_DURABLE_SPEC_RULE,
                    affected_object_id=edge.id,
                    message="Cannot derive OpenSpec traceability because the source is not an OpenSpec change.",
                    severity="warning",
                )
            )
            continue
        if _value(change_scoped_spec.kind) != NodeKind.SPECIFICATION.value:
            diagnostics.append(
                GraphDerivationDiagnostic(
                    rule_id=OPENSPEC_CHANGE_TO_DURABLE_SPEC_RULE,
                    affected_object_id=edge.id,
                    message="Cannot derive OpenSpec traceability because the target is not a canonical specification.",
                    severity="warning",
                )
            )
            continue
        if not edge.evidence_ids or any(item not in evidence_ids for item in edge.evidence_ids):
            diagnostics.append(
                GraphDerivationDiagnostic(
                    rule_id=OPENSPEC_CHANGE_TO_DURABLE_SPEC_RULE,
                    affected_object_id=edge.id,
                    message="Cannot derive OpenSpec traceability because asserted evidence is missing.",
                    severity="warning",
                )
            )
            continue
        if not all(
            has_complete_resolvable_provenance(evidence_by_id[evidence_id], provenance_by_id)
            for evidence_id in edge.evidence_ids
        ):
            diagnostics.append(GraphDerivationDiagnostic(
                OPENSPEC_CHANGE_TO_DURABLE_SPEC_RULE, edge.id,
                "Cannot derive OpenSpec traceability because asserted provenance is incomplete or unresolved.", "warning",
            ))
            continue
        input_provenance_ids = tuple(sorted({
            provenance_id for evidence_id in edge.evidence_ids
            for provenance_id in evidence_by_id[evidence_id].provenance_ids
        }))
        input_representation = json.dumps(
            {"input_edge_id": edge.id, "input_provenance_ids": input_provenance_ids},
            sort_keys=True, separators=(",", ":"),
        )
        provenance = ProvenanceRecord(
            ProvenanceKind.DERIVED,
            max(item.observed_at for item in snapshot.provenance if item.id in input_provenance_ids), "sha256",
            hashlib.sha256(input_representation.encode()).hexdigest(), "engineering-kg-derivation",
            "1", None, OPENSPEC_CHANGE_TO_DURABLE_SPEC_RULE, input_provenance_ids,
        )
        provenance_evidence = Evidence(
            stable_id("evidence", provenance.id), "fixture", f"derivation:{provenance.id}",
            provenance_ids=(provenance.id,),
        )
        derived_provenance.append(provenance)
        derived_evidence.append(provenance_evidence)
        candidate = Edge(
                id=stable_id(
                    "edge",
                    EdgeKind.TRACES_TO,
                    OPENSPEC_CHANGE_TO_DURABLE_SPEC_RULE,
                    change_node.id,
                    change_scoped_spec.id,
                    edge.id,
                ),
                kind=EdgeKind.TRACES_TO,
                source_id=change_node.id,
                target_id=change_scoped_spec.id,
                properties={
                    "derived": True,
                    "input_edge_ids": (edge.id,),
                    "rule_id": OPENSPEC_CHANGE_TO_DURABLE_SPEC_RULE,
                },
                evidence_ids=(provenance_evidence.id,),
            )
        if error := relationship_error(candidate.kind, change_node, change_scoped_spec):
            diagnostics.append(GraphDerivationDiagnostic(
                OPENSPEC_CHANGE_TO_DURABLE_SPEC_RULE, edge.id,
                f"Cannot derive OpenSpec traceability because catalog admission failed: {error}.", "warning",
            ))
            derived_provenance.pop()
            derived_evidence.pop()
            continue
        derived_edges.append(candidate)

    derived_graph = GraphSnapshot(
        edges=tuple(sorted(derived_edges, key=lambda item: item.id)),
        evidence=tuple(sorted(derived_evidence, key=lambda item: item.id)),
        # Admission validates derived input references before a graph can be
        # emitted. Retain the already-admitted inputs in this intermediate
        # snapshot; merge coalesces them with the source snapshot below.
        provenance=tuple(sorted((*snapshot.provenance, *derived_provenance), key=lambda item: item.id)),
    )
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


def _diagnostic_sort_key(item: GraphDerivationDiagnostic) -> tuple[str, str, str, str]:
    return (item.severity, item.rule_id, item.affected_object_id, item.message)


def _value(value: object) -> object:
    return getattr(value, "value", value)
