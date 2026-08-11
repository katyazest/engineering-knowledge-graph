from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
FIXTURES = REPO_ROOT / "tests" / "fixtures"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from engineering_kg.openlore import (
    OpenLoreSourceValidationError,
    validate_workspace_openlore_source,
)
from engineering_kg.project import load_workspace_registry


class WorkspaceOpenLoreSourceTest(unittest.TestCase):
    def test_validation_resolves_explicit_workspace_openlore_source(self) -> None:
        registry = load_workspace_registry(FIXTURES / "repo-index-openlore-stage.yaml")

        result = validate_workspace_openlore_source(registry).as_dict()

        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["source_path"], str((FIXTURES / ".openlore").resolve()))
        self.assertTrue(result["federation_enabled"])
        self.assertEqual(result["freshness_policy"], "validate-only")
        self.assertEqual(result["repository_count"], 1)
        self.assertEqual(
            result["repositories"],
            [
                {
                    "index_location": ".openlore/index",
                    "repository_id": "payment-service",
                    "resolved_index_path": str(
                        (FIXTURES / "src/codebase_repos/payment-service/.openlore/index").resolve()
                    ),
                }
            ],
        )

    def test_validation_resolves_default_workspace_openlore_source(self) -> None:
        registry = load_workspace_registry(FIXTURES / "repo-index-default-openlore.yaml")

        result = validate_workspace_openlore_source(registry).as_dict()

        self.assertEqual(result["source_path"], str((FIXTURES / ".openlore").resolve()))

    def test_validation_rejects_openlore_source_inside_repository_root(self) -> None:
        registry = load_workspace_registry(FIXTURES / "repo-index.yaml")

        with self.assertRaisesRegex(
            OpenLoreSourceValidationError,
            "outside configured repository roots",
        ):
            validate_workspace_openlore_source(registry)

    def test_validation_rejects_missing_federation_index_reference(self) -> None:
        registry = load_workspace_registry(FIXTURES / "repo-index-openlore-missing-index.yaml")

        with self.assertRaisesRegex(OpenLoreSourceValidationError, "index_location"):
            validate_workspace_openlore_source(registry)

    def test_federation_disabled_skips_repository_index_requirements(self) -> None:
        registry = load_workspace_registry(FIXTURES / "repo-index-openlore-federation-disabled.yaml")

        result = validate_workspace_openlore_source(registry).as_dict()

        self.assertFalse(result["federation_enabled"])
        self.assertEqual(result["repository_count"], 0)
        self.assertEqual(result["repositories"], [])

    def test_validation_output_is_deterministic_and_excludes_code_graph_details(self) -> None:
        registry = load_workspace_registry(FIXTURES / "repo-index-openlore-stage.yaml")

        first = validate_workspace_openlore_source(registry).as_dict()
        second = validate_workspace_openlore_source(registry).as_dict()
        serialized = str(first)

        self.assertEqual(first, second)
        for forbidden in (
            "source_code",
            "call_graph",
            "dependency_graph",
            "class_body",
            "function_body",
            "symbol_body",
            "architecture_analysis",
            "impact_analysis",
            "query_response",
            "credentials",
            "tokens",
            "api_response",
        ):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
