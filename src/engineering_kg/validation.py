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
    ProvenanceKind,
    ProvenanceRecord,
    PullRequestImplementationEvidence,
    PullRequestDeclaredAssociation,
    PullRequestObservedRepositoryRelation,
    pull_request_projection_edge,
    SourceArtifactLocator,
    _has_complete_provenance,
    pull_request_source_artifact_error,
    pull_request_relation_provenance_error,
    provenance_association_error,
    source_artifact_identity_error,
    openspec_requirement_id,
    openspec_scenario_id,
    openspec_specification_id,
    stable_id,
)
from engineering_kg.relationship_vocabulary import eligible_for_trusted_cross_graph_projection, relationship_error, pull_request_relationship_error


SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
OPENSPEC_CHANGE_TRACEABILITY_KINDS = {EdgeKind.ASSERTS.value, EdgeKind.TRACES_TO.value}
RETIRED_OPENSPEC_DOMAIN_KINDS = {
    "openspec_change",
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
    diagnostics.extend(_duplicate_conflict_diagnostics("provenance", snapshot.provenance))
    diagnostics.extend(_duplicate_conflict_diagnostics("cross-graph-link-claim", snapshot.cross_graph_link_claims))
    diagnostics.extend(_duplicate_conflict_diagnostics("cross-graph-link-evidence", snapshot.cross_graph_link_evidence))
    diagnostics.extend(_duplicate_conflict_diagnostics("cross-graph-link-lifecycle", snapshot.cross_graph_link_lifecycle))
    diagnostics.extend(_duplicate_conflict_diagnostics("pull-request-evidence", snapshot.pull_request_evidence))
    diagnostics.extend(_duplicate_conflict_diagnostics("pull-request-declared-association", snapshot.pull_request_declared_associations))
    diagnostics.extend(_duplicate_conflict_diagnostics("pull-request-observed-repository-relation", snapshot.pull_request_observed_repository_relations))

    nodes_by_id = {node.id: node for node in snapshot.nodes}
    evidence_by_id = {item.id: item for item in snapshot.evidence}
    diagnostics.extend(_edge_endpoint_diagnostics(snapshot.edges, nodes_by_id))
    diagnostics.extend(_evidence_reference_diagnostics(snapshot, evidence_by_id))
    diagnostics.extend(_retired_vocabulary_diagnostics(snapshot))
    diagnostics.extend(_canonical_identity_diagnostics(snapshot.nodes))
    diagnostics.extend(_relationship_vocabulary_diagnostics(snapshot, nodes_by_id, evidence_by_id))
    diagnostics.extend(_traceability_shape_diagnostics(snapshot.edges, nodes_by_id))
    diagnostics.extend(_unresolved_related_spec_diagnostics(snapshot.nodes, snapshot.edges, snapshot.evidence))
    diagnostics.extend(_cross_graph_link_diagnostics(snapshot, nodes_by_id, evidence_by_id))
    diagnostics.extend(_source_artifact_identity_diagnostics(snapshot))
    diagnostics.extend(_provenance_diagnostics(snapshot))
    diagnostics.extend(_pull_request_diagnostics(snapshot, nodes_by_id, evidence_by_id))

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
            "provenance_count": snapshot.provenance_count,
            "cross_graph_link_claim_count": snapshot.cross_graph_link_claim_count,
            "cross_graph_link_evidence_count": snapshot.cross_graph_link_evidence_count,
            "cross_graph_link_lifecycle_count": snapshot.cross_graph_link_lifecycle_count,
            "pull_request_evidence_count": snapshot.pull_request_evidence_count,
            "pull_request_declared_association_count": snapshot.pull_request_declared_association_count,
            "pull_request_observed_repository_relation_count": snapshot.pull_request_observed_repository_relation_count,
            "node_count": snapshot.node_count,
        },
    )
    return GraphValidationResult(status=status, metadata=metadata)


