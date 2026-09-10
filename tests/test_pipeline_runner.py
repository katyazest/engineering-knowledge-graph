from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.ingest.openspec import RegisteredOpenSpecStore
from engineering_kg.ingest.pr_code_candidates import normalize_pull_request_evidence
from engineering_kg.ontology import Evidence, GraphSnapshot, Node, NodeKind
from engineering_kg.pipeline import run_pipeline
from engineering_kg.persistence import PersistenceIntegrityError, initialize_ladybugdb_store
from engineering_kg.relationship_vocabulary import CATALOG_REVISION

ROOT = REPO_ROOT / "tests/fixtures/non-git-workspace/openspec/requirements_repo"


class PipelineRunnerSmokeTest(unittest.TestCase):
    def _registry_with_candidate_stage(self, temporary: str) -> Path:
        registry = Path(temporary) / "registry.yaml"
        registry.write_text(
            (ROOT / "repo-index-graph-derivation-validation-stage.yaml").read_text().replace(
                "    - openspec-store-source\n    - openspec-graph-extraction\n", ""
            ).replace(
                "    - workspace-registry",
                "    - workspace-registry\n    - engineering-change-subject-input\n    - pr-code-candidate-extraction",
            ),
            encoding="utf-8",
        )
        return registry

    def _input(self, repository_id: str, subject_id: str) -> object:
        return normalize_pull_request_evidence({
            "pull_request_id": "bitbucket:pr-42",
            "repository_node_id": repository_id,
            "base_revision": "a" * 40,
            "head_revision": "b" * 40,
            "merged": True,
            "observed_at": "2026-09-01T12:00:00+00:00",
            "provenance": {"pr": "complete"},
            "pr_source_reference": "urn:example.org/pr-42",
            "repository_source_reference": "urn:example.org/repository-42",
            "association": {
                "id": "association-42",
                "intended_change_id": subject_id,
                "source_reference": "urn:example.org/association-42",
                "intended_change_kind": "jira_story",
            },
            "mappings": [{
                "id": "graphify:mapping-42",
                "file": "src/payments.py",
                "symbol": "payments.submit",
                "outcome": "resolved",
                "repository": repository_id,
                "revision": "b" * 40,
            }],
        })

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

    def test_pipeline_rejects_legacy_records_without_conversion(self) -> None:
        legacy = Node(
            "legacy-spec", "openspec-spec", "Payments",
            {"capability": "payments", "repository_id": "requirements"},
            ("evidence",),
        )
        with tempfile.TemporaryDirectory() as temporary:
            graph_path = Path(temporary) / "graph"
            store = initialize_ladybugdb_store(graph_path)
            store._write_raw({
                "catalog_revision": CATALOG_REVISION,
                "node_order": [legacy.id],
                "nodes": {legacy.id: legacy.as_dict()},
                "edge_order": [], "edges": {},
                "evidence_order": ["evidence"],
                "evidence": {"evidence": Evidence("evidence", "fixture", "fixture").as_dict()},
            })
            result = run_pipeline(
                ROOT / "repo-index-graph-derivation-validation-stage.yaml",
                graph_path,
                openspec_stores=(RegisteredOpenSpecStore("requirements-store", ROOT),),
            ).as_dict()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["ontology_migration"]["status"], "failed")
        self.assertNotIn("ladybugdb-persistence", result["executed_stages"])

    def test_candidate_stage_requires_enriched_input_and_subject_before_extraction(self) -> None:
        subject = Node("change-1", NodeKind.JIRA_STORY, "EKG-72")
        repository = Node("repository-1", NodeKind.REPOSITORY, "payment-service")
        with tempfile.TemporaryDirectory() as temporary:
            registry = self._registry_with_candidate_stage(temporary)
            with self.assertRaisesRegex(ValueError, "requires normalized pr_change_sets input"):
                run_pipeline(registry)
            with self.assertRaisesRegex(ValueError, "requires available prior graph subjects"):
                run_pipeline(
                    registry,
                    pr_change_sets=(self._input(repository.id, "missing-change"),),
                    engineering_change_subject_graph=GraphSnapshot(nodes=(repository, subject)),
                )

    def test_candidate_stage_rejects_legacy_object_before_graph_mutation(self) -> None:
        subject = Node("change-1", NodeKind.JIRA_STORY, "EKG-72")
        repository = Node("repository-1", NodeKind.REPOSITORY, "payment-service")
        with tempfile.TemporaryDirectory() as temporary:
            registry = self._registry_with_candidate_stage(temporary)
            with self.assertRaisesRegex(ValueError, "legacy merged-revision-only"):
                run_pipeline(
                    registry,
                    pr_change_sets=(object(),),  # type: ignore[arg-type]
                    engineering_change_subject_graph=GraphSnapshot(nodes=(repository, subject)),
                )

    def test_candidate_stage_merges_enriched_input(self) -> None:
        subject = Node("change-1", NodeKind.JIRA_STORY, "EKG-72")
        repository = Node("repository-1", NodeKind.REPOSITORY, "payment-service")
        with tempfile.TemporaryDirectory() as temporary:
            result = run_pipeline(
                self._registry_with_candidate_stage(temporary),
                pr_change_sets=(self._input(repository.id, subject.id),),
                engineering_change_subject_graph=GraphSnapshot(nodes=(repository, subject)),
            )
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.pr_code_candidate_extraction.metadata.emitted_candidate_count, 1)
        self.assertEqual(result.graph_integrity_validation.status, "valid")


if __name__ == "__main__":
    unittest.main()
