"""Local workspace registry loader for evolved repo-index.yaml files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from engineering_kg.ontology import Edge, EdgeKind, GraphSnapshot, Node, NodeKind, stable_id


class RegistryValidationError(ValueError):
    """Raised when a workspace registry is structurally invalid."""


FORBIDDEN_FIELDS = frozenset(
    {
        "architecture",
        "architecture_relationships",
        "bitbucket_data",
        "code_structure",
        "generated_documentation",
        "implementation_details",
        "jira_data",
        "openspec_requirements",
    }
)

REPOSITORY_ROLES = frozenset(
    {"requirements", "code", "configuration", "infrastructure", "library", "test", "other"}
)

GIT_DIRTY_WORKTREE_POLICIES = frozenset({"skip", "read-with-warning"})
GIT_REMOTE_POLICIES = frozenset({"allowed", "forbidden"})


@dataclass(frozen=True)
class WorkspaceIdentity:
    id: str
    name: str
    description: str = ""


@dataclass(frozen=True)
class WorkspaceLayout:
    root_path: str = "."
    openlore_path: str = ".openlore"
    resolved_root_path: Path = Path()
    resolved_openlore_path: Path = Path()
    resolved_graph_store_path: Path = Path()
    explicit: bool = False


@dataclass(frozen=True)
class EngineeringKgConfig:
    enabled: bool = True
    store_repository: str = "requirements"
    pipeline_stages: tuple[str, ...] = ("workspace-registry",)
    output_path: str = ".engineering-kg/ladybugdb"


@dataclass(frozen=True)
class OpenLoreConfig:
    federation_enabled: bool = True
    freshness_policy: str = "validate-only"


@dataclass(frozen=True)
class RepositoryExploration:
    include_by_default: bool
    search_exclusions: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True)
class GitPolicy:
    dirty_worktree: str
    fetch: str
    pull: str
    pull_requires_default_branch: bool
    branch_rule: str = ""


@dataclass(frozen=True)
class RepositoryOpenLoreConfig:
    include_in_federation: bool = False
    index_location: str = ""


@dataclass(frozen=True)
class RepositoryEntry:
    id: str
    path: str
    resolved_path: Path
    description: str
    ssh_url: str
    default_branch: str
    role: str
    exploration: RepositoryExploration
    git: GitPolicy
    service_id: str | None = None
    service_name: str | None = None
    openlore: RepositoryOpenLoreConfig = field(default_factory=RepositoryOpenLoreConfig)


@dataclass(frozen=True)
class WorkspaceRegistry:
    version: int
    source_path: Path
    workspace: WorkspaceIdentity
    layout: WorkspaceLayout
    engineering_kg: EngineeringKgConfig
    openlore: OpenLoreConfig
    repositories: tuple[RepositoryEntry, ...]

    def federation_repositories(self) -> tuple[RepositoryEntry, ...]:
        return tuple(repo for repo in self.repositories if repo.openlore.include_in_federation)

    def to_graph_snapshot(self) -> GraphSnapshot:
        workspace_node = Node(
            id=stable_id("node", NodeKind.WORKSPACE, self.workspace.id),
            kind=NodeKind.WORKSPACE,
            name=self.workspace.name,
            properties={
                "description": self.workspace.description,
                "engineering_kg": {
                    "enabled": self.engineering_kg.enabled,
                    "output_path": self.engineering_kg.output_path,
                    "resolved_graph_store_path": str(self.layout.resolved_graph_store_path),
                    "pipeline_stages": self.engineering_kg.pipeline_stages,
                    "store_repository": self.engineering_kg.store_repository,
                },
                "layout": {
                    "openlore_path": self.layout.openlore_path,
                    "resolved_openlore_path": str(self.layout.resolved_openlore_path),
                    "resolved_root_path": str(self.layout.resolved_root_path),
                    "root_path": self.layout.root_path,
                },
                "openlore": {
                    "federation_enabled": self.openlore.federation_enabled,
                    "freshness_policy": self.openlore.freshness_policy,
                },
            },
        )

        nodes: list[Node] = [workspace_node]
        edges: list[Edge] = []

        for repo in sorted(self.repositories, key=lambda item: item.id):
            repository_node = Node(
                id=stable_id("node", NodeKind.REPOSITORY, repo.id),
                kind=NodeKind.REPOSITORY,
                name=repo.id,
                properties={
                    "default_branch": repo.default_branch,
                    "description": repo.description,
                    "path": repo.path,
                    "resolved_path": str(repo.resolved_path),
                    "role": repo.role,
                    "ssh_url": repo.ssh_url,
                    "openlore": {
                        "include_in_federation": repo.openlore.include_in_federation,
                        "index_location": repo.openlore.index_location,
                    },
                },
            )
            nodes.append(repository_node)
            edges.append(
                Edge(
                    id=stable_id("edge", EdgeKind.CONTAINS, workspace_node.id, repository_node.id),
                    kind=EdgeKind.CONTAINS,
                    source_id=workspace_node.id,
                    target_id=repository_node.id,
                )
            )

            if repo.service_id:
                service_node = Node(
                    id=stable_id("node", NodeKind.SERVICE, repo.service_id),
                    kind=NodeKind.SERVICE,
                    name=repo.service_name or repo.service_id,
                    properties={"repository_id": repo.id},
                )
                nodes.append(service_node)
                edges.append(
                    Edge(
                        id=stable_id("edge", EdgeKind.OWNS, service_node.id, repository_node.id),
                        kind=EdgeKind.OWNS,
                        source_id=service_node.id,
                        target_id=repository_node.id,
                    )
                )

        return GraphSnapshot(nodes=tuple(nodes), edges=tuple(edges), evidence=())


def load_workspace_registry(path: str | Path) -> WorkspaceRegistry:
    registry_path = Path(path).expanduser().resolve()
    with registry_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    if not isinstance(raw, dict):
        raise RegistryValidationError("Workspace registry must be a mapping")

    _reject_forbidden_fields(raw)
    return _parse_registry(raw, registry_path)


def _parse_registry(raw: dict[str, Any], registry_path: Path) -> WorkspaceRegistry:
    _require_keys(raw, ("version", "workspace", "repositories"), "registry")
    version = raw["version"]
    if version != 1:
        raise RegistryValidationError("Workspace registry version must be 1")

    workspace = _parse_workspace(_expect_mapping(raw["workspace"], "workspace"))
    engineering_kg = _parse_engineering_kg(
        _expect_mapping(raw.get("engineering_kg", {}), "engineering_kg")
    )
    layout = _parse_layout(
        raw.get("layout"),
        registry_path.parent,
        engineering_kg.output_path,
    )
    openlore = _parse_openlore(_expect_mapping(raw.get("openlore", {}), "openlore"))
    repositories = _parse_repositories(raw["repositories"], registry_path.parent)
    _validate_store_repository(engineering_kg, repositories)
    _validate_workspace_layout(layout, engineering_kg, repositories)
    _validate_service_topology(repositories)

    return WorkspaceRegistry(
        version=version,
        source_path=registry_path,
        workspace=workspace,
        layout=layout,
        engineering_kg=engineering_kg,
        openlore=openlore,
        repositories=tuple(repositories),
    )


def _parse_workspace(raw: dict[str, Any]) -> WorkspaceIdentity:
    _require_keys(raw, ("name",), "workspace")
    name = _expect_string(raw["name"], "workspace.name")
    workspace_id = _expect_string(raw.get("id", name), "workspace.id")
    return WorkspaceIdentity(
        id=workspace_id,
        name=name,
        description=_expect_optional_string(raw.get("description", ""), "workspace.description"),
    )


def _parse_engineering_kg(raw: dict[str, Any]) -> EngineeringKgConfig:
    return EngineeringKgConfig(
        enabled=_expect_bool(raw.get("enabled", True), "engineering_kg.enabled"),
        store_repository=_expect_string(
            raw.get("store_repository", "requirements"),
            "engineering_kg.store_repository",
        ),
        pipeline_stages=_expect_string_tuple(
            raw.get("pipeline_stages", ["workspace-registry"]),
            "engineering_kg.pipeline_stages",
        ),
        output_path=_expect_string(
            raw.get("output_path", ".engineering-kg/ladybugdb"),
            "engineering_kg.output_path",
        ),
    )


def _parse_layout(raw: Any, registry_base_path: Path, graph_store_path: str) -> WorkspaceLayout:
    explicit = raw is not None
    data = _expect_mapping(raw, "layout") if explicit else {}
    root_path = _expect_string(data.get("root_path", "."), "layout.root_path")
    openlore_path = _expect_string(data.get("openlore_path", ".openlore"), "layout.openlore_path")
    resolved_root_path = _resolve_path(registry_base_path, root_path)
    resolved_openlore_path = _resolve_path(resolved_root_path, openlore_path)
    resolved_graph_store_path = _resolve_path(resolved_root_path, graph_store_path)
    return WorkspaceLayout(
        root_path=root_path,
        openlore_path=openlore_path,
        resolved_root_path=resolved_root_path,
        resolved_openlore_path=resolved_openlore_path,
        resolved_graph_store_path=resolved_graph_store_path,
        explicit=explicit,
    )


def _parse_openlore(raw: dict[str, Any]) -> OpenLoreConfig:
    return OpenLoreConfig(
        federation_enabled=_expect_bool(
            raw.get("federation_enabled", True),
            "openlore.federation_enabled",
        ),
        freshness_policy=_expect_string(
            raw.get("freshness_policy", "validate-only"),
            "openlore.freshness_policy",
        ),
    )


def _parse_repositories(raw: Any, base_path: Path) -> list[RepositoryEntry]:
    if not isinstance(raw, list) or not raw:
        raise RegistryValidationError("repositories must be a non-empty list")

    repositories = [_parse_repository(item, base_path, index) for index, item in enumerate(raw)]
    repository_ids = [repo.id for repo in repositories]
    if len(repository_ids) != len(set(repository_ids)):
        raise RegistryValidationError("repository ids must be unique")
    return repositories


def _parse_repository(raw: Any, base_path: Path, index: int) -> RepositoryEntry:
    context = f"repositories[{index}]"
    data = _expect_mapping(raw, context)
    _require_keys(
        data,
        (
            "id",
            "path",
            "description",
            "ssh_url",
            "default_branch",
            "role",
            "exploration",
            "git",
        ),
        context,
    )

    repo_id = _expect_string(data["id"], f"{context}.id")
    role = _expect_string(data["role"], f"{context}.role")
    if role not in REPOSITORY_ROLES:
        raise RegistryValidationError(f"{context}.role has unsupported value: {role}")

    repo_path = _expect_string(data["path"], f"{context}.path")
    resolved_path = _resolve_path(base_path, repo_path)
    service = _expect_mapping(data.get("service", {}), f"{context}.service")
    service_id = service_name = None
    if service:
        service_id = _expect_string(service.get("id"), f"{context}.service.id")
        service_name = _expect_string(service.get("name", service_id), f"{context}.service.name")

    return RepositoryEntry(
        id=repo_id,
        path=repo_path,
        resolved_path=resolved_path,
        description=_expect_string(data["description"], f"{context}.description"),
        ssh_url=_expect_ssh_url(data["ssh_url"], f"{context}.ssh_url"),
        default_branch=_expect_string(data["default_branch"], f"{context}.default_branch"),
        role=role,
        exploration=_parse_exploration(data["exploration"], context),
        git=_parse_git(data["git"], context),
        service_id=service_id,
        service_name=service_name,
        openlore=_parse_repository_openlore(data.get("openlore", {}), context),
    )


def _parse_exploration(raw: Any, context: str) -> RepositoryExploration:
    data = _expect_mapping(raw, f"{context}.exploration")
    _require_keys(data, ("include_by_default", "search_exclusions"), f"{context}.exploration")
    return RepositoryExploration(
        include_by_default=_expect_bool(
            data["include_by_default"], f"{context}.exploration.include_by_default"
        ),
        search_exclusions=_expect_string_tuple(
            data["search_exclusions"], f"{context}.exploration.search_exclusions"
        ),
        notes=_expect_optional_string(data.get("notes", ""), f"{context}.exploration.notes"),
    )


def _parse_git(raw: Any, context: str) -> GitPolicy:
    data = _expect_mapping(raw, f"{context}.git")
    _require_keys(
        data,
        ("dirty_worktree", "fetch", "pull", "pull_requires_default_branch"),
        f"{context}.git",
    )
    dirty_worktree = _expect_string(data["dirty_worktree"], f"{context}.git.dirty_worktree")
    fetch = _expect_string(data["fetch"], f"{context}.git.fetch")
    pull = _expect_string(data["pull"], f"{context}.git.pull")
    if dirty_worktree not in GIT_DIRTY_WORKTREE_POLICIES:
        raise RegistryValidationError(f"{context}.git.dirty_worktree has unsupported value")
    if fetch not in GIT_REMOTE_POLICIES:
        raise RegistryValidationError(f"{context}.git.fetch has unsupported value")
    if pull not in GIT_REMOTE_POLICIES:
        raise RegistryValidationError(f"{context}.git.pull has unsupported value")
    return GitPolicy(
        dirty_worktree=dirty_worktree,
        fetch=fetch,
        pull=pull,
        pull_requires_default_branch=_expect_bool(
            data["pull_requires_default_branch"],
            f"{context}.git.pull_requires_default_branch",
        ),
        branch_rule=_expect_optional_string(data.get("branch_rule", ""), f"{context}.git.branch_rule"),
    )


def _parse_repository_openlore(raw: Any, context: str) -> RepositoryOpenLoreConfig:
    data = _expect_mapping(raw, f"{context}.openlore")
    return RepositoryOpenLoreConfig(
        include_in_federation=_expect_bool(
            data.get("include_in_federation", False),
            f"{context}.openlore.include_in_federation",
        ),
        index_location=_expect_optional_string(
            data.get("index_location", ""),
            f"{context}.openlore.index_location",
        ),
    )


def _validate_store_repository(
    engineering_kg: EngineeringKgConfig, repositories: list[RepositoryEntry]
) -> None:
    repository_by_id = {repo.id: repo for repo in repositories}
    store_repository = repository_by_id.get(engineering_kg.store_repository)
    if store_repository is None:
        raise RegistryValidationError(
            f"engineering_kg.store_repository references unknown repository: "
            f"{engineering_kg.store_repository}"
        )
    if store_repository.role != "requirements":
        raise RegistryValidationError(
            "engineering_kg.store_repository must reference a repository with role requirements"
        )


def _validate_workspace_layout(
    layout: WorkspaceLayout,
    engineering_kg: EngineeringKgConfig,
    repositories: list[RepositoryEntry],
) -> None:
    if not layout.explicit:
        return

    repository_by_id = {repo.id: repo for repo in repositories}
    store_repository = repository_by_id[engineering_kg.store_repository]

    for repo in repositories:
        if repo is store_repository:
            continue
        if repo.role in {"code", "library"} and _is_within_or_equal(
            repo.resolved_path, store_repository.resolved_path
        ):
            raise RegistryValidationError(
                f"repositories[{repo.id}].path must not be inside the OpenSpec store repository"
            )

    generated_paths = {
        "layout.openlore_path": layout.resolved_openlore_path,
        "engineering_kg.output_path": layout.resolved_graph_store_path,
    }
    for context, generated_path in generated_paths.items():
        for repo in repositories:
            if _is_within_or_equal(generated_path, repo.resolved_path):
                raise RegistryValidationError(
                    f"{context} must resolve outside configured repository roots"
                )


def _validate_service_topology(repositories: list[RepositoryEntry]) -> None:
    service_to_repo: dict[str, str] = {}
    for repo in repositories:
        if not repo.service_id:
            continue
        previous = service_to_repo.setdefault(repo.service_id, repo.id)
        if previous != repo.id:
            raise RegistryValidationError(
                f"service '{repo.service_id}' is mapped to multiple repositories: "
                f"{previous}, {repo.id}"
            )


def _reject_forbidden_fields(value: Any, path: str = "registry") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_FIELDS:
                raise RegistryValidationError(f"{path}.{key_text} is not allowed in repo-index.yaml")
            _reject_forbidden_fields(nested, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_forbidden_fields(item, f"{path}[{index}]")


def _require_keys(data: dict[str, Any], keys: tuple[str, ...], context: str) -> None:
    for key in keys:
        if key not in data:
            raise RegistryValidationError(f"{context}.{key} is required")


def _expect_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RegistryValidationError(f"{context} must be a mapping")
    return value


def _expect_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegistryValidationError(f"{context} must be a non-empty string")
    return value


def _expect_optional_string(value: Any, context: str) -> str:
    if not isinstance(value, str):
        raise RegistryValidationError(f"{context} must be a string")
    return value


def _expect_ssh_url(value: Any, context: str) -> str:
    text = _expect_string(value, context)
    if not (text.startswith("ssh://") or text.startswith("git@")):
        raise RegistryValidationError(f"{context} must start with ssh:// or git@")
    return text


def _expect_bool(value: Any, context: str) -> bool:
    if not isinstance(value, bool):
        raise RegistryValidationError(f"{context} must be a boolean")
    return value


def _expect_string_tuple(value: Any, context: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise RegistryValidationError(f"{context} must be a list")
    return tuple(_expect_string(item, f"{context}[]") for item in value)


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
