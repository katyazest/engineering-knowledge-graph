from __future__ import annotations

import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.ingest.openspec import (
    OpenSpecStoreSourceValidationResult,
    RegisteredOpenSpecStore,
    extract_openspec_graph,
    validate_openspec_store_source,
)
from engineering_kg.ontology import EdgeKind, NodeKind
from engineering_kg.project import load_workspace_registry
from engineering_kg.persistence import initialize_ladybugdb_store
from engineering_kg.validation import validate_graph_integrity

ROOT = REPO_ROOT / "tests/fixtures/non-git-workspace/openspec/requirements_repo"


class OpenSpecGraphExtractionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _ensure_git_repository(ROOT)

    def test_extracts_canonical_facts_and_coalesces_source_evidence(self) -> None:
        graph = _extract().graph
        specs = [node for node in graph.nodes if node.kind == NodeKind.SPECIFICATION]
        self.assertEqual({node.properties["capability"] for node in specs}, {"payments", "service/payments", "settlement"})
        payments = next(node for node in specs if node.properties["capability"] == "payments")
        self.assertEqual(len(payments.evidence_ids), 3)
        self.assertFalse(any(str(node.kind).startswith("openspec-") for node in graph.nodes if node.kind not in {NodeKind.OPENSPEC_ACTIVE_CHANGE, NodeKind.OPENSPEC_ARCHIVED_CHANGE, NodeKind.OPENSPEC_ARTIFACT}))
        self.assertTrue(any(edge.kind == EdgeKind.ASSERTS for edge in graph.edges))
        self.assertTrue(any(edge.kind == EdgeKind.CONTAINS for edge in graph.edges))

    def test_extraction_is_deterministic_and_preserves_provenance(self) -> None:
        first = _extract().as_dict()
        self.assertEqual(first, _extract().as_dict())
        self.assertTrue(all("content" not in str(item) for item in first["graph"]["evidence"]))
        self.assertRegex(first["metadata"]["revision_or_version"], r"^[0-9a-f]{40}$")
        for item in first["graph"]["evidence"]:
            identity = item["locator"].get("source_artifact_identity")
            self.assertIsNotNone(identity)
            self.assertNotIn(str(ROOT.resolve()), str(identity))

    def test_missing_revision_rejects_before_graph_output(self) -> None:
        source = _extract_source()
        source = OpenSpecStoreSourceValidationResult(
            **{**source.__dict__, "revision_or_version": ""}
        )
        with self.assertRaisesRegex(ValueError, "invalid-source-artifact-identity"):
            extract_openspec_graph(source)

    def test_revision_qualified_extraction_persists_idempotently(self) -> None:
        source = _extract_source()
        first = extract_openspec_graph(source).graph
        changed_source = OpenSpecStoreSourceValidationResult(
            **{**source.__dict__, "revision_or_version": "b" * 40}
        )
        changed = extract_openspec_graph(changed_source).graph
        self.assertEqual(
            [node.id for node in first.nodes], [node.id for node in changed.nodes]
        )
        self.assertNotEqual(
            [item.id for item in first.evidence], [item.id for item in changed.evidence]
        )
        with tempfile.TemporaryDirectory() as temporary:
            store = initialize_ladybugdb_store(Path(temporary) / "graph")
            persisted_first = store.write_snapshot(first).as_json()
            persisted_second = store.write_snapshot(first).as_json()
        self.assertEqual(persisted_first, persisted_second)

    def test_unresolved_related_spec_is_a_validation_warning(self) -> None:
        validation = validate_graph_integrity(_extract().graph)
        self.assertEqual(validation.status, "valid")
        self.assertTrue(any(item.rule_id == "unresolved-non-confident-related-spec" for item in validation.metadata.diagnostics))

    def test_uniquely_resolved_related_metadata_is_non_confident_references_with_source_evidence(self) -> None:
        graph = _extract().graph
        specifications = {
            node.properties["capability"]: node
            for node in graph.nodes
            if node.kind == NodeKind.SPECIFICATION
        }
        source = specifications["payments"]
        target = specifications["settlement"]
        reference = next(
            edge for edge in graph.edges
            if edge.kind == EdgeKind.REFERENCES
            and edge.source_id == source.id
            and edge.target_id == target.id
        )

        self.assertEqual(reference.confidence, "non-confident")
        self.assertEqual(reference.properties, {"related_title": "Settlement Capability"})
        self.assertEqual(len(reference.evidence_ids), 1)
        self.assertIn(reference.evidence_ids[0], source.evidence_ids)
        evidence = next(item for item in graph.evidence if item.id == reference.evidence_ids[0])
        self.assertEqual(evidence.source, "openspec")
        self.assertEqual(
            evidence.locator.as_dict()["relative_file_path"],
            "openspec/specs/payments/spec.md",
        )

    def test_change_only_nested_capability_creates_canonical_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "openspec/specs").mkdir(parents=True)
            spec_path = root / "openspec/changes/add-refunds/specs/service/refunds/spec.md"
            spec_path.parent.mkdir(parents=True)
            spec_path.write_text(
                "### Requirement: Refund is issued\n\n#### Scenario: Valid refund\n",
                encoding="utf-8",
            )
            source = OpenSpecStoreSourceValidationResult(
                status="valid",
                selection_source="fixture",
                repository_id="requirements",
                repository_role="requirements",
                repository_path=root,
                openspec_root_path=root / "openspec",
                specs_path=root / "openspec/specs",
                changes_path=root / "openspec/changes",
                revision_or_version="a" * 40,
                observed_at="2026-09-01T12:00:00+00:00",
            )
            graph = extract_openspec_graph(source).graph
        specification = next(node for node in graph.nodes if node.kind == NodeKind.SPECIFICATION)
        self.assertEqual(specification.properties["capability"], "service/refunds")
        self.assertTrue(any(node.kind == NodeKind.REQUIREMENT for node in graph.nodes))
        self.assertTrue(any(node.kind == NodeKind.SCENARIO for node in graph.nodes))
        self.assertEqual(len(specification.evidence_ids), 1)


def _extract():
    return extract_openspec_graph(_extract_source())


def _extract_source():
    registry = load_workspace_registry(ROOT / "repo-index-openspec-graph-stage.yaml")
    return validate_openspec_store_source(registry, registered_stores=(RegisteredOpenSpecStore("requirements-store", ROOT),))


def _ensure_git_repository(path: Path) -> None:
    if (path / ".git").exists():
        return
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "-c", "user.email=test@example.invalid", "-c", "user.name=Test", "commit", "-m", "fixture"],
        check=True, capture_output=True,
    )


if __name__ == "__main__":
    unittest.main()
