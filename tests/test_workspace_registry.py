from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
FIXTURES = REPO_ROOT / "tests" / "fixtures"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from engineering_kg.ontology import NodeKind
from engineering_kg.project import RegistryValidationError, load_workspace_registry


class WorkspaceRegistryTest(unittest.TestCase):
    def test_valid_registry_loads_repository_inventory_and_configuration(self) -> None:
        registry = load_workspace_registry(FIXTURES / "repo-index.yaml")

        self.assertEqual(registry.version, 1)
        self.assertEqual(registry.workspace.id, "payments-workspace")
        self.assertEqual(registry.engineering_kg.store_repository, "requirements")
        self.assertEqual(registry.engineering_kg.pipeline_stages, ("workspace-registry",))
        self.assertTrue(registry.openlore.federation_enabled)
        self.assertEqual(len(registry.repositories), 3)

        payment_repo = next(repo for repo in registry.repositories if repo.id == "payment-service")
        self.assertEqual(payment_repo.role, "code")
        self.assertEqual(payment_repo.service_id, "payment-service")
        self.assertEqual(payment_repo.service_name, "Payment Service")
        self.assertTrue(payment_repo.openlore.include_in_federation)
        self.assertEqual(payment_repo.openlore.index_location, ".openlore/index")

    def test_evolved_schema_document_is_valid_json(self) -> None:
        schema = json.loads((REPO_ROOT / "docs" / "repo-index.schema.json").read_text())

        self.assertEqual(schema["title"], "Engineering KG workspace registry")
        self.assertIn("layout", schema["properties"])
        self.assertIn("engineering_kg", schema["properties"])
        self.assertIn("openlore", schema["properties"])
        self.assertIn("service", schema["$defs"]["repository"]["properties"])

    def test_valid_registry_fixtures_match_evolved_schema(self) -> None:
        schema = json.loads((REPO_ROOT / "docs" / "repo-index.schema.json").read_text())
        fixture_paths = [
            FIXTURES / "repo-index.yaml",
            FIXTURES / "non-git-workspace/openspec/requirements_repo/repo-index.yaml",
        ]

        for fixture_path in fixture_paths:
            with self.subTest(fixture=fixture_path.name):
                data = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
                _assert_matches_schema(self, data, schema, schema)

    def test_repository_paths_resolve_relative_to_registry_file(self) -> None:
        registry = load_workspace_registry(FIXTURES / "repo-index.yaml")

        requirements = next(repo for repo in registry.repositories if repo.id == "requirements")
        self.assertEqual(requirements.resolved_path, (FIXTURES / "..").resolve())

        payment_repo = next(repo for repo in registry.repositories if repo.id == "payment-service")
        self.assertEqual(payment_repo.resolved_path, (FIXTURES / "../../payment-service").resolve())

    def test_non_git_workspace_layout_resolves_generated_state_paths(self) -> None:
        registry_path = FIXTURES / "non-git-workspace/openspec/requirements_repo/repo-index.yaml"
        registry = load_workspace_registry(registry_path)
        workspace_root = (FIXTURES / "non-git-workspace").resolve()

        self.assertTrue(registry.layout.explicit)
        self.assertEqual(registry.layout.root_path, "../..")
        self.assertEqual(registry.layout.resolved_root_path, workspace_root)
        self.assertEqual(registry.layout.openlore_path, ".openlore")
        self.assertEqual(registry.layout.resolved_openlore_path, workspace_root / ".openlore")
        self.assertEqual(
            registry.layout.resolved_graph_store_path,
            workspace_root / ".engineering-kg/ladybugdb",
        )

        requirements = next(repo for repo in registry.repositories if repo.id == "requirements")
        payment_repo = next(repo for repo in registry.repositories if repo.id == "payment-service")

        self.assertEqual(requirements.resolved_path, registry_path.parent.resolve())
        self.assertEqual(
            payment_repo.resolved_path,
            workspace_root / "src/codebase_repos/payment-service",
        )

    def test_duplicate_service_mapping_is_rejected(self) -> None:
        with self.assertRaisesRegex(RegistryValidationError, "mapped to multiple repositories"):
            load_workspace_registry(FIXTURES / "repo-index-duplicate-service.yaml")

    def test_store_repository_must_have_requirements_role(self) -> None:
        with self.assertRaisesRegex(RegistryValidationError, "role requirements"):
            load_workspace_registry(FIXTURES / "repo-index-store-wrong-role.yaml")

    def test_code_repositories_must_not_be_nested_inside_openspec_store(self) -> None:
        with self.assertRaisesRegex(RegistryValidationError, "OpenSpec store repository"):
            load_workspace_registry(
                FIXTURES
                / "non-git-workspace/openspec/requirements_repo/repo-index-code-inside-store.yaml"
            )

    def test_workspace_graph_store_must_be_outside_repository_roots(self) -> None:
        with self.assertRaisesRegex(RegistryValidationError, "engineering_kg.output_path"):
            load_workspace_registry(
                FIXTURES
                / "non-git-workspace/openspec/requirements_repo/repo-index-graph-inside-repo.yaml"
            )

    def test_workspace_openlore_must_be_outside_repository_roots(self) -> None:
        with self.assertRaisesRegex(RegistryValidationError, "layout.openlore_path"):
            load_workspace_registry(
                FIXTURES
                / "non-git-workspace/openspec/requirements_repo/repo-index-openlore-inside-repo.yaml"
            )

    def test_forbidden_external_or_derived_fields_are_rejected(self) -> None:
        with self.assertRaisesRegex(RegistryValidationError, "jira_data"):
            load_workspace_registry(FIXTURES / "repo-index-forbidden-fields.yaml")

    def test_registry_converts_to_deterministic_graph_snapshot(self) -> None:
        registry = load_workspace_registry(FIXTURES / "repo-index.yaml")

        first = registry.to_graph_snapshot().as_dict()
        second = registry.to_graph_snapshot().as_dict()

        self.assertEqual(first, second)
        self.assertEqual(first["node_count"], 5)
        self.assertEqual(first["edge_count"], 4)
        self.assertEqual(first["evidence_count"], 0)
        self.assertEqual(first["nodes"][0]["kind"], NodeKind.WORKSPACE.value)

        repository_nodes = [
            node for node in first["nodes"] if node["kind"] == NodeKind.REPOSITORY.value
        ]
        service_nodes = [node for node in first["nodes"] if node["kind"] == NodeKind.SERVICE.value]

        self.assertEqual(len(repository_nodes), 3)
        self.assertEqual(len(service_nodes), 1)
        serialized = str(first)
        self.assertNotIn("source_code", serialized)
        self.assertNotIn("call_graph", serialized)

    def test_non_git_workspace_layout_converts_to_deterministic_graph_references(self) -> None:
        registry = load_workspace_registry(
            FIXTURES / "non-git-workspace/openspec/requirements_repo/repo-index.yaml"
        )

        first = registry.to_graph_snapshot().as_dict()
        second = registry.to_graph_snapshot().as_dict()
        workspace_node = first["nodes"][0]

        self.assertEqual(first, second)
        self.assertEqual(first["node_count"], 6)
        self.assertEqual(first["edge_count"], 5)
        self.assertEqual(workspace_node["properties"]["engineering_kg"]["store_repository"], "requirements")
        self.assertEqual(
            workspace_node["properties"]["layout"]["resolved_root_path"],
            str((FIXTURES / "non-git-workspace").resolve()),
        )
        self.assertEqual(
            workspace_node["properties"]["layout"]["resolved_openlore_path"],
            str((FIXTURES / "non-git-workspace/.openlore").resolve()),
        )
        self.assertEqual(
            workspace_node["properties"]["engineering_kg"]["resolved_graph_store_path"],
            str((FIXTURES / "non-git-workspace/.engineering-kg/ladybugdb").resolve()),
        )

        serialized = str(first)
        self.assertNotIn("source_code", serialized)
        self.assertNotIn("call_graph", serialized)
        self.assertNotIn("generated_graph_data", serialized)
        self.assertNotIn("ladybugdb_records", serialized)

    def test_federation_repositories_are_exposed_without_code_graph_details(self) -> None:
        registry = load_workspace_registry(FIXTURES / "repo-index.yaml")

        federation_repositories = registry.federation_repositories()

        self.assertEqual([repo.id for repo in federation_repositories], ["payment-service"])
        self.assertEqual(federation_repositories[0].openlore.index_location, ".openlore/index")

