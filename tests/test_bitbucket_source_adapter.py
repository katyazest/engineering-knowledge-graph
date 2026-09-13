from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from engineering_kg.ingest.bitbucket import (
    BitbucketChangedFileSourceRecord,
    BitbucketChangedFileObservation,
    BitbucketExplicitReference,
    BitbucketPullRequestSourceRecord,
    BitbucketSourceAdapter,
    BitbucketSourceReference,
    BitbucketSourceResponse,
    BitbucketSourceSelection,
    BitbucketStructuredReference,
    BitbucketValidationError,
    adapt_openlore_result_to_normalized_pull_request_evidence,
    adapt_openlore_result_to_changed_symbol_mappings,
    observations_to_openlore_request,
)
from engineering_kg.openlore_bridge import (
    ChangedFileResolutionOutcome,
    ImplementationEvidenceContext,
    ResolutionResult,
    ResolutionStatus,
    RoutingReference,
)
from engineering_kg.ingest.pr_code_candidates import (
    ChangedSymbolMapping,
    MappingOutcome,
    NormalizedPullRequestEvidence,
    extract_pr_code_candidates,
)
from engineering_kg.ontology import (
    CodeLocator,
    GraphSnapshot,
    Node,
    NodeKind,
    PullRequestImplementationEvidence,
)
from engineering_kg.persistence import initialize_ladybugdb_store
from engineering_kg.validation import validate_graph_integrity


BASE = "a" * 40
HEAD = "b" * 40


class FakeBitbucketPort:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.selections = []

    def fetch_pull_request(self, selection):
        self.selections.append(selection)
        if self.error:
            raise self.error
        return self.response


def reference(identity: str, kind: str = "pr") -> BitbucketSourceReference:
    return BitbucketSourceReference("bitbucket", identity, f"references/{kind}/{identity.split(':')[-1]}")


def source_record(repository: str, *, changed_files=(), declarations=(), merged=True):
    files = None if changed_files == "unavailable" else tuple(changed_files)
    return BitbucketPullRequestSourceRecord(
        "bitbucket:pr-42", repository, merged, BASE, HEAD,
        "2026-09-01T12:00:00+00:00", reference("bitbucket:pr-42"),
        reference("bitbucket:repo-42", "repository"), files, tuple(declarations),
    )


