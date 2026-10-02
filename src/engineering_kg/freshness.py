"""Ephemeral, caller-attested source revision freshness assessment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping

from engineering_kg.ontology import Evidence, ProvenanceKind, ProvenanceRecord, SourceArtifactIdentity


@dataclass(frozen=True)
class CheckedSourceRevision:
    source_type: str
    source_identity: str
    artifact_type: str
    stable_locator: str
    revision_or_version: str
    checked_at: str

    def __post_init__(self) -> None:
        # Use the canonical identity validator without retaining its revision-bearing ID.
        SourceArtifactIdentity(self.source_type, self.source_identity, self.artifact_type,
                              self.revision_or_version, self.stable_locator)
        try:
            instant = datetime.fromisoformat(self.checked_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError) as exc:
            raise FreshnessInputError("checked_at must be an offset-aware ISO-8601 instant") from exc
        if instant.tzinfo is None:
            raise FreshnessInputError("checked_at must be an offset-aware ISO-8601 instant")

    @property
    def key(self) -> tuple[str, str, str, str]:
        return self.source_type, self.source_identity, self.artifact_type, self.stable_locator

    def as_dict(self) -> dict[str, str]:
        return {"artifact_type": self.artifact_type, "checked_at": self.checked_at,
                "revision_or_version": self.revision_or_version, "source_identity": self.source_identity,
                "source_type": self.source_type, "stable_locator": self.stable_locator}


class FreshnessInputError(ValueError):
    """Payload-safe invalid check input."""


@dataclass(frozen=True)
class FreshnessAssessment:
    status: str
    reason: str
    provenance_id: str
    checked_at: str | None = None
    input_assessments: tuple["FreshnessAssessment", ...] = ()
    valid: bool = True

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"provenance_id": self.provenance_id, "reason": self.reason,
                                  "status": self.status}
        if self.checked_at is not None:
            result["checked_at"] = self.checked_at
        if self.input_assessments:
            result["input_assessments"] = [item.as_dict() for item in self.input_assessments]
        return result


def normalize_checked_revisions(values: Iterable[CheckedSourceRevision | Mapping[str, Any]] | None) -> dict[tuple[str, str, str, str], CheckedSourceRevision]:
    checks: dict[tuple[str, str, str, str], CheckedSourceRevision] = {}
    for value in values or ():
        try:
            check = value if isinstance(value, CheckedSourceRevision) else CheckedSourceRevision(**dict(value))
        except FreshnessInputError:
            raise
        except (TypeError, ValueError, KeyError) as exc:
            raise FreshnessInputError("checked source revision must contain a complete safe artifact key, revision, and checked_at") from exc
        previous = checks.get(check.key)
        if previous is not None and previous != check:
            raise FreshnessInputError("conflicting checked source revisions for one artifact")
        checks[check.key] = check
    return checks


class FreshnessAssessor:
    def __init__(self, provenance: Mapping[str, ProvenanceRecord], checks: Mapping[tuple[str, str, str, str], CheckedSourceRevision]):
        self.provenance = provenance
        self.checks = checks
        self.memo: dict[str, FreshnessAssessment] = {}
        self.visiting: set[str] = set()

    def assess(self, provenance_id: str) -> FreshnessAssessment:
        if provenance_id in self.memo:
            return self.memo[provenance_id]
        record = self.provenance.get(provenance_id)
        if record is None or provenance_id in self.visiting:
            return FreshnessAssessment("unknown", "unresolved-provenance", provenance_id, valid=False)
        self.visiting.add(provenance_id)
        try:
            if record.kind is ProvenanceKind.EXTERNAL:
                result = self._external(record)
            else:
                children = tuple(self.assess(item) for item in record.input_provenance_ids)
                if not children or any(not item.valid for item in children):
                    result = FreshnessAssessment("unknown", "unresolved-provenance", provenance_id, input_assessments=children, valid=False)
                else:
                    status = "stale" if any(item.status == "stale" for item in children) else "unknown" if any(item.status == "unknown" for item in children) else "fresh"
                    result = FreshnessAssessment(status, "derived-input-status", provenance_id, input_assessments=children)
            self.memo[provenance_id] = result
            return result
        finally:
            self.visiting.discard(provenance_id)

    def _external(self, record: ProvenanceRecord) -> FreshnessAssessment:
        identity = record.source_artifact_identity
        if identity is None:
            return FreshnessAssessment("unknown", "invalid-provenance", record.id, valid=False)
        try:
            # Records can originate from legacy/unvalidated snapshots; only complete metadata
            # may participate in a comparison.
            SourceArtifactIdentity(identity.source_type, identity.source_identity, identity.artifact_type,
                                   identity.revision_or_version, identity.stable_locator)
            observed = datetime.fromisoformat(record.observed_at.replace("Z", "+00:00"))
            if observed.tzinfo is None or not all((record.content_hash, record.content_hash_algorithm,
                                                   record.extractor_id, record.extractor_version)):
                raise ValueError
        except (AttributeError, TypeError, ValueError):
            return FreshnessAssessment("unknown", "invalid-provenance", record.id, valid=False)
        key = (identity.source_type, identity.source_identity, identity.artifact_type, identity.stable_locator)
        check = self.checks.get(key)
        if check is None:
            return FreshnessAssessment("unknown", "no-check", record.id)
        checked = datetime.fromisoformat(check.checked_at.replace("Z", "+00:00"))
        if checked < observed:
            return FreshnessAssessment("unknown", "check-predates-observation", record.id, check.checked_at)
        status = "fresh" if check.revision_or_version == identity.revision_or_version else "stale"
        return FreshnessAssessment(status, "revision-match" if status == "fresh" else "revision-mismatch", record.id, check.checked_at)

    def evidence(self, evidence: Evidence) -> dict[str, Any]:
        chains = tuple(self.assess(item) for item in evidence.provenance_ids)
        if not chains:
            status = "unknown"
        elif any(item.status == "fresh" and item.valid for item in chains):
            status = "fresh"
        elif any(item.status == "unknown" for item in chains):
            status = "unknown"
        else:
            status = "stale"
        return {"current_evidence_eligible": status == "fresh" and any(item.valid for item in chains),
                "evidence_id": evidence.id, "provenance": [item.as_dict() for item in chains], "status": status}


def current_evidence_eligibility(evidence_ids: Iterable[str], evidence_by_id: Mapping[str, Evidence], assessor: FreshnessAssessor) -> dict[str, Any]:
    requested = tuple(evidence_ids)
    results = [assessor.evidence(evidence_by_id[item]) if item in evidence_by_id else
               {"current_evidence_eligible": False, "evidence_id": item, "provenance": [], "status": "unknown"}
               for item in requested]
    return {"eligible": bool(results) and all(item["current_evidence_eligible"] for item in results),
            "evidence": results, "ineligible_evidence_ids": [item["evidence_id"] for item in results if not item["current_evidence_eligible"]],
            "eligible_evidence_ids": [item["evidence_id"] for item in results if item["current_evidence_eligible"]]}
