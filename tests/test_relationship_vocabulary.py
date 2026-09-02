from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from engineering_kg.ontology import (
    CodeLocator,
    CrossGraphLinkClaim,
    CrossGraphLinkLifecycle,
    Edge,
    Evidence,
    GraphSnapshot,
    Node,
    NodeKind,
    ProvenanceRecord,
    SourceArtifactIdentity,
)
from engineering_kg.relationship_vocabulary import CATALOG_REVISION, catalog_as_dict
from engineering_kg.validation import validate_graph_integrity


class RelationshipVocabularyTest(unittest.TestCase):
    def test_catalog_is_deterministic_and_complete(self) -> None:
        catalog = catalog_as_dict()
        self.assertEqual(catalog["revision"], CATALOG_REVISION)
        self.assertEqual([item["kind"] for item in catalog["relationships"]], [
            "contains", "traces_to", "implements", "verified_by", "touches",
            "depends_on", "references", "owned_by", "provides",
        ])
        self.assertEqual(
            {item["unsupported_behavior"] for item in catalog["source_mappings"]},
            {"diagnose-and-skip"},
        )

    def test_published_reference_matches_catalog_serialization(self) -> None:
        reference = (
            Path(__file__).resolve().parents[1]
            / "docs" / "canonical-relationship-vocabulary.md"
        ).read_text(encoding="utf-8")
        serialized_catalog = re.search(
            r"## Catalog serialization\n\n```json\n(.*?)\n```",
            reference,
            re.DOTALL,
        )

        self.assertIsNotNone(serialized_catalog)
        self.assertEqual(json.loads(serialized_catalog.group(1)), catalog_as_dict())

    def test_published_greenfield_constraint_bounds_verification_matrix(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        constraints = (repository_root / "docs" / "engineering-kg-project-constraints-mvp.md").read_text(
            encoding="utf-8"
        )
        reference = (repository_root / "docs" / "canonical-relationship-vocabulary.md").read_text(
            encoding="utf-8"
        )
        required_boundary = (
            "EKG has no historical deployment or persisted graph data"
        )
        required_future_requirement = (
            "explicit requirement backed by concrete evidence of pre-canonical data"
        )

        normalized_constraints = " ".join(constraints.split())
        normalized_reference = " ".join(reference.split())
        self.assertIn(required_boundary, normalized_constraints)
        self.assertIn(required_future_requirement, normalized_constraints)
        self.assertIn(required_boundary, normalized_reference)
        self.assertIn(required_future_requirement, normalized_reference)
        self.assertIn("The matrix has no compatibility, migration, backup, or rollback case", reference)

    def test_endpoint_kind_and_owner_cardinality_are_checked(self) -> None:
        service = Node("service", NodeKind.SERVICE, "service")
        repo = Node("repo", NodeKind.REPOSITORY, "repo")
        workspace = Node("workspace", NodeKind.WORKSPACE, "workspace")
        external = Node("external", NodeKind.EXTERNAL_SYSTEM, "external")
        provenance = ProvenanceRecord(
            "external", "2026-01-02T03:04:05+00:00", "sha256", "a" * 64,
            "test-extractor", "1",
            SourceArtifactIdentity("fixture-source", "relationship", "fixture", "1", "fixtures/relationship.md"),
        )
        evidence = Evidence("owner-evidence", "fixture", "fixture.md", provenance_ids=(provenance.id,))
        reversed_edge = Edge("reversed", "owned_by", workspace.id, repo.id)
        first = Edge("owner-1", "owned_by", repo.id, workspace.id, evidence_ids=(evidence.id,))
        second = Edge("owner-2", "owned_by", repo.id, external.id, evidence_ids=(evidence.id,))
        result = validate_graph_integrity(GraphSnapshot(
            (service, repo, workspace, external), (reversed_edge, first, second),
            (evidence,), provenance=(provenance,),
        ))
        self.assertEqual(result.status, "invalid")
        self.assertEqual({item.rule_id for item in result.metadata.diagnostics}, {"relationship-endpoint-contract", "relationship-cardinality"})

        admitted = validate_graph_integrity(GraphSnapshot(
            (repo, workspace), (first,), (evidence,), provenance=(provenance,),
        ))
        self.assertEqual(admitted.status, "valid")
        missing_provenance = validate_graph_integrity(GraphSnapshot(
            (repo, workspace), (Edge("unprovenanced", "owned_by", repo.id, workspace.id),),
        ))
        self.assertEqual(
            [item.rule_id for item in missing_provenance.metadata.diagnostics],
            ["relationship-provenance-complete"],
        )

    def test_references_rejects_noncanonical_endpoint_kinds(self) -> None:
        source = Node("source", "unrecognized-source", "source")
        target = Node("target", "unrecognized-target", "target")
        edge = Edge("invalid-reference", "references", source.id, target.id)

        result = validate_graph_integrity(GraphSnapshot((source, target), (edge,)))

        self.assertEqual(result.status, "invalid")
        self.assertEqual(
            [(item.rule_id, item.affected_object_id) for item in result.metadata.diagnostics],
            [("relationship-endpoint-contract", edge.id)],
        )

    def test_structural_contains_requires_complete_evidence_provenance(self) -> None:
        change = Node("change", NodeKind.OPENSPEC_ACTIVE_CHANGE, "change")
        artifact = Node("artifact", NodeKind.OPENSPEC_ARTIFACT, "proposal")
        edge = Edge("contains", "contains", change.id, artifact.id)

        missing_provenance = validate_graph_integrity(
            GraphSnapshot((change, artifact), (edge,))
        )

        self.assertEqual(missing_provenance.status, "invalid")
        self.assertEqual(
            [(item.rule_id, item.affected_object_id) for item in missing_provenance.metadata.diagnostics],
            [("relationship-provenance-complete", edge.id)],
        )

        provenance = ProvenanceRecord(
            "external", "2026-01-02T03:04:05+00:00", "sha256", "a" * 64,
            "test-extractor", "1",
            SourceArtifactIdentity("fixture-source", "contains", "fixture", "1", "fixtures/contains.md"),
        )
        evidence = Evidence("contains-evidence", "fixture", "fixture.md", provenance_ids=(provenance.id,))
        provenanced_edge = Edge(
            edge.id, edge.kind, edge.source_id, edge.target_id, evidence_ids=(evidence.id,)
        )

        admitted = validate_graph_integrity(GraphSnapshot(
            (change, artifact), (provenanced_edge,), (evidence,), provenance=(provenance,),
        ))
        self.assertEqual(admitted.status, "valid")

    def test_code_claim_requires_catalog_and_only_trusted_is_projected(self) -> None:
        story = Node("story", NodeKind.JIRA_STORY, "story")
        claim = CrossGraphLinkClaim(story.id, "touches", CodeLocator("repo", "rev", "a.py", "a.b"))
        candidate = GraphSnapshot(nodes=(story,), cross_graph_link_claims=(claim,), cross_graph_link_lifecycle=(CrossGraphLinkLifecycle(claim.id, 1, "candidate", "e"),))
        # Missing evidence makes it invalid but candidate remains non-semantic.
        self.assertEqual(candidate.trusted_cross_graph_links, ())
        with self.assertRaisesRegex(ValueError, "relationship-vocabulary-kind"):
            CrossGraphLinkClaim(story.id, "unknown", claim.target)


if __name__ == "__main__":
    unittest.main()
