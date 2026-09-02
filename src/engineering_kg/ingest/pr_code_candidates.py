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

from engineering_kg.ontology import (
    CodeLocator,
    CrossGraphLinkClaim,
    CrossGraphLinkEvidence,
    CrossGraphLinkLifecycle,
    CrossGraphLinkLifecycleState,
    Evidence,
    GraphSnapshot,
    SourceArtifactIdentity,
    SourceArtifactLocator,
    ProvenanceKind,
    ProvenanceRecord,
    stable_id,
)
from engineering_kg.relationship_vocabulary import RelationshipKind


STRATEGY_ID = "pr-code-candidate-extraction"
RELATION_KIND = RelationshipKind.TOUCHES.value

# A PR mapping supplies a code-side identity, not display text or source.  The
# extractor accepts a portable, fully-qualified identifier form so it can be
# validated locally without attempting source analysis or symbol resolution.
_QUALIFIED_SYMBOL_IDENTITY = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$"
)

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
_SAFE_IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_SAFE_REPOSITORY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")
_SAFE_RELATIVE_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,1023}$")
# Safe identities may use a colon as a namespace separator.  The URI scheme
# and its value are checked separately so opaque IDs such as
# ``urn:example.org/link-42`` are not confused with navigable URLs.
_URI_SCHEME = re.compile(r"^(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*):(?P<value>.*)$")
_HIERARCHICAL_URL_SCHEMES = frozenset({"http", "https", "ssh", "git", "s3", "vscode"})


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

    text = _text(value, field_name).strip()
    if _is_url_like_identity(text):
        raise PrCodeCandidateValidationError(f"{field_name} must not be URL-like")
    if not _SAFE_IDENTITY.fullmatch(text):
        raise PrCodeCandidateValidationError(f"{field_name} must be a safe identity")
    return text


def _is_url_like_identity(value: str) -> bool:
    """Reject navigable/hierarchical URLs while retaining opaque stable IDs.

    ``urn:example.org/link-42`` is an opaque identifier even though its
    namespace-specific string contains a slash.  URL schemes whose values are
    navigable locations remain disallowed whether they use an authority
    (``https://host/path``) or the shorthand hierarchical form
    (``https:host/path``).
    """

    if value.startswith("//"):
        return True
    match = _URI_SCHEME.fullmatch(value)
    if match is None:
        return False
    scheme = match.group("scheme").lower()
    remainder = match.group("value")
    # A slash immediately after the scheme delimiter is hierarchical URI
    # syntax even without an authority (for example ``file:/private/secret``
    # or ``custom:/provider.example/pr/42``).  Opaque identifiers such as
    # ``urn:example.org/link-42`` have namespace-specific text instead.
    return remainder.startswith("/") or scheme in _HIERARCHICAL_URL_SCHEMES


def _safe_repository(value: object) -> str:
    repository = _text(value, "change_set.repository").strip()
    if not _SAFE_REPOSITORY.fullmatch(repository):
        raise PrCodeCandidateValidationError("change_set.repository must be a safe identity")
    return repository


def _safe_relative_file(value: object) -> str:
    file = _text(value, "mapping.file").strip()
    if (
        not _SAFE_RELATIVE_FILE.fullmatch(file)
        or file.startswith("/")
        or any(part == ".." for part in file.split("/"))
    ):
        raise PrCodeCandidateValidationError("mapping.file must be a safe relative locator")
    return file


@dataclass(frozen=True)
class EngineeringChangePrAssociation:
    """An explicit, source-adapted association; no inferred links are represented."""

    id: str
    engineering_change_subject_id: str
    pull_request_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _safe_identity(self.id, "association.id"))
        object.__setattr__(
            self,
            "engineering_change_subject_id",
            _safe_identity(
                self.engineering_change_subject_id,
                "association.engineering_change_subject_id",
            ),
        )
        object.__setattr__(
            self, "pull_request_id", _safe_identity(self.pull_request_id, "association.pull_request_id")
        )


