"""Workspace-level OpenLore source validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engineering_kg.project import WorkspaceRegistry


class OpenLoreSourceValidationError(ValueError):
    """Raised when workspace OpenLore source configuration is invalid."""


@dataclass(frozen=True)
class OpenLoreRepositoryReference:
    """Deterministic metadata for a repository included in OpenLore federation."""

    repository_id: str
    index_location: str
    resolved_index_path: Path

    def as_dict(self) -> dict[str, Any]:
        return {
            "index_location": self.index_location,
            "repository_id": self.repository_id,
            "resolved_index_path": str(self.resolved_index_path),
        }


@dataclass(frozen=True)
class OpenLoreSourceValidationResult:
    """Deterministic result for workspace OpenLore source validation."""

    status: str
    source_path: Path
    federation_enabled: bool
    freshness_policy: str
    repositories: tuple[OpenLoreRepositoryReference, ...]

    @property
    def repository_count(self) -> int:
        return len(self.repositories)

    def as_dict(self) -> dict[str, Any]:
        return {
            "federation_enabled": self.federation_enabled,
            "freshness_policy": self.freshness_policy,
            "repository_count": self.repository_count,
            "repositories": [repo.as_dict() for repo in self.repositories],
            "source_path": str(self.source_path),
            "status": self.status,
        }


def validate_workspace_openlore_source(
    registry: WorkspaceRegistry,
) -> OpenLoreSourceValidationResult:
    """Validate local OpenLore source references without reading code graph contents."""

    source_path = registry.layout.resolved_openlore_path
    if not _is_within_or_equal(source_path, registry.layout.resolved_root_path):
        raise OpenLoreSourceValidationError(
            "layout.openlore_path must resolve under the workspace root"
        )

    for repo in registry.repositories:
        if _is_within_or_equal(source_path, repo.resolved_path):
            raise OpenLoreSourceValidationError(
                "layout.openlore_path must resolve outside configured repository roots"
            )

    repositories: tuple[OpenLoreRepositoryReference, ...] = ()
    if registry.openlore.federation_enabled:
        repositories = tuple(
            _repository_reference(repo) for repo in sorted(registry.federation_repositories(), key=lambda item: item.id)
        )

    return OpenLoreSourceValidationResult(
        status="valid",
        source_path=source_path,
        federation_enabled=registry.openlore.federation_enabled,
        freshness_policy=registry.openlore.freshness_policy,
        repositories=repositories,
    )


def _repository_reference(repo: Any) -> OpenLoreRepositoryReference:
    index_location = repo.openlore.index_location
    if not index_location.strip():
        raise OpenLoreSourceValidationError(
            f"repositories[{repo.id}].openlore.index_location must be non-empty "
            "when included in federation"
        )
    return OpenLoreRepositoryReference(
        repository_id=repo.id,
        index_location=index_location,
        resolved_index_path=_resolve_path(repo.resolved_path, index_location),
    )


def _resolve_path(base_path: Path, path: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = base_path / candidate
    return candidate.resolve()


def _is_within_or_equal(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
    except ValueError:
        return False
    return True
