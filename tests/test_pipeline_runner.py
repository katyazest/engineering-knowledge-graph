from __future__ import annotations

import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.ingest.openspec import RegisteredOpenSpecStore
from engineering_kg.ontology import Evidence, GraphSnapshot, Node
from engineering_kg.pipeline import run_pipeline
from engineering_kg.persistence import PersistenceIntegrityError, initialize_ladybugdb_store

ROOT = REPO_ROOT / "tests/fixtures/non-git-workspace/openspec/requirements_repo"


class PipelineRunnerSmokeTest(unittest.TestCase):
    def test_empty_pipeline_is_deterministic(self) -> None:
        self.assertEqual(run_pipeline().as_dict(), run_pipeline().as_dict())

    def test_pipeline_runs_canonical_extraction_derivation_and_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = run_pipeline(
                ROOT / "repo-index-graph-derivation-validation-stage.yaml",
                Path(temporary) / "graph",
                openspec_stores=(RegisteredOpenSpecStore("requirements-store", ROOT),),
            ).as_dict()
        self.assertIn("ontology-migration", result["executed_stages"])
        self.assertEqual(result["ontology_migration"]["status"], "not-needed")
        self.assertTrue(any(node["kind"] == "specification" for node in result["graph"]["nodes"]))
        self.assertFalse(any(node["kind"] == "openspec-spec" for node in result["graph"]["nodes"]))
        self.assertEqual(result["graph_integrity_validation"]["metadata"]["status"], "valid")

    def test_migration_failure_returns_deterministic_failed_stage_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch("engineering_kg.pipeline.initialize_ladybugdb_store") as initialize:
                initialize.return_value.migrate_persisted_snapshot.side_effect = PersistenceIntegrityError("conflict")
                result = run_pipeline(
                    ROOT / "repo-index-graph-derivation-validation-stage.yaml",
                    Path(temporary) / "graph",
                    openspec_stores=(RegisteredOpenSpecStore("requirements-store", ROOT),),
                ).as_dict()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["ontology_migration"]["status"], "failed")
        self.assertEqual(result["ontology_migration"]["diagnostics"], ["conflict"])
        self.assertNotIn("graph-derivation", result["executed_stages"])
        self.assertNotIn("graph-integrity-validation", result["executed_stages"])

    def test_pipeline_migrates_legacy_records_before_derivation_and_validation(self) -> None:
        legacy = Node(
            "legacy-spec",
            "openspec-spec",
            "Payments",
            {"capability": "payments", "repository_id": "requirements"},
            ("evidence",),
        )
        with tempfile.TemporaryDirectory() as temporary:
            graph_path = Path(temporary) / "graph"
            store = initialize_ladybugdb_store(graph_path)
            store._write_raw({
                "node_order": [legacy.id],
                "nodes": {legacy.id: legacy.as_dict()},
                "edge_order": [],
                "edges": {},
                "evidence_order": ["evidence"],
                "evidence": {"evidence": Evidence("evidence", "openspec", "fixture").as_dict()},
            })
            result = run_pipeline(
                ROOT / "repo-index-graph-derivation-validation-stage.yaml",
                graph_path,
                openspec_stores=(RegisteredOpenSpecStore("requirements-store", ROOT),),
            ).as_dict()
        self.assertEqual(result["ontology_migration"]["status"], "migrated")
        self.assertEqual(result["graph_integrity_validation"]["metadata"]["status"], "valid")
        self.assertFalse(any(node["kind"] == "openspec-spec" for node in result["graph"]["nodes"]))


if __name__ == "__main__":
    unittest.main()
