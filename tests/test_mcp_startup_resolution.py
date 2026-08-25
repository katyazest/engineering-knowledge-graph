from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from engineering_kg.ingest.openspec import RegisteredOpenSpecStore
from engineering_kg.mcp.startup import (
    McpStartupOptions,
    McpStartupResolutionError,
    OpenSpecProjectContext,
    resolve_current_git_root,
    resolve_mcp_graph_store,
    resolve_openspec_project_context,
)


class McpStartupResolutionTest(unittest.TestCase):
    def test_graph_store_override_is_used_directly_and_wins_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph_store = root / "debug-store"

            result = resolve_mcp_graph_store(
                McpStartupOptions(
                    graph_store=graph_store,
                    registry=root / "should-not-load.yaml",
                    openspec_store="requirements",
                    cwd=root,
                ),
                store_discovery=_forbidden_discovery,
            )

            self.assertEqual(result.graph_store_path, graph_store.resolve())
            self.assertEqual(result.source, "graph-store-override")
            self.assertIsNone(result.registry_path)

    def test_registry_override_resolves_graph_store_from_workspace_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = _write_registry(root)

            result = resolve_mcp_graph_store(
                McpStartupOptions(registry=registry_path, openspec_store="ignored", cwd=root),
                store_discovery=_forbidden_discovery,
            )

            self.assertEqual(result.graph_store_path, (root / ".engineering-kg/ladybugdb").resolve())
            self.assertEqual(result.registry_path, registry_path.resolve())
            self.assertEqual(result.source, "registry-override")

    def test_openspec_store_override_resolves_registered_store_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store_path = root / "requirements"
            registry_path = _write_registry(root, store_path=store_path)

            result = resolve_mcp_graph_store(
                McpStartupOptions(openspec_store="requirements", cwd=root),
                store_discovery=lambda: [RegisteredOpenSpecStore("requirements", store_path)],
            )

            self.assertEqual(result.graph_store_path, (root / ".engineering-kg/ladybugdb").resolve())
            self.assertEqual(result.registry_path, registry_path.resolve())
            self.assertEqual(result.openspec_store_id, "requirements")
            self.assertEqual(result.source, "openspec-store-override")

    def test_automatic_context_uses_project_store_and_validates_git_membership(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store_path = root / "requirements"
            code_repo = root / "services/payment-service"
            _write_registry(root, store_path=store_path, code_repo=code_repo)

            result = resolve_mcp_graph_store(
                McpStartupOptions(
                    cwd=code_repo,
                    openspec_command="/opt/tools/openspec",
                    git_command="/usr/bin/git",
                ),
                openspec_context_resolver=lambda cwd, command: OpenSpecProjectContext(store_id="requirements"),
                store_discovery=lambda: [RegisteredOpenSpecStore("requirements", store_path)],
                git_root_resolver=lambda cwd, command: code_repo,
            )

            self.assertEqual(result.graph_store_path, (root / ".engineering-kg/ladybugdb").resolve())
            self.assertEqual(result.source, "openspec-project-context")

    def test_automatic_context_can_use_root_path_when_store_id_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store_path = root / "requirements"
            _write_registry(root, store_path=store_path)

            result = resolve_mcp_graph_store(
                McpStartupOptions(
                    cwd=store_path,
                    openspec_command="/opt/tools/openspec",
                    git_command="/usr/bin/git",
                ),
                openspec_context_resolver=lambda cwd, command: OpenSpecProjectContext(root_path=store_path),
                store_discovery=_forbidden_discovery,
                git_root_resolver=lambda cwd, command: store_path,
            )

            self.assertEqual(result.graph_store_path, (root / ".engineering-kg/ladybugdb").resolve())

    def test_automatic_context_failure_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(McpStartupResolutionError, "openspec/config.yaml"):
                resolve_mcp_graph_store(
                    McpStartupOptions(cwd=tmp, openspec_command="/opt/tools/openspec"),
                    openspec_context_resolver=lambda cwd, command: OpenSpecProjectContext(),
                )

    def test_missing_registered_store_failure_names_store_without_sensitive_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(McpStartupResolutionError, "missing-store"):
                resolve_mcp_graph_store(
                    McpStartupOptions(openspec_store="missing-store", cwd=tmp),
                    store_discovery=lambda: [],
                )

    def test_missing_registry_in_selected_store_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store_path = root / "requirements"
            store_path.mkdir()

            with self.assertRaisesRegex(McpStartupResolutionError, "repo-index.yaml"):
                resolve_mcp_graph_store(
                    McpStartupOptions(openspec_store="requirements", cwd=root),
                    store_discovery=lambda: [RegisteredOpenSpecStore("requirements", store_path)],
                )

    def test_automatic_context_rejects_current_repository_outside_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store_path = root / "requirements"
            other_repo = root / "other"
            _write_registry(root, store_path=store_path)

            with self.assertRaisesRegex(McpStartupResolutionError, "not part of the selected Engineering workspace"):
                resolve_mcp_graph_store(
                    McpStartupOptions(
                        cwd=other_repo,
                        openspec_command="/opt/tools/openspec",
                        git_command="/usr/bin/git",
                    ),
                    openspec_context_resolver=lambda cwd, command: OpenSpecProjectContext(store_id="requirements"),
                    store_discovery=lambda: [RegisteredOpenSpecStore("requirements", store_path)],
                    git_root_resolver=lambda cwd, command: other_repo,
                )

    def test_automatic_context_requires_absolute_openspec_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(McpStartupResolutionError, "OpenSpec command path is required"):
                resolve_mcp_graph_store(McpStartupOptions(cwd=tmp))

            with self.assertRaisesRegex(McpStartupResolutionError, "must be absolute"):
                resolve_mcp_graph_store(McpStartupOptions(cwd=tmp, openspec_command="openspec"))

    def test_automatic_context_requires_absolute_git_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store_path = root / "requirements"
            _write_registry(root, store_path=store_path)

            with self.assertRaisesRegex(McpStartupResolutionError, "Git command path is required"):
                resolve_mcp_graph_store(
                    McpStartupOptions(cwd=store_path, openspec_command="/usr/local/bin/openspec"),
                    openspec_context_resolver=lambda cwd, command: OpenSpecProjectContext(root_path=store_path),
                    store_discovery=_forbidden_discovery,
                )

            with self.assertRaisesRegex(McpStartupResolutionError, "must be absolute"):
                resolve_mcp_graph_store(
                    McpStartupOptions(
                        cwd=store_path,
                        openspec_command="/usr/local/bin/openspec",
                        git_command="git",
                    ),
                    openspec_context_resolver=lambda cwd, command: OpenSpecProjectContext(root_path=store_path),
                    store_discovery=_forbidden_discovery,
                )

    def test_command_runners_use_configured_absolute_commands(self) -> None:
        cwd = Path("/workspace/repo")

        with patch("engineering_kg.mcp.startup.subprocess.run") as run:
            run.return_value.stdout = '{"root": {"path": "/workspace/requirements"}}'

            context = resolve_openspec_project_context(cwd, "/opt/tools/openspec")

        self.assertEqual(context.root_path, Path("/workspace/requirements"))
        self.assertEqual(run.call_args.args[0][0], "/opt/tools/openspec")

        with patch("engineering_kg.mcp.startup.subprocess.run") as run:
            run.return_value.stdout = "/workspace/repo\n"

            git_root = resolve_current_git_root(cwd, "/usr/bin/git")

        self.assertEqual(git_root, cwd)
        self.assertEqual(run.call_args.args[0][0], "/usr/bin/git")


def _write_registry(
    root: Path,
    *,
    store_path: Path | None = None,
    code_repo: Path | None = None,
) -> Path:
    store = store_path or root / "requirements"
    code = code_repo or root / "services/payment-service"
    store.mkdir(parents=True, exist_ok=True)
    code.mkdir(parents=True, exist_ok=True)
    registry_path = store / "repo-index.yaml"
    registry_path.write_text(
        f"""version: 1

workspace:
  id: test-workspace
  name: Test Workspace

layout:
  root_path: {root}
  openlore_path: .openlore

engineering_kg:
  enabled: true
  store_repository: requirements
  output_path: .engineering-kg/ladybugdb
  pipeline_stages:
    - workspace-registry

openlore:
  federation_enabled: true
  freshness_policy: validate-only

repositories:
  - id: requirements
    path: {store}
    description: Requirements repository.
    ssh_url: git@example.internal:PROJECT/requirements.git
    default_branch: main
    role: requirements
    exploration:
      include_by_default: true
      search_exclusions:
        - .git
    git:
      dirty_worktree: read-with-warning
      fetch: forbidden
      pull: forbidden
      pull_requires_default_branch: true

  - id: payment-service
    path: {code}
    description: Payment service repository.
    ssh_url: git@example.internal:PROJECT/payment-service.git
    default_branch: main
    role: code
    service:
      id: payment-service
      name: Payment Service
    exploration:
      include_by_default: true
      search_exclusions:
        - .git
    git:
      dirty_worktree: read-with-warning
      fetch: forbidden
      pull: forbidden
      pull_requires_default_branch: true
""",
        encoding="utf-8",
    )
    return registry_path


def _forbidden_discovery():
    raise AssertionError("store discovery must not be called")


if __name__ == "__main__":
    unittest.main()