@dataclass(frozen=True)
class ChangedSymbolMapping:
    """One Graphify-adapted changed-file/symbol mapping outcome."""

    id: str
    file: str
    outcome: MappingOutcome | str
    symbol: str | None = None

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


@dataclass(frozen=True)
class MergedPrChangeSet:
    """Immutable PR change-set identity and local mapping outcomes."""

    association: EngineeringChangePrAssociation
    pull_request_id: str
    repository: str
    merged_revision: str
    mappings: tuple[ChangedSymbolMapping, ...]
    merged: bool = True
    observed_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.association, EngineeringChangePrAssociation):
            raise PrCodeCandidateValidationError("association must be an EngineeringChangePrAssociation")
        object.__setattr__(
            self, "pull_request_id", _safe_identity(self.pull_request_id, "change_set.pull_request_id")
        )
        object.__setattr__(self, "repository", _safe_repository(self.repository))
        object.__setattr__(
            self, "merged_revision", _safe_identity(self.merged_revision, "change_set.merged_revision")
        )
        if not _immutable_revision(self.merged_revision):
            raise PrCodeCandidateValidationError(
                "change_set.merged_revision must be an immutable revision"
            )
        if self.pull_request_id != self.association.pull_request_id:
            raise PrCodeCandidateValidationError("change_set.pull_request_id must match association.pull_request_id")
        if not isinstance(self.merged, bool) or not self.merged:
            raise PrCodeCandidateValidationError("change_set must be merged")
        if not isinstance(self.mappings, tuple) or not self.mappings:
            raise PrCodeCandidateValidationError("change_set.mappings must be a non-empty tuple")
        if not all(isinstance(item, ChangedSymbolMapping) for item in self.mappings):
            raise PrCodeCandidateValidationError("change_set.mappings must contain ChangedSymbolMapping records")
        _observed_at(self.observed_at)

    @property
    def id(self) -> str:
        return stable_id("pr-change-set", self.association.id, self.pull_request_id, self.repository, self.merged_revision)


def normalize_merged_pr_change_set(value: Mapping[str, Any]) -> MergedPrChangeSet:
    """Adapt a plain local fixture into project-owned records, dropping all payload fields."""

    if not isinstance(value, Mapping):
        raise PrCodeCandidateValidationError("change_set must be a mapping")
    try:
        association_data = value["association"]
        mappings_data = value["mappings"]
    except KeyError as exc:
        raise PrCodeCandidateValidationError(f"change_set.{exc.args[0]} is required") from None
    if not isinstance(association_data, Mapping):
        raise PrCodeCandidateValidationError("change_set.association must be a mapping")
    if not isinstance(mappings_data, (list, tuple)):
        raise PrCodeCandidateValidationError("change_set.mappings must be a list")
    association = EngineeringChangePrAssociation(
        id=association_data.get("id"),
        engineering_change_subject_id=association_data.get("engineering_change_subject_id"),
        pull_request_id=association_data.get("pull_request_id"),
    )
    mappings = tuple(
        ChangedSymbolMapping(
            id=item.get("id") if isinstance(item, Mapping) else None,
            file=item.get("file") if isinstance(item, Mapping) else None,
            outcome=item.get("outcome") if isinstance(item, Mapping) else None,
            symbol=item.get("symbol") if isinstance(item, Mapping) else None,
        )
        for item in mappings_data
    )
    change_set = MergedPrChangeSet(
        association=association,
        pull_request_id=value.get("pull_request_id"),
        repository=value.get("repository"),
        merged_revision=value.get("merged_revision"),
        mappings=mappings,
        merged=value.get("merged", False),
        observed_at=value.get("observed_at", ""),
    )
    return change_set


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

    def as_dict(self) -> dict[str, Any]:
        return {"accepted_change_set_count": self.accepted_change_set_count, "diagnostics": [item.as_dict() for item in self.diagnostics], "emitted_candidate_count": self.emitted_candidate_count, "graph_counts": dict(sorted(self.graph_counts.items())), "skipped_input_count": self.skipped_input_count, "skipped_reason_counts": dict(sorted(self.skipped_reason_counts.items()))}


