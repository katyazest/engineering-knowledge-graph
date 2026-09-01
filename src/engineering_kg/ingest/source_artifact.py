"""Provider-neutral source-artifact normalization boundary.

Adapters for Jira, Bitbucket, and Graphify must translate provider responses
into this value before creating graph records; provider payloads never cross
this boundary.
"""

from __future__ import annotations

import hashlib
from typing import Any

from engineering_kg.ontology import NormalizedSourceArtifact, ProvenanceKind, ProvenanceRecord, SourceArtifactIdentity


def normalize_source_artifact(
    *,
    source_type: str,
    source_identity: str,
    artifact_type: str,
    revision_or_version: str,
    stable_locator: str,
    navigation_detail: dict[str, Any] | None = None,
) -> NormalizedSourceArtifact:
    """Validate payload-safe identity before any producer emits graph data."""

    return NormalizedSourceArtifact(
        SourceArtifactIdentity(
            source_type, source_identity, artifact_type, revision_or_version, stable_locator
        ),
        dict(navigation_detail or {}),
    )


def external_provenance(
    artifact: NormalizedSourceArtifact,
    *,
    observed_at: str,
    useful_representation: bytes | str,
    extractor_id: str,
    extractor_version: str,
) -> ProvenanceRecord:
    """Construct the only retained representation of a normalized external input."""
    value = useful_representation.encode("utf-8") if isinstance(useful_representation, str) else useful_representation
    if not isinstance(value, bytes):
        raise ValueError("invalid-provenance: useful_representation must be bytes or text")
    return ProvenanceRecord(
        ProvenanceKind.EXTERNAL, observed_at, "sha256", hashlib.sha256(value).hexdigest(),
        extractor_id, extractor_version, artifact.identity,
    )
