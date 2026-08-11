"""Reusable local-first pipeline runner for the MVP bootstrap."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from engineering_kg.ontology import GraphSnapshot
from engineering_kg.openlore import OpenLoreSourceValidationResult, validate_workspace_openlore_source
from engineering_kg.persistence import persist_graph_snapshot
from engineering_kg.project import load_workspace_registry


@dataclass(frozen=True)
class PipelineResult:
    """Deterministic result for a bootstrap pipeline run."""

    status: str
    configured_stages: tuple[str, ...]
    executed_stages: tuple[str, ...]
    graph: GraphSnapshot
    openlore_source: OpenLoreSourceValidationResult | None = None

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
        return data


def run_pipeline(
    registry_path: str | Path | None = None,
    persistence_path: str | Path | None = None,
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
        if "workspace-registry" in configured_stages:
            executed_stages.append("workspace-registry")
            graph = registry.to_graph_snapshot()
        openlore_source = None
        if "workspace-openlore-source" in configured_stages:
            openlore_source = validate_workspace_openlore_source(registry)
            executed_stages.append("workspace-openlore-source")
        if persistence_path is not None and "ladybugdb-persistence" in configured_stages:
            executed_stages.append("ladybugdb-persistence")
            graph = persist_graph_snapshot(persistence_path, graph)
        return PipelineResult(
            status="completed",
            configured_stages=configured_stages,
            executed_stages=tuple(executed_stages),
            graph=graph,
            openlore_source=openlore_source,
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
        stages.append("ladybugdb-persistence")
    return tuple(stages)
