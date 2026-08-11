from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
FIXTURES = REPO_ROOT / "tests" / "fixtures"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from engineering_kg.pipeline import run_pipeline
from engineering_kg.ingest.openspec import RegisteredOpenSpecStore


class PipelineRunnerSmokeTest(unittest.TestCase):
    def test_pipeline_returns_empty_deterministic_status(self) -> None:
        first = run_pipeline().as_dict()
        second = run_pipeline().as_dict()

        expected = {
            "configured_stage_count": 0,
            "configured_stages": [],
            "executed_stage_count": 0,
            "executed_stages": [],
            "graph": {
                "edge_count": 0,
                "edges": [],
                "evidence": [],
                "evidence_count": 0,
                "node_count": 0,
                "nodes": [],
            },
            "status": "completed",
        }

        self.assertEqual(first, expected)
        self.assertEqual(second, expected)

    def test_build_script_reports_empty_bootstrap_run(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC_ROOT)

        completed = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "build.py")],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertEqual(json.loads(completed.stdout), run_pipeline().as_dict())
        self.assertEqual(completed.stderr, "")

    def test_pipeline_executes_registry_stage_deterministically(self) -> None:
        registry_path = FIXTURES / "repo-index.yaml"

        first = run_pipeline(registry_path).as_dict()
        second = run_pipeline(registry_path).as_dict()

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["configured_stages"], ["workspace-registry"])
        self.assertEqual(first["executed_stages"], ["workspace-registry"])
        self.assertEqual(first["configured_stage_count"], 1)
        self.assertEqual(first["executed_stage_count"], 1)
        self.assertEqual(first["graph"]["node_count"], 5)
        self.assertEqual(first["graph"]["edge_count"], 4)
        self.assertEqual(first["graph"]["evidence_count"], 0)

    def test_build_script_accepts_registry_path(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC_ROOT)

        completed = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "build.py"),
                str(FIXTURES / "repo-index.yaml"),
            ],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )

        output = json.loads(completed.stdout)
        self.assertEqual(output, run_pipeline(FIXTURES / "repo-index.yaml").as_dict())
        self.assertEqual(output["configured_stages"], ["workspace-registry"])
        self.assertEqual(output["executed_stages"], ["workspace-registry"])
        self.assertEqual(completed.stderr, "")

    def test_pipeline_executes_registry_and_persistence_stages(self) -> None:
        registry_path = FIXTURES / "repo-index.yaml"

        with tempfile.TemporaryDirectory() as tmp:
            persistence_path = Path(tmp) / "ladybugdb"
            first = run_pipeline(registry_path, persistence_path=persistence_path).as_dict()
            second = run_pipeline(registry_path, persistence_path=persistence_path).as_dict()

        self.assertEqual(first, second)
        self.assertEqual(
            first["configured_stages"],
            ["workspace-registry", "ladybugdb-persistence"],
        )
        self.assertEqual(
            first["executed_stages"],
            ["workspace-registry", "ladybugdb-persistence"],
        )
        self.assertEqual(first["graph"]["node_count"], 5)
        self.assertEqual(first["graph"]["edge_count"], 4)
        self.assertEqual(first["graph"]["evidence_count"], 0)

    def test_pipeline_executes_workspace_openlore_source_stage(self) -> None:
        registry_path = FIXTURES / "repo-index-openlore-stage.yaml"

        first = run_pipeline(registry_path).as_dict()
        second = run_pipeline(registry_path).as_dict()

        self.assertEqual(first, second)
        self.assertEqual(
            first["configured_stages"],
            ["workspace-registry", "workspace-openlore-source"],
        )
        self.assertEqual(
            first["executed_stages"],
            ["workspace-registry", "workspace-openlore-source"],
        )
        self.assertEqual(first["configured_stage_count"], 2)
        self.assertEqual(first["executed_stage_count"], 2)
        self.assertEqual(first["graph"]["node_count"], 5)
        self.assertEqual(first["graph"]["edge_count"], 4)
        self.assertEqual(first["graph"]["evidence_count"], 0)
        self.assertEqual(first["openlore_source"]["status"], "valid")
        self.assertEqual(first["openlore_source"]["repository_count"], 1)

        serialized = str(first)
        for forbidden in (
            "source_code",
            "call_graph",
            "dependency_graph",
            "symbol_body",
            "architecture_analysis",
            "impact_analysis",
            "query_response",
            "credentials",
            "tokens",
            "api_response",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_pipeline_executes_openspec_store_source_stage(self) -> None:
        registry_path = (
            FIXTURES
            / "non-git-workspace"
            / "openspec"
            / "requirements_repo"
            / "repo-index-openspec-store-stage.yaml"
        )
        requirements_repo = registry_path.parent
        stores = (RegisteredOpenSpecStore("requirements-store", requirements_repo),)

        first = run_pipeline(registry_path, openspec_stores=stores).as_dict()
        second = run_pipeline(registry_path, openspec_stores=stores).as_dict()

        self.assertEqual(first, second)
        self.assertEqual(
            first["configured_stages"],
            ["workspace-registry", "openspec-store-source"],
        )
        self.assertEqual(
            first["executed_stages"],
            ["workspace-registry", "openspec-store-source"],
        )
        self.assertEqual(first["configured_stage_count"], 2)
        self.assertEqual(first["executed_stage_count"], 2)
        self.assertEqual(first["graph"]["node_count"], 6)
        self.assertEqual(first["graph"]["edge_count"], 5)
        self.assertEqual(first["openspec_store_source"]["status"], "valid")
        self.assertEqual(
            first["openspec_store_source"]["selection_source"],
            "registered-store",
        )
        self.assertEqual(first["openspec_store_source"]["store_id"], "requirements-store")
        self.assertEqual(
            first["openspec_store_source"]["repository_path"],
            str(requirements_repo.resolve()),
        )

        serialized = str(first)
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

    def test_pipeline_preserves_registry_only_behavior_without_openspec_stage(self) -> None:
        registry_path = (
            FIXTURES / "non-git-workspace" / "openspec" / "requirements_repo" / "repo-index.yaml"
        )
        requirements_repo = registry_path.parent
        stores = (RegisteredOpenSpecStore("requirements-store", requirements_repo),)

        output = run_pipeline(registry_path, openspec_stores=stores).as_dict()

        self.assertEqual(output["configured_stages"], ["workspace-registry"])
        self.assertEqual(output["executed_stages"], ["workspace-registry"])
        self.assertNotIn("openspec_store_source", output)

    def test_pipeline_preserves_registry_only_side_effect_free_behavior(self) -> None:
        registry_path = FIXTURES / "repo-index.yaml"

        with tempfile.TemporaryDirectory() as tmp:
            persistence_path = Path(tmp) / "should-not-exist"
            output = run_pipeline(registry_path).as_dict()

            self.assertFalse(persistence_path.exists())

        self.assertEqual(output["configured_stages"], ["workspace-registry"])
        self.assertEqual(output["executed_stages"], ["workspace-registry"])

    def test_pipeline_rejects_invalid_workspace_openlore_source_stage(self) -> None:
        registry_path = FIXTURES / "repo-index-openlore-missing-index.yaml"

        with self.assertRaisesRegex(ValueError, "index_location"):
            run_pipeline(registry_path)

    def test_build_script_accepts_registry_and_persistence_path(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC_ROOT)

        with tempfile.TemporaryDirectory() as tmp:
            persistence_path = Path(tmp) / "ladybugdb"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "build.py"),
                    str(FIXTURES / "repo-index.yaml"),
                    "--persistence-path",
                    str(persistence_path),
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )

            output = json.loads(completed.stdout)

        self.assertEqual(
            output["configured_stages"],
            ["workspace-registry", "ladybugdb-persistence"],
        )
        self.assertEqual(
            output["executed_stages"],
            ["workspace-registry", "ladybugdb-persistence"],
        )
        self.assertEqual(completed.stderr, "")

    def test_build_script_reports_workspace_openlore_source_validation(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC_ROOT)

        completed = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "build.py"),
                str(FIXTURES / "repo-index-openlore-stage.yaml"),
            ],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )

        output = json.loads(completed.stdout)
        self.assertEqual(
            output["configured_stages"],
            ["workspace-registry", "workspace-openlore-source"],
        )
        self.assertEqual(
            output["executed_stages"],
            ["workspace-registry", "workspace-openlore-source"],
        )
        self.assertEqual(output["graph"]["node_count"], 5)
        self.assertEqual(output["graph"]["edge_count"], 4)
        self.assertEqual(output["openlore_source"]["status"], "valid")
        self.assertEqual(output["openlore_source"]["repository_count"], 1)
        self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
