"""Reusable local-first pipeline runner for the MVP bootstrap."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from engineering_kg.derivation import GraphDerivationResult, derive_graph_relationships
from engineering_kg.ingest.openspec import (
    OpenSpecExtractionResult,
    OpenSpecStoreSourceValidationResult,
    RegisteredOpenSpecStore,
    extract_openspec_graph,
    validate_openspec_store_source,
)
from engineering_kg.ingest.pr_code_candidates import (
    NormalizedPullRequestEvidence,
    PrCodeCandidateValidationError,
    PrCodeCandidateExtractionResult,
    extract_pr_code_candidates,
)
from engineering_kg.ontology import GraphSnapshot
from engineering_kg.openlore import OpenLoreSourceValidationResult, validate_workspace_openlore_source
from engineering_kg.persistence import (
    OntologyMigrationResult,
    PersistenceError,
    initialize_ladybugdb_store,
)
from engineering_kg.project import load_workspace_registry
from engineering_kg.validation import (
    GraphIntegrityValidationError,
    GraphValidationResult,
    validate_graph_integrity,
)


@dataclass(frozen=True)
class PipelineResult:
    """Deterministic result for a bootstrap pipeline run."""

    status: str
    configured_stages: tuple[str, ...]
    executed_stages: tuple[str, ...]
    graph: GraphSnapshot
    openlore_source: OpenLoreSourceValidationResult | None = None
    openspec_store_source: OpenSpecStoreSourceValidationResult | None = None
    openspec_graph_extraction: OpenSpecExtractionResult | None = None
    graph_derivation: GraphDerivationResult | None = None
    graph_integrity_validation: GraphValidationResult | None = None
    ontology_migration: OntologyMigrationResult | None = None
    pr_code_candidate_extraction: PrCodeCandidateExtractionResult | None = None

    @property
    def configured_stage_count(self) -> int:
        return len(self.configured_stages)

    @property
    def executed_stage_count(self) -> int:
        return len(self.executed_stages)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["configured_stages"] = list(self.configured_stages)
        data["executed_stages"] = list(self.executed_stages)
        data["graph"] = self.graph.as_dict()
        data["configured_stage_count"] = self.configured_stage_count
        data["executed_stage_count"] = self.executed_stage_count
        if self.openlore_source is None:
            data.pop("openlore_source")
        else:
            data["openlore_source"] = self.openlore_source.as_dict()
        if self.openspec_store_source is None:
            data.pop("openspec_store_source")
        else:
            data["openspec_store_source"] = self.openspec_store_source.as_dict()
        if self.openspec_graph_extraction is None:
            data.pop("openspec_graph_extraction")
        else:
            data["openspec_graph_extraction"] = {
                "metadata": self.openspec_graph_extraction.metadata.as_dict()
            }
        if self.graph_derivation is None:
            data.pop("graph_derivation")
        else:
            data["graph_derivation"] = {
                "metadata": self.graph_derivation.metadata.as_dict()
            }
        if self.graph_integrity_validation is None:
            data.pop("graph_integrity_validation")
        else:
            data["graph_integrity_validation"] = {
                "metadata": self.graph_integrity_validation.metadata.as_dict()
            }
        if self.ontology_migration is None:
            data.pop("ontology_migration")
        else:
            data["ontology_migration"] = self.ontology_migration.as_dict()
        if self.pr_code_candidate_extraction is None:
            data.pop("pr_code_candidate_extraction")
        else:
            data["pr_code_candidate_extraction"] = {"metadata": self.pr_code_candidate_extraction.metadata.as_dict()}
        return data


def run_pipeline(
    registry_path: str | Path | None = None,
    persistence_path: str | Path | None = None,
    openspec_stores: tuple[RegisteredOpenSpecStore, ...] | None = None,
    openspec_store_id: str | None = None,
    pr_change_sets: tuple[NormalizedPullRequestEvidence, ...] | None = None,
    engineering_change_subject_graph: GraphSnapshot | None = None,
) -> PipelineResult:
    """Start the MVP pipeline, optionally persisting a graph snapshot."""

    if registry_path is not None:
        registry = load_workspace_registry(registry_path)
        configured_stages = _configured_stages(
            registry.engineering_kg.pipeline_stages,
            persistence_path,
        )
        executed_stages: list[str] = []
        graph = GraphSnapshot()
        openspec_store_source = None
        openspec_graph_extraction = None
        graph_derivation = None
        graph_integrity_validation = None
        ontology_migration = None
        pr_code_candidate_extraction = None
        _validate_candidate_stage_order(
            configured_stages, pr_change_sets
        )
        if "workspace-registry" in configured_stages:
            executed_stages.append("workspace-registry")
            graph = registry.to_graph_snapshot()
        if "openspec-store-source" in configured_stages:
            openspec_store_source = validate_openspec_store_source(
                registry,
                registered_stores=openspec_stores,
                selected_store_id=openspec_store_id,
            )
            executed_stages.append("openspec-store-source")
        if "openspec-graph-extraction" in configured_stages:
            if openspec_store_source is None:
                raise ValueError(
                    "openspec-graph-extraction requires successful openspec-store-source stage"
                )
            openspec_graph_extraction = extract_openspec_graph(openspec_store_source)
            graph = graph.merged_with(openspec_graph_extraction.graph)
            executed_stages.append("openspec-graph-extraction")
        openlore_source = None
        if "workspace-openlore-source" in configured_stages:
            openlore_source = validate_workspace_openlore_source(registry)
            executed_stages.append("workspace-openlore-source")
        if "engineering-change-subject-input" in configured_stages:
            if engineering_change_subject_graph is None:
                raise ValueError(
                    "engineering-change-subject-input requires engineering_change_subject_graph input"
                )
            graph = graph.merged_with(engineering_change_subject_graph)
            executed_stages.append("engineering-change-subject-input")
        if "pr-code-candidate-extraction" in configured_stages:
            _validate_candidate_subject_availability(pr_change_sets or (), graph)
            pr_code_candidate_extraction = extract_pr_code_candidates(pr_change_sets or (), graph)
            graph = graph.merged_with(pr_code_candidate_extraction.graph)
            executed_stages.append("pr-code-candidate-extraction")
        if persistence_path is not None and "ladybugdb-persistence" in configured_stages:
            store = initialize_ladybugdb_store(persistence_path)
            executed_stages.append("ontology-migration")
            try:
                ontology_migration = store.migrate_persisted_snapshot()
            except PersistenceError as exc:
                return PipelineResult(
                    status="failed",
                    configured_stages=configured_stages,
                    executed_stages=tuple(executed_stages),
                    graph=graph,
                    openlore_source=openlore_source,
                    openspec_store_source=openspec_store_source,
                    openspec_graph_extraction=openspec_graph_extraction,
                    pr_code_candidate_extraction=pr_code_candidate_extraction,
                    ontology_migration=OntologyMigrationResult(
                        graph,
                        status="failed",
                        diagnostics=(str(exc),),
                    ),
                )
            executed_stages.append("ladybugdb-persistence")
            graph = store.write_snapshot(graph)
            ontology_migration = OntologyMigrationResult(
                graph,
                ontology_migration.migrated_node_count,
                ontology_migration.migrated_edge_count,
            )
        if "graph-derivation" in configured_stages:
            graph_derivation = derive_graph_relationships(graph)
            graph = graph_derivation.graph
            executed_stages.append("graph-derivation")
        if "graph-integrity-validation" in configured_stages:
            graph_integrity_validation = validate_graph_integrity(graph)
            executed_stages.append("graph-integrity-validation")
            if graph_integrity_validation.status == "invalid":
                raise GraphIntegrityValidationError(graph_integrity_validation)
        return PipelineResult(
            status="completed",
            configured_stages=configured_stages,
            executed_stages=tuple(executed_stages),
            graph=graph,
            openlore_source=openlore_source,
            openspec_store_source=openspec_store_source,
            openspec_graph_extraction=openspec_graph_extraction,
            graph_derivation=graph_derivation,
            graph_integrity_validation=graph_integrity_validation,
            ontology_migration=ontology_migration,
            pr_code_candidate_extraction=pr_code_candidate_extraction,
        )

    if persistence_path is not None:
        store = initialize_ladybugdb_store(persistence_path)
        ontology_migration = store.migrate_persisted_snapshot()
        graph = store.write_snapshot(GraphSnapshot())
        ontology_migration = OntologyMigrationResult(
            graph,
            ontology_migration.migrated_node_count,
            ontology_migration.migrated_edge_count,
        )
        return PipelineResult(
            status="completed",
            configured_stages=("ontology-migration", "ladybugdb-persistence"),
            executed_stages=("ontology-migration", "ladybugdb-persistence"),
            graph=graph,
            ontology_migration=ontology_migration,
        )

    return PipelineResult(
        status="completed",
        configured_stages=(),
        executed_stages=(),
        graph=GraphSnapshot(),
    )


def _configured_stages(
    registry_stages: tuple[str, ...],
    persistence_path: str | Path | None,
) -> tuple[str, ...]:
    stages = list(registry_stages)
    if persistence_path is not None and "ladybugdb-persistence" not in stages:
        insertion_index = len(stages)
        for stage in ("graph-derivation", "graph-integrity-validation"):
            if stage in stages:
                insertion_index = min(insertion_index, stages.index(stage))
        stages.insert(insertion_index, "ladybugdb-persistence")
    if persistence_path is not None and "ontology-migration" not in stages:
        stages.insert(stages.index("ladybugdb-persistence"), "ontology-migration")
    return tuple(stages)


def _validate_candidate_stage_order(
    stages: tuple[str, ...],
    change_sets: tuple[NormalizedPullRequestEvidence, ...] | None,
) -> None:
    if "pr-code-candidate-extraction" not in stages:
        return
    if change_sets is None:
        raise ValueError("pr-code-candidate-extraction requires normalized pr_change_sets input")
    candidate_index = stages.index("pr-code-candidate-extraction")
    subject_input_stage = "engineering-change-subject-input"
    if (
        subject_input_stage in stages
        and candidate_index < stages.index(subject_input_stage)
    ):
        raise ValueError(
            "pr-code-candidate-extraction must run after engineering-change-subject-input"
        )
    graph_producing_stages = {
        "workspace-registry",
        "openspec-graph-extraction",
        "engineering-change-subject-input",
    }
    if not any(stage in graph_producing_stages for stage in stages[:candidate_index]):
        raise ValueError("pr-code-candidate-extraction requires a prior graph-producing stage")
    for later in ("graph-derivation", "graph-integrity-validation"):
        if later in stages and candidate_index > stages.index(later):
            raise ValueError(f"pr-code-candidate-extraction must run before {later}")


def _validate_candidate_subject_availability(
    change_sets: tuple[NormalizedPullRequestEvidence, ...], graph: GraphSnapshot
) -> None:
    """Require every explicit candidate subject to exist in the graph at this stage."""

    available_subject_ids = {node.id for node in graph.nodes}
    missing_subject_ids = sorted(
        {
            _change_subject_id(change_set)
            for change_set in change_sets
            if _change_subject_id(change_set) not in available_subject_ids
        }
    )
    if missing_subject_ids:
        raise ValueError(
            "pr-code-candidate-extraction requires available prior graph subjects: "
            + ", ".join(missing_subject_ids)
        )


def _change_subject_id(change_set: NormalizedPullRequestEvidence) -> str:
    if not isinstance(change_set, NormalizedPullRequestEvidence):
        raise PrCodeCandidateValidationError(
            "legacy merged-revision-only PR change-set input is unsupported"
        )
    return change_set.association.intended_change_id
