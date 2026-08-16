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
from engineering_kg.ontology import GraphSnapshot
from engineering_kg.openlore import OpenLoreSourceValidationResult, validate_workspace_openlore_source
from engineering_kg.persistence import persist_graph_snapshot
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
        return data


def run_pipeline(
    registry_path: str | Path | None = None,
    persistence_path: str | Path | None = None,
    openspec_stores: tuple[RegisteredOpenSpecStore, ...] | None = None,
    openspec_store_id: str | None = None,
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
        if persistence_path is not None and "ladybugdb-persistence" in configured_stages:
            executed_stages.append("ladybugdb-persistence")
            graph = persist_graph_snapshot(persistence_path, graph)
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
        )

    if persistence_path is not None:
        graph = persist_graph_snapshot(persistence_path, GraphSnapshot())
        return PipelineResult(
            status="completed",
            configured_stages=("ladybugdb-persistence",),
            executed_stages=("ladybugdb-persistence",),
            graph=graph,
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
    return tuple(stages)