def _provenance_diagnostics(snapshot: GraphSnapshot) -> list[GraphValidationDiagnostic]:
    """Validate the association and chain independently of producer code."""
    diagnostics: list[GraphValidationDiagnostic] = []
    by_id = {item.id: item for item in snapshot.provenance}
    for evidence in sorted(snapshot.evidence, key=lambda item: item.id):
        if evidence.provenance_ids and any(item not in by_id for item in evidence.provenance_ids):
            missing = next(item for item in sorted(evidence.provenance_ids) if item not in by_id)
            diagnostics.append(GraphValidationDiagnostic("error", "provenance-reference-exists", evidence.id, f"Evidence references absent provenance: {missing}"))
        if error := provenance_association_error(evidence, by_id):
            diagnostics.append(GraphValidationDiagnostic(
                "error", "provenance-evidence-semantic-consistency", evidence.id, error,
            ))
        if source_artifact_identity_error(evidence) is None and evidence_requires_external_provenance(evidence) and not evidence.provenance_ids:
            diagnostics.append(GraphValidationDiagnostic("error", "external-provenance-complete", evidence.id, "External evidence lacks complete first-class provenance."))
    for record in sorted(snapshot.provenance, key=lambda item: item.id):
        try:
            # Reconstructing forces stable identity and all immutable field checks.
            expected = ProvenanceRecord(record.kind, record.observed_at, record.content_hash_algorithm, record.content_hash, record.extractor_id, record.extractor_version, record.source_artifact_identity, record.derivation_rule_id, record.input_provenance_ids)
            if record.id != expected.id:
                raise ValueError("stable ID does not match immutable fields")
        except ValueError as exc:
            diagnostics.append(GraphValidationDiagnostic("error", "provenance-valid", record.id, f"Invalid provenance: {exc}"))
            continue
        if record.kind is ProvenanceKind.DERIVED:
            for input_id in record.input_provenance_ids:
                if input_id not in by_id:
                    diagnostics.append(GraphValidationDiagnostic("error", "derived-provenance-input-exists", record.id, f"Derived provenance references absent input provenance: {input_id}"))
    return diagnostics


