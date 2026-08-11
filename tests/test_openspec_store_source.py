from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
FIXTURES = REPO_ROOT / "tests" / "fixtures"
NON_GIT_REQUIREMENTS = FIXTURES / "non-git-workspace" / "openspec" / "requirements_repo"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from engineering_kg.ingest.openspec import (
    OpenSpecStoreSourceValidationError,
    RegisteredOpenSpecStore,
    parse_registered_openspec_stores,
    validate_openspec_store_source,
)
from engineering_kg.project import load_workspace_registry


class OpenSpecStoreSourceTest(unittest.TestCase):
    def test_no_registered_stores_falls_back_to_requirements_repository(self) -> None:
        registry = _registry()

        result = validate_openspec_store_source(registry, registered_stores=()).as_dict()

        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["selection_source"], "registry-fallback")
        self.assertEqual(result["repository_id"], "requirements")
        self.assertEqual(result["repository_role"], "requirements")
        self.assertEqual(result["repository_path"], str(NON_GIT_REQUIREMENTS.resolve()))
        self.assertEqual(result["openspec_root_path"], str((NON_GIT_REQUIREMENTS / "openspec").resolve()))
        self.assertEqual(result["specs_path"], str((NON_GIT_REQUIREMENTS / "openspec/specs").resolve()))
        self.assertEqual(result["changes_path"], str((NON_GIT_REQUIREMENTS / "openspec/changes").resolve()))
        self.assertNotIn("store_id", result)

    def test_one_registered_store_matching_requirements_repository_is_selected(self) -> None:
        registry = _registry()
        store = RegisteredOpenSpecStore("requirements-store", NON_GIT_REQUIREMENTS)

        result = validate_openspec_store_source(registry, registered_stores=(store,)).as_dict()

        self.assertEqual(result["selection_source"], "registered-store")
        self.assertEqual(result["store_id"], "requirements-store")
        self.assertEqual(result["repository_id"], "requirements")

    def test_one_registered_store_not_matching_requirements_repository_requires_explicit_selection(self) -> None:
        registry = _registry()
        store = RegisteredOpenSpecStore("other-store", FIXTURES)

        with self.assertRaisesRegex(
            OpenSpecStoreSourceValidationError,
            "explicit store selection",
        ):
            validate_openspec_store_source(registry, registered_stores=(store,))

    def test_multiple_registered_stores_select_requirements_repository_match(self) -> None:
        registry = _registry()
        stores = (
            RegisteredOpenSpecStore("other-store", FIXTURES),
            RegisteredOpenSpecStore("requirements-store", NON_GIT_REQUIREMENTS),
        )

        result = validate_openspec_store_source(registry, registered_stores=stores).as_dict()

        self.assertEqual(result["selection_source"], "registered-store")
        self.assertEqual(result["store_id"], "requirements-store")
        self.assertEqual(result["repository_path"], str(NON_GIT_REQUIREMENTS.resolve()))

    def test_multiple_registered_stores_without_requirements_repository_match_requires_explicit_selection(
        self,
    ) -> None:
        registry = _registry()
        stores = (
            RegisteredOpenSpecStore("other-store-a", FIXTURES),
            RegisteredOpenSpecStore("other-store-b", REPO_ROOT),
        )

        with self.assertRaisesRegex(
            OpenSpecStoreSourceValidationError,
            "explicit store selection",
        ):
            validate_openspec_store_source(registry, registered_stores=stores)

    def test_explicit_registered_store_must_match_requirements_repository(self) -> None:
        registry = _registry()
        stores = (
            RegisteredOpenSpecStore("other-store", FIXTURES),
            RegisteredOpenSpecStore("requirements-store", NON_GIT_REQUIREMENTS),
        )

        with self.assertRaisesRegex(OpenSpecStoreSourceValidationError, "does not match"):
            validate_openspec_store_source(
                registry,
                registered_stores=stores,
                selected_store_id="other-store",
            )

    def test_parse_registered_store_list_config(self) -> None:
        stores = parse_registered_openspec_stores(
            {
                "stores": [
                    {
                        "id": "requirements-store",
                        "path": str(NON_GIT_REQUIREMENTS),
                    }
                ]
            }
        )

        self.assertEqual(stores, (RegisteredOpenSpecStore("requirements-store", NON_GIT_REQUIREMENTS.resolve()),))

    def test_missing_selected_store_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = _write_registry(Path(tmp), "missing-requirements")
            registry = load_workspace_registry(registry_path)

            with self.assertRaisesRegex(OpenSpecStoreSourceValidationError, "must exist"):
                validate_openspec_store_source(registry, registered_stores=())

    def test_missing_openspec_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requirements = root / "requirements"
            requirements.mkdir()
            registry = load_workspace_registry(_write_registry(root, "requirements"))

            with self.assertRaisesRegex(OpenSpecStoreSourceValidationError, "OpenSpec root"):
                validate_openspec_store_source(registry, registered_stores=())

    def test_missing_specs_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requirements = root / "requirements"
            (requirements / "openspec" / "changes").mkdir(parents=True)
            registry = load_workspace_registry(_write_registry(root, "requirements"))

            with self.assertRaisesRegex(OpenSpecStoreSourceValidationError, "specs"):
                validate_openspec_store_source(registry, registered_stores=())

    def test_missing_changes_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requirements = root / "requirements"
            (requirements / "openspec" / "specs").mkdir(parents=True)
            registry = load_workspace_registry(_write_registry(root, "requirements"))

            with self.assertRaisesRegex(OpenSpecStoreSourceValidationError, "changes"):
                validate_openspec_store_source(registry, registered_stores=())

    def test_validation_output_is_deterministic_and_excludes_content(self) -> None:
        registry = _registry()
        stores = (RegisteredOpenSpecStore("requirements-store", NON_GIT_REQUIREMENTS),)

        first = validate_openspec_store_source(registry, registered_stores=stores).as_dict()
        second = validate_openspec_store_source(registry, registered_stores=stores).as_dict()
        serialized = str(first)

        self.assertEqual(first, second)
        for forbidden in (
            "specification body",
            "change body",
            "source_code",
            "call_graph",
            "dependency_graph",
            "symbol_body",
            "generated_graph_records",
            "credentials",
            "tokens",
            "api_response",
        ):
            self.assertNotIn(forbidden, serialized)


def _registry():
    return load_workspace_registry(NON_GIT_REQUIREMENTS / "repo-index.yaml")


def _write_registry(root: Path, requirements_path: str) -> Path:
    registry_path = root / "repo-index.yaml"
    registry_path.write_text(
        f"""version: 1

workspace:
  id: test-workspace
  name: Test Workspace

layout:
  root_path: .
  openlore_path: .openlore

engineering_kg:
  enabled: true
  store_repository: requirements
  output_path: .engineering-kg/ladybugdb
  pipeline_stages:
    - workspace-registry

openlore:
  federation_enabled: false
  freshness_policy: validate-only

repositories:
  - id: requirements
    path: {requirements_path}
    description: Requirements repository.
    ssh_url: git@example.internal:TEAM/requirements.git
    default_branch: main
    role: requirements
    exploration:
      include_by_default: true
      search_exclusions: []
    git:
      dirty_worktree: read-with-warning
      fetch: forbidden
      pull: forbidden
      pull_requires_default_branch: true
""",
        encoding="utf-8",
    )
    return registry_path


if __name__ == "__main__":
    unittest.main()
