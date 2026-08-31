"""Provider-neutral source-artifact normalization boundary.

Adapters for Jira, Bitbucket, and Graphify must translate provider responses
into this value before creating graph records; provider payloads never cross
this boundary.
"""

from __future__ import annotations

from typing import Any

from engineering_kg.ontology import NormalizedSourceArtifact, SourceArtifactIdentity


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
