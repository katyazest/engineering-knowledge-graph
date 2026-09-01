from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.ontology import Evidence, GraphSnapshot, ProvenanceKind, ProvenanceRecord, SourceArtifactIdentity, SourceArtifactLocator, stable_id
from engineering_kg.persistence import PersistenceIntegrityError, initialize_ladybugdb_store
from engineering_kg.query import EngineeringKgQuery, GraphQueryValidationError
from engineering_kg.validation import validate_graph_integrity


def external() -> ProvenanceRecord:
    identity = SourceArtifactIdentity("jira", "ENG", "issue", "42", "issues/ENG-42")
    return ProvenanceRecord(ProvenanceKind.EXTERNAL, "2026-09-01T12:00:00+00:00", "sha256", hashlib.sha256(b"normalized issue").hexdigest(), "jira-adapter", "1", identity)


class FactProvenanceTest(unittest.TestCase):
    def test_admission_rejects_required_matrix_field_classes(self) -> None:
        record = external()
        for content_hash, message in (
            ("", "content_hash must be a non-empty string"),
            ("A" * 64, "content_hash must be a lowercase sha256 digest"),
        ):
            with self.subTest(content_hash=content_hash), self.assertRaisesRegex(ValueError, message):
                ProvenanceRecord(
                    "external", record.observed_at, "sha256", content_hash,
                    record.extractor_id, record.extractor_version, record.source_artifact_identity,
                )
        for extractor_version, message in (
            ("", "extractor_version must be a non-empty string"),
            ("version 1", "extractor_version contains unsafe content"),
        ):
            with self.subTest(extractor_version=extractor_version), self.assertRaisesRegex(ValueError, message):
                ProvenanceRecord(
                    "external", record.observed_at, "sha256", record.content_hash,
                    record.extractor_id, extractor_version, record.source_artifact_identity,
                )
        for field, invalid_value, message in (
            ("source_identity", "", "source_identity must be non-empty"),
            ("source_identity", "display identity", "source_identity must not be a display name"),
            ("revision_or_version", "", "revision_or_version must be non-empty"),
            ("revision_or_version", " rev-1 ", "revision_or_version is malformed"),
        ):
            values = record.source_artifact_identity.as_dict()
            values[field] = invalid_value
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, message
            ):
                SourceArtifactIdentity(
                    values["source_type"], values["source_identity"], values["artifact_type"],
                    values["revision_or_version"], values["stable_locator"],
                )
        with self.assertRaisesRegex(ValueError, "derived rule and input_provenance_ids are required"):
            ProvenanceRecord(
                "derived", record.observed_at, "sha256", "b" * 64,
                "deriver", "1", None, None, (record.id,),
            )

    def test_complete_external_and_derived_records_are_payload_free_and_ordered(self) -> None:
        asserted = external()
        derived = ProvenanceRecord("derived", "2026-09-01T12:01:00+00:00", "sha256", hashlib.sha256(b"input").hexdigest(), "deriver", "1", None, "rule", (asserted.id,))
        evidence = Evidence(stable_id("evidence", asserted.source_artifact_identity.id), "jira", SourceArtifactLocator(asserted.source_artifact_identity), provenance_ids=(asserted.id,))
        graph = GraphSnapshot(evidence=(evidence,), provenance=(derived, asserted))
        self.assertEqual([item.id for item in graph.provenance], sorted((asserted.id, derived.id)))
        self.assertEqual(validate_graph_integrity(graph).status, "valid")
        serialized = graph.as_json()
        self.assertNotIn("normalized issue", serialized)
        self.assertNotIn("provider_payload", serialized)

    def test_equivalent_coalesces_and_bad_or_dangling_records_are_rejected(self) -> None:
        record = external()
        self.assertEqual(GraphSnapshot(provenance=(record,)).merged_with(GraphSnapshot(provenance=(record,))).provenance, (record,))
        class CollidingProvenance(ProvenanceRecord):
            @property
            def id(self) -> str:
                return "provenance:forced-collision"

        conflicting = CollidingProvenance(
            "external", record.observed_at, record.content_hash_algorithm,
            record.content_hash, record.extractor_id, "2", record.source_artifact_identity,
        )
        colliding = CollidingProvenance(
            "external", record.observed_at, record.content_hash_algorithm,
            record.content_hash, record.extractor_id, "1", record.source_artifact_identity,
        )
        with self.assertRaisesRegex(ValueError, "Conflicting graph record values"):
            GraphSnapshot(provenance=(colliding,)).merged_with(GraphSnapshot(provenance=(conflicting,)))
        with self.assertRaisesRegex(ValueError, "observed_at"):
            ProvenanceRecord("external", "not-a-time", "sha256", "a" * 64, "adapter", "1", record.source_artifact_identity)
        with self.assertRaisesRegex(ValueError, "extractor_id contains unsafe content"):
            ProvenanceRecord("external", record.observed_at, "sha256", "a" * 64, "token=secret", "1", record.source_artifact_identity)
        with self.assertRaisesRegex(
            ValueError, "input_provenance_ids must contain stable provenance IDs"
        ):
            ProvenanceRecord(
                "derived", "2026-09-01T12:01:00+00:00", "sha256", "b" * 64,
                "deriver", "1", None, "rule", ("missing",),
            )

    def test_snapshot_admission_rejects_dangling_derived_input_provenance(self) -> None:
        dangling_id = "provenance:" + "0" * 16
        dangling = ProvenanceRecord(
            "derived", "2026-09-01T12:01:00+00:00", "sha256", "b" * 64,
            "deriver", "1", None, "rule", (dangling_id,),
        )
        with self.assertRaisesRegex(
            ValueError,
            f"derived provenance references absent input provenance: {dangling.id}: {dangling_id}",
        ):
            GraphSnapshot(provenance=(dangling,))

    def test_derived_provenance_rejects_unsafe_rule_and_input_references(self) -> None:
        asserted = external()
        for field, value in (
            ("derivation_rule_id", "token=secret"),
            ("derivation_rule_id", "https://provider.example/response"),
            ("derivation_rule_id", "raw source body"),
            ("derivation_rule_id", "provider response data"),
            ("input_provenance_ids", ("credential=secret",)),
            ("input_provenance_ids", ("https://provider.example/response",)),
            ("input_provenance_ids", ("raw source body",)),
            ("input_provenance_ids", ("provider response data",)),
        ):
            kwargs = {field: value}
            with self.subTest(field=field, value=value), self.assertRaisesRegex(
                ValueError, field
            ):
                ProvenanceRecord(
                    "derived", "2026-09-01T12:01:00+00:00", "sha256", "b" * 64,
                    "deriver", "1", None,
                    kwargs.get("derivation_rule_id", "rule"),
                    kwargs.get("input_provenance_ids", (asserted.id,)),
                )

    def test_persistence_round_trip_and_incomplete_external_rejection(self) -> None:
        record = external()
        evidence = Evidence(stable_id("evidence", record.source_artifact_identity.id), "jira", SourceArtifactLocator(record.source_artifact_identity), provenance_ids=(record.id,))
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "store")
            self.assertEqual(store.write_snapshot(GraphSnapshot(evidence=(evidence,), provenance=(record,))).provenance, (record,))
            with self.assertRaisesRegex(ValueError, "external evidence lacks complete provenance"):
                GraphSnapshot(evidence=(Evidence(evidence.id, "jira", evidence.locator),))

    def test_external_evidence_rejects_derived_or_mismatched_source_provenance(self) -> None:
        asserted = external()
        with self.assertRaisesRegex(ValueError, "derived provenance cannot contain source_artifact_identity"):
            ProvenanceRecord(
                "derived", "2026-09-01T12:01:00+00:00", "sha256", "b" * 64,
                "deriver", "1", asserted.source_artifact_identity, "rule", (asserted.id,),
            )
        derived = ProvenanceRecord(
            "derived", "2026-09-01T12:01:00+00:00", "sha256", "b" * 64,
            "deriver", "1", None, "rule", (asserted.id,),
        )
        evidence = Evidence(
            stable_id("evidence", asserted.source_artifact_identity.id), "jira",
            SourceArtifactLocator(asserted.source_artifact_identity), provenance_ids=(derived.id,),
        )
        with self.assertRaisesRegex(ValueError, "external evidence cannot reference derived provenance"):
            GraphSnapshot(evidence=(evidence,), provenance=(asserted, derived))

        other_identity = SourceArtifactIdentity("jira", "PLAT", "issue", "42", "issues/PLAT-42")
        other = ProvenanceRecord(
            "external", asserted.observed_at, "sha256", asserted.content_hash,
            "jira-adapter", "1", other_identity,
        )
        mismatched = Evidence(
            evidence.id, "jira", evidence.locator, provenance_ids=(other.id,),
        )
        with self.assertRaisesRegex(ValueError, "source-artifact identity does not match evidence"):
            GraphSnapshot(evidence=(mismatched,), provenance=(other,))

        raw_derived = derived.as_dict()
        raw_derived["source_artifact_identity"] = asserted.source_artifact_identity.as_dict()
        with tempfile.TemporaryDirectory() as tmp:
            store = initialize_ladybugdb_store(Path(tmp) / "store")
            store._write_raw({
                "provenance": {raw_derived["id"]: raw_derived},
                "provenance_order": [raw_derived["id"]],
            })
            with self.assertRaisesRegex(PersistenceIntegrityError, "derived provenance cannot contain source_artifact_identity"):
                store.read_snapshot()

    def test_integrity_and_query_reject_an_admission_bypassing_inconsistent_association(self) -> None:
        asserted = external()
        derived = ProvenanceRecord(
            "derived", "2026-09-01T12:01:00+00:00", "sha256", "b" * 64,
            "deriver", "1", None, "rule", (asserted.id,),
        )
        evidence = Evidence(
            stable_id("evidence", asserted.source_artifact_identity.id), "jira",
            SourceArtifactLocator(asserted.source_artifact_identity), provenance_ids=(asserted.id,),
        )
        snapshot = GraphSnapshot(evidence=(evidence,), provenance=(asserted, derived))
        object.__setattr__(
            snapshot, "evidence", (Evidence(evidence.id, "jira", evidence.locator, provenance_ids=(derived.id,)),)
        )
        validation = validate_graph_integrity(snapshot)
        self.assertEqual(validation.status, "invalid")
        self.assertEqual(
            validation.metadata.diagnostics[0].rule_id,
            "provenance-evidence-semantic-consistency",
        )
        with self.assertRaises(GraphQueryValidationError):
            EngineeringKgQuery.from_snapshot(snapshot).get_traceability("missing", require_validation=True)


if __name__ == "__main__":
    unittest.main()