def _pull_request_diagnostics(
    snapshot: GraphSnapshot,
    nodes_by_id: dict[str, Node],
    evidence_by_id: dict[str, object],
) -> list[GraphValidationDiagnostic]:
    """Validate typed PR records and their graph/cross-graph boundaries."""

    diagnostics: list[GraphValidationDiagnostic] = []
    prs = {item.id: item for item in snapshot.pull_request_evidence}
    associations = {item.id: item for item in snapshot.pull_request_declared_associations}
    relations = {item.id: item for item in snapshot.pull_request_observed_repository_relations}
    provenance_by_id = {item.id: item for item in snapshot.provenance}
    for item in snapshot.pull_request_evidence:
        try:
            expected = PullRequestImplementationEvidence(
                item.pull_request_id, item.repository_id, item.base_revision,
                item.head_revision, item.merged, item.source_evidence_id,
                item.provenance_evidence_id,
            )
            if expected.id != item.id:
                raise ValueError("stable identity does not match immutable fields")
        except (AttributeError, ValueError) as exc:
            diagnostics.append(_cross_error("pr-evidence-identity", item.id, f"Invalid PR evidence: {exc}"))
            continue
        repository = nodes_by_id.get(item.repository_id)
        if repository is None or _value(repository.kind) != NodeKind.REPOSITORY.value:
            diagnostics.append(_cross_error("pr-repository-exists", item.id, "PR evidence repository does not reference a canonical REPOSITORY node."))
        evidence = evidence_by_id.get(item.source_evidence_id)
        if evidence is None:
            diagnostics.append(_cross_error("pr-source-evidence-exists", item.id, "PR evidence source_evidence_id is absent."))
        elif not _has_complete_provenance(evidence, provenance_by_id):
            diagnostics.append(_cross_error("pr-source-provenance-complete", item.id, "PR evidence source evidence lacks complete provenance."))
        if item.provenance_evidence_id not in provenance_by_id:
            diagnostics.append(_cross_error("pr-provenance-exists", item.id, "PR evidence provenance reference is absent."))
        if error := pull_request_source_artifact_error(item, evidence_by_id, provenance_by_id):
            diagnostics.append(_cross_error("pr-source-artifact-binding", item.id, error + "."))
        node = nodes_by_id.get(item.node_id)
        if node is None or _value(node.kind) != NodeKind.PULL_REQUEST.value:
            diagnostics.append(_cross_error("pr-node-exists", item.id, "PR evidence has no canonical PULL_REQUEST node."))
    for item in snapshot.pull_request_declared_associations:
        pr = prs.get(item.pull_request_evidence_id)
        subject = nodes_by_id.get(item.intended_change_id)
        if pr is None:
            diagnostics.append(_cross_error("pr-association-pr-exists", item.id, "Declared PR association references absent PR evidence."))
        if subject is None or _value(subject.kind) not in {NodeKind.OPENSPEC_ACTIVE_CHANGE.value, NodeKind.OPENSPEC_ARCHIVED_CHANGE.value, NodeKind.JIRA_STORY.value}:
            diagnostics.append(_cross_error("pr-association-endpoint-contract", item.id, "Declared PR association target is not an eligible intended-change node."))
        evidence = evidence_by_id.get(item.source_evidence_id)
        if evidence is None or not _has_complete_provenance(evidence, provenance_by_id):
            diagnostics.append(_cross_error("pr-association-source-complete", item.id, "Declared association source evidence is absent or incomplete."))
        if item.provenance_evidence_id not in provenance_by_id:
            diagnostics.append(_cross_error("pr-association-provenance-exists", item.id, "Declared association provenance reference is absent."))
        if error := pull_request_relation_provenance_error(
            item.source_evidence_id, item.provenance_evidence_id,
            evidence_by_id, provenance_by_id,
        ):
            diagnostics.append(_cross_error("pr-association-provenance-binding", item.id, error + "."))
    for item in snapshot.pull_request_observed_repository_relations:
        pr = prs.get(item.pull_request_evidence_id)
        repository = nodes_by_id.get(item.repository_id)
        if pr is None:
            diagnostics.append(_cross_error("pr-relation-pr-exists", item.id, "Observed PR repository relation references absent PR evidence."))
        elif item.repository_id != pr.repository_id:
            diagnostics.append(_cross_error("pr-relation-repository-match", item.id, "Observed PR repository relation disagrees with PR evidence."))
        if repository is None or _value(repository.kind) != NodeKind.REPOSITORY.value:
            diagnostics.append(_cross_error("pr-relation-repository-exists", item.id, "Observed PR repository relation target is not a REPOSITORY node."))
        evidence = evidence_by_id.get(item.source_evidence_id)
        if evidence is None or not _has_complete_provenance(evidence, provenance_by_id):
            diagnostics.append(_cross_error("pr-relation-source-complete", item.id, "Observed repository relation source evidence is absent or incomplete."))
        if item.provenance_evidence_id not in provenance_by_id:
            diagnostics.append(_cross_error("pr-relation-provenance-exists", item.id, "Observed repository relation provenance reference is absent."))
        if error := pull_request_relation_provenance_error(
            item.source_evidence_id, item.provenance_evidence_id,
            evidence_by_id, provenance_by_id,
        ):
            diagnostics.append(_cross_error("pr-relation-provenance-binding", item.id, error + "."))

    # Typed PR relations are the source of truth for their canonical edge
    # projections.  Validate the inverse as well as the existing edge-to-record
    # direction, including the source-evidence binding carried by the edge.
    expected_projection_edges = {}
    for association in snapshot.pull_request_declared_associations:
        pr = prs.get(association.pull_request_evidence_id)
        if pr is None:
            continue
        expected_projection_edges[association.id] = pull_request_projection_edge(pr, association)
    for relation in snapshot.pull_request_observed_repository_relations:
        pr = prs.get(relation.pull_request_evidence_id)
        if pr is None:
            continue
        expected_projection_edges[relation.id] = pull_request_projection_edge(pr, relation)

    edges_by_id = {edge.id: edge for edge in snapshot.edges}
    for relation_id, expected in sorted(expected_projection_edges.items()):
        actual = edges_by_id.get(expected.id)
        if actual is None:
            rule_id = (
                "pr-declared-association-projection"
                if expected.kind is EdgeKind.REFERENCES
                else "pr-observed-repository-projection"
            )
            diagnostics.append(_cross_error(
                rule_id, relation_id,
                "Typed PR relation lacks its exact projected edge.",
            ))
        elif actual.as_dict() != expected.as_dict():
            rule_id = (
                "pr-declared-association-projection"
                if expected.kind is EdgeKind.REFERENCES
                else "pr-observed-repository-projection"
            )
            diagnostics.append(_cross_error(
                rule_id, relation_id,
                "Typed PR relation projection disagrees on endpoint, kind, or source evidence.",
            ))

    for observation in snapshot.cross_graph_link_evidence:
        if observation.pull_request_evidence_id is None:
            if observation.strategy_id == "pr-code-candidate-extraction":
                diagnostics.append(_cross_error(
                    "pr-observation-scope", observation.id,
                    "PR candidate observation requires explicit PR evidence and association.",
                ))
            continue
        pr = prs.get(observation.pull_request_evidence_id)
        association = associations.get(observation.declared_association_id or "")
        claim = next((item for item in snapshot.cross_graph_link_claims if item.id == observation.claim_id), None)
        if pr is None or association is None:
            diagnostics.append(_cross_error("pr-observation-scope", observation.id, "PR-scoped observation references absent PR evidence or declared association."))
            continue
        if association.pull_request_evidence_id != pr.id or claim is None or claim.subject_id != association.intended_change_id:
            diagnostics.append(_cross_error("pr-observation-association-scope", observation.id, "PR-scoped observation disagrees with declared association scope."))
        elif claim.target.repository != pr.repository_id or claim.target.revision != pr.head_revision:
            diagnostics.append(_cross_error("pr-observation-revision-scope", observation.id, "PR-scoped observation locator disagrees with PR repository/head revision."))
    for edge in snapshot.edges:
        source = nodes_by_id.get(edge.source_id)
        if source is None or _value(source.kind) != NodeKind.PULL_REQUEST.value:
            continue
        target = nodes_by_id.get(edge.target_id)
        error = pull_request_relationship_error(edge.kind, source, target)
        if error:
            diagnostics.append(_cross_error(error, edge.id, "Pull-request edge does not satisfy the typed relationship catalog."))
            continue
        expected = next(
            (candidate for candidate in expected_projection_edges.values() if candidate.id == edge.id),
            None,
        )
        if expected is None:
            rule_id = (
                "pr-declared-association-record"
                if _value(edge.kind) == EdgeKind.REFERENCES.value
                else "pr-observed-repository-record"
            )
            diagnostics.append(_cross_error(
                rule_id, edge.id,
                "PR projection edge lacks a matching typed relation record.",
            ))
        elif edge.as_dict() != expected.as_dict():
            rule_id = (
                "pr-declared-association-projection"
                if _value(edge.kind) == EdgeKind.REFERENCES.value
                else "pr-observed-repository-projection"
            )
            diagnostics.append(_cross_error(
                rule_id, edge.id,
                "PR projection edge disagrees with its typed relation endpoint, kind, or source evidence.",
            ))
    return diagnostics


