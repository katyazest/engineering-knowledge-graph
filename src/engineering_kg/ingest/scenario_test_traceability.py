"""Admission of explicit, local OpenSpec test traceability facts.

This module is intentionally source-neutral after its input boundary.  It does
not discover tests or interpret test output; callers provide compact execution
and code-resolution observations and this module only admits exact identities.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml

from engineering_kg.compact_identity import (
    is_complete_symbol_identity,
    is_immutable_revision,
    safe_identity,
    safe_repository,
    safe_relative_file,
)
from engineering_kg.ingest.openspec import (
    OpenSpecExtractionResult,
    OpenSpecStoreSourceValidationResult,
    locate_openspec_test_traceability,
)
from engineering_kg.ontology import (
    CodeLocator,
    CrossGraphEvidenceOrigin,
    CrossGraphEvidenceStatus,
    CrossGraphLinkClaim,
    CrossGraphLinkEvidence,
    CrossGraphLinkLifecycle,
    CrossGraphLinkLifecycleState,
    CrossGraphTrustDisposition,
    Edge,
    EdgeKind,
    Evidence,
    GraphSnapshot,
    Node,
    NodeKind,
    OpenSpecLocator,
    ProvenanceKind,
    ProvenanceRecord,
    SourceArtifactIdentity,
    SourceArtifactLocator,
    stable_id,
    verification_node,
    verification_node_id,
)
from engineering_kg.relationship_vocabulary import RelationshipKind, relationship_error


TRACEABILITY_FILE = "openspec/test-traceability.yaml"
TRACEABILITY_ARTIFACT_TYPE = "openspec-test-traceability"
EXECUTION_ARTIFACT_TYPE = "test-execution"
CODE_RESOLUTION_ARTIFACT_TYPE = "test-code-resolution"
CODE_RESOLUTION_STRATEGY = "reliable-test-code-resolution"
ALLOWED_CODE_BASES = frozenset({"static-reachability", "runtime-execution"})
_SAFE_SELECTOR = re.compile(r"^[^\x00-\x1f\x7f]+$")
_FORBIDDEN_INPUT_FIELDS = frozenset({
    "payload", "provider_payload", "framework", "ci_payload", "output", "logs",
    "log", "report", "raw", "source_code", "outcome", "coverage", "result",
    "body", "content", "credentials", "token", "tokens", "url",
})


class TraceabilityAdmissionError(ValueError):
    """Raised when a traceability declaration or normalized observation is unsafe."""


@dataclass(frozen=True)
class TestTraceabilityDiagnostic:
    reason_code: str
    identity: str = ""

    def as_dict(self) -> dict[str, str]:
        result = {"reason_code": self.reason_code}
        if self.identity:
            result["identity"] = self.identity
        return result


@dataclass(frozen=True)
class DeclaredTestMapping:
    """One exact OpenSpec target to source-neutral test mapping."""

    target_id: str
    target_kind: str
    capability: str
    requirement: str
    scenario: str | None
    verification_scope_id: str
    test_case_key: str
    evidence: Evidence
    provenance: ProvenanceRecord

    @property
    def id(self) -> str:
        return stable_id(
            "test-traceability-mapping", self.target_id,
            self.verification_scope_id, self.test_case_key,
        )

    @property
    def test_case_id(self) -> str:
        return verification_node_id(
            NodeKind.TEST_CASE, self.verification_scope_id, self.test_case_key,
        )


@dataclass(frozen=True)
class NormalizedTestExecutionObservation:
    """Payload-free execution presence supplied by a local adapter."""

    verification_scope_id: str
    test_case_key: str
    test_run_key: str
    source_artifact_identity: SourceArtifactIdentity
    observed_at: str
    content_hash_algorithm: str
    content_hash: str
    extractor_id: str
    extractor_version: str

    def __post_init__(self) -> None:
        _verification_identity(self.verification_scope_id, self.test_case_key)
        _verification_identity(self.verification_scope_id, self.test_run_key)
        _validate_provenance_fields(
            self.observed_at, self.content_hash_algorithm, self.content_hash,
            self.extractor_id, self.extractor_version,
        )
        if not isinstance(self.source_artifact_identity, SourceArtifactIdentity):
            raise TraceabilityAdmissionError("execution source_artifact_identity is required")
        if self.source_artifact_identity.artifact_type != EXECUTION_ARTIFACT_TYPE:
            raise TraceabilityAdmissionError("execution source artifact type is inconsistent")

    @property
    def id(self) -> str:
        return stable_id("test-execution-observation", self.verification_scope_id, self.test_case_key, self.test_run_key)

    def source_bundle(self) -> tuple[Evidence, ProvenanceRecord]:
        provenance = ProvenanceRecord(
            ProvenanceKind.EXTERNAL, self.observed_at, self.content_hash_algorithm,
            self.content_hash, self.extractor_id, self.extractor_version,
            self.source_artifact_identity,
        )
        evidence = Evidence(
            stable_id("evidence", self.source_artifact_identity.id),
            "test-execution", SourceArtifactLocator(self.source_artifact_identity),
            provenance_ids=(provenance.id,),
        )
        return evidence, provenance

    @property
    def source_evidence(self) -> Evidence:
        return self.source_bundle()[0]

    @property
    def provenance(self) -> ProvenanceRecord:
        return self.source_bundle()[1]


@dataclass(frozen=True)
class NormalizedTestCodeResolution:
    """One exact, attributed test-to-code observation."""

    verification_scope_id: str
    test_case_key: str
    locator: CodeLocator
    basis: str
    resolver_id: str
    observation_id: str
    source_artifact_identity: SourceArtifactIdentity
    observed_at: str
    content_hash_algorithm: str
    content_hash: str
    extractor_id: str
    extractor_version: str

    def __post_init__(self) -> None:
        _verification_identity(self.verification_scope_id, self.test_case_key)
        if not isinstance(self.locator, CodeLocator) or not _complete_locator(self.locator):
            raise TraceabilityAdmissionError("reliable-test-code-resolution requires one complete CodeLocator")
        if self.basis not in ALLOWED_CODE_BASES:
            raise TraceabilityAdmissionError("unsupported reliable test-code resolution basis")
        for value, field_name in ((self.resolver_id, "resolver_id"), (self.observation_id, "observation_id")):
            try:
                safe_identity(value, f"code resolution {field_name}")
            except ValueError as exc:
                raise TraceabilityAdmissionError(str(exc)) from None
        _validate_provenance_fields(
            self.observed_at, self.content_hash_algorithm, self.content_hash,
            self.extractor_id, self.extractor_version,
        )
        if not isinstance(self.source_artifact_identity, SourceArtifactIdentity):
            raise TraceabilityAdmissionError("code resolution source_artifact_identity is required")
        if self.source_artifact_identity.artifact_type != CODE_RESOLUTION_ARTIFACT_TYPE:
            raise TraceabilityAdmissionError("code resolution source artifact type is inconsistent")

    @property
    def id(self) -> str:
        return stable_id("test-code-resolution", self.verification_scope_id, self.test_case_key, self.observation_id)

    def source_bundle(self) -> tuple[Evidence, ProvenanceRecord]:
        provenance = ProvenanceRecord(
            ProvenanceKind.EXTERNAL, self.observed_at, self.content_hash_algorithm,
            self.content_hash, self.extractor_id, self.extractor_version,
            self.source_artifact_identity,
        )
        evidence = Evidence(
            stable_id("evidence", self.source_artifact_identity.id),
            CODE_RESOLUTION_STRATEGY, SourceArtifactLocator(self.source_artifact_identity),
            provenance_ids=(provenance.id,),
        )
        return evidence, provenance

    @property
    def source_evidence(self) -> Evidence:
        return self.source_bundle()[0]

    @property
    def provenance(self) -> ProvenanceRecord:
        return self.source_bundle()[1]


@dataclass(frozen=True)
class ScenarioTestTraceabilityMetadata:
    admitted_mapping_count: int = 0
    admitted_execution_count: int = 0
    emitted_candidate_count: int = 0
    skipped_input_count: int = 0
    skipped_reason_counts: dict[str, int] = field(default_factory=dict)
    diagnostics: tuple[TestTraceabilityDiagnostic, ...] = ()
    graph_counts: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "admitted_execution_count": self.admitted_execution_count,
            "admitted_mapping_count": self.admitted_mapping_count,
            "diagnostics": [item.as_dict() for item in self.diagnostics],
            "emitted_candidate_count": self.emitted_candidate_count,
            "graph_counts": dict(sorted(self.graph_counts.items())),
            "skipped_input_count": self.skipped_input_count,
            "skipped_reason_counts": dict(sorted(self.skipped_reason_counts.items())),
        }


@dataclass(frozen=True)
class ScenarioTestTraceabilityResult:
    graph: GraphSnapshot
    metadata: ScenarioTestTraceabilityMetadata

    def as_dict(self) -> dict[str, Any]:
        return {"graph": self.graph.as_dict(), "metadata": self.metadata.as_dict()}


def traceability_artifact_path(store_source: OpenSpecStoreSourceValidationResult) -> Path:
    """Return the only permitted sidecar path, rejecting path escape by construction."""

    try:
        context = locate_openspec_test_traceability(store_source)
    except ValueError as exc:
        raise TraceabilityAdmissionError(str(exc)) from None
    return context.path if context is not None else store_source.openspec_root_path.resolve() / "test-traceability.yaml"


def parse_test_traceability(
    store_source: OpenSpecStoreSourceValidationResult,
    extraction: OpenSpecExtractionResult,
) -> tuple[DeclaredTestMapping, ...]:
    """Parse and exactly resolve the optional v1 sidecar against extracted facts."""

    if store_source.status != "valid" or extraction.metadata.status != "completed":
        raise TraceabilityAdmissionError("traceability admission requires validated OpenSpec extraction context")
    path = traceability_artifact_path(store_source)
    if not path.is_file():
        return ()
    try:
        raw_bytes = path.read_bytes()
        document = yaml.safe_load(raw_bytes.decode("utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise TraceabilityAdmissionError("invalid-traceability-document") from exc
    _reject_document_keys(document, {"version", "mappings"}, "traceability")
    if (
        not isinstance(document, dict)
        or isinstance(document.get("version"), bool)
        or document.get("version") != 1
    ):
        raise TraceabilityAdmissionError("unsupported-traceability-version")
    records = document.get("mappings")
    if not isinstance(records, list):
        raise TraceabilityAdmissionError("traceability mappings must be a list")
    source_context = locate_openspec_test_traceability(store_source)
    if source_context is None:
        raise TraceabilityAdmissionError("traceability artifact disappeared during admission")
    source_identity = source_context.source_artifact_identity
    source_hash = hashlib.sha256(raw_bytes).hexdigest()
    by_key: dict[tuple[str, str, str], DeclaredTestMapping] = {}
    for index, record in enumerate(records):
        parsed = _parse_mapping_record(
            record, index, extraction.graph, source_identity, source_hash,
            store_source.observed_at,
        )
        for mapping in parsed:
            # The verification natural key is the canonical identity boundary;
            # use it here so case variants cannot bypass conflicting-duplicate
            # detection while still producing the same stable test node.
            key = (mapping.target_id, mapping.test_case_id)
            previous = by_key.get(key)
            if previous is not None and previous != mapping:
                raise TraceabilityAdmissionError(f"conflicting-duplicate-mapping: {mapping.id}")
            by_key[key] = mapping
    return tuple(sorted(by_key.values(), key=lambda item: item.id))


def normalize_test_execution_observation(value: Mapping[str, Any] | NormalizedTestExecutionObservation) -> NormalizedTestExecutionObservation:
    """Normalize a compact execution identity and construct its source bundle."""

    if isinstance(value, NormalizedTestExecutionObservation):
        return value
    data = _input_mapping(value, "execution")
    _reject_input_keys(data, "execution")
    _reject_allowed_input_keys(
        data,
        {
            "verification_scope_id", "test_case_key", "test_run_key",
            "source_artifact_identity", "source_artifact", "observed_at",
            "observation_instant", "content_hash_algorithm", "content_hash",
            "extractor_id", "extractor_version",
        },
        "execution",
    )
    identity = _source_identity(data, EXECUTION_ARTIFACT_TYPE, "execution")
    return NormalizedTestExecutionObservation(
        data.get("verification_scope_id"), data.get("test_case_key"), data.get("test_run_key"),
        identity, data.get("observed_at", data.get("observation_instant")), data.get("content_hash_algorithm", "sha256"),
        data.get("content_hash"), data.get("extractor_id"), data.get("extractor_version"),
    )


def normalize_test_code_resolution(value: Mapping[str, Any] | NormalizedTestCodeResolution) -> NormalizedTestCodeResolution:
    """Normalize exactly one reliable, revision-qualified code result."""

    if isinstance(value, NormalizedTestCodeResolution):
        return value
    data = _input_mapping(value, "code resolution")
    _reject_input_keys(data, "code resolution")
    _reject_allowed_input_keys(
        data,
        {
            "verification_scope_id", "test_case_key", "code_locator", "locator",
            "code_locators", "basis", "resolver_id", "observation_id",
            "source_artifact_identity", "source_artifact", "observed_at",
            "observation_instant", "content_hash_algorithm", "content_hash",
            "extractor_id", "extractor_version", "repository", "revision",
        },
        "code resolution",
    )
    locator_value = data.get("code_locator", data.get("locator"))
    locators = data.get("code_locators")
    if locators is not None:
        if not isinstance(locators, (list, tuple)) or len(locators) != 1:
            raise TraceabilityAdmissionError("reliable-test-code-resolution requires exactly one locator")
        if locator_value is not None:
            raise TraceabilityAdmissionError("reliable-test-code-resolution has multiple locator fields")
        locator_value = locators[0]
    locator = _code_locator(locator_value)
    identity = _source_identity(data, CODE_RESOLUTION_ARTIFACT_TYPE, "code resolution")
    if data.get("repository") is not None and data.get("repository") != locator.repository:
        raise TraceabilityAdmissionError("code resolution repository mismatch")
    if data.get("revision") is not None and data.get("revision") != locator.revision:
        raise TraceabilityAdmissionError("code resolution revision mismatch")
    return NormalizedTestCodeResolution(
        data.get("verification_scope_id"), data.get("test_case_key"), locator,
        data.get("basis"), data.get("resolver_id"), data.get("observation_id"),
        identity, data.get("observed_at", data.get("observation_instant")), data.get("content_hash_algorithm", "sha256"),
        data.get("content_hash"), data.get("extractor_id"), data.get("extractor_version"),
    )


def admit_scenario_test_traceability(
    store_source: OpenSpecStoreSourceValidationResult,
    extraction: OpenSpecExtractionResult,
    executions: Sequence[Mapping[str, Any] | NormalizedTestExecutionObservation] = (),
    code_resolutions: Sequence[Mapping[str, Any] | NormalizedTestCodeResolution] = (),
    *,
    execution_observations: Sequence[Mapping[str, Any] | NormalizedTestExecutionObservation] | None = None,
    test_code_resolutions: Sequence[Mapping[str, Any] | NormalizedTestCodeResolution] | None = None,
) -> ScenarioTestTraceabilityResult:
    """Build one atomic graph delta from declarations and caller-supplied facts."""

    diagnostics: list[TestTraceabilityDiagnostic] = []
    if execution_observations is not None:
        if executions:
            raise TraceabilityAdmissionError("invalid-execution-input")
        executions = execution_observations
    if test_code_resolutions is not None:
        if code_resolutions:
            raise TraceabilityAdmissionError("invalid-code-resolution-input")
        code_resolutions = test_code_resolutions

    try:
        mappings = parse_test_traceability(store_source, extraction)
    except TraceabilityAdmissionError as exc:
        message = str(exc)
        return _diagnostic_result(_mapping_reason_code(message), _safe_diagnostic_identity(message))

    mapped_by_identity = {
        (item.verification_scope_id, item.test_case_key): item for item in mappings
    }
    normalized_executions: list[NormalizedTestExecutionObservation] = []
    for item in executions:
        try:
            normalized = normalize_test_execution_observation(item)
            if (normalized.verification_scope_id, normalized.test_case_key) not in mapped_by_identity:
                raise TraceabilityAdmissionError(
                    f"undeclared-test-observation: {normalized.verification_scope_id}:{normalized.test_case_key}"
                )
        except TraceabilityAdmissionError as exc:
            diagnostics.append(_input_diagnostic("execution", item, exc))
            continue
        normalized_executions.append(normalized)

    normalized_resolutions: list[NormalizedTestCodeResolution] = []
    for item in code_resolutions:
        try:
            normalized = normalize_test_code_resolution(item)
            if (normalized.verification_scope_id, normalized.test_case_key) not in mapped_by_identity:
                raise TraceabilityAdmissionError(
                    f"undeclared-test-observation: {normalized.verification_scope_id}:{normalized.test_case_key}"
                )
        except TraceabilityAdmissionError as exc:
            diagnostics.append(_input_diagnostic("code-resolution", item, exc))
            continue
        normalized_resolutions.append(normalized)

    # Caller-supplied observations are admitted as one atomic boundary.  Do
    # not build even the declaration portion of the delta when one execution
    # or code-resolution input is invalid: callers must not be able to merge
    # valid facts from a batch that failed admission.
    if diagnostics:
        ordered_diagnostics = tuple(sorted(diagnostics, key=lambda item: (item.reason_code, item.identity)))
        details = ", ".join(
            f"{item.reason_code}:{item.identity}" if item.identity else item.reason_code
            for item in ordered_diagnostics
        )
        raise TraceabilityAdmissionError(f"invalid traceability input: {details}")

    nodes: dict[str, Node] = {}
    edges: dict[str, Edge] = {}
    evidence: dict[str, Evidence] = {}
    provenance: dict[str, ProvenanceRecord] = {}
    claims: dict[str, CrossGraphLinkClaim] = {}
    observations: dict[str, CrossGraphLinkEvidence] = {}
    lifecycle: dict[str, CrossGraphLinkLifecycle] = {}
    for mapping in mappings:
        nodes[mapping.test_case_id] = verification_node(
            NodeKind.TEST_CASE, mapping.verification_scope_id, mapping.test_case_key,
            (mapping.evidence.id,),
        )
        evidence[mapping.evidence.id] = mapping.evidence
        provenance[mapping.provenance.id] = mapping.provenance
        edge = Edge(
            stable_id("edge", EdgeKind.VERIFIED_BY, mapping.target_id, mapping.test_case_id, mapping.id),
            EdgeKind.VERIFIED_BY, mapping.target_id, mapping.test_case_id,
            evidence_ids=(mapping.evidence.id,),
        )
        edges[edge.id] = edge
    for execution in normalized_executions:
        source_evidence, source_provenance = execution.source_bundle()
        evidence[source_evidence.id] = _coalesce_evidence_provenance(
            evidence.get(source_evidence.id), source_evidence,
        )
        provenance[source_provenance.id] = source_provenance
        test_id = verification_node_id(NodeKind.TEST_CASE, execution.verification_scope_id, execution.test_case_key)
        run_id = verification_node_id(NodeKind.TEST_RUN, execution.verification_scope_id, execution.test_run_key)
        run_node = verification_node(
            NodeKind.TEST_RUN, execution.verification_scope_id, execution.test_run_key,
            (source_evidence.id,),
        )
        nodes[run_id] = _coalesce_evidence(nodes.get(run_id), run_node)
        edge = Edge(
            stable_id("edge", EdgeKind.EXECUTED_IN, test_id, run_id, execution.id),
            EdgeKind.EXECUTED_IN, test_id, run_id, evidence_ids=(source_evidence.id,),
        )
        edges[edge.id] = _coalesce_evidence(edges.get(edge.id), edge)
    for resolution in normalized_resolutions:
        source_evidence, source_provenance = resolution.source_bundle()
        evidence[source_evidence.id] = _coalesce_evidence_provenance(
            evidence.get(source_evidence.id), source_evidence,
        )
        provenance[source_provenance.id] = source_provenance
        test_id = verification_node_id(NodeKind.TEST_CASE, resolution.verification_scope_id, resolution.test_case_key)
        claim = CrossGraphLinkClaim(test_id, RelationshipKind.REFERENCES.value, resolution.locator)
        claims[claim.id] = claim
        observations[CrossGraphLinkEvidence(
            claim.id, CODE_RESOLUTION_STRATEGY, resolution.observation_id, source_evidence.id,
            CrossGraphEvidenceOrigin.OBSERVED, CrossGraphEvidenceStatus.AUTHORITATIVE,
            "reliable", CrossGraphTrustDisposition.UNTRUSTED,
        ).id] = CrossGraphLinkEvidence(
            claim.id, CODE_RESOLUTION_STRATEGY, resolution.observation_id, source_evidence.id,
            CrossGraphEvidenceOrigin.OBSERVED, CrossGraphEvidenceStatus.AUTHORITATIVE,
            "reliable", CrossGraphTrustDisposition.UNTRUSTED,
        )
        lifecycle_evidence, lifecycle_provenance = _candidate_lifecycle(claim, source_provenance)
        evidence[lifecycle_evidence.id] = _coalesce_evidence_provenance(
            evidence.get(lifecycle_evidence.id), lifecycle_evidence,
        )
        provenance.update({item.id: item for item in lifecycle_provenance})
        entry = CrossGraphLinkLifecycle(
            claim.id, 1, CrossGraphLinkLifecycleState.CANDIDATE,
            lifecycle_evidence.id, CrossGraphEvidenceOrigin.OBSERVED,
            CrossGraphEvidenceStatus.DERIVED, "candidate-initialization",
            CrossGraphTrustDisposition.UNTRUSTED,
        )
        lifecycle[entry.id] = entry
    graph = GraphSnapshot(
        nodes=tuple(sorted(nodes.values(), key=lambda item: item.id)),
        edges=tuple(sorted(edges.values(), key=lambda item: item.id)),
        evidence=tuple(sorted(evidence.values(), key=lambda item: item.id)),
        provenance=tuple(sorted(provenance.values(), key=lambda item: item.id)),
        cross_graph_link_claims=tuple(sorted(claims.values(), key=lambda item: item.id)),
        cross_graph_link_evidence=tuple(sorted(observations.values(), key=lambda item: item.id)),
        cross_graph_link_lifecycle=tuple(sorted(lifecycle.values(), key=lambda item: item.id)),
    )
    ordered_diagnostics = tuple(sorted(diagnostics, key=lambda item: (item.reason_code, item.identity)))
    metadata = ScenarioTestTraceabilityMetadata(
        admitted_mapping_count=len(mappings),
        admitted_execution_count=len(normalized_executions),
        emitted_candidate_count=len(claims),
        skipped_input_count=len(ordered_diagnostics),
        skipped_reason_counts=dict(Counter(item.reason_code for item in ordered_diagnostics)),
        diagnostics=ordered_diagnostics,
        graph_counts={
            "edge_count": graph.edge_count, "evidence_count": graph.evidence_count,
            "node_count": graph.node_count, "provenance_count": graph.provenance_count,
            "cross_graph_link_claim_count": graph.cross_graph_link_claim_count,
        },
    )
    return ScenarioTestTraceabilityResult(graph, metadata)


def _diagnostic_result(reason_code: str, identity: str = "") -> ScenarioTestTraceabilityResult:
    """Return a payload-free result when the whole admission context is invalid."""

    diagnostic = TestTraceabilityDiagnostic(reason_code, identity)
    return ScenarioTestTraceabilityResult(
        GraphSnapshot(),
        ScenarioTestTraceabilityMetadata(
            skipped_input_count=1,
            skipped_reason_counts={reason_code: 1},
            diagnostics=(diagnostic,),
            graph_counts={
                "edge_count": 0,
                "evidence_count": 0,
                "node_count": 0,
                "provenance_count": 0,
                "cross_graph_link_claim_count": 0,
            },
        ),
    )


def _input_diagnostic(
    category: str, value: object, error: TraceabilityAdmissionError,
) -> TestTraceabilityDiagnostic:
    message = str(error)
    reason_code = _input_reason_code(category, message)
    return TestTraceabilityDiagnostic(reason_code, _input_identity(value))


def _input_reason_code(category: str, message: str) -> str:
    if message.startswith("undeclared-test-observation:"):
        return "undeclared-test-observation"
    if "field is not allowed" in message:
        return f"{category}-payload-rejected"
    if "unknown " in message and " field:" in message:
        return f"invalid-{category}-field"
    if category == "code-resolution":
        if "unsupported reliable" in message:
            return "unsupported-code-resolution-basis"
        if "repository mismatch" in message:
            return "code-resolution-repository-mismatch"
        if "revision mismatch" in message:
            return "code-resolution-revision-mismatch"
        if "exactly one locator" in message or "multiple locator" in message:
            return "ambiguous-code-resolution"
        return "non-emitted-code-resolution"
    return "invalid-execution-observation"


def _mapping_reason_code(message: str) -> str:
    for reason_code in (
        "invalid-traceability-document",
        "unsupported-traceability-version",
        "conflicting-duplicate-mapping",
    ):
        if message.startswith(reason_code):
            return reason_code
    return "invalid-traceability-mapping"


def _input_identity(value: object) -> str:
    if isinstance(value, Mapping):
        scope = value.get("verification_scope_id")
        key = value.get("test_case_key")
    else:
        scope = getattr(value, "verification_scope_id", None)
        key = getattr(value, "test_case_key", None)
    if not isinstance(scope, str) or not isinstance(key, str):
        return ""
    if not scope.strip() or not key.strip() or not _SAFE_SELECTOR.fullmatch(scope.strip()) or not _SAFE_SELECTOR.fullmatch(key.strip()):
        return ""
    return f"{scope.strip()}:{key.strip()}"


def _safe_diagnostic_identity(message: str) -> str:
    """Keep only a stable graph-safe suffix from a context error."""

    if message.startswith("conflicting-duplicate-mapping:"):
        return message.split(":", 1)[1]
    return ""


# Capability-oriented aliases keep the reusable boundary discoverable to callers.
extract_scenario_test_traceability = admit_scenario_test_traceability
admit_test_traceability = admit_scenario_test_traceability
parse_traceability_document = parse_test_traceability
normalize_execution_observation = normalize_test_execution_observation
normalize_test_to_code_resolution = normalize_test_code_resolution
normalize_test_execution = normalize_test_execution_observation
normalize_reliable_test_code_resolution = normalize_test_code_resolution


def _parse_mapping_record(
    record: object, index: int, graph: GraphSnapshot, source_identity: SourceArtifactIdentity,
    source_hash: str, observed_at: str,
) -> tuple[DeclaredTestMapping, ...]:
    if not isinstance(record, dict):
        raise TraceabilityAdmissionError(f"mapping {index} must be a mapping")
    _reject_document_keys(record, {"target", "tests"}, f"mapping {index}")
    target = record.get("target")
    if not isinstance(target, dict):
        raise TraceabilityAdmissionError(f"mapping {index} target must be a mapping")
    _reject_document_keys(target, {"capability", "requirement", "scenario"}, f"mapping {index} target")
    capability = _selector(target.get("capability"), "capability")
    requirement = _selector(target.get("requirement"), "requirement")
    scenario_value = target.get("scenario")
    scenario = _selector(scenario_value, "scenario") if scenario_value is not None else None
    tests = record.get("tests")
    if not isinstance(tests, list) or not tests:
        raise TraceabilityAdmissionError(f"mapping {index} tests must be a non-empty list")
    requirement_by_id = {
        node.id: node for node in graph.nodes
        if _value(node.kind) == NodeKind.REQUIREMENT.value
    }
    candidates = [
        node for node in graph.nodes
        if _node_value(node, "capability") == capability
        and (
            _node_value(node, "requirement_key") == requirement
            or (
                _value(node.kind) == NodeKind.SCENARIO.value
                and (
                    parent := requirement_by_id.get(str(_node_value(node, "requirement_id")))
                ) is not None
                and _node_value(parent, "requirement_key") == requirement
                and _node_value(parent, "capability") == capability
            )
        )
        and (
            (scenario is None and _value(node.kind) == NodeKind.REQUIREMENT.value)
            or (scenario is not None and _value(node.kind) == NodeKind.SCENARIO.value and _node_value(node, "scenario_key") == scenario)
        )
    ]
    if scenario is not None and "requirement" not in target:
        raise TraceabilityAdmissionError(f"mapping {index} scenario requires requirement selector")
    if len(candidates) != 1:
        raise TraceabilityAdmissionError(f"mapping {index} target selector resolved to {len(candidates)} targets")
    target_node = candidates[0]
    result: list[DeclaredTestMapping] = []
    for test_index, test in enumerate(tests):
        if not isinstance(test, dict):
            raise TraceabilityAdmissionError(f"mapping {index} test {test_index} must be a mapping")
        _reject_document_keys(test, {"verification_scope_id", "test_case_key"}, f"mapping {index} test {test_index}")
        scope = _verification_value(test.get("verification_scope_id"), "verification_scope_id")
        key = _verification_value(test.get("test_case_key"), "test_case_key")
        identity = stable_id("mapping", target_node.id, scope, key)
        provenance = ProvenanceRecord(
            ProvenanceKind.EXTERNAL, observed_at, "sha256", source_hash,
            "openspec-test-traceability", "1", source_identity,
        )
        evidence = Evidence(
            stable_id("evidence", source_identity.id, identity), "openspec",
            OpenSpecLocator(TRACEABILITY_FILE, TRACEABILITY_ARTIFACT_TYPE, identity, source_artifact_identity=source_identity),
        )
        # Evidence IDs are derived from the source locator and its mapping identity.
        evidence = Evidence(evidence.id, evidence.source, evidence.locator, provenance_ids=(provenance.id,))
        result.append(DeclaredTestMapping(
            target_node.id, str(_value(target_node.kind)), capability, requirement, scenario,
            scope, key, evidence, provenance,
        ))
    return tuple(result)


def _input_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TraceabilityAdmissionError(f"{label} input must be a mapping")
    return dict(value)


def _reject_input_keys(data: Mapping[str, Any], label: str) -> None:
    for key in data:
        if not isinstance(key, str) or key.casefold() in _FORBIDDEN_INPUT_FIELDS:
            raise TraceabilityAdmissionError(f"{label} field is not allowed: {key}")


def _reject_allowed_input_keys(data: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise TraceabilityAdmissionError(f"unknown {label} field: {unknown[0]}")


def _reject_document_keys(value: object, allowed: set[str], label: str) -> None:
    if not isinstance(value, dict):
        return
    non_string_keys = [key for key in value if not isinstance(key, str)]
    if non_string_keys:
        raise TraceabilityAdmissionError(
            f"unknown {label} field has non-string key: {repr(non_string_keys[0])}"
        )
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise TraceabilityAdmissionError(f"unknown {label} field: {unknown[0]}")


def _selector(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or not _SAFE_SELECTOR.fullmatch(value.strip()):
        raise TraceabilityAdmissionError(f"invalid traceability selector: {field_name}")
    return " ".join(value.strip().lower().split())


def _verification_value(value: object, field_name: str) -> str:
    try:
        text = value.strip() if isinstance(value, str) else value
        if field_name == "verification_scope_id":
            verification_node_id(NodeKind.TEST_CASE, text, "test-case")
        else:
            verification_node_id(NodeKind.TEST_CASE, "test-scope", text)
        return str(text).strip()
    except ValueError as exc:
        raise TraceabilityAdmissionError(str(exc)) from None


def _verification_identity(scope: object, key: object) -> None:
    try:
        verification_node_id(NodeKind.TEST_CASE, scope, key)
    except ValueError as exc:
        raise TraceabilityAdmissionError(str(exc)) from None


def _source_identity(data: Mapping[str, Any], artifact_type: str, label: str) -> SourceArtifactIdentity:
    source = data.get("source_artifact_identity", data.get("source_artifact"))
    if isinstance(source, SourceArtifactIdentity):
        if source.artifact_type != artifact_type:
            raise TraceabilityAdmissionError(f"{label} source artifact type is inconsistent")
        return source
    if not isinstance(source, Mapping):
        raise TraceabilityAdmissionError(f"{label} source_artifact_identity is required")
    _reject_document_keys(source, {"source_type", "source_identity", "artifact_type", "revision_or_version", "stable_locator"}, f"{label} source_artifact_identity")
    try:
        identity = SourceArtifactIdentity(
            source.get("source_type"), source.get("source_identity"),
            source.get("artifact_type", artifact_type), source.get("revision_or_version"),
            source.get("stable_locator"),
        )
    except ValueError as exc:
        raise TraceabilityAdmissionError(str(exc)) from None
    if identity.artifact_type != artifact_type:
        raise TraceabilityAdmissionError(f"{label} source artifact type is inconsistent")
    return identity


def _validate_provenance_fields(observed_at: object, algorithm: object, content_hash: object, extractor_id: object, extractor_version: object) -> None:
    if not isinstance(observed_at, str):
        raise TraceabilityAdmissionError("observation observed_at is required")
    try:
        instant = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TraceabilityAdmissionError("observation observed_at must be offset-aware ISO-8601") from exc
    if instant.tzinfo is None:
        raise TraceabilityAdmissionError("observation observed_at must be offset-aware ISO-8601")
    if algorithm != "sha256" or not isinstance(content_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", content_hash):
        raise TraceabilityAdmissionError("observation content_hash must be lowercase sha256")
    for value, name in ((extractor_id, "extractor_id"), (extractor_version, "extractor_version")):
        try:
            safe_identity(value, f"observation {name}")
        except ValueError as exc:
            raise TraceabilityAdmissionError(str(exc)) from None


def _code_locator(value: object) -> CodeLocator:
    if isinstance(value, CodeLocator):
        if not _complete_locator(value):
            raise TraceabilityAdmissionError("code locator must be complete and revision-qualified")
        return value
    if not isinstance(value, Mapping):
        raise TraceabilityAdmissionError("reliable-test-code-resolution requires one code_locator")
    _reject_document_keys(value, {"repository", "revision", "file", "symbol"}, "code locator")
    try:
        locator = CodeLocator(value.get("repository"), value.get("revision"), value.get("file"), value.get("symbol"))
        if (
            not safe_repository(locator.repository, "code locator.repository")
            or not is_immutable_revision(locator.revision)
            or not safe_relative_file(locator.file, "code locator.file")
            or not is_complete_symbol_identity(locator.symbol)
        ):
            raise TraceabilityAdmissionError("code locator must be complete and revision-qualified")
        return locator
    except (TypeError, ValueError) as exc:
        if isinstance(exc, TraceabilityAdmissionError):
            raise
        raise TraceabilityAdmissionError(f"invalid code locator: {exc}") from None


def _candidate_lifecycle(claim: CrossGraphLinkClaim, input_provenance: ProvenanceRecord) -> tuple[Evidence, tuple[ProvenanceRecord, ...]]:
    representation = json.dumps({"claim_id": claim.id, "input_provenance_ids": [input_provenance.id]}, sort_keys=True, separators=(",", ":"))
    derived = ProvenanceRecord(
        ProvenanceKind.DERIVED, input_provenance.observed_at, "sha256",
        hashlib.sha256(representation.encode()).hexdigest(), CODE_RESOLUTION_STRATEGY, "1",
        None, "cross-graph-candidate-initialization", (input_provenance.id,),
    )
    evidence = Evidence(
        stable_id("evidence", CODE_RESOLUTION_STRATEGY, "candidate-initialization", claim.id),
        CODE_RESOLUTION_STRATEGY, f"cross-graph-link:{claim.id}:candidate-initialization",
        {"claim_id": claim.id, "state": CrossGraphLinkLifecycleState.CANDIDATE.value},
        (derived.id,),
    )
    return evidence, (derived,)


def _complete_locator(locator: CodeLocator) -> bool:
    try:
        repository_valid = bool(safe_repository(locator.repository, "code locator.repository"))
        file_valid = bool(safe_relative_file(locator.file, "code locator.file"))
    except (AttributeError, ValueError):
        return False
    return (
        repository_valid and file_valid and is_immutable_revision(locator.revision)
        and is_complete_symbol_identity(locator.symbol)
    )


def _coalesce_evidence(existing: Node | Edge | None, incoming: Node | Edge) -> Node | Edge:
    """Merge evidence when repeated observations share a canonical record ID."""

    if existing is None:
        return incoming
    return replace(
        incoming,
        evidence_ids=tuple(sorted(set(existing.evidence_ids) | set(incoming.evidence_ids))),
    )


def _coalesce_evidence_provenance(existing: Evidence | None, incoming: Evidence) -> Evidence:
    """Retain every provenance record for a shared evidence ID."""

    if existing is None:
        return incoming
    return replace(
        existing,
        provenance_ids=tuple(sorted(set(existing.provenance_ids) | set(incoming.provenance_ids))),
    )


def _node_value(node: Node, key: str) -> object:
    return node.properties.get(key)


def _value(value: object) -> object:
    return getattr(value, "value", value)