class BitbucketSourceAdapterTest(unittest.TestCase):
    def setUp(self):
        self.repository = Node("repository-1", NodeKind.REPOSITORY, "payments")
        self.change = Node("change-1", NodeKind.OPENSPEC_ACTIVE_CHANGE, "add-payments")
        self.archived_change = Node("change-archived", NodeKind.OPENSPEC_ARCHIVED_CHANGE, "old-payments")
        self.jira = Node("story-1", NodeKind.JIRA_STORY, "PAY-1")
        self.subject_graph = GraphSnapshot(nodes=(self.repository, self.change, self.archived_change, self.jira))
        self.selection = BitbucketSourceSelection("bitbucket:pr-42", self.repository.id)

    def test_complete_pr_is_revision_bounded_and_serialization_is_payload_free(self):
        file_record = BitbucketChangedFileSourceRecord(
            "bitbucket:file-1", "src/payments.py", self.repository.id, HEAD,
            reference("bitbucket:file-1", "file"),
        )
        declaration = BitbucketStructuredReference(
            "OPENSPEC_ACTIVE_CHANGE", self.change.id, reference("bitbucket:ref-1", "association"),
        )
        port = FakeBitbucketPort(source_record(self.repository.id, changed_files=(file_record,), declarations=(declaration,)))
        result = BitbucketSourceAdapter(port).normalize(self.selection, self.subject_graph)

        self.assertTrue(result.admitted)
        self.assertEqual(result.pull_request_evidence.base_revision, BASE)
        self.assertEqual(result.pull_request_evidence.head_revision, HEAD)
        self.assertEqual(len(result.associations), 1)
        self.assertEqual(result.changed_files[0].file, "src/payments.py")
        self.assertEqual({edge.kind for edge in result.graph.edges}, {"touches", "references"})
        self.assertEqual(validate_graph_integrity(self.subject_graph.merged_with(result.graph)).status, "valid")
        serialized = result.as_json()
        for forbidden in ("provider_payload", "https://", "source_code", "credentials", "token", "exception"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(result.as_dict()["changed_files"][0]["head_revision"], HEAD)

    def test_source_failures_are_safe_single_call_outcomes(self):
        for response, expected in (
            (BitbucketSourceResponse(status="unavailable"), "provider-unavailable"),
            (BitbucketSourceResponse(status="future-status"), "unsupported-source-status"),
            (object(), "malformed-source-response"),
        ):
            port = FakeBitbucketPort(response=response)
            result = BitbucketSourceAdapter(port).normalize(self.selection, self.subject_graph)
            self.assertEqual(result.diagnostics[0].reason_code, expected)
            self.assertEqual(result.graph, GraphSnapshot())
            self.assertEqual(len(port.selections), 1)

        port = FakeBitbucketPort(error=RuntimeError("secret response body"))
        result = BitbucketSourceAdapter(port).normalize(self.selection, self.subject_graph)
        self.assertEqual(result.diagnostics[0].reason_code, "provider-unavailable")
        self.assertNotIn("secret", result.as_json())
        self.assertEqual(len(port.selections), 1)

    def test_pr_admission_is_atomic_and_unavailable_files_are_not_empty_success(self):
        unmerged = FakeBitbucketPort(source_record(self.repository.id, merged=False))
        rejected = BitbucketSourceAdapter(unmerged).normalize(self.selection, self.subject_graph)
        self.assertFalse(rejected.admitted)
        self.assertEqual(rejected.graph, GraphSnapshot())
        self.assertEqual(rejected.diagnostics[0].reason_code, "unmerged-pr")

        unavailable = FakeBitbucketPort(source_record(self.repository.id, changed_files="unavailable"))
        result = BitbucketSourceAdapter(unavailable).normalize(self.selection, self.subject_graph)
        self.assertTrue(result.admitted)
        self.assertEqual(result.changed_files, ())
        self.assertEqual(result.diagnostics[0].reason_code, "changed-files-unavailable")
        self.assertEqual(len(result.graph.pull_request_evidence), 1)

        unknown_selection = BitbucketSourceSelection("bitbucket:pr-42", "repository-unknown")
        unknown = BitbucketSourceAdapter(FakeBitbucketPort(source_record("repository-unknown"))).normalize(
            unknown_selection, self.subject_graph,
        )
        self.assertEqual(unknown.diagnostics[0].reason_code, "unknown-repository")
        self.assertEqual(unknown.graph, GraphSnapshot())

    def test_existing_pr_with_conflicting_revision_is_rejected_atomically(self):
        file_record = BitbucketChangedFileSourceRecord(
            "bitbucket:file-1", "src/payments.py", self.repository.id, HEAD,
            reference("bitbucket:file-1", "file"),
        )
        declaration = BitbucketStructuredReference(
            "OPENSPEC_ACTIVE_CHANGE", self.change.id, reference("bitbucket:ref-1", "association"),
        )
        represented_pr = PullRequestImplementationEvidence(
            self.selection.pull_request_id, self.repository.id, "c" * 40, HEAD, True,
            "evidence:represented-pr", "provenance:represented-pr",
        )
        subject_with_pr = GraphSnapshot(
            nodes=(self.repository, self.change),
            pull_request_evidence=(represented_pr,),
        )
        result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, changed_files=(file_record,), declarations=(declaration,),
        ))).normalize(self.selection, subject_with_pr)

        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.diagnostics[0].reason_code, "conflicting-pr-identity")
        self.assertEqual(result.graph, GraphSnapshot())
        self.assertIsNone(result.pull_request_evidence)
        self.assertIsNone(result.repository_relation)
        self.assertEqual(result.associations, ())
        self.assertEqual(result.changed_files, ())
        self.assertEqual(result.changed_file_evidence, ())
        self.assertEqual(result.changed_file_provenance, ())

    def test_equivalent_pr_declaration_and_file_orders_are_idempotent(self):
        first_file = BitbucketChangedFileSourceRecord("bitbucket:file-a", "src/a.py", self.repository.id, HEAD, reference("bitbucket:file-a", "file"))
        second_file = BitbucketChangedFileSourceRecord("bitbucket:file-b", "src/b.py", self.repository.id, HEAD, reference("bitbucket:file-b", "file"))
        first_declaration = BitbucketStructuredReference("OPENSPEC_ACTIVE_CHANGE", self.change.id, reference("bitbucket:ref-a", "association"))
        second_declaration = BitbucketStructuredReference("JIRA_STORY", self.jira.id, reference("bitbucket:ref-b", "association"))
        first = source_record(
            self.repository.id,
            changed_files=(first_file, second_file),
            declarations=(first_declaration, second_declaration),
        )
        second = source_record(
            self.repository.id,
            changed_files=(second_file, first_file),
            declarations=(second_declaration, first_declaration),
        )
        one = BitbucketSourceAdapter(FakeBitbucketPort(first)).normalize(self.selection, self.subject_graph)
        two = BitbucketSourceAdapter(FakeBitbucketPort(second)).normalize(self.selection, self.subject_graph)
        self.assertEqual(one.graph.as_json(), two.graph.as_json())
        self.assertEqual(one.as_json(), two.as_json())

    def test_changed_files_coalesce_and_conflicts_do_not_choose_input_order(self):
        first = BitbucketChangedFileSourceRecord("bitbucket:file-1", "src/a.py", self.repository.id, HEAD, reference("bitbucket:file-1", "file"))
        equivalent = BitbucketChangedFileSourceRecord("bitbucket:file-1", "src/a.py", self.repository.id, HEAD, reference("bitbucket:file-1", "file"))
        conflict = BitbucketChangedFileSourceRecord("bitbucket:file-2", "src/z.py", self.repository.id, HEAD, reference("bitbucket:file-2", "file"))
        conflict_other = BitbucketChangedFileSourceRecord("bitbucket:file-2", "src/a.py", self.repository.id, HEAD, reference("bitbucket:file-2", "file"))
        result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, changed_files=(conflict, first, conflict_other, equivalent),
        ))).normalize(self.selection, self.subject_graph)
        self.assertEqual([item.stable_file_id for item in result.changed_files], ["bitbucket:file-1"])
        self.assertEqual(result.diagnostics[0].stable_file_id, "bitbucket:file-2")
        reversed_result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, changed_files=(equivalent, conflict_other, first, conflict),
        ))).normalize(self.selection, self.subject_graph)
        self.assertEqual(result.as_dict(), reversed_result.as_dict())

    def test_structured_references_are_exact_and_separate(self):
        declarations = (
            BitbucketStructuredReference("OPENSPEC_ACTIVE_CHANGE", self.change.id, reference("bitbucket:ref-a", "association")),
            BitbucketStructuredReference("OPENSPEC_ARCHIVED_CHANGE", self.archived_change.id, reference("bitbucket:ref-archived", "association")),
            BitbucketExplicitReference("JIRA_STORY", self.jira.id, reference("bitbucket:ref-b", "association")),
            BitbucketStructuredReference("JIRA_STORY", "missing-story", reference("bitbucket:ref-c", "association")),
        )
        result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, declarations=declarations,
        ))).normalize(self.selection, self.subject_graph)
        self.assertEqual(len(result.associations), 3)
        self.assertEqual({edge.kind for edge in result.graph.edges}, {"references", "touches"})
        self.assertEqual(result.diagnostics[0].reason_code, "unknown-reference-target")
        self.assertEqual(len({item.source_evidence_id for item in result.associations}), 3)

    def test_declaration_revision_mismatch_is_excluded_without_rejecting_pr(self):
        valid_file = BitbucketChangedFileSourceRecord(
            "bitbucket:file-revision-context", "src/payments.py", self.repository.id, HEAD,
            reference("bitbucket:file-revision-context", "file"),
        )
        valid_declaration = BitbucketStructuredReference(
            "OPENSPEC_ACTIVE_CHANGE", self.change.id,
            reference("bitbucket:ref-valid-revision", "association"),
        )
        mismatched_declaration = BitbucketStructuredReference(
            "JIRA_STORY", self.jira.id,
            BitbucketSourceReference(
                "bitbucket", "bitbucket:ref-wrong-revision", "references/association/wrong", "c" * 40,
            ),
        )

        result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id,
            changed_files=(valid_file,),
            declarations=(mismatched_declaration, valid_declaration),
        ))).normalize(self.selection, self.subject_graph)

        self.assertTrue(result.admitted)
        self.assertEqual([item.intended_change_id for item in result.associations], [self.change.id])
        self.assertEqual([item.stable_file_id for item in result.changed_files], [valid_file.stable_file_id])
        self.assertEqual(
            [diagnostic.as_dict() for diagnostic in result.diagnostics],
            [{"object_id": self.jira.id, "reason_code": "revision-context-mismatch"}],
        )
        self.assertEqual(
            {edge.kind for edge in result.graph.edges},
            {"references", "touches"},
        )

    def test_non_head_eligible_declaration_keeps_valid_pr_evidence(self):
        non_head = BitbucketStructuredReference(
            "OPENSPEC_ACTIVE_CHANGE", self.change.id,
            BitbucketSourceReference(
                "bitbucket", "bitbucket:ref-non-head", "references/association/non-head", "c" * 40,
            ),
        )

        result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, declarations=(non_head,),
        ))).normalize(self.selection, self.subject_graph)

        self.assertTrue(result.admitted)
        self.assertEqual(result.associations, ())
        self.assertEqual(len(result.graph.pull_request_evidence), 1)
        self.assertEqual(len(result.graph.edges), 1)
        self.assertEqual(
            [diagnostic.as_dict() for diagnostic in result.diagnostics],
            [{"object_id": self.change.id, "reason_code": "revision-context-mismatch"}],
        )

    def test_distinct_declaration_locators_are_retained_deterministically(self):
        first_locator = BitbucketStructuredReference(
            "OPENSPEC_ACTIVE_CHANGE", self.change.id,
            BitbucketSourceReference("bitbucket", "bitbucket:shared-reference", "references/association/a"),
        )
        second_locator = BitbucketStructuredReference(
            "OPENSPEC_ACTIVE_CHANGE", self.change.id,
            BitbucketSourceReference("bitbucket", "bitbucket:shared-reference", "references/association/b"),
        )
        first = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, declarations=(second_locator, first_locator),
        ))).normalize(self.selection, self.subject_graph)
        second = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, declarations=(first_locator, second_locator),
        ))).normalize(self.selection, self.subject_graph)

        self.assertEqual(first.as_json(), second.as_json())
        self.assertEqual(len(first.associations), 2)
        association_evidence = {
            evidence.id: evidence
            for evidence in first.graph.evidence
            if evidence.properties.get("association_id") == self.change.id
        }
        self.assertEqual(
            {association.source_evidence_id for association in first.associations},
            set(association_evidence),
        )
        self.assertEqual(
            {association.provenance_evidence_id for association in first.associations},
            {evidence.provenance_ids[0] for evidence in association_evidence.values()},
        )
        self.assertEqual(
            {
                evidence.locator.source_artifact_identity.stable_locator
                for evidence in association_evidence.values()
            },
            {"references/association/a", "references/association/b"},
        )
        self.assertEqual(
            len({edge.id for edge in first.graph.edges if edge.kind == "references"}),
            2,
        )

    def test_conflicting_declaration_source_identity_is_excluded_and_mergeable(self):
        shared_reference = BitbucketSourceReference(
            "bitbucket", "bitbucket:shared-reference", "references/association/shared",
        )
        change_declaration = BitbucketStructuredReference(
            "OPENSPEC_ACTIVE_CHANGE", self.change.id, shared_reference,
        )
        jira_declaration = BitbucketStructuredReference(
            "JIRA_STORY", self.jira.id, shared_reference,
        )

        first = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, declarations=(jira_declaration, change_declaration),
        ))).normalize(self.selection, self.subject_graph)
        second = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, declarations=(change_declaration, jira_declaration),
        ))).normalize(self.selection, self.subject_graph)

        self.assertTrue(first.admitted)
        self.assertEqual(first.as_json(), second.as_json())
        self.assertEqual(first.associations, ())
        self.assertEqual(
            [diagnostic.as_dict() for diagnostic in first.diagnostics],
            [
                {"object_id": self.change.id, "reason_code": "conflicting-reference-identity"},
                {"object_id": self.jira.id, "reason_code": "conflicting-reference-identity"},
            ],
        )
        self.assertEqual(
            {edge.kind for edge in first.graph.edges},
            {"touches"},
        )
        merged = self.subject_graph.merged_with(first.graph)
        self.assertEqual(validate_graph_integrity(merged).status, "valid")

    def test_unsafe_source_identity_and_file_path_are_rejected_before_serialization(self):
        with self.assertRaises(ValueError):
            BitbucketSourceSelection("https://provider.example/pr/42", self.repository.id)
        with self.assertRaises(ValueError):
            reference("https://provider.example/pr/42")
        with self.assertRaises(ValueError):
            BitbucketChangedFileSourceRecord(
                "bitbucket:file-unsafe", "../secrets.txt", self.repository.id, HEAD,
                reference("bitbucket:file-unsafe", "file"),
            )

    def test_context_mismatched_file_is_excluded_without_affecting_pr_evidence(self):
        wrong_context = BitbucketChangedFileSourceRecord(
            "bitbucket:file-wrong", "src/wrong.py", "another-repository", HEAD,
            reference("bitbucket:file-wrong", "file"),
        )
        result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, changed_files=(wrong_context,),
        ))).normalize(self.selection, self.subject_graph)
        self.assertTrue(result.admitted)
        self.assertEqual(result.changed_files, ())
        self.assertEqual(result.diagnostics[0].reason_code, "changed-file-context-mismatch")
        self.assertEqual(len(result.graph.pull_request_evidence), 1)

    def test_classified_malformed_children_are_individual_safe_diagnostics(self):
        valid_file = BitbucketChangedFileSourceRecord(
            "bitbucket:file-valid", "src/valid.py", self.repository.id, HEAD,
            reference("bitbucket:file-valid", "file"),
        )
        invalid_files = (
            BitbucketChangedFileSourceRecord.from_untrusted(
                "bitbucket:file-unsafe", "../secrets.txt", self.repository.id, HEAD,
                reference("bitbucket:file-unsafe", "file"),
            ),
            BitbucketChangedFileSourceRecord.from_untrusted(
                "", "src/missing-id.py", self.repository.id, HEAD,
                reference("bitbucket:file-missing-id", "file"),
            ),
            BitbucketChangedFileSourceRecord.invalid(
                "malformed-changed-file-source", "bitbucket:file-malformed",
            ),
        )
        invalid_declarations = (
            BitbucketStructuredReference.from_untrusted(
                "OPENSPEC_ACTIVE_CHANGE", self.change.id, None,
            ),
            BitbucketStructuredReference.from_untrusted(
                "OPENSPEC_ACTIVE_CHANGE", "", reference("bitbucket:decl-missing-target", "association"),
            ),
            BitbucketStructuredReference.invalid("malformed-reference", "bitbucket:decl-malformed"),
            BitbucketStructuredReference.from_untrusted(
                "OPENSPEC_ACTIVE_CHANGE", "bad-target\n<declaration-body>",
                reference("bitbucket:decl-raw-target", "association"),
            ),
            BitbucketStructuredReference.from_untrusted(
                "OPENSPEC_ACTIVE_CHANGE", self.change.id, "raw declaration body",
            ),
        )
        result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id,
            changed_files=(*invalid_files, valid_file),
            declarations=invalid_declarations,
        ))).normalize(self.selection, self.subject_graph)

        self.assertTrue(result.admitted)
        self.assertEqual([item.stable_file_id for item in result.changed_files], [valid_file.stable_file_id])
        self.assertEqual(
            {item.reason_code for item in result.diagnostics},
            {
                "unsafe-file-path", "missing-file-identity", "malformed-changed-file-source",
                "missing-reference-source", "missing-reference-target", "malformed-reference",
            },
        )
        self.assertEqual(len(result.graph.pull_request_evidence), 1)
        serialized = result.as_json()
        for rejected_text in (
            "../secrets.txt", "src/missing-id.py", "bad-target", "declaration-body",
            "raw declaration body",
        ):
            self.assertNotIn(rejected_text, serialized)

    def test_changed_file_conversion_rejects_forged_evidence_binding(self):
        first = BitbucketChangedFileSourceRecord(
            "bitbucket:file-first", "src/first.py", self.repository.id, HEAD,
            reference("bitbucket:file-first", "file"),
        )
        second = BitbucketChangedFileSourceRecord(
            "bitbucket:file-second", "src/second.py", self.repository.id, HEAD,
            reference("bitbucket:file-second", "file"),
        )
        adapter_result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, changed_files=(first, second), declarations=(
                BitbucketStructuredReference(
                    "OPENSPEC_ACTIVE_CHANGE", self.change.id,
                    reference("bitbucket:ref-forged-binding", "association"),
                ),
            ),
        ))).normalize(self.selection, self.subject_graph)
        target, _ = adapter_result.changed_files
        forged = replace(
            target,
            source_evidence_id=adapter_result.pull_request_evidence.source_evidence_id,
            provenance_evidence_id=adapter_result.pull_request_evidence.provenance_evidence_id,
        )
        request = observations_to_openlore_request((forged,))
        bridge_result = ResolutionResult(
            request.id, "admitted", RoutingReference("repository-index-path", ".openlore/index"),
            (ChangedFileResolutionOutcome(
                forged.stable_file_id, forged.file, ResolutionStatus.RESOLVED,
                CodeLocator(self.repository.id, HEAD, forged.file, "payments.submit"),
            ),),
        )
        normalized = NormalizedPullRequestEvidence(
            adapter_result.pull_request_evidence,
            adapter_result.associations[0],
            adapter_result.repository_relation,
            (ChangedSymbolMapping(
                target.stable_file_id, target.file, MappingOutcome.UNRESOLVED,
                repository=self.repository.id, revision=HEAD,
            ),),
            adapter_result.graph.evidence,
            adapter_result.graph.provenance,
        )

        with self.assertRaisesRegex(BitbucketValidationError, "not bound"):
            adapt_openlore_result_to_normalized_pull_request_evidence(
                bridge_result, normalized, (forged,),
                changed_file_evidence=adapter_result.changed_file_evidence,
                changed_file_provenance=adapter_result.changed_file_provenance,
            )

    def test_candidate_extraction_rejects_explicit_forged_changed_file_source(self):
        first = BitbucketChangedFileSourceRecord(
            "bitbucket:file-candidate-first", "src/first.py", self.repository.id, HEAD,
            reference("bitbucket:file-candidate-first", "file"),
        )
        second = BitbucketChangedFileSourceRecord(
            "bitbucket:file-candidate-second", "src/second.py", self.repository.id, HEAD,
            reference("bitbucket:file-candidate-second", "file"),
        )
        adapter_result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, changed_files=(first, second), declarations=(
                BitbucketStructuredReference(
                    "OPENSPEC_ACTIVE_CHANGE", self.change.id,
                    reference("bitbucket:ref-candidate-binding", "association"),
                ),
            ),
        ))).normalize(self.selection, self.subject_graph)
        target, foreign = adapter_result.changed_files
        forged_mapping = ChangedSymbolMapping(
            target.stable_file_id, target.file, MappingOutcome.RESOLVED, "payments.submit",
            self.repository.id, HEAD, foreign.source_evidence_id, foreign.provenance_evidence_id,
        )
        normalized = NormalizedPullRequestEvidence(
            adapter_result.pull_request_evidence,
            adapter_result.associations[0],
            adapter_result.repository_relation,
            (forged_mapping,),
            adapter_result.graph.evidence + adapter_result.changed_file_evidence,
            adapter_result.graph.provenance + adapter_result.changed_file_provenance,
        )

        extracted = extract_pr_code_candidates((normalized,), self.subject_graph)

        self.assertEqual(extracted.metadata.emitted_candidate_count, 0)
        self.assertEqual(extracted.metadata.skipped_reason_counts, {"invalid-mapping-source": 1})
        self.assertEqual(extracted.graph.cross_graph_link_claims, ())

    def test_tampered_observation_path_cannot_cross_openlore_boundary(self):
        file_record = BitbucketChangedFileSourceRecord(
            "bitbucket:file-tampered-observation", "src/payments.py", self.repository.id, HEAD,
            reference("bitbucket:file-tampered-observation", "file"),
        )
        adapter_result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, changed_files=(file_record,), declarations=(
                BitbucketStructuredReference(
                    "OPENSPEC_ACTIVE_CHANGE", self.change.id,
                    reference("bitbucket:ref-tampered-observation", "association"),
                ),
            ),
        ))).normalize(self.selection, self.subject_graph)
        observation = adapter_result.changed_files[0]
        tampered = replace(observation, file="src/forged.py")
        request = observations_to_openlore_request((tampered,))
        bridge_result = ResolutionResult(
            request.id, "admitted", RoutingReference("repository-index-path", ".openlore/index"),
            (ChangedFileResolutionOutcome(
                tampered.stable_file_id, tampered.file, ResolutionStatus.RESOLVED,
                CodeLocator(self.repository.id, HEAD, tampered.file, "payments.submit"),
            ),),
        )
        normalized = NormalizedPullRequestEvidence(
            adapter_result.pull_request_evidence,
            adapter_result.associations[0],
            adapter_result.repository_relation,
            (ChangedSymbolMapping(
                observation.stable_file_id, observation.file, MappingOutcome.UNRESOLVED,
                repository=self.repository.id, revision=HEAD,
            ),),
            adapter_result.graph.evidence,
            adapter_result.graph.provenance,
        )

        with self.assertRaisesRegex(BitbucketValidationError, "not bound"):
            adapt_openlore_result_to_normalized_pull_request_evidence(
                bridge_result, normalized, (tampered,),
                changed_file_evidence=adapter_result.changed_file_evidence,
                changed_file_provenance=adapter_result.changed_file_provenance,
            )

    def test_direct_tampered_mapping_path_cannot_create_candidate_or_projection(self):
        file_record = BitbucketChangedFileSourceRecord(
            "bitbucket:file-tampered-mapping", "src/payments.py", self.repository.id, HEAD,
            reference("bitbucket:file-tampered-mapping", "file"),
        )
        adapter_result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, changed_files=(file_record,), declarations=(
                BitbucketStructuredReference(
                    "OPENSPEC_ACTIVE_CHANGE", self.change.id,
                    reference("bitbucket:ref-tampered-mapping", "association"),
                ),
            ),
        ))).normalize(self.selection, self.subject_graph)
        observation = adapter_result.changed_files[0]
        tampered_mapping = ChangedSymbolMapping(
            observation.stable_file_id, "src/forged.py", MappingOutcome.RESOLVED, "payments.submit",
            self.repository.id, HEAD, observation.source_evidence_id, observation.provenance_evidence_id,
        )
        normalized = NormalizedPullRequestEvidence(
            adapter_result.pull_request_evidence,
            adapter_result.associations[0],
            adapter_result.repository_relation,
            (tampered_mapping,),
            adapter_result.graph.evidence + adapter_result.changed_file_evidence,
            adapter_result.graph.provenance + adapter_result.changed_file_provenance,
        )

        extracted = extract_pr_code_candidates((normalized,), self.subject_graph)

        self.assertEqual(extracted.metadata.emitted_candidate_count, 0)
        self.assertEqual(extracted.graph.cross_graph_link_claims, ())
        self.assertEqual(extracted.graph.cross_graph_link_evidence, ())
        self.assertEqual(extracted.graph.cross_graph_link_lifecycle, ())
        self.assertEqual(extracted.graph.trusted_cross_graph_links, ())
        self.assertEqual(extracted.metadata.skipped_reason_counts, {"invalid-mapping-source": 1})

    def test_genuine_file_ids_with_substituted_path_cannot_cross_conversion_or_extraction(self):
        file_record = BitbucketChangedFileSourceRecord(
            "bitbucket:file-genuine-ids", "src/payments.py", self.repository.id, HEAD,
            reference("bitbucket:file-genuine-ids", "file"),
        )
        adapter_result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, changed_files=(file_record,), declarations=(
                BitbucketStructuredReference(
                    "OPENSPEC_ACTIVE_CHANGE", self.change.id,
                    reference("bitbucket:ref-genuine-ids", "association"),
                ),
            ),
        ))).normalize(self.selection, self.subject_graph)
        observation = adapter_result.changed_files[0]
        genuine_evidence = adapter_result.changed_file_evidence[0]
        genuine_provenance = adapter_result.changed_file_provenance[0]
        substituted_file = "src/substituted.py"
        substituted_evidence = replace(
            genuine_evidence,
            properties={**genuine_evidence.properties, "file": substituted_file},
        )
        substituted_observation = replace(
            observation,
            file=substituted_file,
            source_evidence=substituted_evidence,
            provenance=genuine_provenance,
        )
        request = observations_to_openlore_request((substituted_observation,))
        bridge_result = ResolutionResult(
            request.id, "admitted", RoutingReference("repository-index-path", ".openlore/index"),
            (ChangedFileResolutionOutcome(
                substituted_observation.stable_file_id, substituted_file, ResolutionStatus.RESOLVED,
                CodeLocator(self.repository.id, HEAD, substituted_file, "payments.submit"),
            ),),
        )
        normalized = NormalizedPullRequestEvidence(
            adapter_result.pull_request_evidence,
            adapter_result.associations[0],
            adapter_result.repository_relation,
            (ChangedSymbolMapping(
                observation.stable_file_id, substituted_file, MappingOutcome.RESOLVED,
                "payments.submit", self.repository.id, HEAD,
                observation.source_evidence_id, observation.provenance_evidence_id,
            ),),
            adapter_result.graph.evidence + (substituted_evidence,),
            adapter_result.graph.provenance + (genuine_provenance,),
        )

        with self.assertRaisesRegex(BitbucketValidationError, "not bound"):
            adapt_openlore_result_to_normalized_pull_request_evidence(
                bridge_result, normalized, (substituted_observation,),
                changed_file_evidence=(substituted_evidence,),
                changed_file_provenance=(genuine_provenance,),
            )

        extracted = extract_pr_code_candidates((normalized,), self.subject_graph)
        self.assertEqual(extracted.metadata.emitted_candidate_count, 0)
        self.assertEqual(extracted.metadata.skipped_reason_counts, {"invalid-mapping-source": 1})
        self.assertEqual(extracted.graph.cross_graph_link_claims, ())

    def test_openlore_handoff_preserves_file_and_source_context(self):
        file_record = BitbucketChangedFileSourceRecord(
            "bitbucket:file-1", "src/payments.py", self.repository.id, HEAD,
            reference("bitbucket:file-1", "file"),
        )
        result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, changed_files=(file_record,),
        ))).normalize(self.selection, self.subject_graph)
        request = observations_to_openlore_request(result.changed_files)
        self.assertEqual(request.evidence.source_evidence_id, result.changed_files[0].source_evidence_id)
        self.assertEqual(request.changed_files[0].source_provenance_id, result.changed_files[0].provenance_evidence_id)
        bridge_result = ResolutionResult(
            request.id, "admitted", RoutingReference("repository-index-path", ".openlore/index"),
            (ChangedFileResolutionOutcome(
                result.changed_files[0].stable_file_id, "src/payments.py", ResolutionStatus.RESOLVED,
                CodeLocator(self.repository.id, HEAD, "src/payments.py", "payments.submit"),
            ),),
        )
        mappings = adapt_openlore_result_to_changed_symbol_mappings(bridge_result, result.changed_files)
        self.assertEqual(mappings[0].id, result.changed_files[0].stable_file_id)
        self.assertEqual(mappings[0].repository, self.repository.id)
        self.assertEqual(mappings[0].revision, HEAD)
        self.assertEqual(mappings[0].source_evidence_id, result.changed_files[0].source_evidence_id)
        self.assertEqual(mappings[0].source_provenance_id, result.changed_files[0].provenance_evidence_id)

        unresolved = ResolutionResult(
            request.id, "admitted", RoutingReference("repository-index-path", ".openlore/index"),
            (ChangedFileResolutionOutcome(
                result.changed_files[0].stable_file_id, "src/payments.py", ResolutionStatus.AMBIGUOUS,
            ),),
        )
        unresolved_mapping = adapt_openlore_result_to_changed_symbol_mappings(unresolved, result.changed_files)[0]
        self.assertEqual(unresolved_mapping.outcome, "ambiguous")
        self.assertIsNone(unresolved_mapping.symbol)
        mismatched = ResolutionResult("different-request", "admitted", unresolved.routing, unresolved.outcomes)
        mismatched_mapping = adapt_openlore_result_to_changed_symbol_mappings(mismatched, result.changed_files)[0]
        self.assertEqual(mismatched_mapping.outcome, "unsupported")

    def test_invalid_context_result_cannot_create_resolved_mapping(self):
        file_record = BitbucketChangedFileSourceRecord(
            "bitbucket:file-invalid-context", "src/payments.py", self.repository.id, HEAD,
            reference("bitbucket:file-invalid-context", "file"),
        )
        result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, changed_files=(file_record,),
        ))).normalize(self.selection, self.subject_graph)
        request = observations_to_openlore_request(result.changed_files)
        invalid_context = ResolutionResult(
            request.id, "invalid-context", None,
            (ChangedFileResolutionOutcome(
                file_record.stable_file_id, file_record.file, ResolutionStatus.RESOLVED,
                CodeLocator(self.repository.id, HEAD, file_record.file, "payments.submit"),
            ),),
        )

        mapping = adapt_openlore_result_to_changed_symbol_mappings(
            invalid_context, result.changed_files,
        )[0]

        self.assertEqual(mapping.outcome, MappingOutcome.UNSUPPORTED)
        self.assertIsNone(mapping.symbol)
        self.assertEqual(mapping.repository, self.repository.id)
        self.assertEqual(mapping.revision, HEAD)

    def test_normalized_evidence_adapter_preserves_context_and_rejects_other_pr(self):
        file_record = BitbucketChangedFileSourceRecord(
            "bitbucket:file-1", "src/payments.py", self.repository.id, HEAD,
            reference("bitbucket:file-1", "file"),
        )
        declaration = BitbucketStructuredReference(
            "OPENSPEC_ACTIVE_CHANGE", self.change.id, reference("bitbucket:ref-1", "association"),
        )
        result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, changed_files=(file_record,), declarations=(declaration,),
        ))).normalize(self.selection, self.subject_graph)
        request = observations_to_openlore_request(result.changed_files)
        bridge_result = ResolutionResult(
            request.id, "admitted", RoutingReference("repository-index-path", ".openlore/index"),
            (ChangedFileResolutionOutcome(
                file_record.stable_file_id, file_record.file, ResolutionStatus.RESOLVED,
                CodeLocator(self.repository.id, HEAD, file_record.file, "payments.submit"),
            ),),
        )
        normalized = NormalizedPullRequestEvidence(
            result.pull_request_evidence,
            result.associations[0],
            result.repository_relation,
            (ChangedSymbolMapping(
                file_record.stable_file_id, file_record.file, MappingOutcome.UNRESOLVED,
                repository=self.repository.id, revision=HEAD,
            ),),
            result.graph.evidence,
            result.graph.provenance,
        )

        converted = adapt_openlore_result_to_normalized_pull_request_evidence(
            bridge_result, normalized, result.changed_files,
        )
        mapping = converted.mappings[0]
        self.assertEqual(mapping.outcome, MappingOutcome.RESOLVED)
        self.assertEqual(mapping.id, file_record.stable_file_id)
        self.assertEqual(mapping.repository, self.repository.id)
        self.assertEqual(mapping.revision, HEAD)
        self.assertEqual(mapping.source_evidence_id, result.changed_files[0].source_evidence_id)
        self.assertEqual(mapping.source_provenance_id, result.changed_files[0].provenance_evidence_id)

        mismatched_pr = BitbucketChangedFileObservation(
            file_record.stable_file_id, file_record.file, "bitbucket:other-pr",
            self.repository.id, HEAD, result.changed_files[0].source_evidence_id,
            result.changed_files[0].provenance_evidence_id,
        )
        with self.assertRaisesRegex(BitbucketValidationError, "PR context"):
            adapt_openlore_result_to_normalized_pull_request_evidence(
                bridge_result, normalized, (mismatched_pr,),
            )

    def test_normalized_evidence_adapter_rejects_changed_files_sharing_source_artifact(self):
        shared_reference = reference("bitbucket:file-shared", "file")
        first_file = BitbucketChangedFileSourceRecord(
            "bitbucket:file-first", "src/first.py", self.repository.id, HEAD, shared_reference,
        )
        second_file = BitbucketChangedFileSourceRecord(
            "bitbucket:file-second", "src/second.py", self.repository.id, HEAD, shared_reference,
        )
        collision_result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, changed_files=(first_file, second_file),
        ))).normalize(self.selection, self.subject_graph)

        self.assertEqual(collision_result.changed_files, ())
        self.assertEqual(collision_result.changed_file_evidence, ())
        self.assertEqual(collision_result.changed_file_provenance, ())
        self.assertTrue(collision_result.pull_request_evidence)
        self.assertEqual(
            [item.stable_file_id for item in collision_result.diagnostics],
            ["bitbucket:file-first", "bitbucket:file-second"],
        )

        valid_result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, changed_files=(first_file,), declarations=(
                BitbucketStructuredReference(
                    "OPENSPEC_ACTIVE_CHANGE", self.change.id,
                    reference("bitbucket:ref-shared-file", "association"),
                ),
            ),
        ))).normalize(self.selection, self.subject_graph)
        observation = valid_result.changed_files[0]
        source_evidence = valid_result.changed_file_evidence[0]
        source_provenance = valid_result.changed_file_provenance[0]
        other_provenance = replace(source_provenance, content_hash="0" * 64)
        other_evidence = replace(source_evidence, provenance_ids=(other_provenance.id,))
        other_observation = replace(
            observation,
            stable_file_id="bitbucket:file-second",
            file="src/second.py",
            provenance_evidence_id=other_provenance.id,
            source_evidence=other_evidence,
            provenance=other_provenance,
        )
        observations = (observation, other_observation)
        request = observations_to_openlore_request(observations)
        bridge_result = ResolutionResult(
            request.id, "admitted", RoutingReference("repository-index-path", ".openlore/index"),
            tuple(
                ChangedFileResolutionOutcome(
                    item.stable_file_id, item.file, ResolutionStatus.RESOLVED,
                    CodeLocator(self.repository.id, HEAD, item.file, "payments.submit"),
                )
                for item in observations
            ),
        )
        normalized = NormalizedPullRequestEvidence(
            valid_result.pull_request_evidence,
            valid_result.associations[0],
            valid_result.repository_relation,
            (ChangedSymbolMapping(
                observation.stable_file_id, observation.file, MappingOutcome.UNRESOLVED,
                repository=self.repository.id, revision=HEAD,
            ),),
            valid_result.graph.evidence,
            valid_result.graph.provenance,
        )

        with self.assertRaisesRegex(BitbucketValidationError, "ambiguous"):
            adapt_openlore_result_to_normalized_pull_request_evidence(
                bridge_result, normalized, observations,
                changed_file_evidence=(source_evidence, other_evidence),
                changed_file_provenance=(source_provenance, other_provenance),
            )

    def test_adapter_openlore_conversion_preserves_file_evidence_for_candidate_extraction(self):
        file_record = BitbucketChangedFileSourceRecord(
            "bitbucket:file-end-to-end", "src/payments.py", self.repository.id, HEAD,
            reference("bitbucket:file-end-to-end", "file"),
        )
        declaration = BitbucketStructuredReference(
            "OPENSPEC_ACTIVE_CHANGE", self.change.id, reference("bitbucket:ref-end-to-end", "association"),
        )
        adapter_result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, changed_files=(file_record,), declarations=(declaration,),
        ))).normalize(self.selection, self.subject_graph)
        observation = adapter_result.changed_files[0]
        request = observations_to_openlore_request((replace(
            observation, source_evidence=None, provenance=None,
        ),))
        bridge_result = ResolutionResult(
            request.id, "admitted", RoutingReference("repository-index-path", ".openlore/index"),
            (ChangedFileResolutionOutcome(
                observation.stable_file_id, observation.file, ResolutionStatus.RESOLVED,
                CodeLocator(self.repository.id, HEAD, observation.file, "payments.submit"),
            ),),
        )
        normalized = NormalizedPullRequestEvidence(
            adapter_result.pull_request_evidence,
            adapter_result.associations[0],
            adapter_result.repository_relation,
            (ChangedSymbolMapping(
                observation.stable_file_id, observation.file, MappingOutcome.UNRESOLVED,
                repository=self.repository.id, revision=HEAD,
            ),),
            adapter_result.graph.evidence,
            adapter_result.graph.provenance,
        )

        converted = adapt_openlore_result_to_normalized_pull_request_evidence(
            bridge_result,
            normalized,
            (replace(observation, source_evidence=None, provenance=None),),
            changed_file_evidence=adapter_result.changed_file_evidence,
            changed_file_provenance=adapter_result.changed_file_provenance,
        )
        extracted = extract_pr_code_candidates((converted,), self.subject_graph)

        self.assertIn(
            observation.source_evidence_id,
            {item.id for item in converted.evidence},
        )
        self.assertIn(
            observation.provenance_evidence_id,
            {item.id for item in converted.provenance},
        )
        self.assertEqual(extracted.metadata.emitted_candidate_count, 1)
        self.assertNotIn(
            "missing-mapping-source",
            extracted.metadata.skipped_reason_counts,
        )
        self.assertEqual(
            extracted.graph.cross_graph_link_evidence[0].provenance_evidence_id,
            observation.source_evidence_id,
        )
        self.assertEqual(
            extracted.graph.cross_graph_link_evidence[0].observation_id,
            observation.stable_file_id,
        )
        self.assertEqual(
            extracted.graph.cross_graph_link_evidence[0].trust_disposition,
            "untrusted",
        )

    def test_detached_existing_provenance_cannot_emit_candidate(self):
        file_record = BitbucketChangedFileSourceRecord(
            "bitbucket:file-detached-provenance", "src/payments.py", self.repository.id, HEAD,
            reference("bitbucket:file-detached-provenance", "file"),
        )
        declaration = BitbucketStructuredReference(
            "OPENSPEC_ACTIVE_CHANGE", self.change.id,
            reference("bitbucket:ref-detached-provenance", "association"),
        )
        adapter_result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, changed_files=(file_record,), declarations=(declaration,),
        ))).normalize(self.selection, self.subject_graph)
        observation = adapter_result.changed_files[0]
        request = observations_to_openlore_request((replace(
            observation, source_evidence=None, provenance=None,
        ),))
        bridge_result = ResolutionResult(
            request.id, "admitted", RoutingReference("repository-index-path", ".openlore/index"),
            (ChangedFileResolutionOutcome(
                observation.stable_file_id, observation.file, ResolutionStatus.RESOLVED,
                CodeLocator(self.repository.id, HEAD, observation.file, "payments.submit"),
            ),),
        )
        normalized = NormalizedPullRequestEvidence(
            adapter_result.pull_request_evidence,
            adapter_result.associations[0],
            adapter_result.repository_relation,
            (ChangedSymbolMapping(
                observation.stable_file_id, observation.file, MappingOutcome.UNRESOLVED,
                repository=self.repository.id, revision=HEAD,
            ),),
            adapter_result.graph.evidence + adapter_result.changed_file_evidence,
            adapter_result.graph.provenance + adapter_result.changed_file_provenance,
        )
        converted = adapt_openlore_result_to_normalized_pull_request_evidence(
            bridge_result, normalized, (replace(observation, source_evidence=None, provenance=None),),
            changed_file_evidence=adapter_result.changed_file_evidence,
            changed_file_provenance=adapter_result.changed_file_provenance,
        )
        detached = next(
            record for record in converted.provenance
            if record.id != observation.provenance_evidence_id
        )
        detached_mapping = replace(
            converted.mappings[0], source_provenance_id=detached.id,
        )
        extracted = extract_pr_code_candidates(
            (replace(converted, mappings=(detached_mapping,)),), self.subject_graph,
        )

        self.assertEqual(extracted.metadata.emitted_candidate_count, 0)
        self.assertEqual(
            extracted.metadata.skipped_reason_counts["mapping-provenance-mismatch"], 1,
        )
        self.assertEqual(extracted.graph.cross_graph_link_claims, ())

    def test_openlore_conversion_rejects_detached_existing_provenance(self):
        file_record = BitbucketChangedFileSourceRecord(
            "bitbucket:file-detached-conversion", "src/payments.py", self.repository.id, HEAD,
            reference("bitbucket:file-detached-conversion", "file"),
        )
        adapter_result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(
            self.repository.id, changed_files=(file_record,), declarations=(
                BitbucketStructuredReference(
                    "OPENSPEC_ACTIVE_CHANGE", self.change.id,
                    reference("bitbucket:ref-detached-conversion", "association"),
                ),
            ),
        ))).normalize(self.selection, self.subject_graph)
        observation = adapter_result.changed_files[0]
        detached = next(
            record for record in adapter_result.graph.provenance
            if record.id != observation.provenance_evidence_id
        )
        detached_observation = replace(observation, provenance_evidence_id=detached.id)
        request = observations_to_openlore_request((detached_observation,))
        bridge_result = ResolutionResult(
            request.id, "admitted", RoutingReference("repository-index-path", ".openlore/index"),
            (ChangedFileResolutionOutcome(
                observation.stable_file_id, observation.file, ResolutionStatus.RESOLVED,
                CodeLocator(self.repository.id, HEAD, observation.file, "payments.submit"),
            ),),
        )
        normalized = NormalizedPullRequestEvidence(
            adapter_result.pull_request_evidence,
            adapter_result.associations[0],
            adapter_result.repository_relation,
            (ChangedSymbolMapping(
                observation.stable_file_id, observation.file, MappingOutcome.UNRESOLVED,
                repository=self.repository.id, revision=HEAD,
            ),),
            adapter_result.graph.evidence,
            adapter_result.graph.provenance,
        )

        with self.assertRaisesRegex(BitbucketValidationError, "source evidence/provenance"):
            adapt_openlore_result_to_normalized_pull_request_evidence(
                bridge_result, normalized, (detached_observation,),
                changed_file_evidence=adapter_result.changed_file_evidence,
                changed_file_provenance=(*adapter_result.changed_file_provenance, detached),
            )

    def test_openlore_result_cannot_cross_mixed_pull_request_batch(self):
        pr_a = BitbucketChangedFileObservation(
            "bitbucket:file-a", "src/a.py", "bitbucket:pr-a", self.repository.id,
            HEAD, "evidence:file-a", "provenance:file-a",
        )
        pr_b = BitbucketChangedFileObservation(
            "bitbucket:file-b", "src/b.py", "bitbucket:pr-b", self.repository.id,
            HEAD, "evidence:file-b", "provenance:file-b",
        )
        request_a = observations_to_openlore_request((pr_a,))
        result_a = ResolutionResult(
            request_a.id, "admitted", RoutingReference("repository-index-path", ".openlore/index"),
            (ChangedFileResolutionOutcome(
                pr_a.stable_file_id, pr_a.file, ResolutionStatus.RESOLVED,
                CodeLocator(self.repository.id, HEAD, pr_a.file, "payments.submit"),
            ),),
        )
        self.assertEqual(
            adapt_openlore_result_to_changed_symbol_mappings(result_a, (pr_a,))[0].outcome,
            "resolved",
        )

        with self.assertRaises(BitbucketValidationError):
            observations_to_openlore_request((pr_a, pr_b))
        with self.assertRaises(BitbucketValidationError):
            adapt_openlore_result_to_changed_symbol_mappings(result_a, (pr_a, pr_b))

    def test_merge_and_readback_are_current_format_and_adapter_does_not_persist(self):
        result = BitbucketSourceAdapter(FakeBitbucketPort(source_record(self.repository.id))).normalize(self.selection, self.subject_graph)
        merged = self.subject_graph.merged_with(result.graph)
        with tempfile.TemporaryDirectory() as temporary:
            readback = initialize_ladybugdb_store(Path(temporary) / "store").write_snapshot(merged)
        self.assertEqual(readback.as_json(), merged.as_json())
        self.assertEqual(result.graph.pull_request_evidence_count, 1)
        self.assertEqual(result.changed_file_evidence, ())


if __name__ == "__main__":
    unittest.main()
