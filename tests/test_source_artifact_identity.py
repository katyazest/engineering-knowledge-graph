from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from engineering_kg.ingest.source_artifact import normalize_source_artifact
from engineering_kg.ontology import (
    Evidence, GraphSnapshot, OpenSpecLocator, SourceArtifactIdentity, SourceArtifactLocator, stable_id,
)


class SourceArtifactIdentityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fields = {
            "source_type": "openspec",
            "source_identity": "requirements",
            "artifact_type": "openspec-spec",
            "revision_or_version": "a" * 40,
            "stable_locator": "openspec/specs/payments/spec.md",
        }

    def test_equivalent_identity_is_stable_and_each_component_is_distinct(self) -> None:
        base = SourceArtifactIdentity(**self.fields)
        self.assertEqual(base.id, SourceArtifactIdentity(**self.fields).id)
        for field, replacement in {
            "source_type": "jira",
            "source_identity": "other-requirements",
            "artifact_type": "openspec-change",
            "revision_or_version": "b" * 40,
            "stable_locator": "openspec/specs/refunds/spec.md",
        }.items():
            fields = dict(self.fields)
            fields[field] = replacement
            self.assertNotEqual(base.id, SourceArtifactIdentity(**fields).id)

    def test_incomplete_or_unsafe_identity_is_rejected_deterministically(self) -> None:
        for field, value in (
            ("revision_or_version", ""),
            ("source_identity", "Requirements Store"),
            ("stable_locator", "/private/tmp/spec.md"),
            ("stable_locator", "https://example.invalid/spec.md"),
            ("source_identity", "token=secret"),
        ):
            fields = dict(self.fields)
            fields[field] = value
            with self.assertRaisesRegex(ValueError, "invalid-source-artifact-identity"):
                SourceArtifactIdentity(**fields)

    def test_embedded_navigation_uris_and_credential_variants_are_rejected_in_every_component(self) -> None:
        for unsafe_value in (
            "repo;https://example.invalid/artifact",
            "repo;mailto:owner@example.invalid",
            "ssh://git@example.invalid/repository",
            "git://example.invalid/repository",
            "credentials=secret",
        ):
            for field in self.fields:
                fields = dict(self.fields)
                fields[field] = unsafe_value
                with self.assertRaisesRegex(ValueError, "invalid-source-artifact-identity"):
                    SourceArtifactIdentity(**fields)

    def test_absolute_paths_are_rejected_in_every_identity_component(self) -> None:
        for field in self.fields:
            fields = dict(self.fields)
            fields[field] = "/private/checkout/artifact"
            with self.assertRaisesRegex(ValueError, f"{field}.*absolute path"):
                SourceArtifactIdentity(**fields)

    def test_provider_neutral_adapter_accepts_only_identity_and_navigation_detail(self) -> None:
        artifact = normalize_source_artifact(**self.fields, navigation_detail={"heading_name": "Payment"})
        self.assertEqual(artifact.identity.id, SourceArtifactIdentity(**self.fields).id)
        self.assertEqual(artifact.as_dict()["navigation_detail"], {"heading_name": "Payment"})
        for detail in ({"url": "https://example.invalid"}, {"payload": "body"}, {"heading_name": "token=secret"}):
            with self.assertRaisesRegex(ValueError, "invalid-source-artifact-identity"):
                normalize_source_artifact(**self.fields, navigation_detail=detail)
        for unsafe_value in ("mailto:owner@example.invalid", "credentials=secret"):
            for field in self.fields:
                fields = dict(self.fields)
                fields[field] = unsafe_value
                with self.assertRaisesRegex(ValueError, "invalid-source-artifact-identity"):
                    normalize_source_artifact(**fields)

    def test_normalization_rejects_payload_body_and_content_values_in_every_identity_field(self) -> None:
        for unsafe_value in ("provider payload", "full source body", "artifact content"):
            for field in self.fields:
                fields = dict(self.fields)
                fields[field] = unsafe_value
                with self.subTest(field=field, value=unsafe_value):
                    with self.assertRaisesRegex(
                        ValueError, f"{field} contains unsafe content"
                    ):
                        normalize_source_artifact(**fields)

    def test_navigation_detail_rejects_unknown_nested_and_body_like_values_before_graph_emission(self) -> None:
        for detail in (
            {"provider_field": "value"},
            {"heading_name": "# heading\nfull requirement body"},
            {"section": {"nested": "payload"}},
            {"line_start": 0},
        ):
            with self.assertRaisesRegex(ValueError, "invalid-source-artifact-identity"):
                normalize_source_artifact(**self.fields, navigation_detail=detail)

    def test_source_evidence_metadata_rejects_provider_bodies_before_graph_emission(self) -> None:
        identity = SourceArtifactIdentity(**self.fields)
        for properties in (
            {"provider_payload": "body"},
            {"repository": "payments", "extra": "arbitrary"},
            {"repository": "payments", "merged_revision": "abc\nsource body"},
        ):
            with self.assertRaisesRegex(ValueError, "invalid-source-artifact-identity"):
                Evidence(
                    stable_id("evidence", identity.id), "openspec",
                    SourceArtifactLocator(identity), properties,
                )

    def test_graph_merge_exercises_equivalent_distinct_and_conflicting_identity_cases(self) -> None:
        base = SourceArtifactIdentity(**self.fields)
        equivalent = Evidence(stable_id("evidence", base.id), "openspec", SourceArtifactLocator(base))
        self.assertEqual(
            GraphSnapshot(evidence=(equivalent,)).merged_with(
                GraphSnapshot(evidence=(equivalent,))
            ).evidence_count,
            1,
        )
        for field, replacement in {
            "source_type": "jira",
            "source_identity": "other-requirements",
            "artifact_type": "openspec-change",
            "revision_or_version": "b" * 40,
            "stable_locator": "openspec/specs/refunds/spec.md",
        }.items():
            fields = dict(self.fields)
            fields[field] = replacement
            distinct = SourceArtifactIdentity(**fields)
            record = Evidence(
                stable_id("evidence", distinct.id), "openspec", SourceArtifactLocator(distinct)
            )
            self.assertEqual(
                GraphSnapshot(evidence=(equivalent,)).merged_with(
                    GraphSnapshot(evidence=(record,))
                ).evidence_count,
                2,
            )
        conflicting = Evidence(
            equivalent.id, "openspec", SourceArtifactLocator(base, {"section": "other"})
        )
        for first, second in ((equivalent, conflicting), (conflicting, equivalent)):
            with self.assertRaisesRegex(ValueError, "Conflicting graph record values"):
                GraphSnapshot(evidence=(first,)).merged_with(GraphSnapshot(evidence=(second,)))

    def test_graph_merge_rejects_an_arbitrary_id_for_identity_evidence(self) -> None:
        identity = SourceArtifactIdentity(**self.fields)
        arbitrary = Evidence("evidence:arbitrary", "openspec", SourceArtifactLocator(identity))

        with self.assertRaisesRegex(
            ValueError, "evidence ID does not match its derived source-artifact identity"
        ):
            GraphSnapshot().merged_with(
                GraphSnapshot(evidence=(arbitrary,), allow_legacy_evidence=True)
            )

    def test_openspec_locator_rejects_embedded_identity_disagreement(self) -> None:
        identity = SourceArtifactIdentity(**self.fields)
        for artifact_type, relative_file_path in (
            ("openspec-change", self.fields["stable_locator"]),
            (self.fields["artifact_type"], "openspec/specs/refunds/spec.md"),
        ):
            with self.assertRaisesRegex(ValueError, "does not match source-artifact identity"):
                OpenSpecLocator(
                    relative_file_path, artifact_type, "durable:payments",
                    source_artifact_identity=identity,
                )


if __name__ == "__main__":
    unittest.main()
