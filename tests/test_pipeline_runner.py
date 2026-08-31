from __future__ import annotations

import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.ingest.openspec import RegisteredOpenSpecStore
from engineering_kg.ingest.pr_code_candidates import ChangedSymbolMapping, EngineeringChangePrAssociation, MergedPrChangeSet
from engineering_kg.ontology import Evidence, GraphSnapshot, Node, NodeKind, stable_id
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
                "evidence": {"evidence": Evidence("evidence", "fixture", "fixture").as_dict()},
            })
            result = run_pipeline(
                ROOT / "repo-index-graph-derivation-validation-stage.yaml",
                graph_path,
                openspec_stores=(RegisteredOpenSpecStore("requirements-store", ROOT),),
            ).as_dict()
        self.assertEqual(result["ontology_migration"]["status"], "migrated")
        self.assertEqual(result["graph_integrity_validation"]["metadata"]["status"], "valid")
        self.assertFalse(any(node["kind"] == "openspec-spec" for node in result["graph"]["nodes"]))

    def test_candidate_stage_requires_input_and_prior_available_subject(self) -> None:
        subject_id = "missing-engineering-change"
        change_set = MergedPrChangeSet(
            EngineeringChangePrAssociation("link-1", subject_id, "pr-1"), "pr-1", "payment-service", "a" * 40,
            (ChangedSymbolMapping("graphify:mapping-1", "src/payment.py", "resolved", "payments.submit"),),
        )
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "registry.yaml"
            registry.write_text(
                (ROOT / "repo-index-graph-derivation-validation-stage.yaml").read_text().replace(
                    "    - openspec-store-source\n    - openspec-graph-extraction\n", ""
                ).replace("    - workspace-registry", "    - workspace-registry\n    - pr-code-candidate-extraction"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "requires normalized pr_change_sets input"):
                run_pipeline(registry)
            with self.assertRaisesRegex(ValueError, "requires available prior graph subjects"):
                run_pipeline(registry, pr_change_sets=(change_set,))

    def test_candidate_stage_before_its_subject_input_is_rejected_without_reordering(self) -> None:
        subject = Node("change-1", NodeKind.JIRA_STORY, "EKG-72")
        change_set = MergedPrChangeSet(
            EngineeringChangePrAssociation("link-1", subject.id, "pr-1"),
            "pr-1",
            "payment-service",
            "a" * 40,
            (ChangedSymbolMapping("graphify:mapping-1", "src/payment.py", "resolved", "payments.submit"),),
        )
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "registry.yaml"
            registry.write_text(
                (ROOT / "repo-index-graph-derivation-validation-stage.yaml").read_text().replace(
                    "    - openspec-store-source\n    - openspec-graph-extraction\n", ""
                ).replace(
                    "    - workspace-registry",
                    "    - workspace-registry\n    - pr-code-candidate-extraction\n    - engineering-change-subject-input",
                ),
                encoding="utf-8",
            )
            with mock.patch("engineering_kg.pipeline.extract_pr_code_candidates") as extract:
                with self.assertRaisesRegex(
                    ValueError,
                    "pr-code-candidate-extraction must run after engineering-change-subject-input",
                ):
                    run_pipeline(
                        registry,
                        pr_change_sets=(change_set,),
                        engineering_change_subject_graph=GraphSnapshot(nodes=(subject,)),
                    )
        extract.assert_not_called()

    def test_candidate_stage_rejects_non_story_subject_from_prior_graph_producer(self) -> None:
        subject_id = stable_id("node", NodeKind.WORKSPACE, "payments-workspace")
        change_set = MergedPrChangeSet(
            EngineeringChangePrAssociation("link-1", subject_id, "pr-1"),
            "pr-1",
            "payment-service",
            "a" * 40,
            (ChangedSymbolMapping("graphify:mapping-1", "src/payment.py", "resolved", "payments.submit"),),
        )
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "registry.yaml"
            registry.write_text(
                (ROOT / "repo-index-graph-derivation-validation-stage.yaml").read_text().replace(
                    "    - openspec-store-source\n    - openspec-graph-extraction\n", ""
                ).replace("    - workspace-registry", "    - workspace-registry\n    - pr-code-candidate-extraction"),
                encoding="utf-8",
            )
            result = run_pipeline(registry, pr_change_sets=(change_set,))

        self.assertEqual(result.status, "completed")
        self.assertNotIn("engineering-change-subject-input", result.executed_stages)
        self.assertEqual(result.pr_code_candidate_extraction.metadata.accepted_change_set_count, 0)
        self.assertEqual(result.pr_code_candidate_extraction.metadata.emitted_candidate_count, 0)
        self.assertEqual(
            result.pr_code_candidate_extraction.metadata.skipped_reason_counts,
            {"ineligible-subject-kind": 1},
        )
        self.assertEqual(result.graph.cross_graph_link_claims, ())
        self.assertEqual(result.graph.trusted_cross_graph_links, ())

    def test_candidate_stage_merges_configured_jira_subject_input_before_derivation(self) -> None:
        subject = Node("change-1", NodeKind.JIRA_STORY, "EKG-72")
        opaque_id = "urn:example.org/link-42"
        change_set = MergedPrChangeSet(
            EngineeringChangePrAssociation(opaque_id, subject.id, opaque_id),
            opaque_id,
            "payment-service",
            "a" * 40,
            (ChangedSymbolMapping("graphify:mapping-1", "src/payment.py", "resolved", "payments.submit"),),
        )
        with tempfile.TemporaryDirectory() as temporary:
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
            result = run_pipeline(
                registry,
                pr_change_sets=(change_set,),
                engineering_change_subject_graph=GraphSnapshot(nodes=(subject,)),
            )

        self.assertEqual(
            result.executed_stages,
            (
                "workspace-registry",
                "engineering-change-subject-input",
                "pr-code-candidate-extraction",
                "graph-derivation",
                "graph-integrity-validation",
            ),
        )
        self.assertEqual(result.pr_code_candidate_extraction.metadata.emitted_candidate_count, 1)
        self.assertEqual(
            result.as_dict()["pr_code_candidate_extraction"]["metadata"]
            ["emitted_candidate_count"],
            1,
        )
        self.assertEqual(result.graph_integrity_validation.status, "valid")
        self.assertEqual(len(result.graph.cross_graph_link_claims), 1)
        self.assertIn(opaque_id, result.graph.as_json())

    def test_candidate_stage_reports_empty_normalized_input_when_subject_is_available(self) -> None:
        subject = Node("change-1", NodeKind.JIRA_STORY, "EKG-72")
        with tempfile.TemporaryDirectory() as temporary:
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
            result = run_pipeline(
                registry,
                pr_change_sets=(),
                engineering_change_subject_graph=GraphSnapshot(nodes=(subject,)),
            )

        self.assertEqual(result.status, "completed")
        self.assertIn("pr-code-candidate-extraction", result.executed_stages)
        self.assertEqual(result.pr_code_candidate_extraction.metadata.accepted_change_set_count, 0)
        self.assertEqual(result.pr_code_candidate_extraction.metadata.emitted_candidate_count, 0)
        self.assertEqual(result.pr_code_candidate_extraction.metadata.skipped_input_count, 0)
        self.assertEqual(result.pr_code_candidate_extraction.metadata.diagnostics, ())
        self.assertEqual(result.pr_code_candidate_extraction.metadata.graph_counts, {
            "cross_graph_link_claim_count": 0,
            "cross_graph_link_evidence_count": 0,
            "cross_graph_link_lifecycle_count": 0,
            "evidence_count": 0,
        })
        self.assertEqual(result.graph_integrity_validation.status, "valid")


if __name__ == "__main__":
    unittest.main()