@dataclass(frozen=True)
class PrCodeCandidateExtractionResult:
    graph: GraphSnapshot
    metadata: PrCodeCandidateExtractionMetadata


def extract_pr_code_candidates(
    change_sets: tuple[MergedPrChangeSet, ...], subject_graph: GraphSnapshot
) -> PrCodeCandidateExtractionResult:
    """Produce observed candidates only; neither edges nor trusted projections are emitted."""

    diagnostics: list[PrCodeCandidateDiagnostic] = []
    evidence: list[Evidence] = []
    claims: list[CrossGraphLinkClaim] = []
    observations: list[CrossGraphLinkEvidence] = []
    lifecycle: list[CrossGraphLinkLifecycle] = []
    provenance_records: list[ProvenanceRecord] = []
    accepted = 0
    subjects = {node.id: node for node in subject_graph.nodes}
    change_sets_by_id = _change_sets_by_id(change_sets)
    conflicting_change_set_ids = {
        change_set_id
        for change_set_id, duplicates in change_sets_by_id.items()
        if len({_change_set_identity(item) for item in duplicates}) > 1
    }
    for change_set_id in sorted(change_sets_by_id):
        duplicates = change_sets_by_id[change_set_id]
        # `MergedPrChangeSet.id` intentionally case-normalizes its identity
        # parts. Select a canonical representative rather than accepting the
        # caller's first spelling of those parts, so equivalent duplicate input
        # cannot make graph output or conflict provenance order-dependent.
        canonical_change_set = min(duplicates, key=_change_set_sort_key)
        if change_set_id in conflicting_change_set_ids:
            # The immutable change-set identity must identify one normalized record.
            # Retain only identity-level, payload-safe conflict provenance; admitting
            # either record would make candidate output depend on input ordering.
            provenance = _change_set_conflict_provenance(canonical_change_set)
            evidence.append(provenance)
            diagnostics.append(
                PrCodeCandidateDiagnostic(
                    "conflicting-change-set-identity",
                    change_set_id,
                    provenance_evidence_id=provenance.id,
                )
            )
            continue
        change_set = canonical_change_set
        if change_set.association.engineering_change_subject_id not in subjects:
            diagnostics.append(PrCodeCandidateDiagnostic("missing-subject", change_set.id))
            continue
        if subjects[change_set.association.engineering_change_subject_id].kind != "jira_story":
            diagnostics.append(
                PrCodeCandidateDiagnostic("ineligible-subject-kind", change_set.id)
            )
            continue
        accepted += 1
        conflicting_mapping_ids = {
            mapping_id
            for mapping_id, identities in _mapping_identities(change_set.mappings).items()
            if len(identities) > 1
        }
        reported_conflicts: set[str] = set()
        for mapping in sorted(change_set.mappings, key=lambda item: item.id):
            if not mapping.id:
                diagnostics.append(
                    PrCodeCandidateDiagnostic("invalid-mapping-identity", change_set.id)
                )
                continue
            provenance, record = _mapping_provenance(change_set, mapping)
            evidence.append(provenance)
            provenance_records.append(record)
            if mapping.id in conflicting_mapping_ids:
                # A source mapping must identify one outcome.  Conflicting adapted
                # records cannot be safely resolved by processing order, so retain
                # their safe provenance but admit no target for that source identity.
                if mapping.id not in reported_conflicts:
                    diagnostics.append(PrCodeCandidateDiagnostic(
                        "conflicting-mapping-identity", change_set.id, mapping.id, provenance.id
                    ))
                    reported_conflicts.add(mapping.id)
                continue
            if mapping.outcome is not MappingOutcome.RESOLVED:
                reason_code = (
                    "unsupported-source-mapping"
                    if mapping.outcome is MappingOutcome.UNSUPPORTED
                    else f"{mapping.outcome.value}-symbol"
                )
                diagnostics.append(PrCodeCandidateDiagnostic(
                    reason_code, change_set.id, mapping.id, provenance.id
                ))
                continue
            # Constructors protect complete strings; this guard preserves behavior for
            # deliberately malformed records supplied by a future adapter.
            if not mapping.symbol:
                diagnostics.append(PrCodeCandidateDiagnostic(
                    "incomplete-locator", change_set.id, mapping.id, provenance.id
                ))
                continue
            target = CodeLocator(change_set.repository, change_set.merged_revision, mapping.file, mapping.symbol)
            claim = CrossGraphLinkClaim(change_set.association.engineering_change_subject_id, RELATION_KIND, target)
            lifecycle_provenance, lifecycle_records = _initial_candidate_lifecycle_provenance(claim, record)
            evidence.append(lifecycle_provenance)
            provenance_records.extend(lifecycle_records)
            claims.append(claim)
            observations.append(CrossGraphLinkEvidence(claim.id, STRATEGY_ID, mapping.id, provenance.id))
            # Lifecycle revisions are claim-wide.  PR mapping provenance belongs to
            # its observation; a claim-scoped initialization record lets separately
            # extracted observations of the same claim merge without revision-one
            # provenance conflicts.
            lifecycle.append(CrossGraphLinkLifecycle(claim.id, 1, CrossGraphLinkLifecycleState.CANDIDATE, lifecycle_provenance.id))
    graph = GraphSnapshot(
        evidence=tuple({item.id: item for item in evidence}.values()),
        cross_graph_link_claims=tuple({item.id: item for item in claims}.values()),
        cross_graph_link_evidence=tuple({item.id: item for item in observations}.values()),
        cross_graph_link_lifecycle=tuple({item.id: item for item in lifecycle}.values()),
        provenance=tuple({item.id: item for item in provenance_records}.values()),
    )
    # Validate/collapse duplicate records against subjects without leaking those subjects into output.
    subject_graph.merged_with(graph)
    ordered_diagnostics = tuple(sorted(diagnostics, key=lambda item: (item.reason_code, item.change_set_id, item.mapping_id, item.provenance_evidence_id)))
    metadata = PrCodeCandidateExtractionMetadata(accepted, len(graph.cross_graph_link_claims), len(ordered_diagnostics), dict(Counter(item.reason_code for item in ordered_diagnostics)), ordered_diagnostics, {"cross_graph_link_claim_count": graph.cross_graph_link_claim_count, "cross_graph_link_evidence_count": graph.cross_graph_link_evidence_count, "cross_graph_link_lifecycle_count": graph.cross_graph_link_lifecycle_count, "evidence_count": graph.evidence_count})
    return PrCodeCandidateExtractionResult(graph, metadata)


