from __future__ import annotations

import sys
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
from engineering_kg.validation import validate_graph_integrity

ROOT = REPO_ROOT / "tests/fixtures/non-git-workspace/openspec/requirements_repo"


class OpenSpecGraphExtractionTest(unittest.TestCase):
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

    def test_unresolved_related_spec_is_a_validation_warning(self) -> None:
        validation = validate_graph_integrity(_extract().graph)
        self.assertEqual(validation.status, "valid")
        self.assertTrue(any(item.rule_id == "unresolved-non-confident-related-spec" for item in validation.metadata.diagnostics))

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
            )
            graph = extract_openspec_graph(source).graph
        specification = next(node for node in graph.nodes if node.kind == NodeKind.SPECIFICATION)
        self.assertEqual(specification.properties["capability"], "service/refunds")
        self.assertTrue(any(node.kind == NodeKind.REQUIREMENT for node in graph.nodes))
        self.assertTrue(any(node.kind == NodeKind.SCENARIO for node in graph.nodes))
        self.assertEqual(len(specification.evidence_ids), 1)


def _extract():
    registry = load_workspace_registry(ROOT / "repo-index-openspec-graph-stage.yaml")
    source = validate_openspec_store_source(registry, registered_stores=(RegisteredOpenSpecStore("requirements-store", ROOT),))
    return extract_openspec_graph(source)


if __name__ == "__main__":
    unittest.main()
