"""Canonical in-memory ontology models for the Engineering KG MVP."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
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
    TRACES_TO = "traces_to"
    VERIFIED_BY = "verified_by"
    TOUCHES = "touches"
    REFERENCES = "references"
    OWNED_BY = "owned_by"
    PROVIDES = "provides"
    # ASSERTS is support for OpenSpec derivation, never a semantic catalog edge.
    ASSERTS = "asserts"


class ProvenanceKind(StrEnum):
    EXTERNAL = "external"
    DERIVED = "derived"


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


class CrossGraphLinkLifecycleState(StrEnum):
    CANDIDATE = "candidate"
    TRUSTED = "trusted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


CROSS_GRAPH_LINK_LIFECYCLE_STATES = frozenset(
    state.value for state in CrossGraphLinkLifecycleState
)


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


_ABSOLUTE_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/])")
_UNSAFE_IDENTITY_RE = re.compile(
    r"(?:\b(?:body|content|payload|credential(?:s)?|password(?:s)?|secret(?:s)?|token(?:s)?|authorization|bearer)\b|"
    r"(?:api|access)[_-]?key|(?:https?|ftp|file|mailto|data|javascript|ssh|git):)",
    re.IGNORECASE,
)
_UNSAFE_NAVIGATION_KEY_RE = re.compile(
    r"(?:body|content|payload|credential|password|secret|token|url)", re.IGNORECASE
)
_NAVIGATION_DETAIL_SCHEMA = {
    "association_id": str,
    "heading_name": str,
    "line_end": int,
    "line_start": int,
    "pull_request_id": str,
    "section": str,
    "source_mapping_id": str,
}
_SOURCE_ARTIFACT_EVIDENCE_METADATA_SCHEMA = {
    "association_id": str,
    "merged_revision": str,
    "pull_request_id": str,
    "related": tuple,
    "repository": str,
    "specification_id": str,
    "source_mapping_id": str,
}
_MAX_NAVIGATION_TEXT_LENGTH = 512
_MAX_NAVIGATION_LINE_NUMBER = 10_000_000


def _identity_text(value: object, field_name: str) -> str:
    """Validate one payload-safe source-artifact identity component."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"invalid-source-artifact-identity: {field_name} must be non-empty")
    if value != value.strip() or "\n" in value or "\r" in value or len(value) > 512:
        raise ValueError(f"invalid-source-artifact-identity: {field_name} is malformed")
    if _UNSAFE_IDENTITY_RE.search(value):
        raise ValueError(f"invalid-source-artifact-identity: {field_name} contains unsafe content")
    if _ABSOLUTE_PATH_RE.match(value):
        raise ValueError(
            f"invalid-source-artifact-identity: {field_name} must not be an absolute path"
        )
    return value


@dataclass(frozen=True)
class SourceArtifactIdentity:
    """Immutable, source-agnostic identity for one authoritative artifact."""

    source_type: str
    source_identity: str
    artifact_type: str
    revision_or_version: str
    stable_locator: str

    def __post_init__(self) -> None:
        for field_name in (
            "source_type", "source_identity", "artifact_type", "revision_or_version", "stable_locator"
        ):
            _identity_text(getattr(self, field_name), field_name)
        if (
            _ABSOLUTE_PATH_RE.match(self.stable_locator)
            or "\\" in self.stable_locator
            or ".." in self.stable_locator.split("/")
        ):
            raise ValueError("invalid-source-artifact-identity: stable_locator must be repository-relative")
        if any(char.isspace() for char in self.source_identity):
            raise ValueError("invalid-source-artifact-identity: source_identity must not be a display name")

    @property
    def id(self) -> str:
        # JSON preserves field boundaries even when a component contains a delimiter.
        raw = json.dumps(
            [self.source_type, self.source_identity, self.artifact_type,
             self.revision_or_version, self.stable_locator],
            ensure_ascii=False, separators=(",", ":"),
        )
        return f"source-artifact:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"

    def as_dict(self) -> dict[str, str]:
        return {
            "artifact_type": self.artifact_type,
            "id": self.id,
            "revision_or_version": self.revision_or_version,
            "source_identity": self.source_identity,
            "source_type": self.source_type,
            "stable_locator": self.stable_locator,
        }


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PROVENANCE_ID_RE = re.compile(r"^provenance:[0-9a-f]{16}$")


