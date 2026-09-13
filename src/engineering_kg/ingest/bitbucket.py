"""A payload-free, provider-neutral Bitbucket pull-request adapter.

The concrete Bitbucket MCP/API client is deliberately not part of this module.
It implements :class:`BitbucketSourcePort` and translates its response into the
small source-private records below.  Only the records produced by
``BitbucketSourceAdapter`` may cross into the canonical graph model.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
import hashlib
import json
from typing import Any, Mapping, Protocol, Sequence

from engineering_kg.compact_identity import (
    is_immutable_revision,
    safe_identity,
    safe_relative_file,
    safe_repository,
)
from engineering_kg.ingest.pr_code_candidates import (
    ChangedSymbolMapping,
    MappingOutcome,
    NormalizedPullRequestEvidence,
)
from engineering_kg.openlore_bridge import (
    ChangedFileReference,
    ChangedFileResolutionRequest,
    ImplementationEvidenceContext,
    ResolutionResult,
    ResolutionStatus,
)
from engineering_kg.ontology import (
    Evidence,
    GraphSnapshot,
    NodeKind,
    ProvenanceRecord,
    PullRequestDeclaredAssociation,
    PullRequestImplementationEvidence,
    PullRequestObservedRepositoryRelation,
    SourceArtifactIdentity,
    SourceArtifactLocator,
    project_pull_request_evidence,
    stable_id,
)
from engineering_kg.ingest.source_artifact import external_provenance, normalize_source_artifact


ADAPTER_ID = "bitbucket-source-adapter"
ADAPTER_VERSION = "1"


class BitbucketValidationError(ValueError):
    """A source-private or public adapter DTO is not safely representable."""


class BitbucketSourceStatus(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"


class BitbucketResultStatus(StrEnum):
    ADMITTED = "admitted"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"
    INVALID_SOURCE = "invalid-source"


# This is intentionally a closed set.  Diagnostics do not carry provider
# messages, exception text, URLs, or snippets.
FROZEN_BITBUCKET_DIAGNOSTIC_REASONS = frozenset(
    {
        "invalid-selection",
        "provider-unavailable",
        "malformed-source-response",
        "unsupported-source-status",
        "missing-pr-identity",
        "conflicting-pr-identity",
        "unknown-repository",
        "repository-context-mismatch",
        "unmerged-pr",
        "missing-base-revision",
        "missing-head-revision",
        "mutable-revision",
        "abbreviated-revision",
        "revision-context-mismatch",
        "missing-source-reference",
        "unsafe-source-reference",
        "missing-observation-time",
        "invalid-observation-time",
        "changed-files-unavailable",
        "malformed-changed-file-source",
        "missing-file-identity",
        "unsafe-file-path",
        "changed-file-context-mismatch",
        "conflicting-changed-file-identity",
        "missing-reference-source",
        "unsupported-reference-kind",
        "missing-reference-target",
        "unknown-reference-target",
        "ineligible-reference-target",
        "malformed-reference",
        "conflicting-reference-identity",
    }
)

_INVALID_CHANGED_FILE_REASONS = frozenset({
    "malformed-changed-file-source",
    "missing-file-identity",
    "unsafe-file-path",
})
_INVALID_REFERENCE_REASONS = frozenset({
    "malformed-reference",
    "missing-reference-source",
    "unsupported-reference-kind",
    "missing-reference-target",
})


def _identity(value: object, field_name: str) -> str:
    try:
        return safe_identity(value, field_name)
    except ValueError as exc:
        raise BitbucketValidationError(str(exc)) from None


def _repository(value: object, field_name: str) -> str:
    try:
        return safe_repository(value, field_name)
    except ValueError as exc:
        raise BitbucketValidationError(str(exc)) from None


def _file(value: object, field_name: str) -> str:
    try:
        return safe_relative_file(value, field_name)
    except ValueError as exc:
        raise BitbucketValidationError(str(exc)) from None


def _revision(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BitbucketValidationError(f"{field_name} is required")
    text = value.strip()
    if not is_immutable_revision(text):
        raise BitbucketValidationError(f"{field_name} must be an immutable revision")
    return text


def _observed_at(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BitbucketValidationError("observed_at is required")
    text = value.strip()
    try:
        instant = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise BitbucketValidationError("observed_at must be an offset-aware ISO-8601 instant") from None
    if instant.tzinfo is None:
        raise BitbucketValidationError("observed_at must be an offset-aware ISO-8601 instant")
    return text


@dataclass(frozen=True)
class BitbucketSourceSelection:
    """The caller-selected PR and its already canonical repository identity."""

    pull_request_id: str
    repository_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "pull_request_id", _identity(self.pull_request_id, "pull_request_id"))
        object.__setattr__(self, "repository_id", _repository(self.repository_id, "repository_id"))

    @property
    def pr_id(self) -> str:
        return self.pull_request_id

    def as_dict(self) -> dict[str, str]:
        return {"pull_request_id": self.pull_request_id, "repository_id": self.repository_id}


# More descriptive aliases are kept for integrations and tests using either
# naming convention.
BitbucketPullRequestSelection = BitbucketSourceSelection


@dataclass(frozen=True)
class BitbucketSourceReference:
    """A compact source-artifact identity, never a navigation URL."""

    source_type: str
    source_identity: str
    stable_locator: str
    revision_or_version: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_type", _identity(self.source_type, "source_reference.source_type"))
        object.__setattr__(self, "source_identity", _identity(self.source_identity, "source_reference.source_identity"))
        object.__setattr__(self, "stable_locator", _file(self.stable_locator, "source_reference.stable_locator"))
        if self.revision_or_version is not None:
            object.__setattr__(self, "revision_or_version", _identity(self.revision_or_version, "source_reference.revision_or_version"))

    def as_dict(self) -> dict[str, str]:
        result = {
            "source_identity": self.source_identity,
            "source_type": self.source_type,
            "stable_locator": self.stable_locator,
        }
        if self.revision_or_version is not None:
            result["revision_or_version"] = self.revision_or_version
        return result


@dataclass(frozen=True)
class BitbucketInvalidChangedFileSource:
    """A classified child-source defect with no rejected payload retained."""

    reason_code: str
    stable_file_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.reason_code, str) or self.reason_code not in _INVALID_CHANGED_FILE_REASONS:
            raise BitbucketValidationError("invalid changed-file reason is unsupported")
        if self.stable_file_id:
            try:
                object.__setattr__(self, "stable_file_id", safe_identity(self.stable_file_id, "stable_file_id"))
            except ValueError:
                # An unsafe provider identifier is itself not safe to expose.
                object.__setattr__(self, "stable_file_id", "")

    @classmethod
    def invalid(cls, reason_code: str, stable_file_id: str = "") -> "BitbucketInvalidChangedFileSource":
        return cls(reason_code, stable_file_id)

    def as_dict(self) -> dict[str, str]:
        result = {"invalid_reason": self.reason_code}
        if self.stable_file_id:
            result["stable_file_id"] = self.stable_file_id
        return result


BitbucketInvalidChangedFileSourceRecord = BitbucketInvalidChangedFileSource


@dataclass(frozen=True)
class BitbucketChangedFileSourceRecord:
    """Source-private changed-file identity supplied by an external adapter."""

    stable_file_id: str = ""
    file: str = ""
    repository_id: str = ""
    head_revision: str = ""
    source_reference: BitbucketSourceReference | None = None
    path: str = ""

    def __post_init__(self) -> None:
        path = self.file or self.path
        normalized_path = _file(path, "file")
        object.__setattr__(self, "file", normalized_path)
        object.__setattr__(self, "path", normalized_path)
        object.__setattr__(self, "stable_file_id", _identity(self.stable_file_id, "stable_file_id"))
        object.__setattr__(self, "repository_id", _repository(self.repository_id, "repository_id"))
        object.__setattr__(self, "head_revision", _revision(self.head_revision, "head_revision"))
        if not isinstance(self.source_reference, BitbucketSourceReference):
            raise BitbucketValidationError("source_reference is required")

    def as_dict(self) -> dict[str, object]:
        return {
            "file": self.file,
            "head_revision": self.head_revision,
            "repository_id": self.repository_id,
            "source_reference": self.source_reference.as_dict(),
            "stable_file_id": self.stable_file_id,
        }

    @classmethod
    def invalid(cls, reason_code: str, stable_file_id: str = "") -> BitbucketInvalidChangedFileSource:
        """Represent a rejected child without constructing unsafe child fields."""

        return BitbucketInvalidChangedFileSource(reason_code, stable_file_id)

    @classmethod
    def from_untrusted(
        cls,
        stable_file_id: object,
        file: object,
        repository_id: object,
        head_revision: object,
        source_reference: object,
    ) -> "BitbucketChangedFileSourceRecord | BitbucketInvalidChangedFileSource":
        """Classify wire-level child input before constructing the strict DTO."""

        safe_file_id = stable_file_id if isinstance(stable_file_id, str) else ""
        try:
            if not isinstance(stable_file_id, str) or not stable_file_id.strip():
                return cls.invalid("missing-file-identity")
            try:
                safe_file_id = safe_identity(stable_file_id, "stable_file_id")
            except ValueError:
                return cls.invalid("missing-file-identity")
            if not isinstance(file, str) or not file.strip():
                return cls.invalid("missing-file-identity", safe_file_id)
            try:
                _file(file, "file")
            except BitbucketValidationError:
                return cls.invalid("unsafe-file-path", safe_file_id)
            try:
                return cls(stable_file_id, file, repository_id, head_revision, source_reference)
            except BitbucketValidationError:
                return cls.invalid("malformed-changed-file-source", safe_file_id)
        except (TypeError, ValueError):
            return cls.invalid("malformed-changed-file-source", safe_file_id)


BitbucketChangedFileSource = BitbucketChangedFileSourceRecord


REFERENCE_KINDS = frozenset({
    "OPENSPEC_ACTIVE_CHANGE",
    "OPENSPEC_ARCHIVED_CHANGE",
    "JIRA_STORY",
})
_REFERENCE_NODE_KINDS = {
    "OPENSPEC_ACTIVE_CHANGE": NodeKind.OPENSPEC_ACTIVE_CHANGE.value,
    "OPENSPEC_ARCHIVED_CHANGE": NodeKind.OPENSPEC_ARCHIVED_CHANGE.value,
    "JIRA_STORY": NodeKind.JIRA_STORY.value,
}


@dataclass(frozen=True)
class BitbucketInvalidStructuredReference:
    """A classified declaration defect with no rejected source text retained."""

    reason_code: str
    target_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.reason_code, str) or self.reason_code not in _INVALID_REFERENCE_REASONS:
            raise BitbucketValidationError("invalid reference reason is unsupported")
        if self.target_id:
            try:
                object.__setattr__(self, "target_id", safe_identity(self.target_id, "target_id"))
            except ValueError:
                object.__setattr__(self, "target_id", "")

    @classmethod
    def invalid(cls, reason_code: str, target_id: str = "") -> "BitbucketInvalidStructuredReference":
        return cls(reason_code, target_id)

    def as_dict(self) -> dict[str, str]:
        result = {"invalid_reason": self.reason_code}
        if self.target_id:
            result["target_id"] = self.target_id
        return result


BitbucketInvalidDeclarationSourceRecord = BitbucketInvalidStructuredReference


@dataclass(frozen=True)
class BitbucketStructuredReference:
    """A separately classified explicit declaration, not parsed text."""

    target_kind: str = ""
    target_id: str = ""
    source_reference: BitbucketSourceReference | None = None
    intended_change_kind: str = ""
    intended_change_id: str = ""

    def __post_init__(self) -> None:
        kind = self.target_kind or self.intended_change_kind
        target = self.target_id or self.intended_change_id
        object.__setattr__(self, "target_kind", _identity(kind, "reference.target_kind"))
        object.__setattr__(self, "target_id", _identity(target, "reference.target_id"))
        object.__setattr__(self, "intended_change_kind", self.target_kind)
        object.__setattr__(self, "intended_change_id", self.target_id)
        if not isinstance(self.source_reference, BitbucketSourceReference):
            raise BitbucketValidationError("reference.source_reference is required")

    def as_dict(self) -> dict[str, object]:
        return {
            "source_reference": self.source_reference.as_dict(),
            "target_id": self.target_id,
            "target_kind": self.target_kind,
        }

    @classmethod
    def invalid(cls, reason_code: str, target_id: str = "") -> BitbucketInvalidStructuredReference:
        """Represent a rejected declaration without retaining its source fields."""

        return BitbucketInvalidStructuredReference(reason_code, target_id)

    @classmethod
    def from_untrusted(
        cls, target_kind: object, target_id: object, source_reference: object,
    ) -> "BitbucketStructuredReference | BitbucketInvalidStructuredReference":
        """Classify wire-level declaration input before strict DTO construction."""

        safe_target_id = target_id if isinstance(target_id, str) else ""
        if not isinstance(source_reference, BitbucketSourceReference):
            return cls.invalid("missing-reference-source", safe_target_id)
        if not isinstance(target_id, str) or not target_id.strip():
            return cls.invalid("missing-reference-target")
        if not isinstance(target_kind, str) or not target_kind.strip():
            return cls.invalid("unsupported-reference-kind", safe_target_id)
        try:
            return cls(target_kind, target_id, source_reference)
        except BitbucketValidationError:
            try:
                safe_target_id = safe_identity(target_id, "target_id")
            except ValueError:
                safe_target_id = ""
            return cls.invalid("malformed-reference", safe_target_id)


BitbucketExplicitReference = BitbucketStructuredReference


@dataclass(frozen=True)
class BitbucketPullRequestSourceRecord:
    """Allowlisted source-private selected PR response."""

    pull_request_id: str
    repository_id: str
    merged: bool
    base_revision: str
    head_revision: str
    observed_at: str
    source_reference: BitbucketSourceReference | None = None
    repository_source_reference: BitbucketSourceReference | None = None
    changed_files: tuple[BitbucketChangedFileSourceRecord | BitbucketInvalidChangedFileSource, ...] | None = None
    structured_references: tuple[BitbucketStructuredReference | BitbucketInvalidStructuredReference, ...] = ()
    pr_source_reference: BitbucketSourceReference | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "pull_request_id", _identity(self.pull_request_id, "pull_request_id"))
        object.__setattr__(self, "repository_id", _repository(self.repository_id, "repository_id"))
        if not isinstance(self.merged, bool):
            raise BitbucketValidationError("merged must be boolean")
        object.__setattr__(self, "base_revision", _revision(self.base_revision, "base_revision"))
        object.__setattr__(self, "head_revision", _revision(self.head_revision, "head_revision"))
        object.__setattr__(self, "observed_at", _observed_at(self.observed_at))
        pr_source = self.source_reference or self.pr_source_reference
        if not isinstance(pr_source, BitbucketSourceReference):
            raise BitbucketValidationError("source_reference is required")
        object.__setattr__(self, "source_reference", pr_source)
        if not isinstance(self.repository_source_reference, BitbucketSourceReference):
            raise BitbucketValidationError("repository_source_reference is required")
        if self.changed_files is not None:
            if not isinstance(self.changed_files, (tuple, list)):
                raise BitbucketValidationError("changed_files must be a sequence or None")
            object.__setattr__(
                self,
                "changed_files",
                tuple(
                    item if isinstance(item, (BitbucketChangedFileSourceRecord, BitbucketInvalidChangedFileSource))
                    else BitbucketInvalidChangedFileSource("malformed-changed-file-source")
                    for item in self.changed_files
                ),
            )
        if not isinstance(self.structured_references, (tuple, list)):
            raise BitbucketValidationError("structured_references must be a sequence")
        object.__setattr__(
            self,
            "structured_references",
            tuple(
                item if isinstance(item, (BitbucketStructuredReference, BitbucketInvalidStructuredReference))
                else BitbucketInvalidStructuredReference("malformed-reference")
                for item in self.structured_references
            ),
        )

    @property
    def declarations(self) -> tuple[BitbucketStructuredReference | BitbucketInvalidStructuredReference, ...]:
        return self.structured_references

    def as_dict(self) -> dict[str, object]:
        return {
            "base_revision": self.base_revision,
            "changed_files": [item.as_dict() for item in self.changed_files] if self.changed_files is not None else None,
            "head_revision": self.head_revision,
            "merged": self.merged,
            "observed_at": self.observed_at,
            "pull_request_id": self.pull_request_id,
            "repository_id": self.repository_id,
            "repository_source_reference": self.repository_source_reference.as_dict(),
            "source_reference": self.source_reference.as_dict(),
            "structured_references": [item.as_dict() for item in self.structured_references],
        }


BitbucketPullRequestSource = BitbucketPullRequestSourceRecord


@dataclass(frozen=True)
class BitbucketSourceResponse:
    """Provider-neutral response envelope accepted from a source port."""

    record: BitbucketPullRequestSourceRecord | None = None
    status: str = BitbucketSourceStatus.OK.value

    def __post_init__(self) -> None:
        if not isinstance(self.status, str):
            raise BitbucketValidationError("source response status must be a string")

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"status": self.status}
        if isinstance(self.record, BitbucketPullRequestSourceRecord):
            result["record"] = self.record.as_dict()
        return result


class BitbucketSourcePort(Protocol):
    """The sole transport seam owned by a deployment-specific integration."""

    def fetch_pull_request(self, selection: BitbucketSourceSelection) -> object:
        """Return one source response for exactly the selected PR."""


@dataclass(frozen=True)
class BitbucketDiagnostic:
    reason_code: str
    object_id: str = ""
    stable_file_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.reason_code, str) or self.reason_code not in FROZEN_BITBUCKET_DIAGNOSTIC_REASONS:
            raise BitbucketValidationError("diagnostic.reason_code is unsupported")
        if self.object_id:
            object.__setattr__(self, "object_id", _identity(self.object_id, "diagnostic.object_id"))
        if self.stable_file_id:
            object.__setattr__(self, "stable_file_id", _identity(self.stable_file_id, "diagnostic.stable_file_id"))

    @property
    def affected_object_id(self) -> str:
        return self.object_id or self.stable_file_id

    def as_dict(self) -> dict[str, str]:
        result = {"reason_code": self.reason_code}
        if self.object_id:
            result["object_id"] = self.object_id
        if self.stable_file_id:
            result["stable_file_id"] = self.stable_file_id
        return result


@dataclass(frozen=True)
class BitbucketChangedFileObservation:
    """Ephemeral exact file fact, suitable for a later OpenLore handoff only."""

    stable_file_id: str
    file: str
    pull_request_evidence_id: str
    repository_id: str
    head_revision: str
    source_evidence_id: str
    provenance_evidence_id: str
    source_evidence: Evidence | None = None
    provenance: ProvenanceRecord | None = None

    @property
    def id(self) -> str:
        return stable_id(
            "bitbucket-changed-file-observation",
            self.pull_request_evidence_id, self.repository_id, self.head_revision,
            self.stable_file_id,
        )

    @property
    def path(self) -> str:
        return self.file

    @property
    def evidence_id(self) -> str:
        return self.source_evidence_id

    @property
    def provenance_id(self) -> str:
        return self.provenance_evidence_id

    def __post_init__(self) -> None:
        object.__setattr__(self, "stable_file_id", _identity(self.stable_file_id, "stable_file_id"))
        object.__setattr__(self, "file", _file(self.file, "file"))
        object.__setattr__(self, "pull_request_evidence_id", _identity(self.pull_request_evidence_id, "pull_request_evidence_id"))
        object.__setattr__(self, "repository_id", _repository(self.repository_id, "repository_id"))
        object.__setattr__(self, "head_revision", _revision(self.head_revision, "head_revision"))
        object.__setattr__(self, "source_evidence_id", _identity(self.source_evidence_id, "source_evidence_id"))
        object.__setattr__(self, "provenance_evidence_id", _identity(self.provenance_evidence_id, "provenance_evidence_id"))
        if self.source_evidence is not None and not isinstance(self.source_evidence, Evidence):
            raise BitbucketValidationError("source_evidence must be Evidence")
        if self.provenance is not None and not isinstance(self.provenance, ProvenanceRecord):
            raise BitbucketValidationError("provenance must be ProvenanceRecord")

    def as_dict(self) -> dict[str, str]:
        return {
            "file": self.file,
            "head_revision": self.head_revision,
            "id": self.id,
            "provenance_evidence_id": self.provenance_evidence_id,
            "pull_request_evidence_id": self.pull_request_evidence_id,
            "repository_id": self.repository_id,
            "source_evidence_id": self.source_evidence_id,
            "stable_file_id": self.stable_file_id,
        }

    def to_changed_file_reference(self) -> ChangedFileReference:
        return ChangedFileReference(
            self.stable_file_id, self.file,
            self.source_evidence_id, self.provenance_evidence_id,
        )

    def to_implementation_evidence_context(self) -> ImplementationEvidenceContext:
        return ImplementationEvidenceContext(
            self.pull_request_evidence_id, self.repository_id, self.head_revision,
            self.source_evidence_id, self.provenance_evidence_id,
        )


@dataclass(frozen=True)
class BitbucketSourceMetadata:
    """Safe counts and fixed diagnostics for one adapter invocation."""

    changed_file_count: int
    association_count: int
    diagnostic_count: int
    reason_counts: dict[str, int]

    def as_dict(self) -> dict[str, object]:
        return {
            "association_count": self.association_count,
            "changed_file_count": self.changed_file_count,
            "diagnostic_count": self.diagnostic_count,
            "reason_counts": dict(sorted(self.reason_counts.items())),
        }


@dataclass(frozen=True)
class BitbucketSourceResult:
    status: str
    selection: BitbucketSourceSelection
    graph: GraphSnapshot
    pull_request_evidence: PullRequestImplementationEvidence | None = None
    repository_relation: PullRequestObservedRepositoryRelation | None = None
    associations: tuple[PullRequestDeclaredAssociation, ...] = ()
    changed_files: tuple[BitbucketChangedFileObservation, ...] = ()
    changed_file_evidence: tuple[Evidence, ...] = ()
    changed_file_provenance: tuple[ProvenanceRecord, ...] = ()
    diagnostics: tuple[BitbucketDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, str) or self.status not in {item.value for item in BitbucketResultStatus}:
            raise BitbucketValidationError("result.status is unsupported")
        if not isinstance(self.selection, BitbucketSourceSelection):
            raise BitbucketValidationError("result.selection is invalid")
        if not isinstance(self.graph, GraphSnapshot):
            raise BitbucketValidationError("result.graph must be GraphSnapshot")
        associations = tuple(self.associations)
        changed_files = tuple(self.changed_files)
        changed_file_evidence = tuple(self.changed_file_evidence)
        changed_file_provenance = tuple(self.changed_file_provenance)
        diagnostics = tuple(self.diagnostics)
        if not all(isinstance(item, PullRequestDeclaredAssociation) for item in associations):
            raise BitbucketValidationError("result.associations must contain association records")
        if not all(isinstance(item, BitbucketChangedFileObservation) for item in changed_files):
            raise BitbucketValidationError("result.changed_files must contain observations")
        if not all(isinstance(item, Evidence) for item in changed_file_evidence):
            raise BitbucketValidationError("result.changed_file_evidence must contain Evidence records")
        if not all(isinstance(item, ProvenanceRecord) for item in changed_file_provenance):
            raise BitbucketValidationError("result.changed_file_provenance must contain provenance records")
        if not all(isinstance(item, BitbucketDiagnostic) for item in diagnostics):
            raise BitbucketValidationError("result.diagnostics must contain BitbucketDiagnostic records")
        object.__setattr__(self, "associations", associations)
        object.__setattr__(self, "changed_files", tuple(sorted(changed_files, key=lambda item: item.id)))
        object.__setattr__(self, "changed_file_evidence", tuple(sorted(changed_file_evidence, key=lambda item: item.id)))
        object.__setattr__(self, "changed_file_provenance", tuple(sorted(changed_file_provenance, key=lambda item: item.id)))
        object.__setattr__(self, "diagnostics", tuple(sorted(diagnostics, key=lambda item: (item.reason_code, item.affected_object_id))))

    @property
    def graph_contribution(self) -> GraphSnapshot:
        return self.graph

    @property
    def pull_request(self) -> PullRequestImplementationEvidence | None:
        return self.pull_request_evidence

    @property
    def repository_relation_record(self) -> PullRequestObservedRepositoryRelation | None:
        return self.repository_relation

    @property
    def admitted(self) -> bool:
        return self.status == BitbucketResultStatus.ADMITTED.value

    @property
    def metadata(self) -> BitbucketSourceMetadata:
        counts: dict[str, int] = {}
        for diagnostic in self.diagnostics:
            counts[diagnostic.reason_code] = counts.get(diagnostic.reason_code, 0) + 1
        return BitbucketSourceMetadata(
            len(self.changed_files), len(self.associations), len(self.diagnostics), counts,
        )

    def to_openlore_request(self) -> ChangedFileResolutionRequest:
        return observations_to_openlore_request(self.changed_files)

    def as_dict(self) -> dict[str, object]:
        return {
            "associations": [item.as_dict() for item in self.associations],
            "changed_files": [item.as_dict() for item in self.changed_files],
            "diagnostics": [item.as_dict() for item in self.diagnostics],
            "graph_counts": {
                "edge_count": self.graph.edge_count,
                "evidence_count": self.graph.evidence_count,
                "node_count": self.graph.node_count,
                "provenance_count": self.graph.provenance_count,
            },
            "metadata": self.metadata.as_dict(),
            "pull_request_evidence": self.pull_request_evidence.as_dict() if self.pull_request_evidence else None,
            "repository_relation": self.repository_relation.as_dict() if self.repository_relation else None,
            "selection": self.selection.as_dict(),
            "status": self.status,
        }

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True)


class BitbucketSourceAdapter:
    """Normalize one selected PR without fallback acquisition or persistence."""

    def __init__(self, source_port: BitbucketSourcePort) -> None:
        if not hasattr(source_port, "fetch_pull_request") and not hasattr(source_port, "get_pull_request"):
            raise TypeError("source_port must implement fetch_pull_request")
        self.source_port = source_port

    def normalize(
        self,
        selection: BitbucketSourceSelection,
        subject_graph: GraphSnapshot,
    ) -> BitbucketSourceResult:
        if not isinstance(selection, BitbucketSourceSelection) or not isinstance(subject_graph, GraphSnapshot):
            fallback = selection if isinstance(selection, BitbucketSourceSelection) else BitbucketSourceSelection("bitbucket:invalid-selection", "invalid-repository")
            return _result(BitbucketResultStatus.INVALID_SOURCE, fallback, BitbucketDiagnostic("invalid-selection"))

        response = self._invoke(selection)
        if isinstance(response, BitbucketSourceResponse):
            if response.status == BitbucketSourceStatus.UNAVAILABLE.value:
                return _result(BitbucketResultStatus.UNAVAILABLE, selection, BitbucketDiagnostic("provider-unavailable"))
            if response.status != BitbucketSourceStatus.OK.value:
                return _result(BitbucketResultStatus.INVALID_SOURCE, selection, BitbucketDiagnostic("unsupported-source-status"))
            response = response.record
        elif isinstance(response, Mapping):
            # Raw mappings are not a supported crossing of the boundary.  Do
            # not inspect them, since doing so could retain provider payload.
            return _result(BitbucketResultStatus.INVALID_SOURCE, selection, BitbucketDiagnostic("malformed-source-response"))
        if not isinstance(response, BitbucketPullRequestSourceRecord):
            return _result(BitbucketResultStatus.INVALID_SOURCE, selection, BitbucketDiagnostic("malformed-source-response"))

        try:
            admission = self._admit_pr(selection, subject_graph, response)
        except Exception:
            return _result(BitbucketResultStatus.REJECTED, selection, BitbucketDiagnostic("malformed-source-response"))
        if admission:
            return _result(BitbucketResultStatus.REJECTED, selection, *admission)
        try:
            return self._normalize_admitted(selection, subject_graph, response)
        except (BitbucketValidationError, ValueError):
            # Structural source DTO defects remain a safe non-admission; no
            # source/provider error text is returned.
            return _result(BitbucketResultStatus.REJECTED, selection, BitbucketDiagnostic("malformed-source-response"))

    def acquire(self, selection: BitbucketSourceSelection, subject_graph: GraphSnapshot) -> BitbucketSourceResult:
        return self.normalize(selection, subject_graph)

    def _invoke(self, selection: BitbucketSourceSelection) -> object:
        method = getattr(self.source_port, "fetch_pull_request", None)
        if method is None:
            method = getattr(self.source_port, "get_pull_request")
        try:
            return method(selection)
        except Exception:
            # The exception is deliberately reduced to a fixed diagnostic.
            return BitbucketSourceResponse(status=BitbucketSourceStatus.UNAVAILABLE.value)

    @staticmethod
    def _admit_pr(
        selection: BitbucketSourceSelection,
        subject_graph: GraphSnapshot,
        record: BitbucketPullRequestSourceRecord,
    ) -> tuple[BitbucketDiagnostic, ...]:
        diagnostics: list[BitbucketDiagnostic] = []
        if record.pull_request_id != selection.pull_request_id:
            diagnostics.append(BitbucketDiagnostic("conflicting-pr-identity", selection.pull_request_id))
        if record.repository_id != selection.repository_id:
            diagnostics.append(BitbucketDiagnostic("repository-context-mismatch", selection.repository_id))
        if not record.merged:
            diagnostics.append(BitbucketDiagnostic("unmerged-pr", selection.pull_request_id))
        repository = next((node for node in subject_graph.nodes if node.id == selection.repository_id), None)
        if repository is None:
            diagnostics.append(BitbucketDiagnostic("unknown-repository", selection.repository_id))
        elif str(getattr(repository.kind, "value", repository.kind)) != NodeKind.REPOSITORY.value:
            diagnostics.append(BitbucketDiagnostic("unknown-repository", selection.repository_id))
        try:
            _revision(record.base_revision, "base_revision")
        except BitbucketValidationError:
            diagnostics.append(BitbucketDiagnostic("abbreviated-revision", selection.pull_request_id))
        try:
            _revision(record.head_revision, "head_revision")
        except BitbucketValidationError:
            diagnostics.append(BitbucketDiagnostic("abbreviated-revision", selection.pull_request_id))
        if record.source_reference.revision_or_version not in (None, record.head_revision):
            diagnostics.append(BitbucketDiagnostic("revision-context-mismatch", selection.pull_request_id))
        if record.repository_source_reference.revision_or_version not in (None, record.head_revision):
            diagnostics.append(BitbucketDiagnostic("revision-context-mismatch", selection.pull_request_id))
        try:
            _observed_at(record.observed_at)
        except BitbucketValidationError:
            diagnostics.append(BitbucketDiagnostic("invalid-observation-time", selection.pull_request_id))
        if not diagnostics:
            evidence_id = stable_id(
                "pull-request-evidence", selection.pull_request_id, selection.repository_id,
            )
            represented = tuple(
                item for item in subject_graph.pull_request_evidence if item.id == evidence_id
            )
            if represented:
                pr_artifact, pr_provenance = _bundle(
                    record.source_reference, "pull-request", record.head_revision,
                    record.observed_at,
                    {
                        "pull_request_id": selection.pull_request_id,
                        "repository": selection.repository_id,
                        "base_revision": record.base_revision,
                        "head_revision": record.head_revision,
                    },
                )
                incoming_fields = (
                    record.pull_request_id, record.repository_id,
                    record.base_revision, record.head_revision, record.merged,
                    _evidence_id(pr_artifact.identity), pr_provenance.id,
                )
                if any(
                    incoming_fields != (
                        item.pull_request_id, item.repository_id,
                        item.base_revision, item.head_revision, item.merged,
                        item.source_evidence_id, item.provenance_evidence_id,
                    )
                    for item in represented
                ):
                    diagnostics.append(BitbucketDiagnostic("conflicting-pr-identity", selection.pull_request_id))
        return tuple(sorted(diagnostics, key=lambda item: (item.reason_code, item.affected_object_id)))

    def _normalize_admitted(
        self,
        selection: BitbucketSourceSelection,
        subject_graph: GraphSnapshot,
        record: BitbucketPullRequestSourceRecord,
    ) -> BitbucketSourceResult:
        head = record.head_revision
        pr_artifact, pr_provenance = _bundle(
            record.source_reference, "pull-request", head, record.observed_at,
            {"pull_request_id": selection.pull_request_id, "repository": selection.repository_id,
             "base_revision": record.base_revision, "head_revision": head},
        )
        repository_artifact, repository_provenance = _bundle(
            record.repository_source_reference, "pr-repository", head, record.observed_at,
            {"pull_request_id": selection.pull_request_id, "repository": selection.repository_id,
             "base_revision": record.base_revision, "head_revision": head},
        )
        pr_evidence = PullRequestImplementationEvidence(
            selection.pull_request_id, selection.repository_id, record.base_revision, head, True,
            _evidence_id(pr_artifact.identity), pr_provenance.id,
        )
        relation = PullRequestObservedRepositoryRelation(
            pr_evidence.id, selection.repository_id,
            _evidence_id(repository_artifact.identity), repository_provenance.id,
        )
        evidence = [
            _evidence(pr_artifact, pr_provenance, {"pull_request_id": selection.pull_request_id, "repository": selection.repository_id, "base_revision": record.base_revision, "head_revision": head}),
            _evidence(repository_artifact, repository_provenance, {"pull_request_id": selection.pull_request_id, "repository": selection.repository_id, "base_revision": record.base_revision, "head_revision": head}),
        ]
        provenance = [pr_provenance, repository_provenance]
        associations: list[PullRequestDeclaredAssociation] = []
        association_seen: set[str] = set()
        diagnostics: list[BitbucketDiagnostic] = []
        nodes = {node.id: node for node in subject_graph.nodes}
        eligible_declarations: list[tuple[BitbucketStructuredReference, str]] = []
        for declaration in sorted(
            record.structured_references,
            key=lambda item: (
                getattr(item, "target_id", ""),
                getattr(item, "target_kind", ""),
                getattr(getattr(item, "source_reference", None), "source_type", ""),
                getattr(getattr(item, "source_reference", None), "source_identity", ""),
                getattr(getattr(item, "source_reference", None), "stable_locator", ""),
                getattr(getattr(item, "source_reference", None), "revision_or_version", "") or "",
            ),
        ):
            if isinstance(declaration, BitbucketInvalidStructuredReference):
                diagnostics.append(BitbucketDiagnostic(declaration.reason_code, declaration.target_id))
                continue
            if declaration.target_kind not in REFERENCE_KINDS:
                diagnostics.append(BitbucketDiagnostic("unsupported-reference-kind", declaration.target_id))
                continue
            target = nodes.get(declaration.target_id)
            if target is None:
                diagnostics.append(BitbucketDiagnostic("unknown-reference-target", declaration.target_id))
                continue
            if str(getattr(target.kind, "value", target.kind)) != _REFERENCE_NODE_KINDS[declaration.target_kind]:
                diagnostics.append(BitbucketDiagnostic("ineligible-reference-target", declaration.target_id))
                continue
            if declaration.source_reference.revision_or_version not in (None, head):
                diagnostics.append(BitbucketDiagnostic("revision-context-mismatch", declaration.target_id))
                continue
            try:
                declaration_artifact = normalize_source_artifact(
                    source_type=declaration.source_reference.source_type,
                    source_identity=declaration.source_reference.source_identity,
                    artifact_type="pr-association",
                    revision_or_version=head,
                    stable_locator=declaration.source_reference.stable_locator,
                )
            except (BitbucketValidationError, ValueError):
                # A declaration is subordinate to the independently admitted
                # PR.  A declaration-specific identity defect is diagnosed at
                # this reference rather than escaping into the PR-level
                # rejection handler in normalize().
                diagnostics.append(BitbucketDiagnostic("malformed-reference", declaration.target_id))
                continue
            eligible_declarations.append((declaration, declaration_artifact.identity.id))

        declaration_targets_by_artifact: dict[str, set[str]] = {}
        for declaration, artifact_id in eligible_declarations:
            declaration_targets_by_artifact.setdefault(artifact_id, set()).add(declaration.target_id)
        conflicting_reference_artifacts = {
            artifact_id
            for artifact_id, target_ids in declaration_targets_by_artifact.items()
            if len(target_ids) > 1
        }
        for declaration, artifact_id in eligible_declarations:
            if artifact_id in conflicting_reference_artifacts:
                diagnostics.append(BitbucketDiagnostic("conflicting-reference-identity", declaration.target_id))
                continue
            artifact, declaration_provenance = _bundle(
                declaration.source_reference, "pr-association", head, record.observed_at,
                {"association_id": declaration.target_id, "pull_request_id": selection.pull_request_id, "repository": selection.repository_id, "head_revision": head},
            )
            declaration_evidence = _evidence(artifact, declaration_provenance, {"association_id": declaration.target_id, "pull_request_id": selection.pull_request_id, "repository": selection.repository_id, "head_revision": head})
            association = PullRequestDeclaredAssociation(pr_evidence.id, declaration.target_id, declaration_evidence.id, declaration_provenance.id)
            # The association ID includes the complete source-artifact identity
            # through source evidence.  Coalesce only declarations that produce
            # the same canonical association; distinct stable locators remain
            # independently attributable declarations.
            if association.id in association_seen:
                continue
            association_seen.add(association.id)
            associations.append(association)
            evidence.append(declaration_evidence)
            provenance.append(declaration_provenance)

        changed, changed_evidence, changed_provenance, file_diagnostics = self._normalize_files(selection, record, pr_evidence.id)
        diagnostics.extend(file_diagnostics)
        projected = project_pull_request_evidence((pr_evidence,), tuple(associations), (relation,))
        graph = GraphSnapshot(
            projected.nodes, projected.edges, tuple(evidence),
            provenance=tuple(provenance), pull_request_evidence=(pr_evidence,),
            pull_request_declared_associations=tuple(associations),
            pull_request_observed_repository_relations=(relation,),
        )
        return BitbucketSourceResult(
            BitbucketResultStatus.ADMITTED.value, selection, graph, pr_evidence, relation,
            tuple(associations), tuple(changed), tuple(changed_evidence), tuple(changed_provenance), tuple(diagnostics),
        )

    @staticmethod
    def _normalize_files(
        selection: BitbucketSourceSelection,
        record: BitbucketPullRequestSourceRecord,
        pr_evidence_id: str,
    ) -> tuple[list[BitbucketChangedFileObservation], list[Evidence], list[ProvenanceRecord], list[BitbucketDiagnostic]]:
        if record.changed_files is None:
            return [], [], [], [BitbucketDiagnostic("changed-files-unavailable", selection.pull_request_id)]
        valid: dict[str, list[tuple[BitbucketChangedFileSourceRecord, Evidence, ProvenanceRecord]]] = {}
        diagnostics: list[BitbucketDiagnostic] = []
        for item in record.changed_files:
            if isinstance(item, BitbucketInvalidChangedFileSource):
                diagnostics.append(
                    BitbucketDiagnostic(item.reason_code, stable_file_id=item.stable_file_id)
                )
                continue
            if item.repository_id != selection.repository_id or item.head_revision != record.head_revision:
                diagnostics.append(BitbucketDiagnostic("changed-file-context-mismatch", stable_file_id=item.stable_file_id))
                continue
            if item.source_reference.revision_or_version not in (None, record.head_revision):
                diagnostics.append(BitbucketDiagnostic("changed-file-context-mismatch", stable_file_id=item.stable_file_id))
                continue
            artifact, item_provenance = _bundle(
                item.source_reference, "changed-file", record.head_revision, record.observed_at,
                {"pull_request_id": selection.pull_request_id, "repository": selection.repository_id, "head_revision": record.head_revision, "source_mapping_id": item.stable_file_id, "file": item.file},
            )
            item_evidence = _evidence(artifact, item_provenance, {"pull_request_id": selection.pull_request_id, "repository": selection.repository_id, "head_revision": record.head_revision, "source_mapping_id": item.stable_file_id, "file": item.file})
            valid.setdefault(item.stable_file_id, []).append((item, item_evidence, item_provenance))
        observations: list[BitbucketChangedFileObservation] = []
        evidence: list[Evidence] = []
        provenance: list[ProvenanceRecord] = []
        selected: list[tuple[str, BitbucketChangedFileSourceRecord, Evidence, ProvenanceRecord]] = []
        for stable_file_id in sorted(valid):
            records = valid[stable_file_id]
            signatures = {
                (item.file, item.repository_id, item.head_revision, json.dumps(item.source_reference.as_dict(), sort_keys=True))
                for item, _, _ in records
            }
            if len(signatures) > 1:
                diagnostics.append(BitbucketDiagnostic("conflicting-changed-file-identity", stable_file_id=stable_file_id))
                continue
            item, item_evidence, item_provenance = sorted(records, key=lambda value: value[0].file)[0]
            selected.append((stable_file_id, item, item_evidence, item_provenance))

        source_artifact_to_file_ids: dict[str, set[str]] = {}
        for stable_file_id, _, item_evidence, _ in selected:
            source_artifact_id = item_evidence.locator.source_artifact_identity.id
            source_artifact_to_file_ids.setdefault(source_artifact_id, set()).add(stable_file_id)
        colliding_file_ids = {
            stable_file_id
            for source_artifact_id, file_ids in source_artifact_to_file_ids.items()
            if len(file_ids) > 1
            for stable_file_id in file_ids
        }
        for stable_file_id in sorted(colliding_file_ids):
            diagnostics.append(BitbucketDiagnostic("conflicting-changed-file-identity", stable_file_id=stable_file_id))

        for stable_file_id, item, item_evidence, item_provenance in selected:
            if stable_file_id in colliding_file_ids:
                continue
            observation = BitbucketChangedFileObservation(
                stable_file_id, item.file, pr_evidence_id, selection.repository_id,
                record.head_revision, item_evidence.id, item_provenance.id,
                item_evidence, item_provenance,
            )
            observations.append(observation)
            evidence.append(item_evidence)
            provenance.append(item_provenance)
        return observations, evidence, provenance, diagnostics


def _evidence_id(identity: SourceArtifactIdentity) -> str:
    return stable_id("evidence", identity.id)


def _bundle(
    reference: BitbucketSourceReference,
    artifact_type: str,
    revision: str,
    observed_at: str,
    context: Mapping[str, str],
) -> tuple[Any, ProvenanceRecord]:
    if reference.revision_or_version not in (None, revision):
        raise BitbucketValidationError("source reference revision does not match represented head")
    artifact = normalize_source_artifact(
        source_type=reference.source_type,
        source_identity=reference.source_identity,
        artifact_type=artifact_type,
        revision_or_version=revision,
        stable_locator=reference.stable_locator,
    )
    useful = json.dumps(
        {"artifact": artifact.identity.as_dict(), "context": dict(sorted(context.items()))},
        sort_keys=True, separators=(",", ":"),
    )
    provenance = external_provenance(
        artifact, observed_at=observed_at, useful_representation=useful,
        extractor_id=ADAPTER_ID, extractor_version=ADAPTER_VERSION,
    )
    return artifact, provenance


def _evidence(artifact: Any, provenance: ProvenanceRecord, properties: Mapping[str, object]) -> Evidence:
    return Evidence(_evidence_id(artifact.identity), ADAPTER_ID, SourceArtifactLocator(artifact.identity), dict(properties), (provenance.id,))


def _result(status: BitbucketResultStatus, selection: BitbucketSourceSelection, *diagnostics: BitbucketDiagnostic) -> BitbucketSourceResult:
    return BitbucketSourceResult(status.value, selection, GraphSnapshot(), diagnostics=tuple(diagnostics))


def adapt_bitbucket_pull_request(
    selection: BitbucketSourceSelection,
    source_port: BitbucketSourcePort,
    subject_graph: GraphSnapshot,
) -> BitbucketSourceResult:
    """Convenience function for callers that do not need an adapter object."""

    return BitbucketSourceAdapter(source_port).normalize(selection, subject_graph)


def changed_file_to_openlore_reference(observation: BitbucketChangedFileObservation) -> ChangedFileReference:
    if not isinstance(observation, BitbucketChangedFileObservation):
        raise BitbucketValidationError("observation must be a BitbucketChangedFileObservation")
    return ChangedFileReference(
        observation.stable_file_id, observation.file,
        observation.source_evidence_id, observation.provenance_evidence_id,
    )


def observations_to_openlore_request(
    observations: Sequence[BitbucketChangedFileObservation],
    evidence: ImplementationEvidenceContext | None = None,
) -> ChangedFileResolutionRequest:
    """Convert admitted observations to the existing compact bridge request."""

    items = tuple(observations)
    if not items:
        raise BitbucketValidationError("at least one changed-file observation is required")
    if not all(isinstance(item, BitbucketChangedFileObservation) for item in items):
        raise BitbucketValidationError("observations must be BitbucketChangedFileObservation records")
    _require_single_pull_request_batch(items)
    first = items[0]
    if any((item.repository_id, item.head_revision) != (first.repository_id, first.head_revision) for item in items):
        raise BitbucketValidationError("observations must share repository and head context")
    context = evidence or ImplementationEvidenceContext(
        first.pull_request_evidence_id, first.repository_id, first.head_revision,
        first.source_evidence_id, first.provenance_evidence_id,
    )
    if context.evidence_id != first.pull_request_evidence_id or context.repository != first.repository_id or context.revision != first.head_revision:
        raise BitbucketValidationError("OpenLore evidence context does not match changed-file observations")
    refs = tuple(changed_file_to_openlore_reference(item) for item in sorted(items, key=lambda value: value.id))
    return ChangedFileResolutionRequest(context, first.repository_id, first.head_revision, refs)


def adapt_openlore_result_to_changed_symbol_mappings(
    result: ResolutionResult,
    observations: Sequence[BitbucketChangedFileObservation],
) -> tuple[ChangedSymbolMapping, ...]:
    """Explicitly adapt only context-matching bridge outcomes to EKG-14 input."""

    if not isinstance(result, ResolutionResult):
        raise BitbucketValidationError("result must be a ResolutionResult")
    items = tuple(observations)
    if items and not all(isinstance(item, BitbucketChangedFileObservation) for item in items):
        raise BitbucketValidationError("observations must be BitbucketChangedFileObservation records")
    _require_single_pull_request_batch(items)
    _require_unambiguous_changed_file_source_bindings(items)
    by_id = {item.stable_file_id: item for item in observations}
    if not by_id:
        return ()
    if result.status != "admitted":
        return tuple(
            ChangedSymbolMapping(
                item.stable_file_id, item.file, MappingOutcome.UNSUPPORTED,
                repository=item.repository_id, revision=item.head_revision,
                source_evidence_id=item.source_evidence_id,
                source_provenance_id=item.provenance_evidence_id,
            )
            for item in sorted(by_id.values(), key=lambda value: value.stable_file_id)
        )
    expected_request = observations_to_openlore_request(tuple(by_id.values()))
    if result.request_id != expected_request.id:
        return tuple(
            ChangedSymbolMapping(
                item.stable_file_id, item.file, MappingOutcome.UNSUPPORTED,
                repository=item.repository_id, revision=item.head_revision,
                source_evidence_id=item.source_evidence_id,
                source_provenance_id=item.provenance_evidence_id,
            )
            for item in sorted(by_id.values(), key=lambda value: value.stable_file_id)
        )
    # A request ID is stable but does not encode enough context to establish a
    # match by itself.  The result's routing-independent outcomes are checked
    # against every original file identity and the observation context.
    outcomes_by_id: dict[str, object] = {}
    duplicate_outcomes = False
    for outcome in result.outcomes:
        if outcome.stable_file_id in outcomes_by_id:
            duplicate_outcomes = True
        outcomes_by_id[outcome.stable_file_id] = outcome
    mappings: list[ChangedSymbolMapping] = []
    for observation in sorted(by_id.values(), key=lambda value: value.stable_file_id):
        outcome = outcomes_by_id.get(observation.stable_file_id)
        if duplicate_outcomes or outcome is None or outcome.file != observation.file:
            mappings.append(ChangedSymbolMapping(
                observation.stable_file_id, observation.file, MappingOutcome.UNSUPPORTED,
                repository=observation.repository_id, revision=observation.head_revision,
                source_evidence_id=observation.source_evidence_id,
                source_provenance_id=observation.provenance_evidence_id,
            ))
            continue
        resolved = outcome.status == ResolutionStatus.RESOLVED and outcome.locator is not None
        if resolved and (
            outcome.locator.repository != observation.repository_id
            or outcome.locator.revision != observation.head_revision
            or outcome.locator.file != observation.file
        ):
            resolved = False
        mappings.append(ChangedSymbolMapping(
            observation.stable_file_id,
            observation.file,
            MappingOutcome.RESOLVED if resolved else _mapping_outcome(outcome.status),
            outcome.locator.symbol if resolved and outcome.locator else None,
            observation.repository_id,
            observation.head_revision,
            observation.source_evidence_id,
            observation.provenance_evidence_id,
        ))
    return tuple(sorted(mappings, key=lambda item: item.id))


def _require_single_pull_request_batch(
    observations: Sequence[BitbucketChangedFileObservation],
) -> None:
    if len({item.pull_request_evidence_id for item in observations}) > 1:
        raise BitbucketValidationError("observations must share pull-request evidence context")


def _require_unambiguous_changed_file_source_bindings(
    observations: Sequence[BitbucketChangedFileObservation],
) -> None:
    bindings_by_evidence_id: dict[str, set[tuple[str, str, str]]] = {}
    for item in observations:
        bindings_by_evidence_id.setdefault(item.source_evidence_id, set()).add(
            (item.stable_file_id, item.file, item.provenance_evidence_id)
        )
    if any(len(bindings) > 1 for bindings in bindings_by_evidence_id.values()):
        raise BitbucketValidationError(
            "changed-file source evidence identity is ambiguous across observations"
        )


def _mapping_outcome(status: object) -> MappingOutcome:
    value = getattr(status, "value", status)
    return {
        "unresolved": MappingOutcome.UNRESOLVED,
        "ambiguous": MappingOutcome.AMBIGUOUS,
    }.get(value, MappingOutcome.UNSUPPORTED)


def adapt_openlore_result_to_normalized_pull_request_evidence(
    result: ResolutionResult,
    normalized: NormalizedPullRequestEvidence,
    observations: Sequence[BitbucketChangedFileObservation],
    *,
    changed_file_evidence: Sequence[Evidence] = (),
    changed_file_provenance: Sequence[ProvenanceRecord] = (),
) -> NormalizedPullRequestEvidence:
    """Adapt a bridge result while retaining the source file evidence bundle.

    The adapter returns file evidence and provenance separately from its graph
    contribution.  Accept those collections explicitly at this seam; the
    observation-local references remain a compatibility fallback for callers
    holding the richer in-memory observation DTOs.
    """

    if not isinstance(normalized, NormalizedPullRequestEvidence):
        raise BitbucketValidationError("normalized must be NormalizedPullRequestEvidence")
    items = tuple(observations)
    if items and not all(isinstance(item, BitbucketChangedFileObservation) for item in items):
        raise BitbucketValidationError("observations must be BitbucketChangedFileObservation records")
    if any(item.pull_request_evidence_id != normalized.pull_request.id for item in items):
        raise BitbucketValidationError("changed-file observation PR context does not match normalized evidence")
    _require_unambiguous_changed_file_source_bindings(items)
    supplied_evidence = tuple(changed_file_evidence)
    supplied_provenance = tuple(changed_file_provenance)
    if not all(isinstance(item, Evidence) for item in supplied_evidence):
        raise BitbucketValidationError("changed_file_evidence must contain Evidence records")
    if not all(isinstance(item, ProvenanceRecord) for item in supplied_provenance):
        raise BitbucketValidationError("changed_file_provenance must contain provenance records")
    embedded_evidence = tuple(
        item.source_evidence for item in items if item.source_evidence is not None
    )
    embedded_provenance = tuple(
        item.provenance for item in items if item.provenance is not None
    )
    evidence_by_id = _index_records(
        (*normalized.evidence, *supplied_evidence, *embedded_evidence),
        "changed-file evidence",
    )
    provenance_by_id = _index_records(
        (*normalized.provenance, *supplied_provenance, *embedded_provenance),
        "changed-file provenance",
    )
    missing_evidence = [
        item.source_evidence_id for item in items
        if item.source_evidence_id not in evidence_by_id
    ]
    missing_provenance = [
        item.provenance_evidence_id for item in items
        if item.provenance_evidence_id not in provenance_by_id
    ]
    detached_provenance = [
        (item.source_evidence_id, item.provenance_evidence_id)
        for item in items
        if item.source_evidence_id in evidence_by_id
        and item.provenance_evidence_id in provenance_by_id
        and item.provenance_evidence_id not in evidence_by_id[item.source_evidence_id].provenance_ids
    ]
    if missing_evidence or missing_provenance or detached_provenance:
        raise BitbucketValidationError("changed-file source evidence/provenance is incomplete")
    invalid_bindings = [
        item.stable_file_id
        for item in items
        if not _is_exact_changed_file_source_binding(
            item,
            evidence_by_id.get(item.source_evidence_id),
            provenance_by_id.get(item.provenance_evidence_id),
            normalized.pull_request.pull_request_id,
        )
    ]
    if invalid_bindings:
        raise BitbucketValidationError("changed-file source evidence is not bound to its observation")
    mappings = adapt_openlore_result_to_changed_symbol_mappings(result, items)
    return replace(
        normalized,
        mappings=mappings or normalized.mappings,
        evidence=tuple(sorted(evidence_by_id.values(), key=lambda item: item.id)),
        provenance=tuple(sorted(provenance_by_id.values(), key=lambda item: item.id)),
    )


def _is_exact_changed_file_source_binding(
    observation: BitbucketChangedFileObservation,
    evidence: Evidence | None,
    provenance: ProvenanceRecord | None,
    pull_request_id: str | None = None,
) -> bool:
    """Verify IDs are bound to this exact changed-file fact, not merely linked."""

    if evidence is None or provenance is None:
        return False
    if evidence.id != observation.source_evidence_id:
        return False
    if not isinstance(evidence.locator, SourceArtifactLocator):
        return False
    artifact = evidence.locator.source_artifact_identity
    if artifact.artifact_type != "changed-file" or artifact.revision_or_version != observation.head_revision:
        return False
    properties = evidence.properties
    if (
        properties.get("source_mapping_id") != observation.stable_file_id
        or properties.get("file") != observation.file
        or properties.get("repository") != observation.repository_id
        or properties.get("head_revision") != observation.head_revision
        or (pull_request_id is not None and properties.get("pull_request_id") != pull_request_id)
    ):
        return False
    if provenance.id != observation.provenance_evidence_id:
        return False
    if provenance.source_artifact_identity != artifact:
        return False
    if provenance.id not in evidence.provenance_ids:
        return False
    # The evidence properties are mutable metadata, so the IDs and artifact
    # identity alone do not bind the path.  The adapter's external provenance
    # hash also covers the exact changed-file context; verify that binding
    # before allowing a later bridge result to cross this seam.
    expected_representation = json.dumps(
        {
            "artifact": artifact.as_dict(),
            "context": {
                "file": observation.file,
                "head_revision": observation.head_revision,
                "pull_request_id": pull_request_id or observation.pull_request_evidence_id,
                "repository": observation.repository_id,
                "source_mapping_id": observation.stable_file_id,
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        provenance.content_hash_algorithm == "sha256"
        and provenance.content_hash == hashlib.sha256(expected_representation.encode()).hexdigest()
    )


def _index_records(records: Sequence[Any], label: str) -> dict[str, Any]:
    """Index duplicate-equal records, but reject conflicting same-ID records."""

    indexed: dict[str, Any] = {}
    for record in records:
        previous = indexed.get(record.id)
        if previous is not None and previous != record:
            raise BitbucketValidationError(f"conflicting {label} identity")
        indexed[record.id] = record
    return indexed


# Explicit names used by source integrations and downstream seam tests.
adapt_changed_file_observations_to_openlore = observations_to_openlore_request
adapt_resolution_to_changed_symbol_mappings = adapt_openlore_result_to_changed_symbol_mappings
adapt_resolution_to_normalized_pull_request_evidence = adapt_openlore_result_to_normalized_pull_request_evidence
normalize_bitbucket_pull_request = adapt_bitbucket_pull_request