def evidence_requires_external_provenance(evidence: object) -> bool:
    """Only authoritative source evidence is governed by external provenance."""
    return getattr(evidence, "source", "") not in {
        "fixture", "openlore", "pr-code-candidate-extraction", "repo-index", "review"
    }


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
        "provenance": _duplicate_id_count(snapshot.provenance),
        "node": _duplicate_id_count(snapshot.nodes),
        "cross_graph_link_claim": _duplicate_id_count(snapshot.cross_graph_link_claims),
        "cross_graph_link_evidence": _duplicate_id_count(snapshot.cross_graph_link_evidence),
        "cross_graph_link_lifecycle": _duplicate_id_count(snapshot.cross_graph_link_lifecycle),
        "pull_request_evidence": _duplicate_id_count(snapshot.pull_request_evidence),
        "pull_request_declared_association": _duplicate_id_count(snapshot.pull_request_declared_associations),
        "pull_request_observed_repository_relation": _duplicate_id_count(snapshot.pull_request_observed_repository_relations),
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
        try:
            serialized = item.as_dict()
        except (AttributeError, ValueError):
            # Classified support that bypassed frozen construction must be
            # diagnosed by _classified_support_diagnostics, not serialized
            # while checking duplicate identities.
            if collection in {
                "cross-graph-link-evidence", "cross-graph-link-lifecycle",
            }:
                continue
            raise
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
    provenance_by_id = {item.id: item for item in snapshot.provenance}
    for claim in snapshot.cross_graph_link_claims:
        if claim.subject_id not in nodes_by_id:
            diagnostics.append(_cross_error("cross-graph-subject-exists", claim.id, "Cross-graph claim subject_id does not reference an existing node."))
        if not _complete_code_locator(claim.target):
            diagnostics.append(_cross_error("cross-graph-target-complete", claim.id, "Cross-graph claim target must be a complete CodeLocator."))
        error = relationship_error(claim.relation_kind, nodes_by_id.get(claim.subject_id), claim.target)
        if error:
            diagnostics.append(_cross_error(error, claim.id, "Cross-graph claim does not satisfy the canonical relationship catalog."))
    for observation in snapshot.cross_graph_link_evidence:
        diagnostics.extend(_classified_support_diagnostics(observation, evidence_by_id, provenance_by_id))
        if observation.claim_id not in claims_by_id:
            diagnostics.append(_cross_error("cross-graph-claim-exists", observation.id, "Cross-graph evidence references an absent claim."))
        if observation.provenance_evidence_id not in evidence_by_id:
            diagnostics.append(_cross_error("cross-graph-provenance-exists", observation.id, "Cross-graph evidence references absent provenance evidence."))
        elif not _has_complete_provenance(
            evidence_by_id[observation.provenance_evidence_id], provenance_by_id
        ):
            diagnostics.append(_cross_error("cross-graph-provenance-complete", observation.id, "Cross-graph evidence requires complete resolvable first-class provenance."))
    revisions: dict[tuple[str, int], CrossGraphLinkLifecycle] = {}
    lifecycle_claims: set[str] = set()
    latest_lifecycle: dict[str, CrossGraphLinkLifecycle] = {}
    for entry in snapshot.cross_graph_link_lifecycle:
        diagnostics.extend(_classified_support_diagnostics(entry, evidence_by_id, provenance_by_id))
        lifecycle_claims.add(entry.claim_id)
        if entry.claim_id not in claims_by_id:
            diagnostics.append(_cross_error("cross-graph-claim-exists", entry.id, "Cross-graph lifecycle references an absent claim."))
        if entry.provenance_evidence_id not in evidence_by_id:
            diagnostics.append(_cross_error("cross-graph-provenance-exists", entry.id, "Cross-graph lifecycle references absent provenance evidence."))
        elif not _has_complete_provenance(
            evidence_by_id[entry.provenance_evidence_id], provenance_by_id
        ):
            diagnostics.append(_cross_error("cross-graph-provenance-complete", entry.id, "Cross-graph lifecycle requires complete resolvable first-class provenance."))
        if not isinstance(entry.revision, int) or isinstance(entry.revision, bool) or entry.revision <= 0:
            diagnostics.append(_cross_error("cross-graph-lifecycle-revision", entry.id, "Cross-graph lifecycle revision must be a positive integer."))
        if _value(entry.state) not in CROSS_GRAPH_LINK_LIFECYCLE_STATES:
            diagnostics.append(_cross_error("cross-graph-lifecycle-state", entry.id, "Cross-graph lifecycle state is unsupported."))
        key = (entry.claim_id, entry.revision)
        previous = revisions.get(key)
        if previous is not None and previous.as_dict() != entry.as_dict():
            diagnostics.append(_cross_error("cross-graph-lifecycle-revision-conflict", entry.id, "Cross-graph lifecycle revision has conflicting values."))
        revisions[key] = entry
        current = latest_lifecycle.get(entry.claim_id)
        if current is None or entry.revision > current.revision:
            latest_lifecycle[entry.claim_id] = entry
    for claim in snapshot.cross_graph_link_claims:
        if claim.id not in lifecycle_claims:
            diagnostics.append(_cross_error("cross-graph-lifecycle-current", claim.id, "Cross-graph claim has no determinable current lifecycle revision."))
        elif (
            _value(latest_lifecycle[claim.id].state) == "trusted"
            and not any(item.claim_id == claim.id for item in snapshot.cross_graph_link_evidence)
        ):
            diagnostics.append(_cross_error(
                "cross-graph-trusted-supporting-observation",
                claim.id,
                "Trusted cross-graph claims require attributable supporting observation evidence.",
            ))
        elif _value(latest_lifecycle[claim.id].state) == "trusted" and not eligible_for_trusted_cross_graph_projection(
            claim,
            tuple(item for item in snapshot.cross_graph_link_evidence if item.claim_id == claim.id),
            latest_lifecycle[claim.id],
            tuple(item for item in snapshot.cross_graph_link_lifecycle if item.claim_id == claim.id),
        ):
            diagnostics.append(_cross_error(
                "cross-graph-implementation-trust",
                claim.id,
                "Trusted IMPLEMENTS projection requires authoritative declared support and an explicit trusted lifecycle disposition.",
            ))
    return diagnostics