def _immutable_revision(value: str) -> bool:
    """Accept only complete Git object IDs, never abbreviated references."""
    return len(value) in (40, 64) and all(
        character in "0123456789abcdefABCDEF" for character in value
    )


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

    return bool(_QUALIFIED_SYMBOL_IDENTITY.fullmatch(value))


def _normalized_source_mapping_id(value: object) -> str | None:
    """Return a safe, qualified mapping identity or no retained identity."""

    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if len(normalized) > 256 or not _QUALIFIED_SOURCE_MAPPING_IDENTITY.fullmatch(normalized):
        return None
    return normalized


def _mapping_identities(
    mappings: tuple[ChangedSymbolMapping, ...],
) -> dict[str, set[tuple[str, MappingOutcome, str | None]]]:
    """Group normalized mapping identities by their source mapping identifier."""

    identities: dict[str, set[tuple[str, MappingOutcome, str | None]]] = {}
    for mapping in mappings:
        identities.setdefault(mapping.id, set()).add(
            (mapping.file, mapping.outcome, mapping.symbol)
        )
    return identities


def _change_sets_by_id(
    change_sets: tuple[MergedPrChangeSet, ...],
) -> dict[str, tuple[MergedPrChangeSet, ...]]:
    """Group normalized inputs before deduplicating their immutable identities."""

    grouped: dict[str, list[MergedPrChangeSet]] = {}
    for change_set in change_sets:
        grouped.setdefault(change_set.id, []).append(change_set)
    return {change_set_id: tuple(items) for change_set_id, items in grouped.items()}


