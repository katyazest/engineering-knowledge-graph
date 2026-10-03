"""Pure, query-time evidence-use result DTO and deterministic evaluator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ALLOWED_REASONS = frozenset({"unknown", "stale", "conflicting", "candidate", "inferred"})


@dataclass(frozen=True)
class EvidenceUseResult:
    disposition: str
    reason_codes: tuple[str, ...]
    references: tuple[tuple[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {"disposition": self.disposition, "reason_codes": list(self.reason_codes),
                **{key: value for key, value in self.references}}


def evaluate_evidence_use(
    *,
    eligible: bool,
    reason_codes: tuple[str, ...] | list[str] = (),
    **references: Any,
) -> EvidenceUseResult:
    """Build deterministic safe policy output without mutating graph state."""
    reasons = tuple(sorted(set(reason_codes)))
    if any(reason not in ALLOWED_REASONS for reason in reasons):
        raise ValueError("unsupported evidence-use reason")
    disposition = "supported" if eligible and not reasons else "unresolved"
    if disposition == "unresolved" and not reasons:
        reasons = ("unknown",)
    ordered_references = tuple((key, references[key]) for key in sorted(references))
    return EvidenceUseResult(disposition, reasons, ordered_references)
