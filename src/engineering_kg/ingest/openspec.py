"""OpenSpec store source validation for Engineering KG."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from engineering_kg.project import RepositoryEntry, WorkspaceRegistry


class OpenSpecStoreSourceValidationError(ValueError):
    """Raised when the OpenSpec store source cannot be validated."""


@dataclass(frozen=True)
class RegisteredOpenSpecStore:
    """Structured metadata for one locally registered OpenSpec store."""

    id: str
    path: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "path": str(self.path),
        }


@dataclass(frozen=True)
class OpenSpecStoreSourceValidationResult:
    """Deterministic result for OpenSpec store source validation."""

    status: str
    selection_source: str
    repository_id: str
    repository_role: str
    repository_path: Path
    openspec_root_path: Path
    specs_path: Path
    changes_path: Path
    store_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        data = {
            "changes_path": str(self.changes_path),
            "openspec_root_path": str(self.openspec_root_path),
            "repository_id": self.repository_id,
            "repository_path": str(self.repository_path),
            "repository_role": self.repository_role,
            "selection_source": self.selection_source,
            "specs_path": str(self.specs_path),
            "status": self.status,
        }
        if self.store_id:
            data["store_id"] = self.store_id
        return data


def discover_registered_openspec_stores() -> tuple[RegisteredOpenSpecStore, ...]:
    """Read locally registered OpenSpec stores through the OpenSpec CLI."""

    completed = subprocess.run(
        ["openspec", "store", "list", "--json"],
        text=True,
        capture_output=True,
        check=True,
    )
    return parse_registered_openspec_stores(json.loads(completed.stdout))


def parse_registered_openspec_stores(raw: Any) -> tuple[RegisteredOpenSpecStore, ...]:
    """Parse structured OpenSpec store list/config data into stable store records."""

    stores = raw.get("stores", raw) if isinstance(raw, dict) else raw
    if stores is None:
        stores = []
    if not isinstance(stores, list):
        raise OpenSpecStoreSourceValidationError("OpenSpec store discovery must be a list")

    parsed: list[RegisteredOpenSpecStore] = []
    for index, item in enumerate(stores):
        if not isinstance(item, dict):
            raise OpenSpecStoreSourceValidationError(
                f"OpenSpec store discovery entry {index} must be a mapping"
            )
        store_id = _store_id(item, index)
        store_path = _store_path(item, store_id)
        parsed.append(RegisteredOpenSpecStore(id=store_id, path=store_path))

    return tuple(parsed)


def validate_openspec_store_source(
    registry: WorkspaceRegistry,
    registered_stores: Iterable[RegisteredOpenSpecStore | dict[str, Any]] | None = None,
    selected_store_id: str | None = None,
) -> OpenSpecStoreSourceValidationResult:
    """Validate the OpenSpec store source without reading spec or change bodies."""

    requirements_repo = _requirements_repository(registry)
    stores = _normalized_registered_stores(registered_stores)

    if selected_store_id:
        selected = _select_explicit_store(stores, selected_store_id)
    elif stores:
        selected = _select_matching_registered_store(stores, requirements_repo)
    else:
        return _validate_selected_store(
            selection_source="registry-fallback",
            repository=requirements_repo,
            store_path=requirements_repo.resolved_path,
        )

    _require_matching_path(selected.path, requirements_repo)
    return _validate_selected_store(
        selection_source="registered-store",
        repository=requirements_repo,
        store_path=selected.path,
        store_id=selected.id,
    )


def _requirements_repository(registry: WorkspaceRegistry) -> RepositoryEntry:
    matches = [
        repo for repo in registry.repositories if repo.id == registry.engineering_kg.store_repository
    ]
    if len(matches) != 1:
        raise OpenSpecStoreSourceValidationError(
            "engineering_kg.store_repository must resolve to exactly one repository entry"
        )
    repository = matches[0]
    if repository.role != "requirements":
        raise OpenSpecStoreSourceValidationError(
            "engineering_kg.store_repository must reference a repository with role requirements"
        )
    return repository


def _normalized_registered_stores(
    stores: Iterable[RegisteredOpenSpecStore | dict[str, Any]] | None,
) -> tuple[RegisteredOpenSpecStore, ...]:
    if stores is None:
        return discover_registered_openspec_stores()

    normalized: list[RegisteredOpenSpecStore] = []
    for index, store in enumerate(stores):
        if isinstance(store, RegisteredOpenSpecStore):
            normalized.append(
                RegisteredOpenSpecStore(id=store.id, path=Path(store.path).expanduser().resolve())
            )
        elif isinstance(store, dict):
            normalized.append(RegisteredOpenSpecStore(id=_store_id(store, index), path=_store_path(store, str(index))))
        else:
            raise OpenSpecStoreSourceValidationError(
                f"OpenSpec store discovery entry {index} must be a registered store or mapping"
            )
    return tuple(normalized)


def _select_explicit_store(
    stores: tuple[RegisteredOpenSpecStore, ...],
    selected_store_id: str,
) -> RegisteredOpenSpecStore:
    for store in stores:
        if store.id == selected_store_id:
            return store
    raise OpenSpecStoreSourceValidationError(
        f"selected OpenSpec store id is not registered: {selected_store_id}"
    )


def _select_matching_registered_store(
    stores: tuple[RegisteredOpenSpecStore, ...],
    requirements_repo: RepositoryEntry,
) -> RegisteredOpenSpecStore:
    matches = [store for store in stores if _same_path(store.path, requirements_repo.resolved_path)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise OpenSpecStoreSourceValidationError(
            "multiple registered OpenSpec stores match the requirements repository; "
            "explicit store selection is required"
        )
    raise OpenSpecStoreSourceValidationError(
        "registered OpenSpec stores do not match the requirements repository; "
        "explicit store selection is required"
    )


def _require_matching_path(store_path: Path, requirements_repo: RepositoryEntry) -> None:
    if not _same_path(store_path, requirements_repo.resolved_path):
        raise OpenSpecStoreSourceValidationError(
            "registered OpenSpec store does not match the requirements repository; "
            "explicit store selection is required"
        )


def _validate_selected_store(
    selection_source: str,
    repository: RepositoryEntry,
    store_path: Path,
    store_id: str = "",
) -> OpenSpecStoreSourceValidationResult:
    resolved_store_path = Path(store_path).expanduser().resolve()
    if not resolved_store_path.is_dir():
        raise OpenSpecStoreSourceValidationError(
            f"OpenSpec store repository path must exist as a directory: {resolved_store_path}"
        )

    openspec_root = resolved_store_path / "openspec"
    if not openspec_root.is_dir():
        raise OpenSpecStoreSourceValidationError(
            f"OpenSpec root directory is missing: {openspec_root}"
        )

    specs_path = openspec_root / "specs"
    if not specs_path.is_dir():
        raise OpenSpecStoreSourceValidationError(
            f"OpenSpec specs directory is missing: {specs_path}"
        )

    changes_path = openspec_root / "changes"
    if not changes_path.is_dir():
        raise OpenSpecStoreSourceValidationError(
            f"OpenSpec changes directory is missing: {changes_path}"
        )

    return OpenSpecStoreSourceValidationResult(
        status="valid",
        selection_source=selection_source,
        store_id=store_id,
        repository_id=repository.id,
        repository_role=repository.role,
        repository_path=repository.resolved_path,
        openspec_root_path=openspec_root,
        specs_path=specs_path,
        changes_path=changes_path,
    )


def _store_id(item: dict[str, Any], index: int) -> str:
    value = item.get("id", item.get("name"))
    if not isinstance(value, str) or not value.strip():
        raise OpenSpecStoreSourceValidationError(
            f"OpenSpec store discovery entry {index} must contain a non-empty id"
        )
    return value


def _store_path(item: dict[str, Any], store_id: str) -> Path:
    value = (
        item.get("path")
        or item.get("root")
        or item.get("storePath")
        or item.get("store_path")
        or item.get("location")
    )
    if not isinstance(value, str) or not value.strip():
        raise OpenSpecStoreSourceValidationError(
            f"OpenSpec store discovery entry {store_id} must contain a non-empty path"
        )
    return Path(value).expanduser().resolve()


def _same_path(left: Path, right: Path) -> bool:
    return Path(left).expanduser().resolve() == Path(right).expanduser().resolve()