def _classified_support_diagnostics(
    support: object, evidence_by_id: dict[str, object],
    provenance_by_id: dict[str, ProvenanceRecord],
) -> list[GraphValidationDiagnostic]:
    """Validate support classification against its directly referenced provenance."""
    diagnostics: list[GraphValidationDiagnostic] = []
    try:
        # Reconstruction catches records bypassing frozen constructors.
        if isinstance(support, CrossGraphLinkEvidence):
            CrossGraphLinkEvidence(support.claim_id, support.strategy_id, support.observation_id,
                                   support.provenance_evidence_id, support.origin, support.status,
                                   support.confidence, support.trust_disposition,
                                   support.pull_request_evidence_id,
                                   support.declared_association_id)
        else:
            CrossGraphLinkLifecycle(support.claim_id, support.revision, support.state,
                                    support.provenance_evidence_id, support.origin, support.status,
                                    support.confidence, support.trust_disposition)
    except (AttributeError, ValueError):
        return [_cross_error("cross-graph-classification-valid", getattr(support, "claim_id", "unknown"),
                              "Cross-graph support has invalid classification or trust fields.")]
    evidence = evidence_by_id.get(support.provenance_evidence_id)
    records = [provenance_by_id[item] for item in evidence.provenance_ids if item in provenance_by_id] if evidence else []
    if support.status is ProvenanceKind.EXTERNAL or getattr(support.status, "value", support.status) == "authoritative":
        if not records or any(item.kind is not ProvenanceKind.EXTERNAL for item in records):
            diagnostics.append(_cross_error("cross-graph-classification-provenance", support.id,
                "Authoritative cross-graph support requires authoritative external provenance."))
    elif not records or any(item.kind is not ProvenanceKind.DERIVED for item in records):
        diagnostics.append(_cross_error("cross-graph-classification-provenance", support.id,
            "Derived cross-graph support requires derived provenance."))
    return diagnostics