def _change_set_identity(
    change_set: MergedPrChangeSet,
) -> tuple[
    str,
    str,
    str,
    str,
    str,
    tuple[tuple[str, str, MappingOutcome, str | None], ...],
]:
    """Return normalized record content aligned with ``MergedPrChangeSet.id``."""

    return (
        _normalized_change_set_identity_part(change_set.association.id),
        _normalized_change_set_identity_part(
            change_set.association.engineering_change_subject_id
        ),
        _normalized_change_set_identity_part(change_set.association.pull_request_id),
        _normalized_change_set_identity_part(change_set.repository),
        _normalized_change_set_identity_part(change_set.merged_revision),
        tuple(
            sorted(
                (mapping.id, mapping.file, mapping.outcome, mapping.symbol)
                for mapping in change_set.mappings
            )
        ),
    )


def _change_set_sort_key(
    change_set: MergedPrChangeSet,
) -> tuple[
    tuple[
        str,
        str,
        str,
        str,
        str,
        tuple[tuple[str, str, MappingOutcome, str | None], ...],
    ],
    tuple[str, str, str, str, str, tuple[tuple[str, str, str, str], ...]],
]:
    """Order duplicate inputs canonically, including raw spelling as a tie-breaker."""

    return (
        _change_set_identity(change_set),
        (
            change_set.association.id,
            change_set.association.engineering_change_subject_id,
            change_set.association.pull_request_id,
            change_set.repository,
            change_set.merged_revision,
            tuple(
                sorted(
                    (
                        mapping.id,
                        mapping.file,
                        mapping.outcome.value,
                        mapping.symbol or "",
                    )
                    for mapping in change_set.mappings
                )
            ),
        ),
    )


def _normalized_change_set_identity_part(value: str) -> str:
    """Mirror ``stable_id`` normalization used by ``MergedPrChangeSet.id``."""

    return " ".join(value.strip().lower().split())


def _change_set_conflict_provenance(change_set: MergedPrChangeSet) -> Evidence:
    """Return safe provenance for a conflicting normalized change-set identity."""

    provenance_id = stable_id(
        "evidence", STRATEGY_ID, "change-set-conflict", change_set.id
    )
    return Evidence(
        provenance_id,
        STRATEGY_ID,
        f"pr-change-set:{change_set.id}:conflict",
        {
            "association_id": change_set.association.id,
            "merged_revision": change_set.merged_revision,
            "pull_request_id": change_set.pull_request_id,
            "repository": change_set.repository,
        },
    )


def _mapping_provenance(change_set: MergedPrChangeSet, mapping: ChangedSymbolMapping) -> tuple[Evidence, ProvenanceRecord]:
    """Return payload-safe provenance for one admissible source mapping."""

    artifact_identity = SourceArtifactIdentity(
        source_type="graphify",
        source_identity=change_set.repository,
        artifact_type="pull-request-mapping",
        revision_or_version=change_set.merged_revision,
        stable_locator=f"pr-change-set:{change_set.id}:mapping:{mapping.id}",
    )
    record = ProvenanceRecord(
        ProvenanceKind.EXTERNAL, change_set.observed_at, "sha256",
        hashlib.sha256(json.dumps({"mapping_id": mapping.id, "outcome": mapping.outcome.value, "file": mapping.file, "symbol": mapping.symbol}, sort_keys=True).encode()).hexdigest(),
        STRATEGY_ID, "1", artifact_identity,
    )
    evidence_id = stable_id("evidence", artifact_identity.id)
    return Evidence(
        evidence_id,
        STRATEGY_ID,
        SourceArtifactLocator(
            artifact_identity,
            {
                "association_id": change_set.association.id,
                "pull_request_id": change_set.pull_request_id,
                "source_mapping_id": mapping.id,
            },
        ),
        {
            "association_id": change_set.association.id,
            "merged_revision": change_set.merged_revision,
            "pull_request_id": change_set.pull_request_id,
            "repository": change_set.repository,
            "source_mapping_id": mapping.id,
        }, (record.id,),
    ), record


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