@dataclass(frozen=True)
class ProvenanceRecord:
    """Immutable and payload-free provenance for an external or derived fact."""

    kind: ProvenanceKind | str
    observed_at: str
    content_hash_algorithm: str
    content_hash: str
    extractor_id: str
    extractor_version: str
    source_artifact_identity: SourceArtifactIdentity | None = None
    derivation_rule_id: str | None = None
    input_provenance_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", ProvenanceKind(self.kind))
        _validate_provenance_input_ids(self.input_provenance_ids)
        object.__setattr__(self, "input_provenance_ids", tuple(sorted(set(self.input_provenance_ids))))
        _validate_provenance_record(self)

    @property
    def id(self) -> str:
        raw = json.dumps([
            self.kind.value, self.source_artifact_identity.id if self.source_artifact_identity else "",
            self.source_artifact_identity.revision_or_version if self.source_artifact_identity else "",
            self.observed_at, self.content_hash_algorithm, self.content_hash,
            self.extractor_id, self.extractor_version, self.derivation_rule_id or "", *self.input_provenance_ids,
        ], ensure_ascii=False, separators=(",", ":"))
        return f"provenance:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "content_hash": self.content_hash, "content_hash_algorithm": self.content_hash_algorithm,
            "extractor_id": self.extractor_id, "extractor_version": self.extractor_version,
            "id": self.id, "input_provenance_ids": list(self.input_provenance_ids),
            "kind": self.kind.value, "observed_at": self.observed_at,
        }
        if self.source_artifact_identity is not None:
            result["source_artifact_identity"] = self.source_artifact_identity.as_dict()
        if self.derivation_rule_id is not None:
            result["derivation_rule_id"] = self.derivation_rule_id
        return result