def _assert_matches_schema(
    test_case: unittest.TestCase,
    value: object,
    schema: dict[str, object],
    root_schema: dict[str, object],
    path: str = "$",
) -> None:
    if "$ref" in schema:
        schema = _resolve_schema_ref(schema["$ref"], root_schema)

    expected_type = schema.get("type")
    if expected_type is not None:
        _assert_schema_type(test_case, value, expected_type, path)

    if "const" in schema:
        test_case.assertEqual(value, schema["const"], path)

    if "enum" in schema:
        test_case.assertIn(value, schema["enum"], path)

    if "minLength" in schema and isinstance(value, str):
        test_case.assertGreaterEqual(len(value), schema["minLength"], path)

    if "pattern" in schema and isinstance(value, str):
        test_case.assertRegex(value, re.compile(str(schema["pattern"])), path)

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for key in required:
            test_case.assertIn(key, value, f"{path}.{key}")
        if schema.get("additionalProperties") is False:
            extra_keys = set(value) - set(properties)
            test_case.assertFalse(extra_keys, f"{path} has extra keys: {sorted(extra_keys)}")
        for key, nested_value in value.items():
            if key in properties:
                _assert_matches_schema(
                    test_case,
                    nested_value,
                    properties[key],
                    root_schema,
                    f"{path}.{key}",
                )

    if isinstance(value, list):
        if "minItems" in schema:
            test_case.assertGreaterEqual(len(value), schema["minItems"], path)
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                _assert_matches_schema(test_case, item, item_schema, root_schema, f"{path}[{index}]")


def _resolve_schema_ref(ref: object, root_schema: dict[str, object]) -> dict[str, object]:
    if ref != "#/$defs/repository":
        raise AssertionError(f"Unsupported schema ref: {ref}")
    defs = root_schema["$defs"]
    if not isinstance(defs, dict):
        raise AssertionError("Schema $defs must be a mapping")
    repository_schema = defs["repository"]
    if not isinstance(repository_schema, dict):
        raise AssertionError("Repository schema must be a mapping")
    return repository_schema


def _assert_schema_type(
    test_case: unittest.TestCase,
    value: object,
    expected_type: object,
    path: str,
) -> None:
    type_checks = {
        "array": lambda item: isinstance(item, list),
        "boolean": lambda item: isinstance(item, bool),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "object": lambda item: isinstance(item, dict),
        "string": lambda item: isinstance(item, str),
    }
    type_name = str(expected_type)
    if type_name not in type_checks:
        raise AssertionError(f"Unsupported schema type: {type_name}")
    test_case.assertTrue(type_checks[type_name](value), f"{path} must be {type_name}")


if __name__ == "__main__":
    unittest.main()
