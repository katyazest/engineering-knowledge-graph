from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
FIXTURES = REPO_ROOT / "tests" / "fixtures"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from engineering_kg.pipeline import run_pipeline
from engineering_kg.ingest.openspec import RegisteredOpenSpecStore
from engineering_kg.persistence import read_graph_snapshot
from engineering_kg.query import EngineeringKgQuery
from engineering_kg.validation import (
    GraphIntegrityValidationError,
    GraphValidationMetadata,
    GraphValidationResult,
)


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

    def test_pipeline_executes_openspec_graph_extraction_after_store_source(self) -> None:
        registry_path = (
            FIXTURES
            / "non-git-workspace"
            / "openspec"
            / "requirements_repo"
            / "repo-index-openspec-graph-stage.yaml"
        )
        requirements_repo = registry_path.parent
        stores = (RegisteredOpenSpecStore("requirements-store", requirements_repo),)

        first = run_pipeline(registry_path, openspec_stores=stores).as_dict()
        second = run_pipeline(registry_path, openspec_stores=stores).as_dict()

        self.assertEqual(first, second)
        self.assertEqual(
            first["configured_stages"],
            ["workspace-registry", "openspec-store-source", "openspec-graph-extraction"],
        )
        self.assertEqual(
            first["executed_stages"],
            ["workspace-registry", "openspec-store-source", "openspec-graph-extraction"],
        )
        self.assertEqual(first["openspec_graph_extraction"]["metadata"]["status"], "completed")
        self.assertEqual(
            first["openspec_graph_extraction"]["metadata"]["durable_spec_count"],
            3,
        )
        self.assertGreater(first["graph"]["node_count"], 6)
        self.assertTrue(
            any(node["kind"] == "openspec-spec" for node in first["graph"]["nodes"])
        )

        serialized = str(first)
        for forbidden in (
            "The system SHALL submit payments",
            "source_code",
            "openlore_analysis",
            "generated_graph_records",
            "credentials",
            "tokens",
            "api_response",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_pipeline_rejects_graph_extraction_without_store_source(self) -> None:
        registry_path = (
            FIXTURES
            / "non-git-workspace"
            / "openspec"
            / "requirements_repo"
            / "repo-index-openspec-graph-missing-source.yaml"
        )

        with self.assertRaisesRegex(ValueError, "openspec-store-source"):
            run_pipeline(registry_path, openspec_stores=())

    def test_build_script_reports_openspec_graph_extraction(self) -> None:
        registry_path = (
            FIXTURES
            / "non-git-workspace"
            / "openspec"
            / "requirements_repo"
            / "repo-index-openspec-graph-stage.yaml"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC_ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            fake_bin = Path(tmp) / "bin"
            fake_bin.mkdir()
            openspec = fake_bin / "openspec"
            openspec.write_text(
                "#!/bin/sh\nprintf '%s\\n' '{\"stores\":[{\"id\":\"requirements-store\",\"path\":\""
                + str(registry_path.parent)
                + "\"}]}'\n",
                encoding="utf-8",
            )
            openspec.chmod(0o755)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "build.py"),
                    str(registry_path),
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )

        output = json.loads(completed.stdout)
        self.assertEqual(
            output["executed_stages"],
            ["workspace-registry", "openspec-store-source", "openspec-graph-extraction"],
        )
        self.assertEqual(output["openspec_graph_extraction"]["metadata"]["status"], "completed")
        self.assertGreater(output["openspec_graph_extraction"]["metadata"]["graph_counts"]["node_count"], 0)
        self.assertEqual(completed.stderr, "")

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

    def test_pipeline_executes_graph_derivation_stage(self) -> None:
        registry_path = (
            FIXTURES
            / "non-git-workspace"
            / "openspec"
            / "requirements_repo"
            / "repo-index-graph-derivation-stage.yaml"
        )
        requirements_repo = registry_path.parent
        stores = (RegisteredOpenSpecStore("requirements-store", requirements_repo),)

        first = run_pipeline(registry_path, openspec_stores=stores).as_dict()
        second = run_pipeline(registry_path, openspec_stores=stores).as_dict()

        self.assertEqual(first, second)
        self.assertEqual(
            first["configured_stages"],
            [
                "workspace-registry",
                "openspec-store-source",
                "openspec-graph-extraction",
                "graph-derivation",
            ],
        )
        self.assertEqual(first["executed_stages"], first["configured_stages"])
        self.assertEqual(first["graph_derivation"]["metadata"]["status"], "completed")
        self.assertEqual(first["graph_derivation"]["metadata"]["derived_edge_count"], 4)
        self.assertTrue(
            any(edge["kind"] == "openspec-change-traces-to-spec" for edge in first["graph"]["edges"])
        )

    def test_pipeline_executes_validation_after_derivation(self) -> None:
        registry_path = (
            FIXTURES
            / "non-git-workspace"
            / "openspec"
            / "requirements_repo"
            / "repo-index-graph-derivation-validation-stage.yaml"
        )
        requirements_repo = registry_path.parent
        stores = (RegisteredOpenSpecStore("requirements-store", requirements_repo),)

        output = run_pipeline(registry_path, openspec_stores=stores).as_dict()

        self.assertEqual(
            output["executed_stages"],
            [
                "workspace-registry",
                "openspec-store-source",
                "openspec-graph-extraction",
                "graph-derivation",
                "graph-integrity-validation",
            ],
        )
        self.assertEqual(output["graph_integrity_validation"]["metadata"]["status"], "valid")
        self.assertEqual(
            output["graph_integrity_validation"]["metadata"]["severity_counts"],
            {"warning": 1},
        )

    def test_pipeline_executes_validation_without_derivation(self) -> None:
        registry_path = (
            FIXTURES
            / "non-git-workspace"
            / "openspec"
            / "requirements_repo"
            / "repo-index-graph-validation-stage.yaml"
        )
        requirements_repo = registry_path.parent
        stores = (RegisteredOpenSpecStore("requirements-store", requirements_repo),)

        output = run_pipeline(registry_path, openspec_stores=stores).as_dict()

        self.assertEqual(
            output["executed_stages"],
            [
                "workspace-registry",
                "openspec-store-source",
                "openspec-graph-extraction",
                "graph-integrity-validation",
            ],
        )
        self.assertNotIn("graph_derivation", output)
        self.assertEqual(output["graph_integrity_validation"]["metadata"]["status"], "valid")

    def test_pipeline_executes_empty_graph_derivation_deterministically(self) -> None:
        registry_path = (
            FIXTURES
            / "non-git-workspace"
            / "openspec"
            / "requirements_repo"
            / "repo-index-graph-empty-derivation-stage.yaml"
        )

        first = run_pipeline(registry_path, openspec_stores=()).as_dict()
        second = run_pipeline(registry_path, openspec_stores=()).as_dict()

        self.assertEqual(first, second)
        self.assertEqual(first["configured_stages"], ["graph-derivation"])
        self.assertEqual(first["executed_stages"], ["graph-derivation"])
        self.assertEqual(first["graph_derivation"]["metadata"]["derived_edge_count"], 0)
        self.assertEqual(first["graph"]["node_count"], 0)

    def test_pipeline_runs_persistence_readback_before_derivation(self) -> None:
        registry_path = (
            FIXTURES
            / "non-git-workspace"
            / "openspec"
            / "requirements_repo"
            / "repo-index-graph-derivation-stage.yaml"
        )
        requirements_repo = registry_path.parent
        stores = (RegisteredOpenSpecStore("requirements-store", requirements_repo),)

        with tempfile.TemporaryDirectory() as tmp:
            output = run_pipeline(
                registry_path,
                persistence_path=Path(tmp) / "ladybugdb",
                openspec_stores=stores,
            ).as_dict()

        self.assertEqual(
            output["configured_stages"],
            [
                "workspace-registry",
                "openspec-store-source",
                "openspec-graph-extraction",
                "ladybugdb-persistence",
                "graph-derivation",
            ],
        )
        self.assertEqual(output["executed_stages"], output["configured_stages"])
        self.assertEqual(output["graph_derivation"]["metadata"]["derived_edge_count"], 4)

    def test_pipeline_proves_complete_mvp_e2e_scenario(self) -> None:
        registry_path = (
            FIXTURES
            / "non-git-workspace"
            / "openspec"
            / "requirements_repo"
            / "repo-index-graph-derivation-validation-stage.yaml"
        )
        requirements_repo = registry_path.parent
        stores = (RegisteredOpenSpecStore("requirements-store", requirements_repo),)

        with tempfile.TemporaryDirectory() as first_tmp:
            first_store = Path(first_tmp) / "ladybugdb"
            first = run_pipeline(
                registry_path,
                persistence_path=first_store,
                openspec_stores=stores,
            )
            first_output = first.as_dict()
            persisted = read_graph_snapshot(first_store)
            persisted_query = EngineeringKgQuery.from_store(first_store)
            final_query = EngineeringKgQuery.from_snapshot(
                first.graph,
                validation=first.graph_integrity_validation,
            )

            persisted_requirements = persisted_query.list_requirements()
            persisted_services = persisted_query.list_services()
            persisted_changes = persisted_query.list_changes()
            persisted_active_change = next(
                item for item in persisted_changes if item["name"] == "JIRA-123-add-refund"
            )
            persisted_traceability = persisted_query.get_traceability(persisted_active_change["id"])
            final_changes = final_query.list_changes()
            active_change = next(
                item for item in final_changes if item["name"] == "JIRA-123-add-refund"
            )
            final_traceability = final_query.get_traceability(
                active_change["id"],
                require_validation=True,
            )

        with tempfile.TemporaryDirectory() as second_tmp:
            second_output = run_pipeline(
                registry_path,
                persistence_path=Path(second_tmp) / "ladybugdb",
                openspec_stores=stores,
            ).as_dict()

        self.assertEqual(first_output, second_output)
        self.assertEqual(
            first_output["configured_stages"],
            [
                "workspace-registry",
                "openspec-store-source",
                "openspec-graph-extraction",
                "ladybugdb-persistence",
                "graph-derivation",
                "graph-integrity-validation",
            ],
        )
        self.assertEqual(first_output["executed_stages"], first_output["configured_stages"])
        self.assertEqual(first_output["configured_stage_count"], 6)
        self.assertEqual(first_output["executed_stage_count"], 6)

        self.assertEqual(first_output["openspec_store_source"]["status"], "valid")
        self.assertEqual(
            first_output["openspec_graph_extraction"]["metadata"]["status"],
            "completed",
        )
        self.assertEqual(first_output["graph_derivation"]["metadata"]["status"], "completed")
        self.assertEqual(first_output["graph_derivation"]["metadata"]["derived_edge_count"], 4)
        self.assertEqual(
            first_output["graph_integrity_validation"]["metadata"]["status"],
            "valid",
        )
        self.assertEqual(first_output["graph"]["node_count"], 34)
        self.assertEqual(first_output["graph"]["edge_count"], 33)
        self.assertEqual(first_output["graph"]["evidence_count"], 28)

        persisted_output = persisted.as_dict()
        self.assertEqual(persisted_output["node_count"], 34)
        self.assertEqual(persisted_output["edge_count"], 29)
        self.assertEqual(persisted_output["evidence_count"], 28)
        self.assertEqual(
            [item["name"] for item in persisted_services],
            ["Payment Service", "Shared Model"],
        )
        self.assertEqual(
            [item["name"] for item in persisted_changes],
            ["JIRA-123-add-refund", "2026-08-01-JIRA-122-add-payments"],
        )
        self.assertEqual(len(persisted_requirements), 7)
        self.assertGreater(len(persisted_traceability["relationships"]), 0)
        self.assertTrue(
            any(
                item["kind"] == "openspec-change-traces-to-spec"
                for item in final_traceability["relationships"]
            )
        )
        self.assertFalse(final_traceability["missing"])

        serialized = str(
            {
                "pipeline": first_output,
                "persisted": persisted_output,
                "queries": {
                    "requirements": persisted_requirements,
                    "services": persisted_services,
                    "changes": persisted_changes,
                    "persisted_traceability": persisted_traceability,
                    "traceability": final_traceability,
                },
            }
        )
        for forbidden in (
            "source_code",
            "call_graph",
            "dependency_graph",
            "symbol_body",
            "openlore_analysis",
            "jira_payload",
            "bitbucket_payload",
            "confluence_content",
            "generated_graph_records",
            "credentials",
            "tokens",
            "api_response",
            "The system SHALL submit payments",
            "The system SHALL support refunds",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_pipeline_blocks_after_invalid_graph_integrity_validation(self) -> None:
        registry_path = (
            FIXTURES
            / "non-git-workspace"
            / "openspec"
            / "requirements_repo"
            / "repo-index-graph-validation-stage.yaml"
        )
        invalid_result = GraphValidationResult(
            status="invalid",
            metadata=GraphValidationMetadata(status="invalid", severity_counts={"error": 1}),
        )

        with patch("engineering_kg.pipeline.validate_graph_integrity", return_value=invalid_result):
            with self.assertRaises(GraphIntegrityValidationError) as caught:
                run_pipeline(registry_path, openspec_stores=())

        self.assertEqual(caught.exception.result.status, "invalid")

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

    def test_build_script_reports_graph_derivation_and_validation(self) -> None:
        registry_path = (
            FIXTURES
            / "non-git-workspace"
            / "openspec"
            / "requirements_repo"
            / "repo-index-graph-derivation-validation-stage.yaml"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC_ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            fake_bin = Path(tmp) / "bin"
            fake_bin.mkdir()
            openspec = fake_bin / "openspec"
            openspec.write_text(
                "#!/bin/sh\nprintf '%s\\n' '{\"stores\":[{\"id\":\"requirements-store\",\"path\":\""
                + str(registry_path.parent)
                + "\"}]}'\n",
                encoding="utf-8",
            )
            openspec.chmod(0o755)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "build.py"),
                    str(registry_path),
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )

        output = json.loads(completed.stdout)
        self.assertEqual(output["graph_derivation"]["metadata"]["derived_edge_count"], 4)
        self.assertEqual(output["graph_integrity_validation"]["metadata"]["status"], "valid")
        self.assertEqual(completed.stderr, "")

    def test_derive_script_reports_configured_graph_derivation(self) -> None:
        registry_path = (
            FIXTURES
            / "non-git-workspace"
            / "openspec"
            / "requirements_repo"
            / "repo-index-graph-derivation-stage.yaml"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC_ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            fake_bin = Path(tmp) / "bin"
            fake_bin.mkdir()
            openspec = fake_bin / "openspec"
            openspec.write_text(
                "#!/bin/sh\nprintf '%s\\n' '{\"stores\":[{\"id\":\"requirements-store\",\"path\":\""
                + str(registry_path.parent)
                + "\"}]}'\n",
                encoding="utf-8",
            )
            openspec.chmod(0o755)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "derive.py"),
                    str(registry_path),
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )

        output = json.loads(completed.stdout)
        self.assertEqual(output["graph_derivation"]["metadata"]["status"], "completed")
        self.assertEqual(output["graph_derivation"]["metadata"]["derived_edge_count"], 4)
        self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