def _validate_provenance_record(record: ProvenanceRecord) -> None:
    for name in ("observed_at", "content_hash_algorithm", "content_hash"):
        value = getattr(record, name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"invalid-provenance: {name} must be a non-empty string")
        if value != value.strip() or _UNSAFE_IDENTITY_RE.search(value):
            raise ValueError(f"invalid-provenance: {name} contains unsafe content")
    _validate_provenance_identifier(record.extractor_id, "extractor_id")
    _validate_provenance_identifier(record.extractor_version, "extractor_version")
    try:
        instant = datetime.fromisoformat(record.observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid-provenance: observed_at must be an offset-aware ISO-8601 instant") from exc
    if instant.tzinfo is None:
        raise ValueError("invalid-provenance: observed_at must be an offset-aware ISO-8601 instant")
    if record.content_hash_algorithm != "sha256" or not _SHA256_RE.fullmatch(record.content_hash):
        raise ValueError("invalid-provenance: content_hash must be a lowercase sha256 digest")
    if record.kind is ProvenanceKind.EXTERNAL:
        if record.source_artifact_identity is None:
            raise ValueError("invalid-provenance: external source_artifact_identity is required")
        if record.derivation_rule_id is not None or record.input_provenance_ids:
            raise ValueError("invalid-provenance: external provenance cannot contain derivation fields")
    else:
        if record.source_artifact_identity is not None:
            raise ValueError("invalid-provenance: derived provenance cannot contain source_artifact_identity")
        if (
            not isinstance(record.derivation_rule_id, str)
            or not record.derivation_rule_id.strip()
            or not record.input_provenance_ids
        ):
            raise ValueError("invalid-provenance: derived rule and input_provenance_ids are required")
        _validate_provenance_identifier(record.derivation_rule_id, "derivation_rule_id")


def _validate_provenance_identifier(value: object, field_name: str) -> None:
    """Reject source payloads from identifier-valued provenance fields."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"invalid-provenance: {field_name} must be a non-empty string")
    if (
        value != value.strip()
        or any(char.isspace() for char in value)
        or len(value) > 512
        or _UNSAFE_IDENTITY_RE.search(value)
    ):
        raise ValueError(f"invalid-provenance: {field_name} contains unsafe content")


def _validate_provenance_input_ids(value: object) -> None:
    if not isinstance(value, (tuple, list)):
        raise ValueError("invalid-provenance: input_provenance_ids must be references")
    for item in value:
        _validate_provenance_identifier(item, "input_provenance_ids")
        if not _PROVENANCE_ID_RE.fullmatch(item):
            raise ValueError(
                "invalid-provenance: input_provenance_ids must contain stable provenance IDs"
            )


@dataclass(frozen=True)
class NormalizedSourceArtifact:
    """Provider-neutral adapter output admitted before graph construction."""

    identity: SourceArtifactIdentity
    navigation_detail: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_navigation_detail(self.navigation_detail)

    def as_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.as_dict(),
            "navigation_detail": _serialize_value(self.navigation_detail),
        }


@dataclass(frozen=True)
class SourceArtifactLocator:
    """Payload-safe evidence locator for a normalized authoritative artifact."""

    source_artifact_identity: SourceArtifactIdentity
    navigation_detail: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.source_artifact_identity, SourceArtifactIdentity):
            raise ValueError("source_artifact_identity must be a SourceArtifactIdentity")
        _validate_navigation_detail(self.navigation_detail)

    def as_dict(self) -> dict[str, Any]:
        return {
            "navigation_detail": _serialize_value(self.navigation_detail),
            "source_artifact_identity": self.source_artifact_identity.as_dict(),
        }


def _validate_navigation_detail(value: object, path: str = "navigation_detail") -> None:
    """Validate the finite payload-safe schema retained for source navigation."""

    _validate_payload_safe_metadata(value, path, _NAVIGATION_DETAIL_SCHEMA)


def _validate_payload_safe_metadata(
    value: object, path: str, schema: dict[str, type],
) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"invalid-source-artifact-identity: {path} must be a mapping")
    for key, nested in value.items():
        field_path = f"{path}.{key}"
        expected_type = schema.get(key) if isinstance(key, str) else None
        if expected_type is None or _UNSAFE_NAVIGATION_KEY_RE.search(key):
            raise ValueError(f"invalid-source-artifact-identity: {field_path} is not allowed")
        if expected_type is int:
            if (
                isinstance(nested, bool) or not isinstance(nested, int)
                or not 1 <= nested <= _MAX_NAVIGATION_LINE_NUMBER
            ):
                raise ValueError(f"invalid-source-artifact-identity: {field_path} must be a positive integer")
        elif expected_type is tuple:
            # Tuples serialize as lists at the persistence boundary.
            if not isinstance(nested, (tuple, list)) or len(nested) > 32:
                raise ValueError(f"invalid-source-artifact-identity: {field_path} must be bounded references")
            for index, item in enumerate(nested):
                item_path = f"{field_path}[{index}]"
                if (
                    not isinstance(item, str) or not item or len(item) > _MAX_NAVIGATION_TEXT_LENGTH
                    or item != item.strip() or "\n" in item or "\r" in item
                    or _UNSAFE_IDENTITY_RE.search(item)
                ):
                    raise ValueError(f"invalid-source-artifact-identity: {item_path} contains unsafe content")
        elif not isinstance(nested, str) or not nested or len(nested) > _MAX_NAVIGATION_TEXT_LENGTH:
            raise ValueError(f"invalid-source-artifact-identity: {field_path} must be bounded text")
        elif nested != nested.strip() or "\n" in nested or "\r" in nested or _UNSAFE_IDENTITY_RE.search(nested):
            raise ValueError(f"invalid-source-artifact-identity: {field_path} contains unsafe content")


def _validate_source_artifact_evidence_metadata(value: object) -> None:
    """Allow only bounded reference metadata alongside source-artifact evidence."""

    _validate_payload_safe_metadata(
        value, "evidence.properties", _SOURCE_ARTIFACT_EVIDENCE_METADATA_SCHEMA,
    )


def _validate_code_locator(locator: CodeLocator) -> None:
    if not isinstance(locator, CodeLocator):
        raise ValueError("target must be a CodeLocator")
    for field_name in ("repository", "revision", "file", "symbol"):
        _required_text(getattr(locator, field_name), f"target.{field_name}")


def cross_graph_link_claim_id(subject_id: str, relation_kind: str, target: CodeLocator) -> str:
    """Return the stable identity of a proposed EKG-to-code relationship."""

    _required_text(subject_id, "subject_id")
    _required_text(relation_kind, "relation_kind")
    _validate_code_locator(target)
    # CodeLocator fields are exact code-side identity values.  Unlike generic
    # graph identity parts, they must not be case-folded or whitespace-normalized.
    identity = json.dumps(
        [
            _normalize_identity_part("cross-graph-link"),
            _normalize_identity_part(subject_id),
            _normalize_identity_part(relation_kind),
            target.repository,
            target.revision,
            target.file,
            target.symbol,
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"cross-graph-link:{digest}"


def cross_graph_link_evidence_id(
    claim_id: str, strategy_id: str, observation_id: str, provenance_evidence_id: str
) -> str:
    """Return the stable identity of one attributable link observation."""

    return stable_id(
        "cross-graph-link-evidence",
        _required_text(claim_id, "claim_id"),
        _required_text(strategy_id, "strategy_id"),
        _required_text(observation_id, "observation_id"),
        _required_text(provenance_evidence_id, "provenance_evidence_id"),
    )


def cross_graph_link_lifecycle_id(claim_id: str, revision: int) -> str:
    """Return the stable identity of an append-only lifecycle revision."""

    _required_text(claim_id, "claim_id")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision <= 0:
        raise ValueError("revision must be a positive integer")
    return stable_id("cross-graph-link-lifecycle", claim_id, revision)


@dataclass(frozen=True)
class CrossGraphLinkClaim:
    subject_id: str
    relation_kind: str
    target: CodeLocator

    def __post_init__(self) -> None:
        cross_graph_link_claim_id(self.subject_id, self.relation_kind, self.target)
        from engineering_kg.relationship_vocabulary import CATALOG_BY_KIND, complete_code_locator
        if self.relation_kind not in CATALOG_BY_KIND:
            raise ValueError("relationship-vocabulary-kind")
        if not CATALOG_BY_KIND[self.relation_kind].permits_code_locator or not complete_code_locator(self.target):
            raise ValueError("relationship-code-locator-contract")

    @property
    def id(self) -> str:
        return cross_graph_link_claim_id(self.subject_id, self.relation_kind, self.target)

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "relation_kind": self.relation_kind, "subject_id": self.subject_id, "target": self.target.as_dict()}


@dataclass(frozen=True)
class CrossGraphLinkEvidence:
    claim_id: str
    strategy_id: str
    observation_id: str
    provenance_evidence_id: str

    def __post_init__(self) -> None:
        cross_graph_link_evidence_id(self.claim_id, self.strategy_id, self.observation_id, self.provenance_evidence_id)

    @property
    def id(self) -> str:
        return cross_graph_link_evidence_id(self.claim_id, self.strategy_id, self.observation_id, self.provenance_evidence_id)

    def as_dict(self) -> dict[str, str]:
        return {"claim_id": self.claim_id, "id": self.id, "observation_id": self.observation_id, "provenance_evidence_id": self.provenance_evidence_id, "strategy_id": self.strategy_id}


@dataclass(frozen=True)
class CrossGraphLinkLifecycle:
    claim_id: str
    revision: int
    state: CrossGraphLinkLifecycleState | str
    provenance_evidence_id: str

    def __post_init__(self) -> None:
        cross_graph_link_lifecycle_id(self.claim_id, self.revision)
        if _lifecycle_state_value(self.state) not in CROSS_GRAPH_LINK_LIFECYCLE_STATES:
            raise ValueError(f"Unsupported cross-graph lifecycle state: {self.state}")
        _required_text(self.provenance_evidence_id, "provenance_evidence_id")

    @property
    def id(self) -> str:
        return cross_graph_link_lifecycle_id(self.claim_id, self.revision)

    def as_dict(self) -> dict[str, Any]:
        return {"claim_id": self.claim_id, "id": self.id, "provenance_evidence_id": self.provenance_evidence_id, "revision": self.revision, "state": _lifecycle_state_value(self.state)}


@dataclass(frozen=True)
class TrustedCrossGraphLink:
    claim_id: str
    subject_id: str
    relation_kind: str
    target: CodeLocator
    supporting_evidence_ids: tuple[str, ...]
    supporting_provenance_evidence_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"claim_id": self.claim_id, "relation_kind": self.relation_kind, "subject_id": self.subject_id, "supporting_evidence_ids": list(self.supporting_evidence_ids), "supporting_provenance_evidence_ids": list(self.supporting_provenance_evidence_ids), "target": self.target.as_dict()}


def _lifecycle_state_value(state: CrossGraphLinkLifecycleState | str) -> str:
    return state.value if isinstance(state, CrossGraphLinkLifecycleState) else state


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
    source_artifact_identity: SourceArtifactIdentity | None = None

    def __post_init__(self) -> None:
        if self.source_artifact_identity is not None:
            if self.source_artifact_identity.artifact_type != self.artifact_type:
                raise ValueError(
                    "invalid-source-artifact-identity: OpenSpec locator artifact_type "
                    "does not match source-artifact identity"
                )
            if self.source_artifact_identity.stable_locator != self.relative_file_path:
                raise ValueError(
                    "invalid-source-artifact-identity: OpenSpec locator relative_file_path "
                    "does not match source-artifact identity stable_locator"
                )
            _validate_navigation_detail({
                **({"heading_name": self.heading_name} if self.heading_name else {}),
                **({"line_start": self.line_start} if self.line_start is not None else {}),
                **({"line_end": self.line_end} if self.line_end is not None else {}),
            })

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
        if self.source_artifact_identity is not None:
            data["source_artifact_identity"] = self.source_artifact_identity.as_dict()
        return data


@dataclass(frozen=True)
class Evidence:
    id: str
    source: str
    locator: str | CodeLocator | ConfluencePageRef | OpenSpecLocator | SourceArtifactLocator
    properties: dict[str, Any] = field(default_factory=dict)
    provenance_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.locator, SourceArtifactLocator):
            _validate_source_artifact_evidence_metadata(self.properties)
        elif isinstance(self.locator, OpenSpecLocator) and self.locator.source_artifact_identity:
            _validate_source_artifact_evidence_metadata(self.properties)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "locator": _serialize_value(self.locator),
            "properties": _serialize_value(self.properties),
            "provenance_ids": list(sorted(self.provenance_ids)),
            "source": self.source,
        }


# These records describe local pipeline output or test fixtures rather than an
# authoritative external artifact. Every other evidence source is treated as
# authoritative and must carry the shared identity at graph boundaries.
INTERNAL_OR_GENERATED_EVIDENCE_SOURCES = frozenset(
    {"fixture", "openlore", "pr-code-candidate-extraction", "repo-index", "review"}
)


def evidence_requires_source_artifact_identity(evidence: Evidence) -> bool:
    """Return whether evidence represents an authoritative external artifact."""

    return evidence.source not in INTERNAL_OR_GENERATED_EVIDENCE_SOURCES


def source_artifact_identity_error(evidence: Evidence) -> str | None:
    """Return the deterministic identity-boundary failure for evidence, if any."""

    locator = evidence.locator
    if isinstance(locator, SourceArtifactLocator):
        expected_id = stable_id("evidence", locator.source_artifact_identity.id)
    elif isinstance(locator, OpenSpecLocator) and locator.source_artifact_identity is not None:
        # OpenSpecLocator validates that the embedded identity agrees with its
        # artifact type and repository-relative navigation path.
        expected_id = stable_id(
            "evidence", locator.source_artifact_identity.id, locator.openspec_identity
        )
    else:
        if evidence_requires_source_artifact_identity(evidence):
            return "authoritative external evidence lacks a complete explicit source-artifact identity"
        return None
    if evidence.id != expected_id:
        return "evidence ID does not match its derived source-artifact identity"
    return None


def provenance_association_error(
    evidence: Evidence,
    provenance_by_id: dict[str, ProvenanceRecord],
) -> str | None:
    """Return the semantic provenance/evidence association failure, if any."""

    if not evidence_requires_source_artifact_identity(evidence):
        return None
    locator = evidence.locator
    identity = (
        locator.source_artifact_identity
        if isinstance(locator, SourceArtifactLocator)
        else locator.source_artifact_identity
        if isinstance(locator, OpenSpecLocator)
        else None
    )
    if identity is None:
        return None
    for provenance_id in sorted(evidence.provenance_ids):
        record = provenance_by_id.get(provenance_id)
        if record is None:
            continue
        if record.kind is ProvenanceKind.DERIVED:
            return (
                "external evidence cannot reference derived provenance: "
                f"{evidence.id}: {record.id}"
            )
        if record.source_artifact_identity != identity:
            return (
                "external evidence provenance source-artifact identity does not match "
                f"evidence: {evidence.id}: {record.id}"
            )
    return None


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
    cross_graph_link_claims: tuple[CrossGraphLinkClaim, ...] = ()
    cross_graph_link_evidence: tuple[CrossGraphLinkEvidence, ...] = ()
    cross_graph_link_lifecycle: tuple[CrossGraphLinkLifecycle, ...] = ()
    provenance: tuple[ProvenanceRecord, ...] = ()
    # Legacy persistence decoding explicitly opts in before guarded migration.
    allow_legacy_evidence: bool = field(default=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.allow_legacy_evidence:
            for item in self.evidence:
                if error := source_artifact_identity_error(item):
                    raise ValueError(f"invalid-source-artifact-identity: {error}: {item.id}")
                if evidence_requires_source_artifact_identity(item) and not item.provenance_ids:
                    raise ValueError(f"invalid-provenance: external evidence lacks complete provenance: {item.id}")
            provenance_ids = {item.id for item in self.provenance}
            for item in self.provenance:
                if item.kind is ProvenanceKind.DERIVED:
                    missing = next(
                        (
                            provenance_id
                            for provenance_id in item.input_provenance_ids
                            if provenance_id not in provenance_ids
                        ),
                        None,
                    )
                    if missing is not None:
                        raise ValueError(
                            "invalid-provenance: derived provenance references absent input "
                            f"provenance: {item.id}: {missing}"
                        )
            for item in self.evidence:
                if any(provenance_id not in provenance_ids for provenance_id in item.provenance_ids):
                    missing = next(provenance_id for provenance_id in item.provenance_ids if provenance_id not in provenance_ids)
                    raise ValueError(f"invalid-provenance: evidence references absent provenance: {item.id}: {missing}")
                if error := provenance_association_error(
                    item, {record.id: record for record in self.provenance}
                ):
                    raise ValueError(f"invalid-provenance: {error}")
        object.__setattr__(self, "cross_graph_link_claims", tuple(sorted(self.cross_graph_link_claims, key=lambda item: item.id)))
        object.__setattr__(self, "provenance", tuple(sorted(self.provenance, key=lambda item: item.id)))
        object.__setattr__(self, "cross_graph_link_evidence", tuple(sorted(self.cross_graph_link_evidence, key=lambda item: item.id)))
        object.__setattr__(self, "cross_graph_link_lifecycle", tuple(sorted(self.cross_graph_link_lifecycle, key=lambda item: (item.claim_id, item.revision))))

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)

    @property
    def provenance_count(self) -> int:
        return len(self.provenance)

    @property
    def cross_graph_link_claim_count(self) -> int:
        return len(self.cross_graph_link_claims)

    @property
    def cross_graph_link_evidence_count(self) -> int:
        return len(self.cross_graph_link_evidence)

    @property
    def cross_graph_link_lifecycle_count(self) -> int:
        return len(self.cross_graph_link_lifecycle)

    @property
    def trusted_cross_graph_links(self) -> tuple[TrustedCrossGraphLink, ...]:
        lifecycles: dict[str, CrossGraphLinkLifecycle] = {}
        invalid_claims: set[str] = set()
        for entry in self.cross_graph_link_lifecycle:
            previous = lifecycles.get(entry.claim_id)
            if previous and previous.revision == entry.revision and previous.as_dict() != entry.as_dict():
                invalid_claims.add(entry.claim_id)
            elif previous is None or entry.revision > previous.revision:
                lifecycles[entry.claim_id] = entry
        evidence_by_claim: dict[str, list[CrossGraphLinkEvidence]] = {}
        for observation in self.cross_graph_link_evidence:
            evidence_by_claim.setdefault(observation.claim_id, []).append(observation)
        evidence_by_id = {item.id: item for item in self.evidence}
        provenance_by_id = {item.id: item for item in self.provenance}
        return tuple(
            TrustedCrossGraphLink(claim.id, claim.subject_id, claim.relation_kind, claim.target,
                tuple(item.id for item in evidence_by_claim.get(claim.id, ())),
                tuple(sorted({
                    *(item.provenance_evidence_id for item in evidence_by_claim.get(claim.id, ())),
                    lifecycles[claim.id].provenance_evidence_id,
                })))
            for claim in self.cross_graph_link_claims
            if claim.id not in invalid_claims
            and lifecycles.get(claim.id) is not None
            and _lifecycle_state_value(lifecycles[claim.id].state) == CrossGraphLinkLifecycleState.TRUSTED.value
            and _trusted_claim_is_catalog_valid(claim, {node.id: node for node in self.nodes})
            and _trusted_claim_has_complete_provenance(
                claim.id, lifecycles[claim.id], evidence_by_claim, evidence_by_id, provenance_by_id,
            )
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "edge_count": self.edge_count,
            "edges": [_serialize_value(edge) for edge in self.edges],
            "evidence": [_serialize_value(item) for item in self.evidence],
            "evidence_count": self.evidence_count,
            "provenance": [_serialize_value(item) for item in self.provenance],
            "provenance_count": self.provenance_count,
            "cross_graph_link_claim_count": self.cross_graph_link_claim_count,
            "cross_graph_link_claims": [_serialize_value(item) for item in self.cross_graph_link_claims],
            "cross_graph_link_evidence_count": self.cross_graph_link_evidence_count,
            "cross_graph_link_evidence": [_serialize_value(item) for item in self.cross_graph_link_evidence],
            "cross_graph_link_lifecycle_count": self.cross_graph_link_lifecycle_count,
            "cross_graph_link_lifecycle": [_serialize_value(item) for item in self.cross_graph_link_lifecycle],
            "node_count": self.node_count,
            "nodes": [_serialize_value(node) for node in self.nodes],
        }

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True)

    def merged_with(self, other: "GraphSnapshot") -> "GraphSnapshot":
        nodes = _merge_records(self.nodes, other.nodes)
        edges = _merge_records(self.edges, other.edges)
        evidence = _merge_records(self.evidence, other.evidence)
        provenance = _merge_records(self.provenance, other.provenance)
        for item in evidence:
            if error := source_artifact_identity_error(item):
                raise ValueError(f"invalid-source-artifact-identity: {error}: {item.id}")
        claims = _merge_records(self.cross_graph_link_claims, other.cross_graph_link_claims)
        observations = _merge_records(self.cross_graph_link_evidence, other.cross_graph_link_evidence)
        lifecycle = _merge_records(self.cross_graph_link_lifecycle, other.cross_graph_link_lifecycle)
        _validate_cross_graph_claim_references(
            nodes, evidence, provenance, claims, observations, lifecycle
        )
        return GraphSnapshot(
            nodes, edges, evidence, claims, observations, lifecycle, provenance
        )


def _validate_cross_graph_claim_references(
    nodes: tuple[Node, ...],
    evidence: tuple[Evidence, ...],
    provenance: tuple[ProvenanceRecord, ...],
    claims: tuple[CrossGraphLinkClaim, ...],
    observations: tuple[CrossGraphLinkEvidence, ...],
    lifecycle: tuple[CrossGraphLinkLifecycle, ...],
) -> None:
    """Reject merged cross-graph records with dangling claim or provenance references."""

    node_ids = {node.id for node in nodes}
    claim_ids = {claim.id for claim in claims}
    evidence_ids = {item.id for item in evidence}
    provenance_ids = {item.id for item in provenance}
    for item in evidence:
        if any(provenance_id not in provenance_ids for provenance_id in item.provenance_ids):
            missing = next(provenance_id for provenance_id in item.provenance_ids if provenance_id not in provenance_ids)
            raise ValueError(f"Evidence references absent provenance: {item.id}: {missing}")
    for claim in sorted(claims, key=lambda item: item.id):
        if claim.subject_id not in node_ids:
            raise ValueError(
                "Cross-graph claim subject_id does not reference an existing node: "
                f"{claim.subject_id}"
            )
    evidence_by_id = {item.id: item for item in evidence}
    provenance_by_id = {item.id: item for item in provenance}
    for observation in sorted(observations, key=lambda item: item.id):
        if observation.claim_id not in claim_ids:
            raise ValueError(
                "Cross-graph evidence references an absent claim: "
                f"{observation.claim_id}"
            )
        if observation.provenance_evidence_id not in evidence_ids:
            raise ValueError(
                "Cross-graph evidence references absent provenance evidence: "
                f"{observation.provenance_evidence_id}"
            )
        elif not _has_complete_provenance(
            evidence_by_id[observation.provenance_evidence_id], provenance_by_id
        ):
            raise ValueError(f"Cross-graph evidence requires complete provenance: {observation.id}")
    for entry in sorted(lifecycle, key=lambda item: item.id):
        if entry.claim_id not in claim_ids:
            raise ValueError(
                "Cross-graph lifecycle references an absent claim: "
                f"{entry.claim_id}"
            )
        if entry.provenance_evidence_id not in evidence_ids:
            raise ValueError(
                "Cross-graph lifecycle references absent provenance evidence: "
                f"{entry.provenance_evidence_id}"
            )
        elif not _has_complete_provenance(
            evidence_by_id[entry.provenance_evidence_id], provenance_by_id
        ):
            raise ValueError(f"Cross-graph lifecycle requires complete provenance: {entry.id}")


def has_complete_resolvable_provenance(
    evidence: Evidence, provenance_by_id: dict[str, ProvenanceRecord],
) -> bool:
    """Return whether every provenance record resolves through a valid acyclic chain."""

    if not evidence.provenance_ids:
        return False
    return all(
        _has_valid_provenance_record(provenance_id, provenance_by_id, set())
        for provenance_id in evidence.provenance_ids
    )


def _has_valid_provenance_record(
    provenance_id: str,
    provenance_by_id: dict[str, ProvenanceRecord],
    resolving_ids: set[str],
) -> bool:
    """Validate a provenance record, including every derived input recursively."""

    if provenance_id in resolving_ids:
        return False
    record = provenance_by_id.get(provenance_id)
    if record is None:
        return False
    try:
        expected = ProvenanceRecord(
            record.kind, record.observed_at, record.content_hash_algorithm,
            record.content_hash, record.extractor_id, record.extractor_version,
            record.source_artifact_identity, record.derivation_rule_id,
            record.input_provenance_ids,
        )
    except (AttributeError, ValueError):
        return False
    if record.id != expected.id:
        return False
    if record.kind is not ProvenanceKind.DERIVED:
        return True
    return all(
        _has_valid_provenance_record(input_id, provenance_by_id, resolving_ids | {provenance_id})
        for input_id in record.input_provenance_ids
    )


# Compatibility for existing internal validation imports.
def _has_complete_provenance(
    evidence: Evidence, provenance_by_id: dict[str, ProvenanceRecord],
) -> bool:
    return has_complete_resolvable_provenance(evidence, provenance_by_id)


def _trusted_claim_is_catalog_valid(
    claim: CrossGraphLinkClaim, nodes_by_id: dict[str, Node],
) -> bool:
    from engineering_kg.relationship_vocabulary import relationship_error
    return relationship_error(claim.relation_kind, nodes_by_id.get(claim.subject_id), claim.target) is None


def _trusted_claim_has_complete_provenance(
    claim_id: str,
    lifecycle: CrossGraphLinkLifecycle,
    evidence_by_claim: dict[str, list[CrossGraphLinkEvidence]],
    evidence_by_id: dict[str, Evidence],
    provenance_by_id: dict[str, ProvenanceRecord],
) -> bool:
    """Require attributed observation and resolvable provenance for trusted projection."""

    lifecycle_evidence = evidence_by_id.get(lifecycle.provenance_evidence_id)
    if lifecycle_evidence is None or not _has_complete_provenance(
        lifecycle_evidence, provenance_by_id
    ):
        return False
    observations = evidence_by_claim.get(claim_id, ())
    return bool(observations) and all(
        (observation_evidence := evidence_by_id.get(observation.provenance_evidence_id))
        is not None
        and _has_complete_provenance(observation_evidence, provenance_by_id)
        for observation in observations
    )


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
    if isinstance(left, Evidence):
        left_data = left.as_dict()
        right_data = right.as_dict()
        left_data.pop("provenance_ids")
        right_data.pop("provenance_ids")
        if left_data != right_data:
            raise ValueError(f"Conflicting graph record values for ID: {left.id}")
        return dataclass_replace(
            left,
            provenance_ids=tuple(sorted(set(left.provenance_ids) | set(right.provenance_ids))),
        )
    if left.as_dict() != right.as_dict():
        raise ValueError(f"Conflicting graph record values for ID: {left.id}")
    return left


def dataclass_replace(value: Any, **changes: Any) -> Any:
    """Avoid exposing dataclasses.replace at the graph model boundary."""

    from dataclasses import replace

    return replace(value, **changes)