def _relationship_vocabulary_diagnostics(
    snapshot: GraphSnapshot, nodes_by_id: dict[str, Node], evidence_by_id: dict[str, object],
) -> list[GraphValidationDiagnostic]:
    diagnostics: list[GraphValidationDiagnostic] = []
    owner_targets: dict[str, set[str]] = defaultdict(set)
    provenance_by_id = {item.id: item for item in snapshot.provenance}
    for edge in snapshot.edges:
        kind = _value(edge.kind)
        if kind == EdgeKind.ASSERTS.value:
            # ASSERTS is deliberately narrow non-semantic source support.
            source, target = nodes_by_id.get(edge.source_id), nodes_by_id.get(edge.target_id)
            if (source is None or target is None or
                _value(source.kind) not in {NodeKind.OPENSPEC_ACTIVE_CHANGE.value, NodeKind.OPENSPEC_ARCHIVED_CHANGE.value} or
                _value(target.kind) != NodeKind.SPECIFICATION.value):
                diagnostics.append(GraphValidationDiagnostic("error", "asserts-support-contract", edge.id, "ASSERTS is restricted to OpenSpec change-to-specification support."))
            continue
        error = relationship_error(kind, nodes_by_id.get(edge.source_id), nodes_by_id.get(edge.target_id))
        if error:
            diagnostics.append(GraphValidationDiagnostic("error", error, edge.id, "Edge does not satisfy the canonical relationship catalog."))
        elif (
            not edge.evidence_ids
            or any(
                evidence_id not in evidence_by_id
                or not _has_complete_provenance(evidence_by_id[evidence_id], provenance_by_id)
                for evidence_id in edge.evidence_ids
            )
        ):
            diagnostics.append(GraphValidationDiagnostic(
                "error", "relationship-provenance-complete", edge.id,
                "Canonical relationships require complete evidence provenance.",
            ))
        if kind == EdgeKind.OWNED_BY.value:
            owner_targets[edge.source_id].add(edge.target_id)
    for source_id, targets in sorted(owner_targets.items()):
        if len(targets) > 1:
            diagnostics.append(GraphValidationDiagnostic("error", "relationship-cardinality", source_id, "OWNED_BY permits at most one target per source."))
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
        if _value(edge.kind) != EdgeKind.REFERENCES.value:
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
