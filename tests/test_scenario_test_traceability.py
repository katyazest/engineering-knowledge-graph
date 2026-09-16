from __future__ import annotations

import sys
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from engineering_kg.ingest.openspec import OpenSpecStoreSourceValidationResult, extract_openspec_graph
from engineering_kg.ingest.scenario_test_traceability import (
    TraceabilityAdmissionError,
    admit_scenario_test_traceability,
    normalize_test_code_resolution,
    normalize_test_execution_observation,
)
from engineering_kg.ontology import CodeLocator, Edge, EdgeKind, NodeKind, verification_node
from engineering_kg.query import EngineeringKgQuery, GraphObjectNotFoundError, GraphQueryValidationError
from engineering_kg.persistence import PersistenceIntegrityError, initialize_ladybugdb_store
from engineering_kg.pipeline import run_pipeline
from engineering_kg.ingest.openspec import RegisteredOpenSpecStore
from engineering_kg.ontology import GraphSnapshot, SourceArtifactIdentity, SourceArtifactLocator, ProvenanceRecord, Evidence, stable_id

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures/non-git-workspace/openspec/requirements_repo"
from engineering_kg.validation import validate_graph_integrity


class ScenarioTestTraceabilityTest(unittest.TestCase):
    def _source(self, root: Path) -> OpenSpecStoreSourceValidationResult:
        return OpenSpecStoreSourceValidationResult(
            "valid", "fixture", "requirements", "requirements", root,
            root / "openspec", root / "openspec/specs", root / "openspec/changes",
            revision_or_version="a" * 40, observed_at="2026-09-01T12:00:00+00:00",
        )

    def _workspace(self, sidecar: str | None = None) -> tuple[Path, OpenSpecStoreSourceValidationResult, tempfile.TemporaryDirectory[str]]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "openspec/specs/payments").mkdir(parents=True)
        (root / "openspec/changes").mkdir(parents=True)
        (root / "openspec/specs/payments/spec.md").write_text(
            "### Requirement: Payment is submitted\n\n"
            "#### Scenario: Valid payment\n\n"
            "### Requirement: Payment is refunded\n",
            encoding="utf-8",
        )
        if sidecar is not None:
            (root / "openspec/test-traceability.yaml").write_text(sidecar, encoding="utf-8")
        source = self._source(root)
        self.addCleanup(temporary.cleanup)
        return root, source, temporary

    def test_exact_mapping_is_deterministic_and_queryable_as_unexecuted(self) -> None:
        _, source, _temporary = self._workspace(
            "version: 1\nmappings:\n"
            "  - target:\n      capability: payments\n      requirement: Payment is submitted\n      scenario: Valid payment\n"
            "    tests:\n      - verification_scope_id: payment-service\n        test_case_key: acceptance-payment-submit\n"
        )
        extracted = extract_openspec_graph(source)
        first = admit_scenario_test_traceability(source, extracted)
        second = admit_scenario_test_traceability(source, extracted)
        self.assertEqual(first.graph.as_json(), second.graph.as_json())
        scenario = next(node for node in extracted.graph.nodes if node.kind == NodeKind.SCENARIO)
        result = EngineeringKgQuery.from_snapshot(extracted.graph.merged_with(first.graph)).get_scenario_test_traceability(scenario.id)
        self.assertEqual(result["status"], "mapped")
        self.assertEqual(result["mappings"][0]["execution_state"], "not-executed")
        self.assertEqual(validate_graph_integrity(extracted.graph.merged_with(first.graph)).status, "valid")

    def test_invalid_sidecar_fails_without_delta_and_similarity_is_not_mapping(self) -> None:
        _, source, _temporary = self._workspace(
            "version: 2\nmappings: []\n"
        )
        extracted = extract_openspec_graph(source)
        invalid = admit_scenario_test_traceability(source, extracted)
        self.assertEqual(invalid.graph, GraphSnapshot())
        self.assertEqual(invalid.metadata.skipped_reason_counts, {"unsupported-traceability-version": 1})
        self.assertEqual(invalid.metadata.diagnostics[0].reason_code, "unsupported-traceability-version")
        _, source_without_sidecar, _temporary_without_sidecar = self._workspace()
        extracted_without_sidecar = extract_openspec_graph(source_without_sidecar)
        self.assertEqual(admit_scenario_test_traceability(source_without_sidecar, extracted_without_sidecar).graph.nodes, ())
        requirement = next(node for node in extracted_without_sidecar.graph.nodes if node.kind == NodeKind.REQUIREMENT)
        self.assertEqual(
            EngineeringKgQuery.from_snapshot(extracted_without_sidecar.graph)
            .get_scenario_test_traceability(requirement.id)["status"],
            "unmapped",
        )
        similar_execution = normalize_test_execution_observation({
            "verification_scope_id": "payment-service", "test_case_key": "payment-is-submitted",
            "test_run_key": "run-similar", "observed_at": "2026-09-01T12:00:00+00:00",
            "content_hash": "b" * 64, "extractor_id": "local-adapter", "extractor_version": "1",
            "source_artifact_identity": {
                "source_type": "test-runner", "source_identity": "payment-runner",
                "artifact_type": "test-execution", "revision_or_version": "run-similar",
                "stable_locator": "runs/run-similar",
            },
        })
        with self.assertRaisesRegex(TraceabilityAdmissionError, "undeclared-test-observation"):
            admit_scenario_test_traceability(source_without_sidecar, extracted_without_sidecar, (similar_execution,))

    def test_mixed_type_sidecar_keys_fail_closed_deterministically(self) -> None:
        _, source, _temporary = self._workspace(
            "version: 1\nmappings: []\n1: unexpected\nunknown: also-unexpected\n"
        )
        extracted = extract_openspec_graph(source)

        first = admit_scenario_test_traceability(source, extracted)
        second = admit_scenario_test_traceability(source, extracted)

        self.assertEqual(first.graph, GraphSnapshot())
        self.assertEqual(first.metadata.as_dict(), second.metadata.as_dict())
        self.assertEqual(first.metadata.diagnostics[0].reason_code, "invalid-traceability-mapping")

    def test_required_invalid_sidecar_selector_and_identity_cases_fail_closed(self) -> None:
        cases = (
            (
                "malformed-selector",
                "version: 1\nmappings:\n"
                "  - target: {capability: payments, requirement: 42}\n"
                "    tests: [{verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}]\n",
                "invalid-traceability-mapping",
            ),
            (
                "unknown-selector-field",
                "version: 1\nmappings:\n"
                "  - target: {capability: payments, requirement: Payment is submitted, unknown: selector}\n"
                "    tests: [{verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}]\n",
                "invalid-traceability-mapping",
            ),
            (
                "unresolved-selector",
                "version: 1\nmappings:\n"
                "  - target: {capability: payments, requirement: Does not exist}\n"
                "    tests: [{verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}]\n",
                "invalid-traceability-mapping",
            ),
            (
                "unsafe-test-identity",
                "version: 1\nmappings:\n"
                "  - target: {capability: payments, requirement: Payment is submitted}\n"
                "    tests: [{verification_scope_id: payment-service, test_case_key: ../unsafe}]\n",
                "invalid-traceability-mapping",
            ),
            (
                "scenario-without-requirement",
                "version: 1\nmappings:\n"
                "  - target: {capability: payments, scenario: Valid payment}\n"
                "    tests: [{verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}]\n",
                "invalid-traceability-mapping",
            ),
            (
                "duplicate-conflict",
                "version: 1\nmappings:\n"
                "  - target: {capability: payments, requirement: Payment is submitted}\n"
                "    tests: [{verification_scope_id: payment-service, test_case_key: Acceptance-payment-submit}]\n"
                "  - target: {capability: payments, requirement: payment is submitted}\n"
                "    tests: [{verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}]\n",
                "conflicting-duplicate-mapping",
            ),
        )
        for name, sidecar, reason_code in cases:
            with self.subTest(case=name):
                _, source, _temporary = self._workspace(sidecar)
                extracted = extract_openspec_graph(source)
                result = admit_scenario_test_traceability(source, extracted)
                self.assertEqual(result.graph, GraphSnapshot())
                self.assertEqual(result.metadata.skipped_reason_counts, {reason_code: 1})
                self.assertEqual(result.metadata.diagnostics[0].reason_code, reason_code)

    def test_unresolved_and_non_unique_selectors_are_rejected(self) -> None:
        root, source, _temporary = self._workspace()
        (root / "openspec/test-traceability.yaml").write_text(
            "version: 1\nmappings:\n"
            "  - target: {capability: payments, requirement: Payment is submitted}\n"
            "    tests: [{verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}]\n",
            encoding="utf-8",
        )
        extracted = extract_openspec_graph(source)
        requirement = next(node for node in extracted.graph.nodes if node.kind == NodeKind.REQUIREMENT)
        extracted = replace(
            extracted,
            graph=replace(
                extracted.graph,
                nodes=extracted.graph.nodes + (replace(requirement, id="duplicate-target"),),
            ),
        )
        result = admit_scenario_test_traceability(source, extracted)
        self.assertEqual(result.graph, GraphSnapshot())
        self.assertEqual(result.metadata.skipped_reason_counts, {"invalid-traceability-mapping": 1})
        self.assertEqual(result.metadata.diagnostics[0].reason_code, "invalid-traceability-mapping")

    def test_query_keeps_unknown_and_wrong_kind_ids_in_missing_behavior(self) -> None:
        _, source, _temporary = self._workspace(
            "version: 1\nmappings:\n"
            "  - target: {capability: payments, requirement: Payment is submitted}\n"
            "    tests: [{verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}]\n"
        )
        extracted = extract_openspec_graph(source)
        graph = extracted.graph.merged_with(admit_scenario_test_traceability(source, extracted).graph)
        test_case = next(node for node in graph.nodes if node.kind == NodeKind.TEST_CASE)
        query = EngineeringKgQuery.from_snapshot(graph)

        for object_id in (test_case.id, "unknown-object"):
            result = query.get_scenario_test_traceability(object_id)
            self.assertEqual(result, {
                "cross_graph_links": [],
                "missing": True,
                "object_id": object_id,
                "relationships": [],
                "support_records": [],
            })
            with self.assertRaises(GraphObjectNotFoundError):
                query.get_scenario_test_traceability(object_id, missing_ok=False)

    def test_execution_and_exact_code_candidate_are_separate_and_payload_free(self) -> None:
        _, source, _temporary = self._workspace(
            "version: 1\nmappings:\n"
            "  - target: {capability: payments, requirement: Payment is submitted}\n"
            "    tests: [{verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}]\n"
        )
        extracted = extract_openspec_graph(source)
        content_hash = "b" * 64
        execution = normalize_test_execution_observation({
            "verification_scope_id": "payment-service", "test_case_key": "acceptance-payment-submit",
            "test_run_key": "run-1", "observed_at": "2026-09-01T12:00:00+00:00",
            "content_hash": content_hash, "extractor_id": "local-adapter", "extractor_version": "1",
            "source_artifact_identity": {
                "source_type": "test-runner", "source_identity": "payment-runner",
                "artifact_type": "test-execution", "revision_or_version": "run-1",
                "stable_locator": "runs/run-1",
            },
        })
        resolution = normalize_test_code_resolution({
            "verification_scope_id": "payment-service", "test_case_key": "acceptance-payment-submit",
            "basis": "static-reachability", "resolver_id": "resolver-1", "observation_id": "observation-1",
            "code_locator": {"repository": "payment-repo", "revision": "c" * 40, "file": "src/payments.py", "symbol": "payments.submit"},
            "observed_at": "2026-09-01T12:00:00+00:00", "content_hash": content_hash,
            "extractor_id": "resolver-adapter", "extractor_version": "1",
            "source_artifact_identity": {
                "source_type": "resolver", "source_identity": "resolver-1",
                "artifact_type": "test-code-resolution", "revision_or_version": "resolver-1",
                "stable_locator": "observations/observation-1",
            },
        })
        delta = admit_scenario_test_traceability(source, extracted, (execution,), (resolution,))
        graph = extracted.graph.merged_with(delta.graph)
        validation = validate_graph_integrity(graph)
        self.assertEqual(validation.status, "valid", validation.metadata.as_dict())
        self.assertEqual({edge.kind for edge in delta.graph.edges}, {EdgeKind.VERIFIED_BY, EdgeKind.EXECUTED_IN})
        self.assertEqual(len(delta.graph.cross_graph_link_claims), 1)
        self.assertEqual(delta.graph.cross_graph_link_claims[0].relation_kind, "references")
        self.assertEqual(graph.trusted_cross_graph_links, ())
        self.assertNotIn("payload", delta.graph.as_json())
        requirement = next(node for node in extracted.graph.nodes if node.kind == NodeKind.REQUIREMENT)
        projection = EngineeringKgQuery.from_snapshot(graph).get_scenario_test_traceability(requirement.id)
        self.assertEqual(projection["mappings"][0]["execution_state"], "executed")
        self.assertEqual(len(projection["mappings"][0]["candidates"]), 1)
        with tempfile.TemporaryDirectory() as temporary:
            readback = initialize_ladybugdb_store(Path(temporary) / "candidate-graph").write_snapshot(graph)
        readback_projection = EngineeringKgQuery.from_snapshot(readback).get_scenario_test_traceability(requirement.id)
        self.assertEqual(readback_projection["mappings"][0]["candidates"][0]["lifecycle"], "candidate")

    def test_multiple_observations_for_one_run_coalesce_execution_evidence(self) -> None:
        _, source, _temporary = self._workspace(
            "version: 1\nmappings:\n"
            "  - target: {capability: payments, requirement: Payment is submitted}\n"
            "    tests: [{verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}]\n"
        )
        extracted = extract_openspec_graph(source)
        common = {
            "verification_scope_id": "payment-service",
            "test_case_key": "acceptance-payment-submit",
            "test_run_key": "run-1",
            "observed_at": "2026-09-01T12:00:00+00:00",
            "extractor_id": "local-adapter",
            "extractor_version": "1",
        }
        first = normalize_test_execution_observation({
            **common,
            "content_hash": "b" * 64,
            "source_artifact_identity": {
                "source_type": "test-runner", "source_identity": "payment-runner-a",
                "artifact_type": "test-execution", "revision_or_version": "run-1-a",
                "stable_locator": "runs/run-1-a",
            },
        })
        second = normalize_test_execution_observation({
            **common,
            "content_hash": "c" * 64,
            "source_artifact_identity": {
                "source_type": "test-runner", "source_identity": "payment-runner-b",
                "artifact_type": "test-execution", "revision_or_version": "run-1-b",
                "stable_locator": "runs/run-1-b",
            },
        })

        delta = admit_scenario_test_traceability(source, extracted, (first, second))
        execution_edges = [edge for edge in delta.graph.edges if edge.kind == EdgeKind.EXECUTED_IN]
        self.assertEqual(len(execution_edges), 1)
        self.assertEqual(
            execution_edges[0].evidence_ids,
            tuple(sorted((first.source_evidence.id, second.source_evidence.id))),
        )

    def test_shared_source_artifacts_coalesce_observation_provenance(self) -> None:
        _, source, _temporary = self._workspace(
            "version: 1\nmappings:\n"
            "  - target: {capability: payments, requirement: Payment is submitted}\n"
            "    tests: [{verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}]\n"
        )
        extracted = extract_openspec_graph(source)

        execution_common = {
            "verification_scope_id": "payment-service",
            "test_case_key": "acceptance-payment-submit",
            "test_run_key": "run-shared",
            "extractor_id": "local-adapter",
            "extractor_version": "1",
            "source_artifact_identity": {
                "source_type": "test-runner",
                "source_identity": "payment-runner",
                "artifact_type": "test-execution",
                "revision_or_version": "run-shared",
                "stable_locator": "runs/run-shared",
            },
        }
        executions = tuple(normalize_test_execution_observation({
            **execution_common,
            "observed_at": observed_at,
            "content_hash": content_hash,
        }) for observed_at, content_hash in (
            ("2026-09-01T12:00:00+00:00", "b" * 64),
            ("2026-09-01T12:01:00+00:00", "c" * 64),
        ))

        resolution_common = {
            "verification_scope_id": "payment-service",
            "test_case_key": "acceptance-payment-submit",
            "basis": "runtime-execution",
            "resolver_id": "resolver-shared",
            "code_locator": {
                "repository": "payment-repo",
                "revision": "d" * 40,
                "file": "src/payments.py",
                "symbol": "payments.submit",
            },
            "extractor_id": "resolver-adapter",
            "extractor_version": "1",
            "source_artifact_identity": {
                "source_type": "resolver",
                "source_identity": "resolver-shared",
                "artifact_type": "test-code-resolution",
                "revision_or_version": "resolver-shared",
                "stable_locator": "observations/shared",
            },
        }
        resolutions = tuple(normalize_test_code_resolution({
            **resolution_common,
            "observation_id": observation_id,
            "observed_at": observed_at,
            "content_hash": content_hash,
        }) for observation_id, observed_at, content_hash in (
            ("observation-a", "2026-09-01T12:00:00+00:00", "e" * 64),
            ("observation-b", "2026-09-01T12:01:00+00:00", "f" * 64),
        ))

        forward = admit_scenario_test_traceability(
            source, extracted, executions=executions, code_resolutions=resolutions,
        )
        reverse = admit_scenario_test_traceability(
            source, extracted, executions=tuple(reversed(executions)),
            code_resolutions=tuple(reversed(resolutions)),
        )
        self.assertEqual(forward.graph.as_json(), reverse.graph.as_json())

        for observation_group in (executions, resolutions):
            evidence_id = observation_group[0].source_evidence.id
            evidence = next(item for item in forward.graph.evidence if item.id == evidence_id)
            self.assertEqual(
                evidence.provenance_ids,
                tuple(sorted(item.provenance.id for item in observation_group)),
            )

    def test_reverse_order_observations_produces_identical_graph(self) -> None:
        _, source, _temporary = self._workspace(
            "version: 1\nmappings:\n"
            "  - target: {capability: payments, requirement: Payment is submitted}\n"
            "    tests: [{verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}]\n"
        )
        extracted = extract_openspec_graph(source)
        observations = []
        for suffix, content_hash in (("a", "b" * 64), ("b", "c" * 64)):
            observations.append(normalize_test_execution_observation({
                "verification_scope_id": "payment-service",
                "test_case_key": "acceptance-payment-submit",
                "test_run_key": "run-1",
                "observed_at": "2026-09-01T12:00:00+00:00",
                "content_hash": content_hash,
                "extractor_id": "local-adapter",
                "extractor_version": "1",
                "source_artifact_identity": {
                    "source_type": "test-runner", "source_identity": f"payment-runner-{suffix}",
                    "artifact_type": "test-execution", "revision_or_version": f"run-1-{suffix}",
                    "stable_locator": f"runs/run-1-{suffix}",
                },
            }))

        forward = admit_scenario_test_traceability(source, extracted, tuple(observations))
        reverse = admit_scenario_test_traceability(source, extracted, tuple(reversed(observations)))
        self.assertEqual(forward.graph.as_json(), reverse.graph.as_json())

    def test_execution_for_undeclared_test_is_rejected_atomically(self) -> None:
        _, source, _temporary = self._workspace()
        extracted = extract_openspec_graph(source)
        execution = normalize_test_execution_observation({
            "verification_scope_id": "payment-service", "test_case_key": "unknown-test",
            "test_run_key": "run-1", "observed_at": "2026-09-01T12:00:00+00:00",
            "content_hash": "b" * 64, "extractor_id": "local-adapter", "extractor_version": "1",
            "source_artifact_identity": {
                "source_type": "test-runner", "source_identity": "payment-runner",
                "artifact_type": "test-execution", "revision_or_version": "run-1",
                "stable_locator": "runs/run-1",
            },
        })
        with self.assertRaisesRegex(TraceabilityAdmissionError, "undeclared-test-observation"):
            admit_scenario_test_traceability(source, extracted, (execution,))

    def test_mixed_valid_and_invalid_inputs_fail_before_delta_or_pipeline_mutation(self) -> None:
        _, source, _temporary = self._workspace(
            "version: 1\nmappings:\n"
            "  - target: {capability: payments, requirement: Payment is submitted}\n"
            "    tests: [{verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}]\n"
        )
        extracted = extract_openspec_graph(source)
        valid_execution = normalize_test_execution_observation({
            "verification_scope_id": "payment-service",
            "test_case_key": "acceptance-payment-submit",
            "test_run_key": "run-atomic",
            "observed_at": "2026-09-01T12:00:00+00:00",
            "content_hash": "b" * 64,
            "extractor_id": "local-adapter",
            "extractor_version": "1",
            "source_artifact_identity": {
                "source_type": "test-runner",
                "source_identity": "payment-runner",
                "artifact_type": "test-execution",
                "revision_or_version": "run-atomic",
                "stable_locator": "runs/run-atomic",
            },
        })
        valid_resolution = normalize_test_code_resolution({
            "verification_scope_id": "payment-service",
            "test_case_key": "acceptance-payment-submit",
            "basis": "static-reachability",
            "resolver_id": "resolver-atomic",
            "observation_id": "observation-atomic",
            "code_locator": {
                "repository": "payment-repo",
                "revision": "c" * 40,
                "file": "src/payments.py",
                "symbol": "payments.submit",
            },
            "observed_at": "2026-09-01T12:00:00+00:00",
            "content_hash": "b" * 64,
            "extractor_id": "resolver-adapter",
            "extractor_version": "1",
            "source_artifact_identity": {
                "source_type": "resolver",
                "source_identity": "resolver-atomic",
                "artifact_type": "test-code-resolution",
                "revision_or_version": "resolver-atomic",
                "stable_locator": "observations/observation-atomic",
            },
        })
        invalid_execution = {"outcome": "passed"}
        invalid_resolution = {
            "verification_scope_id": "payment-service",
            "test_case_key": "acceptance-payment-submit",
            "code_locators": [],
        }
        with self.assertRaisesRegex(
            TraceabilityAdmissionError,
            "invalid traceability input: ambiguous-code-resolution.*execution-payload-rejected",
        ):
            admit_scenario_test_traceability(
                source,
                extracted,
                executions=(valid_execution, invalid_execution),
                code_resolutions=(valid_resolution, invalid_resolution),
            )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "requirements_repo"
            shutil.copytree(FIXTURE_ROOT, root)
            (root / "openspec/test-traceability.yaml").write_text(
                "version: 1\nmappings:\n"
                "  - target: {capability: payments, requirement: Payment is submitted}\n"
                "    tests: [{verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}]\n",
                encoding="utf-8",
            )
            registry = Path(temporary) / "registry.yaml"
            registry.write_text(
                (root / "repo-index-openspec-graph-stage.yaml").read_text(encoding="utf-8").replace(
                    "    path: .", f"    path: {root}",
                ).replace(
                    "    - openspec-graph-extraction\n",
                    "    - openspec-graph-extraction\n    - scenario-test-traceability\n    - ladybugdb-persistence\n",
                ),
                encoding="utf-8",
            )
            graph_path = Path(temporary) / "graph"
            store = initialize_ladybugdb_store(graph_path)
            before = store.write_snapshot(GraphSnapshot())
            with self.assertRaisesRegex(TraceabilityAdmissionError, "invalid traceability input"):
                run_pipeline(
                    registry,
                    graph_path,
                    openspec_stores=(RegisteredOpenSpecStore("requirements-store", root),),
                    openspec_store_id="requirements-store",
                    test_execution_observations=(valid_execution, invalid_execution),
                    test_code_resolutions=(valid_resolution, invalid_resolution),
                )
            self.assertEqual(store.read_snapshot(), before)

    def test_invalid_traceability_validation_blocks_required_query_and_persistence(self) -> None:
        _, source, _temporary = self._workspace(
            "version: 1\nmappings:\n"
            "  - target: {capability: payments, requirement: Payment is submitted}\n"
            "    tests: [{verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}]\n"
        )
        extracted = extract_openspec_graph(source)
        graph = extracted.graph.merged_with(admit_scenario_test_traceability(source, extracted).graph)
        requirement = next(node for node in graph.nodes if node.kind == NodeKind.REQUIREMENT)
        mapping_edge = next(edge for edge in graph.edges if edge.kind == EdgeKind.VERIFIED_BY)
        invalid_graph = replace(graph, edges=(replace(mapping_edge, target_id=requirement.id),))
        validation = validate_graph_integrity(invalid_graph)
        self.assertEqual(validation.status, "invalid")
        self.assertIn(
            "traceability-mapping-target-kind",
            {item.rule_id for item in validation.metadata.diagnostics},
        )
        with self.assertRaises(GraphQueryValidationError):
            EngineeringKgQuery.from_snapshot(invalid_graph).get_scenario_test_traceability(
                requirement.id, require_validation=True,
            )
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(PersistenceIntegrityError):
                initialize_ladybugdb_store(Path(temporary) / "invalid").write_snapshot(invalid_graph)

    def test_forged_test_execution_evidence_is_invalid_and_cannot_persist_or_query(self) -> None:
        _, source, _temporary = self._workspace(
            "version: 1\nmappings:\n"
            "  - target: {capability: payments, requirement: Payment is submitted}\n"
            "    tests: [{verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}]\n"
        )
        extracted = extract_openspec_graph(source)
        graph = extracted.graph.merged_with(admit_scenario_test_traceability(source, extracted).graph)
        test_case = next(node for node in graph.nodes if node.kind == NodeKind.TEST_CASE)
        mapping_evidence_id = next(edge for edge in graph.edges if edge.kind == EdgeKind.VERIFIED_BY).evidence_ids[0]
        test_run = verification_node(NodeKind.TEST_RUN, "payment-service", "forged-run", (mapping_evidence_id,))
        forged_identity = SourceArtifactIdentity(
            "test-runner", "payment-runner", "test-execution", "forged-run", "runs/forged-run",
        )
        forged_provenance = ProvenanceRecord(
            "external", "2026-09-01T12:00:00+00:00", "sha256", "b" * 64,
            "local-adapter", "1", forged_identity,
        )
        forged_evidence = Evidence(
            "forged-test-execution", "test-execution", "runs/forged-run",
            provenance_ids=(forged_provenance.id,),
        )
        forged_execution = Edge(
            "forged-execution", EdgeKind.EXECUTED_IN, test_case.id, test_run.id,
            evidence_ids=(forged_evidence.id,),
        )
        invalid_graph = GraphSnapshot(
            nodes=graph.nodes + (test_run,),
            edges=graph.edges + (forged_execution,),
            evidence=graph.evidence + (forged_evidence,),
            provenance=graph.provenance + (forged_provenance,),
            allow_legacy_evidence=True,
        )

        validation = validate_graph_integrity(invalid_graph)
        self.assertEqual(validation.status, "invalid")
        self.assertIn(
            "traceability-execution-source-contract",
            {item.rule_id for item in validation.metadata.diagnostics},
        )
        self.assertIn(
            "traceability-execution-provenance-complete",
            {item.rule_id for item in validation.metadata.diagnostics},
        )
        with self.assertRaises(GraphQueryValidationError):
            EngineeringKgQuery.from_snapshot(invalid_graph).get_scenario_test_traceability(
                next(node for node in graph.nodes if node.kind == NodeKind.REQUIREMENT).id,
                require_validation=True,
            )
        with tempfile.TemporaryDirectory() as temporary:
            store = initialize_ladybugdb_store(Path(temporary) / "forged")
            before = store.read_snapshot()
            with self.assertRaises(PersistenceIntegrityError):
                store.write_snapshot(invalid_graph)
            self.assertEqual(store.read_snapshot(), before)

    def test_normalizers_reject_payload_and_ambiguous_code_context(self) -> None:
        with self.assertRaisesRegex(TraceabilityAdmissionError, "field is not allowed"):
            normalize_test_execution_observation({"outcome": "passed"})
        with self.assertRaisesRegex(TraceabilityAdmissionError, "exactly one locator"):
            normalize_test_code_resolution({"code_locators": []})
        with self.assertRaisesRegex(TraceabilityAdmissionError, "unsupported reliable"):
            normalize_test_code_resolution({
                "verification_scope_id": "scope", "test_case_key": "case",
                "basis": "coverage", "resolver_id": "resolver", "observation_id": "observation",
                "code_locator": {"repository": "repo", "revision": "c" * 40, "file": "src/a.py", "symbol": "a.b"},
                "observed_at": "2026-09-01T12:00:00+00:00", "content_hash": "b" * 64,
                "extractor_id": "resolver", "extractor_version": "1",
                "source_artifact_identity": {
                    "source_type": "resolver", "source_identity": "resolver",
                    "artifact_type": "test-code-resolution", "revision_or_version": "resolver",
                    "stable_locator": "observations/observation",
                },
            })

    def test_code_resolution_promotion_input_is_rejected(self) -> None:
        with self.assertRaisesRegex(TraceabilityAdmissionError, "unknown code resolution field"):
            normalize_test_code_resolution({
                "verification_scope_id": "scope",
                "test_case_key": "case",
                "relation_kind": "implements",
            })

    def test_validation_rejects_forged_candidate_locators(self) -> None:
        _, source, _temporary = self._workspace(
            "version: 1\nmappings:\n"
            "  - target: {capability: payments, requirement: Payment is submitted}\n"
            "    tests: [{verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}]\n"
        )
        extracted = extract_openspec_graph(source)
        resolution = normalize_test_code_resolution({
            "verification_scope_id": "payment-service",
            "test_case_key": "acceptance-payment-submit",
            "basis": "static-reachability",
            "resolver_id": "resolver-1",
            "observation_id": "observation-1",
            "code_locator": {
                "repository": "payment-repo",
                "revision": "c" * 40,
                "file": "src/payments.py",
                "symbol": "payments.submit",
            },
            "observed_at": "2026-09-01T12:00:00+00:00",
            "content_hash": "b" * 64,
            "extractor_id": "resolver-adapter",
            "extractor_version": "1",
            "source_artifact_identity": {
                "source_type": "resolver",
                "source_identity": "resolver-1",
                "artifact_type": "test-code-resolution",
                "revision_or_version": "resolver-1",
                "stable_locator": "observations/observation-1",
            },
        })
        graph = extracted.graph.merged_with(
            admit_scenario_test_traceability(source, extracted, code_resolutions=(resolution,)).graph
        )
        claim = graph.cross_graph_link_claims[0]
        invalid_locators = (
            CodeLocator("https://unsafe.example/repo", "c" * 40, "src/payments.py", "payments.submit"),
            CodeLocator("payment-repo", "main", "src/payments.py", "payments.submit"),
            CodeLocator("payment-repo", "c" * 40, "../secret.py", "payments.submit"),
            CodeLocator("payment-repo", "c" * 40, "src/payments.py", "def submit(): pass"),
        )
        for locator in invalid_locators:
            with self.subTest(locator=locator):
                forged_claim = replace(claim, target=locator)
                invalid_graph = replace(
                    graph,
                    cross_graph_link_claims=(forged_claim,),
                    cross_graph_link_evidence=tuple(
                        replace(item, claim_id=forged_claim.id)
                        for item in graph.cross_graph_link_evidence
                    ),
                    cross_graph_link_lifecycle=tuple(
                        replace(item, claim_id=forged_claim.id)
                        for item in graph.cross_graph_link_lifecycle
                    ),
                )
                validation = validate_graph_integrity(invalid_graph)
                rules = {item.rule_id for item in validation.metadata.diagnostics}
                self.assertEqual(validation.status, "invalid")
                self.assertIn("reliable-test-code-resolution-scope", rules)

    def test_mixed_mappings_keep_independent_execution_state(self) -> None:
        _, source, _temporary = self._workspace(
            "version: 1\nmappings:\n"
            "  - target: {capability: payments, requirement: Payment is submitted}\n"
            "    tests:\n"
            "      - {verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}\n"
            "      - {verification_scope_id: payment-service, test_case_key: acceptance-payment-invalid}\n"
        )
        extracted = extract_openspec_graph(source)
        execution = normalize_test_execution_observation({
            "verification_scope_id": "payment-service", "test_case_key": "acceptance-payment-submit",
            "test_run_key": "run-1", "observed_at": "2026-09-01T12:00:00+00:00",
            "content_hash": "b" * 64, "extractor_id": "local-adapter", "extractor_version": "1",
            "source_artifact_identity": {
                "source_type": "test-runner", "source_identity": "payment-runner",
                "artifact_type": "test-execution", "revision_or_version": "run-1",
                "stable_locator": "runs/run-1",
            },
        })
        graph = extracted.graph.merged_with(
            admit_scenario_test_traceability(source, extracted, (execution,)).graph
        )
        requirement = next(node for node in extracted.graph.nodes if node.kind == NodeKind.REQUIREMENT)
        mapping_states = {
            item["test_case_key"]: item["execution_state"]
            for item in EngineeringKgQuery.from_snapshot(graph)
            .get_scenario_test_traceability(requirement.id)["mappings"]
        }
        self.assertEqual(mapping_states, {
            "acceptance-payment-submit": "executed",
            "acceptance-payment-invalid": "not-executed",
        })

    def test_persistence_readback_preserves_traceability_projection(self) -> None:
        _, source, _temporary = self._workspace(
            "version: 1\nmappings:\n"
            "  - target: {capability: payments, requirement: Payment is submitted}\n"
            "    tests: [{verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}]\n"
        )
        extracted = extract_openspec_graph(source)
        graph = extracted.graph.merged_with(admit_scenario_test_traceability(source, extracted).graph)
        with tempfile.TemporaryDirectory() as temporary:
            store = initialize_ladybugdb_store(Path(temporary) / "graph")
            first = store.write_snapshot(graph)
            second = store.write_snapshot(graph)
        self.assertEqual(first.as_json(), second.as_json())
        requirement = next(node for node in graph.nodes if node.kind == NodeKind.REQUIREMENT)
        self.assertEqual(
            EngineeringKgQuery.from_snapshot(second).get_scenario_test_traceability(requirement.id)["status"],
            "mapped",
        )

    def test_pipeline_keeps_optional_stage_after_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "registry.yaml"
            registry.write_text(
                (FIXTURE_ROOT / "repo-index-openspec-graph-stage.yaml").read_text(encoding="utf-8").replace(
                    "    path: .", f"    path: {FIXTURE_ROOT}",
                ).replace(
                    "    - openspec-graph-extraction\n",
                    "    - openspec-graph-extraction\n    - scenario-test-traceability\n",
                ),
                encoding="utf-8",
            )
            result = run_pipeline(
                registry,
                openspec_stores=(RegisteredOpenSpecStore("requirements-store", FIXTURE_ROOT),),
                openspec_store_id="requirements-store",
            )
        self.assertEqual(result.executed_stages[-1], "scenario-test-traceability")
        self.assertEqual(result.scenario_test_traceability.metadata.admitted_mapping_count, 0)

    def test_configured_pipeline_persists_and_validates_execution_and_code_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "requirements_repo"
            shutil.copytree(FIXTURE_ROOT, root)
            (root / "openspec/test-traceability.yaml").write_text(
                "version: 1\nmappings:\n"
                "  - target: {capability: payments, requirement: Payment is submitted}\n"
                "    tests: [{verification_scope_id: payment-service, test_case_key: acceptance-payment-submit}]\n",
                encoding="utf-8",
            )
            registry = Path(temporary) / "registry.yaml"
            registry.write_text(
                (root / "repo-index-openspec-graph-stage.yaml").read_text(encoding="utf-8").replace(
                    "    path: .", f"    path: {root}",
                ).replace(
                    "    - openspec-graph-extraction\n",
                    "    - openspec-graph-extraction\n    - scenario-test-traceability\n    - graph-integrity-validation\n",
                ),
                encoding="utf-8",
            )
            execution = normalize_test_execution_observation({
                "verification_scope_id": "payment-service", "test_case_key": "acceptance-payment-submit",
                "test_run_key": "run-pipeline", "observed_at": "2026-09-01T12:00:00+00:00",
                "content_hash": "b" * 64, "extractor_id": "local-adapter", "extractor_version": "1",
                "source_artifact_identity": {
                    "source_type": "test-runner", "source_identity": "payment-runner",
                    "artifact_type": "test-execution", "revision_or_version": "run-pipeline",
                    "stable_locator": "runs/run-pipeline",
                },
            })
            resolution = normalize_test_code_resolution({
                "verification_scope_id": "payment-service", "test_case_key": "acceptance-payment-submit",
                "basis": "runtime-execution", "resolver_id": "resolver-pipeline", "observation_id": "observation-pipeline",
                "code_locator": {"repository": "payment-repo", "revision": "c" * 40, "file": "src/payments.py", "symbol": "payments.submit"},
                "observed_at": "2026-09-01T12:00:00+00:00", "content_hash": "b" * 64,
                "extractor_id": "resolver-adapter", "extractor_version": "1",
                "source_artifact_identity": {
                    "source_type": "resolver", "source_identity": "resolver-pipeline",
                    "artifact_type": "test-code-resolution", "revision_or_version": "resolver-pipeline",
                    "stable_locator": "observations/observation-pipeline",
                },
            })
            result = run_pipeline(
                registry,
                Path(temporary) / "graph",
                openspec_stores=(RegisteredOpenSpecStore("requirements-store", root),),
                openspec_store_id="requirements-store",
                test_execution_observations=(execution,),
                test_code_resolutions=(resolution,),
            )
            self.assertEqual(result.status, "completed")
            self.assertLess(
                result.executed_stages.index("scenario-test-traceability"),
                result.executed_stages.index("ladybugdb-persistence"),
            )
            self.assertEqual(result.scenario_test_traceability.metadata.admitted_execution_count, 1)
            self.assertEqual(result.scenario_test_traceability.metadata.emitted_candidate_count, 1)
            self.assertEqual(result.graph_integrity_validation.status, "valid")
            self.assertEqual(len(result.graph.cross_graph_link_claims), 1)

    def test_empty_snapshot_persistence_readback_and_query_remain_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = initialize_ladybugdb_store(Path(temporary) / "empty")
            readback = store.write_snapshot(GraphSnapshot())
            self.assertEqual(readback, GraphSnapshot())
            self.assertEqual(validate_graph_integrity(readback).status, "valid")
            self.assertEqual(
                EngineeringKgQuery.from_snapshot(readback).get_scenario_test_traceability("missing") ["missing"],
                True,
            )

    def test_pipeline_rejects_traceability_without_extraction_prerequisite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "registry.yaml"
            registry.write_text(
                (FIXTURE_ROOT / "repo-index-openspec-store-stage.yaml").read_text(encoding="utf-8").replace(
                    "    path: .", f"    path: {FIXTURE_ROOT}",
                ).replace(
                    "    - openspec-store-source\n",
                    "    - openspec-store-source\n    - scenario-test-traceability\n",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "requires prior openspec-graph-extraction"):
                run_pipeline(
                    registry,
                    openspec_stores=(RegisteredOpenSpecStore("requirements-store", FIXTURE_ROOT),),
                    openspec_store_id="requirements-store",
                )


if __name__ == "__main__":
    unittest.main()
