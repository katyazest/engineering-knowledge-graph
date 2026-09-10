"""Local, provider-neutral extraction of observed PR-to-code candidates."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
import re
import hashlib
import json
from typing import Any, Mapping

from engineering_kg.compact_identity import (
    is_complete_symbol_identity,
    is_immutable_revision,
    safe_identity,
    safe_relative_file,
    safe_repository,
)
from engineering_kg.ontology import (
    CodeLocator,
    CrossGraphLinkClaim,
    CrossGraphLinkEvidence,
    CrossGraphLinkLifecycle,
    CrossGraphLinkLifecycleState,
    CrossGraphEvidenceOrigin,
    CrossGraphEvidenceStatus,
    CrossGraphTrustDisposition,
    Evidence,
    GraphSnapshot,
    SourceArtifactIdentity,
    SourceArtifactLocator,
    ProvenanceKind,
    ProvenanceRecord,
    PullRequestImplementationEvidence,
    PullRequestDeclaredAssociation,
    PullRequestObservedRepositoryRelation,
    project_pull_request_evidence,
    stable_id,
)
from engineering_kg.relationship_vocabulary import RelationshipKind


STRATEGY_ID = "pr-code-candidate-extraction"
RELATION_KIND = RelationshipKind.TOUCHES.value

# Mapping identities identify adapted provider records, not source text. A
# namespace-qualified token prevents source snippets or bodies from becoming
# observation IDs, evidence locators, or retained provenance properties.
_QUALIFIED_SOURCE_MAPPING_IDENTITY = re.compile(
    r"^[A-Za-z][A-Za-z0-9_-]*(?::[A-Za-z0-9][A-Za-z0-9._/-]*)+$"
)

# These values are retained in provenance and/or a code locator.  Keep the
# normalized boundary deliberately narrower than arbitrary provider display
# fields so bodies, payload fragments, and multiline source cannot become
# canonical graph identity.
# Safe identities may use a colon as a namespace separator.  The URI scheme
# and its value are checked separately so opaque IDs such as
# ``urn:example.org/link-42`` are not confused with navigable URLs.
class PrCodeCandidateValidationError(ValueError):
    """A provider-neutral input did not meet the normalized contract."""


class MappingOutcome(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"
    MALFORMED = "malformed"
    UNSUPPORTED = "unsupported"


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PrCodeCandidateValidationError(f"{field_name} must be a non-empty string")
    return value


def _safe_identity(value: object, field_name: str) -> str:
    """Return a trimmed opaque identifier that cannot carry payload-like text."""

    try:
        return safe_identity(value, field_name)
    except ValueError as exc:
        raise PrCodeCandidateValidationError(str(exc)) from None


def _is_url_like_identity(value: str) -> bool:
    """Reject navigable/hierarchical URLs while retaining opaque stable IDs.

    ``urn:example.org/link-42`` is an opaque identifier even though its
    namespace-specific string contains a slash.  URL schemes whose values are
    navigable locations remain disallowed whether they use an authority
    (``https://host/path``) or the shorthand hierarchical form
    (``https:host/path``).
    """

    from engineering_kg.compact_identity import is_url_like_identity

    return is_url_like_identity(value)


def _safe_repository(value: object) -> str:
    try:
        return safe_repository(value, "change_set.repository")
    except ValueError as exc:
        raise PrCodeCandidateValidationError(str(exc)) from None


def _safe_relative_file(value: object) -> str:
    try:
        return safe_relative_file(value, "mapping.file")
    except ValueError as exc:
        raise PrCodeCandidateValidationError(str(exc)) from None


@dataclass(frozen=True)
class ChangedSymbolMapping:
    """One Graphify-adapted changed-file/symbol mapping outcome."""

    id: str
    file: str
    outcome: MappingOutcome | str
    symbol: str | None = None
    repository: str | None = None
    revision: str | None = None

    def __post_init__(self) -> None:
        mapping_id = _normalized_source_mapping_id(self.id)
        object.__setattr__(self, "id", mapping_id or "")
        object.__setattr__(self, "file", _safe_relative_file(self.file))
        try:
            outcome = MappingOutcome(self.outcome)
        except ValueError:
            # A future/provider-specific relationship assertion has no approved
            # source mapping. Preserve only its classified non-admission state.
            outcome = MappingOutcome.UNSUPPORTED
        object.__setattr__(self, "outcome", outcome)
        if mapping_id is None:
            object.__setattr__(self, "outcome", MappingOutcome.MALFORMED)
            object.__setattr__(self, "symbol", None)
            return
        if outcome is MappingOutcome.RESOLVED:
            _text(self.symbol, "mapping.symbol")
            if not _is_complete_deterministic_symbol_identity(self.symbol):
                # Do not retain a purported symbol when it is only a bare
                # display name, malformed text, or source/body-like content.
                # Treat it as a classified malformed outcome so extraction can
                # produce an explainable, payload-safe non-admission result.
                object.__setattr__(self, "outcome", MappingOutcome.MALFORMED)
                object.__setattr__(self, "symbol", None)
        elif self.symbol is not None:
            # Non-resolved records carry a classified outcome, never a
            # provider-provided candidate string or body.
            object.__setattr__(self, "symbol", None)
        if self.repository is not None:
            object.__setattr__(self, "repository", _safe_identity(self.repository, "mapping.repository"))
        if self.revision is not None:
            object.__setattr__(self, "revision", _safe_identity(self.revision, "mapping.revision"))
            if not _immutable_revision(self.revision):
                raise PrCodeCandidateValidationError("mapping.revision must be immutable")


@dataclass(frozen=True)
class NormalizedPullRequestEvidence:
    """Provider-neutral enriched PR input admitted by the adapter boundary."""

    pull_request: PullRequestImplementationEvidence
    association: PullRequestDeclaredAssociation
    repository_relation: PullRequestObservedRepositoryRelation
    mappings: tuple[ChangedSymbolMapping, ...]
    evidence: tuple[Evidence, ...] = ()
    provenance: tuple[ProvenanceRecord, ...] = ()

    @property
    def id(self) -> str:
        return self.pull_request.id

    def __post_init__(self) -> None:
        if self.association.pull_request_evidence_id != self.pull_request.id:
            raise PrCodeCandidateValidationError("association must reference pull_request evidence")
        if self.repository_relation.pull_request_evidence_id != self.pull_request.id:
            raise PrCodeCandidateValidationError("repository relation must reference pull_request evidence")
        if self.repository_relation.repository_id != self.pull_request.repository_id:
            raise PrCodeCandidateValidationError("repository relation must match pull_request repository")
        if not isinstance(self.mappings, tuple) or not self.mappings:
            raise PrCodeCandidateValidationError("pr evidence mappings must be a non-empty tuple")
        if not all(isinstance(item, ChangedSymbolMapping) for item in self.mappings):
            raise PrCodeCandidateValidationError("pr evidence mappings must contain ChangedSymbolMapping records")
        object.__setattr__(self, "mappings", tuple(sorted(self.mappings, key=lambda item: item.id)))


def normalize_pull_request_evidence(value: Mapping[str, Any]) -> NormalizedPullRequestEvidence:
    """Normalize identity-level PR evidence and discard provider payload fields."""

    if not isinstance(value, Mapping):
        raise PrCodeCandidateValidationError("pr evidence must be a mapping")
    forbidden_input_keys = {
        "provider_payload", "payload", "diff", "source_code", "title", "description",
        "comments", "credentials", "token", "tokens",
    }
    forbidden = sorted(key for key in value if key in forbidden_input_keys)
    if forbidden:
        raise PrCodeCandidateValidationError(f"raw payload field is not allowed: {forbidden[0]}")
    provenance_input = value.get("provenance", value.get("provenance_inputs"))
    if not isinstance(provenance_input, Mapping) or not provenance_input:
        raise PrCodeCandidateValidationError("provenance input is required")
    if any(key in forbidden_input_keys for key in provenance_input):
        raise PrCodeCandidateValidationError("raw provenance payload field is not allowed")
    pull_request_id = value.get("pull_request_id", value.get("source_qualified_pr_id"))
    repository_id = value.get(
        "repository_node_id", value.get("repository_id", value.get("repository"))
    )
    base_revision = value.get("base_revision")
    head_revision = value.get("head_revision")
    if "merged_revision" in value:
        raise PrCodeCandidateValidationError(
            "merged_revision-only input is unsupported; use base_revision and head_revision"
        )
    if not base_revision:
        raise PrCodeCandidateValidationError("base_revision is required")
    if not head_revision:
        raise PrCodeCandidateValidationError("head_revision is required")
    observed_at = value.get("observed_at", "")
    observed_at = _observed_at(observed_at)
    association_data = value.get("association")
    if not isinstance(association_data, Mapping):
        raise PrCodeCandidateValidationError("pr evidence.association is required")
    intended_change_id = association_data.get(
        "intended_change_id", association_data.get("engineering_change_subject_id")
    )
    intended_kind = association_data.get("intended_change_kind")
    if intended_kind is not None and intended_kind not in {
        "openspec-active-change", "openspec-archived-change", "jira_story",
    }:
        raise PrCodeCandidateValidationError("association intended-change endpoint kind is unsupported")
    mappings_data = value.get("mappings")
    if not isinstance(mappings_data, (list, tuple)):
        raise PrCodeCandidateValidationError("pr evidence.mappings must be a list")
    mappings = tuple(
        ChangedSymbolMapping(
            item.get("id") if isinstance(item, Mapping) else None,
            item.get("file") if isinstance(item, Mapping) else None,
            item.get("outcome") if isinstance(item, Mapping) else None,
            item.get("symbol") if isinstance(item, Mapping) else None,
            item.get("repository") if isinstance(item, Mapping) else None,
            item.get("revision", item.get("head_revision")) if isinstance(item, Mapping) else None,
        ) for item in mappings_data
    )
    pr_evidence_source, pr_evidence_provenance = _normalized_source_bundle(
        value.get("pr_source_reference", value.get("pr_source")),
        pull_request_id, repository_id, head_revision, observed_at, "pull-request",
    )
    association_source, association_provenance = _normalized_source_bundle(
        association_data.get("source_reference", association_data.get("source")),
        intended_change_id, repository_id, head_revision, observed_at, "pr-association",
    )
    repository_source, repository_provenance = _normalized_source_bundle(
        value.get("repository_source_reference", value.get("repository_source")),
        pull_request_id, repository_id, head_revision, observed_at, "pr-repository",
    )
    pull_request = PullRequestImplementationEvidence(
        pull_request_id, repository_id, base_revision, head_revision, value.get("merged", False),
        pr_evidence_source.id, pr_evidence_provenance.id,
    )
    association = PullRequestDeclaredAssociation(
        pull_request.id, intended_change_id, association_source.id, association_provenance.id,
    )
    relation = PullRequestObservedRepositoryRelation(
        pull_request.id, repository_id, repository_source.id, repository_provenance.id,
    )
    mapping_evidence: list[Evidence] = []
    mapping_provenance: list[ProvenanceRecord] = []
    for mapping in mappings:
        if not mapping.id:
            continue
        evidence, provenance = _normalized_source_bundle(
            mapping.id, mapping.id, repository_id, head_revision, observed_at, "pull-request-mapping",
        )
        mapping_evidence.append(evidence)
        mapping_provenance.append(provenance)
    return NormalizedPullRequestEvidence(
        pull_request, association, relation, mappings,
        (pr_evidence_source, association_source, repository_source, *mapping_evidence),
        (pr_evidence_provenance, association_provenance, repository_provenance, *mapping_provenance),
    )


# Clear aliases for callers that use the capability name rather than the
# historical candidate-extraction name.
normalize_pr_implementation_evidence = normalize_pull_request_evidence
PullRequestEvidenceInput = NormalizedPullRequestEvidence


def _normalized_source_bundle(
    reference: object,
    identity_value: object,
    repository_id: object,
    revision: object,
    observed_at: str,
    artifact_type: str,
) -> tuple[Evidence, ProvenanceRecord]:
    if reference is None:
        raise PrCodeCandidateValidationError("source reference is required")
    if isinstance(reference, Mapping):
        allowed_keys = {"source_type", "source_identity", "stable_locator", "revision_or_version", "evidence_id"}
        unknown = sorted(key for key in reference if key not in allowed_keys)
        if unknown:
            raise PrCodeCandidateValidationError(f"raw source reference field is not allowed: {unknown[0]}")
        source_type = reference.get("source_type", "normalized-source")
        source_identity = reference.get("source_identity", identity_value)
        stable_locator = reference.get("stable_locator")
        if stable_locator is None:
            stable_locator = f"references/{stable_id('source', identity_value, artifact_type).replace(':', '-') }"
        revision_value = reference.get("revision_or_version", revision)
        if artifact_type == "pull-request" and "revision_or_version" in reference:
            if not isinstance(revision_value, str) or not _immutable_revision(revision_value):
                raise PrCodeCandidateValidationError(
                    "pull-request source reference revision_or_version must be immutable"
                )
            if revision_value != revision:
                raise PrCodeCandidateValidationError(
                    "pull-request source reference revision_or_version must match head_revision"
                )
        evidence_id = reference.get("evidence_id")
    else:
        source_type = "normalized-source"
        source_identity = reference
        stable_locator = f"references/{stable_id('source', reference, artifact_type).replace(':', '-') }"
        revision_value = revision
        evidence_id = None
    try:
        source_identity = safe_identity(source_identity, "source_reference.source_identity")
        source_type = safe_identity(source_type, "source_reference.source_type")
        stable_locator = safe_relative_file(stable_locator, "source_reference.stable_locator")
        revision_value = safe_identity(revision_value, "source_reference.revision_or_version")
    except ValueError as exc:
        raise PrCodeCandidateValidationError(str(exc)) from None
    identity = SourceArtifactIdentity(source_type, source_identity, artifact_type, revision_value, stable_locator)
    provenance = ProvenanceRecord(
        ProvenanceKind.EXTERNAL,
        observed_at,
        "sha256",
        hashlib.sha256(json.dumps({"identity": identity.id, "repository": repository_id, "revision": revision, "artifact_type": artifact_type}, sort_keys=True).encode()).hexdigest(),
        STRATEGY_ID,
        "2",
        identity,
    )
    resolved_evidence_id = evidence_id or stable_id("evidence", identity.id)
    if resolved_evidence_id != stable_id("evidence", identity.id):
        raise PrCodeCandidateValidationError("source reference evidence_id must match its identity")
    evidence = Evidence(
        resolved_evidence_id,
        STRATEGY_ID,
        SourceArtifactLocator(identity, {}),
        {"pull_request_id": str(identity_value), "repository": str(repository_id)},
        (provenance.id,),
    )
    return evidence, provenance


@dataclass(frozen=True)
class PrCodeCandidateDiagnostic:
    reason_code: str
    change_set_id: str
    mapping_id: str = ""
    provenance_evidence_id: str = ""

    def as_dict(self) -> dict[str, str]:
        data = {"change_set_id": self.change_set_id, "reason_code": self.reason_code}
        if self.mapping_id:
            data["mapping_id"] = self.mapping_id
        if self.provenance_evidence_id:
            data["provenance_evidence_id"] = self.provenance_evidence_id
        return data


@dataclass(frozen=True)
class PrCodeCandidateExtractionMetadata:
    accepted_change_set_count: int
    emitted_candidate_count: int
    skipped_input_count: int
    skipped_reason_counts: dict[str, int] = field(default_factory=dict)
    diagnostics: tuple[PrCodeCandidateDiagnostic, ...] = ()
    graph_counts: dict[str, int] = field(default_factory=dict)
    admitted_pr_evidence_count: int = 0
    declared_association_count: int = 0
    observed_repository_relation_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {"accepted_change_set_count": self.accepted_change_set_count, "admitted_pr_evidence_count": self.admitted_pr_evidence_count, "declared_association_count": self.declared_association_count, "diagnostics": [item.as_dict() for item in self.diagnostics], "emitted_candidate_count": self.emitted_candidate_count, "graph_counts": dict(sorted(self.graph_counts.items())), "observed_repository_relation_count": self.observed_repository_relation_count, "skipped_input_count": self.skipped_input_count, "skipped_reason_counts": dict(sorted(self.skipped_reason_counts.items()))}


@dataclass(frozen=True)
class PrCodeCandidateExtractionResult:
    graph: GraphSnapshot
    metadata: PrCodeCandidateExtractionMetadata


def extract_pr_code_candidates(
    change_sets: tuple[NormalizedPullRequestEvidence, ...], subject_graph: GraphSnapshot
) -> PrCodeCandidateExtractionResult:
    """Produce observed candidates only; neither edges nor trusted projections are emitted."""

    if not all(isinstance(item, NormalizedPullRequestEvidence) for item in change_sets):
        raise PrCodeCandidateValidationError(
            "legacy merged-revision-only PR change-set input is unsupported"
        )
    return extract_pull_request_implementation_evidence(tuple(change_sets), subject_graph)


def extract_pull_request_implementation_evidence(
    inputs: tuple[NormalizedPullRequestEvidence, ...], subject_graph: GraphSnapshot,
) -> PrCodeCandidateExtractionResult:
    """Admit enriched PR evidence and association-scoped observed candidates."""

    diagnostics: list[PrCodeCandidateDiagnostic] = []
    accepted: list[NormalizedPullRequestEvidence] = []
    subjects = {node.id: node for node in subject_graph.nodes}
    repository_nodes = {
        node.id for node in subject_graph.nodes if str(getattr(node.kind, "value", node.kind)) == "repository"
    }
    by_id: dict[str, list[NormalizedPullRequestEvidence]] = {}
    for item in inputs:
        by_id.setdefault(item.id, []).append(item)
    for evidence_id in sorted(by_id):
        records = sorted(
            by_id[evidence_id],
            key=lambda item: (
                json.dumps(item.association.as_dict(), sort_keys=True),
                tuple(
                    (mapping.id, mapping.file, mapping.outcome.value, mapping.symbol or "",
                     mapping.repository or "", mapping.revision or "")
                    for mapping in item.mappings
                ),
            ),
        )
        pr_identities = {
            json.dumps(item.pull_request.as_dict(), sort_keys=True)
            for item in records
        }
        if len(pr_identities) > 1:
            diagnostics.append(PrCodeCandidateDiagnostic("conflicting-pr-evidence-identity", evidence_id))
            continue
        for item in records:
            if item.association.intended_change_id not in subjects:
                diagnostics.append(PrCodeCandidateDiagnostic("missing-intended-change", item.id))
                continue
            intended_kind = str(getattr(subjects[item.association.intended_change_id].kind, "value", subjects[item.association.intended_change_id].kind))
            if intended_kind not in {"openspec-active-change", "openspec-archived-change", "jira_story"}:
                diagnostics.append(PrCodeCandidateDiagnostic("ineligible-intended-change-kind", item.id))
                continue
            if item.pull_request.repository_id not in repository_nodes:
                diagnostics.append(PrCodeCandidateDiagnostic("missing-repository", item.id))
                continue
            accepted.append(item)

    # A source mapping ID is an immutable identity.  If an adapter supplies
    # the same ID with different locator identity, neither occurrence is safe
    # to coalesce: reject that mapping while retaining other associations and
    # mappings for the same PR.
    mapping_locators: dict[str, tuple[str, str, str | None, str | None, str | None]] = {}
    conflicting_mapping_ids: set[str] = set()
    for item in accepted:
        for mapping in item.mappings:
            if not mapping.id:
                continue
            locator = (
                mapping.file,
                mapping.outcome.value,
                mapping.symbol,
                mapping.repository,
                mapping.revision,
            )
            previous = mapping_locators.get(mapping.id)
            if previous is None:
                mapping_locators[mapping.id] = locator
            elif previous != locator:
                conflicting_mapping_ids.add(mapping.id)
    for mapping_id in sorted(conflicting_mapping_ids):
        diagnostics.append(PrCodeCandidateDiagnostic(
            "conflicting-source-mapping-identity",
            min(item.id for item in accepted if any(mapping.id == mapping_id for mapping in item.mappings)),
            mapping_id,
        ))

    all_prs: list[PullRequestImplementationEvidence] = []
    all_associations: list[PullRequestDeclaredAssociation] = []
    all_relations: list[PullRequestObservedRepositoryRelation] = []
    all_evidence: list[Evidence] = []
    all_provenance: list[ProvenanceRecord] = []
    claims: list[CrossGraphLinkClaim] = []
    observations: list[CrossGraphLinkEvidence] = []
    lifecycle: list[CrossGraphLinkLifecycle] = []
    for item in accepted:
        all_prs.append(item.pull_request)
        all_associations.append(item.association)
        all_relations.append(item.repository_relation)
        all_evidence.extend(item.evidence)
        all_provenance.extend(item.provenance)
        provenance_by_mapping_id = {
            evidence.properties.get("pull_request_id"): evidence
            for evidence in item.evidence
            if evidence.properties.get("pull_request_id") in {mapping.id for mapping in item.mappings}
        }
        for mapping in sorted(item.mappings, key=lambda value: value.id):
            if not mapping.id:
                diagnostics.append(PrCodeCandidateDiagnostic("invalid-mapping-identity", item.id))
                continue
            if mapping.id in conflicting_mapping_ids:
                continue
            source_evidence = provenance_by_mapping_id.get(mapping.id)
            if mapping.outcome is not MappingOutcome.RESOLVED:
                reason = "unsupported-source-mapping" if mapping.outcome is MappingOutcome.UNSUPPORTED else f"{mapping.outcome.value}-symbol"
                diagnostics.append(PrCodeCandidateDiagnostic(reason, item.id, mapping.id, source_evidence.id if source_evidence else ""))
                continue
            if not mapping.symbol:
                diagnostics.append(PrCodeCandidateDiagnostic("incomplete-locator", item.id, mapping.id, source_evidence.id if source_evidence else ""))
                continue
            if mapping.repository is not None and mapping.repository != item.pull_request.repository_id:
                diagnostics.append(PrCodeCandidateDiagnostic("repository-mismatch", item.id, mapping.id, source_evidence.id if source_evidence else ""))
                continue
            if mapping.revision is not None and mapping.revision != item.pull_request.head_revision:
                diagnostics.append(PrCodeCandidateDiagnostic("revision-mismatch", item.id, mapping.id, source_evidence.id if source_evidence else ""))
                continue
            if source_evidence is None:
                diagnostics.append(PrCodeCandidateDiagnostic("missing-mapping-source", item.id, mapping.id))
                continue
            target = CodeLocator(item.pull_request.repository_id, item.pull_request.head_revision, mapping.file, mapping.symbol)
            claim = CrossGraphLinkClaim(item.association.intended_change_id, RELATION_KIND, target)
            mapping_provenance = next(
                (record for record in item.provenance if record.id in source_evidence.provenance_ids),
                None,
            )
            if mapping_provenance is None:
                diagnostics.append(PrCodeCandidateDiagnostic("missing-mapping-provenance", item.id, mapping.id, source_evidence.id))
                continue
            lifecycle_evidence, lifecycle_provenance = _initial_candidate_lifecycle_provenance(
                claim, mapping_provenance
            )
            all_evidence.append(lifecycle_evidence)
            all_provenance.extend(lifecycle_provenance)
            claims.append(claim)
            observations.append(CrossGraphLinkEvidence(
                claim.id, STRATEGY_ID, mapping.id, source_evidence.id,
                CrossGraphEvidenceOrigin.OBSERVED, CrossGraphEvidenceStatus.AUTHORITATIVE,
                "pr-changed-symbol", CrossGraphTrustDisposition.UNTRUSTED,
                item.pull_request.id, item.association.id,
            ))
            lifecycle.append(CrossGraphLinkLifecycle(
                claim.id, 1, CrossGraphLinkLifecycleState.CANDIDATE, lifecycle_evidence.id,
                CrossGraphEvidenceOrigin.OBSERVED, CrossGraphEvidenceStatus.DERIVED,
                "candidate-initialization", CrossGraphTrustDisposition.UNTRUSTED,
            ))
    projected = project_pull_request_evidence(
        tuple({item.id: item for item in all_prs}.values()),
        tuple({item.id: item for item in all_associations}.values()),
        tuple({item.id: item for item in all_relations}.values()),
    )
    graph = GraphSnapshot(
        nodes=projected.nodes,
        edges=projected.edges,
        evidence=tuple(sorted({item.id: item for item in all_evidence}.values(), key=lambda item: item.id)),
        cross_graph_link_claims=tuple({item.id: item for item in claims}.values()),
        cross_graph_link_evidence=tuple({item.id: item for item in observations}.values()),
        cross_graph_link_lifecycle=tuple({item.id: item for item in lifecycle}.values()),
        provenance=tuple(sorted({item.id: item for item in all_provenance}.values(), key=lambda item: item.id)),
        pull_request_evidence=projected.pull_request_evidence,
        pull_request_declared_associations=projected.pull_request_declared_associations,
        pull_request_observed_repository_relations=projected.pull_request_observed_repository_relations,
    )
    subject_graph.merged_with(graph)
    ordered = tuple(sorted(diagnostics, key=lambda value: (value.reason_code, value.change_set_id, value.mapping_id, value.provenance_evidence_id)))
    metadata = PrCodeCandidateExtractionMetadata(
        len(accepted), len(graph.cross_graph_link_claims), len(ordered),
        dict(Counter(item.reason_code for item in ordered)), ordered,
        {
            "cross_graph_link_claim_count": graph.cross_graph_link_claim_count,
            "cross_graph_link_evidence_count": graph.cross_graph_link_evidence_count,
            "cross_graph_link_lifecycle_count": graph.cross_graph_link_lifecycle_count,
            "evidence_count": graph.evidence_count,
            "pull_request_evidence_count": graph.pull_request_evidence_count,
            "pull_request_declared_association_count": graph.pull_request_declared_association_count,
            "pull_request_observed_repository_relation_count": graph.pull_request_observed_repository_relation_count,
        },
        graph.pull_request_evidence_count,
        graph.pull_request_declared_association_count,
        graph.pull_request_observed_repository_relation_count,
    )
    return PrCodeCandidateExtractionResult(graph, metadata)


def _immutable_revision(value: str) -> bool:
    """Accept only complete Git object IDs, never abbreviated references."""
    return is_immutable_revision(value)


def _observed_at(value: object) -> str:
    """Require the adapter-provided instant used by external provenance.

    Extraction intentionally does not substitute a clock or repository timestamp:
    the normalized provider input must supply this immutable observation value.
    """

    if not isinstance(value, str) or not value.strip():
        raise PrCodeCandidateValidationError("change_set.observed_at is required")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PrCodeCandidateValidationError(
            "change_set.observed_at must be an offset-aware ISO-8601 instant"
        ) from exc
    if instant.tzinfo is None:
        raise PrCodeCandidateValidationError(
            "change_set.observed_at must be an offset-aware ISO-8601 instant"
        )
    return value


def _is_complete_deterministic_symbol_identity(value: str) -> bool:
    """Return whether ``value`` is a complete, qualified code symbol identity."""

    return is_complete_symbol_identity(value)


def _normalized_source_mapping_id(value: object) -> str | None:
    """Return a safe, qualified mapping identity or no retained identity."""

    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if len(normalized) > 256 or not _QUALIFIED_SOURCE_MAPPING_IDENTITY.fullmatch(normalized):
        return None
    return normalized


def _initial_candidate_lifecycle_provenance(
    claim: CrossGraphLinkClaim, input_record: ProvenanceRecord
) -> tuple[Evidence, tuple[ProvenanceRecord, ...]]:
    """Return the deterministic, claim-scoped provenance of candidate initialization."""

    # A lifecycle is claim-scoped while a mapping observation is not.  Retain
    # each actual mapping provenance as an input rather than inventing a
    # claim-scoped external observation.  When several mappings support the
    # same claim, merge unions their derived lifecycle evidence associations
    # deterministically, preserving every mapping's external provenance chain.
    input_provenance_ids = (input_record.id,)
    input_representation = json.dumps(
        {
            "claim_id": claim.id,
            "input_provenance_ids": input_provenance_ids,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    record = ProvenanceRecord(
        ProvenanceKind.DERIVED, input_record.observed_at, "sha256",
        hashlib.sha256(input_representation.encode()).hexdigest(), STRATEGY_ID, "1", None,
        "cross-graph-candidate-initialization", input_provenance_ids,
    )
    evidence_id = stable_id("evidence", STRATEGY_ID, "candidate-initialization", claim.id)
    return Evidence(
        evidence_id,
        STRATEGY_ID,
        f"cross-graph-link:{claim.id}:candidate-initialization",
        {"claim_id": claim.id, "state": CrossGraphLinkLifecycleState.CANDIDATE.value}, (record.id,),
    ), (record,)
