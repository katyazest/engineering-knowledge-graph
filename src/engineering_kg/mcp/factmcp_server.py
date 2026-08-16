"""FactMCP/FastMCP tool wrappers for local Engineering KG queries."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from engineering_kg.query import EngineeringKgQuery, GraphQueryError


QueryFactory = Callable[[str | Path], EngineeringKgQuery]


def create_factmcp_server(
    *,
    graph_store_path: str | Path | None = None,
    require_validation: bool = False,
) -> Any:
    """Create a FactMCP-compatible server with Engineering KG query tools.

    The currently verified public Python MCP runtime exposes FastMCP under
    ``mcp.server.fastmcp``. Importing it lazily keeps the reusable query API
    and tests independent from an installed MCP runtime.
    """

    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "FactMCP/FastMCP runtime is not installed; install the verified MCP runtime "
            "before starting the wrapper server."
        ) from exc

    server = FastMCP("Engineering KG")
    register_query_tools(
        server,
        graph_store_path=graph_store_path,
        require_validation=require_validation,
    )
    return server


def register_query_tools(
    server: Any,
    *,
    graph_store_path: str | Path | None = None,
    query_factory: QueryFactory | None = None,
    require_validation: bool = False,
) -> Any:
    """Register Engineering KG query operations as FactMCP tools only."""

    if not hasattr(server, "tool"):
        raise TypeError("FactMCP-compatible server must provide a tool decorator")

    factory = query_factory or _store_query_factory(require_validation=require_validation)

    @server.tool()
    def list_requirements(
        graph_store: str | None = None,
        capability: str | None = None,
        service: str | None = None,
        change: str | None = None,
        evidence_ref: str | None = None,
    ) -> dict[str, Any]:
        """List Engineering KG requirement facts."""

        return _call_tool(
            lambda: _query(factory, graph_store_path, graph_store).list_requirements(
                capability=capability,
                service=service,
                change=change,
                evidence_ref=evidence_ref,
            )
        )

    @server.tool()
    def list_services(graph_store: str | None = None) -> dict[str, Any]:
        """List Engineering KG service and repository facts."""

        return _call_tool(lambda: _query(factory, graph_store_path, graph_store).list_services())

    @server.tool()
    def list_changes(graph_store: str | None = None) -> dict[str, Any]:
        """List Engineering KG OpenSpec change facts."""

        return _call_tool(lambda: _query(factory, graph_store_path, graph_store).list_changes())

    @server.tool()
    def get_traceability(
        object_id: str,
        graph_store: str | None = None,
    ) -> dict[str, Any]:
        """Return traceability relationships for one Engineering KG graph object."""

        return _call_tool(
            lambda: _query(factory, graph_store_path, graph_store).get_traceability(
                object_id,
                require_validation=require_validation,
            )
        )

    return server


def _store_query_factory(*, require_validation: bool) -> QueryFactory:
    def factory(path: str | Path) -> EngineeringKgQuery:
        return EngineeringKgQuery.from_store(path, require_validation=require_validation)

    return factory


def _query(
    query_factory: QueryFactory,
    default_graph_store_path: str | Path | None,
    request_graph_store_path: str | None,
) -> EngineeringKgQuery:
    graph_store = request_graph_store_path or default_graph_store_path
    if graph_store is None:
        raise GraphQueryError("A local graph store path is required")
    return query_factory(graph_store)


def _call_tool(callback: Callable[[], Any]) -> dict[str, Any]:
    try:
        return {
            "ok": True,
            "result": callback(),
        }
    except GraphQueryError as exc:
        return {
            "error": exc.as_dict(),
            "ok": False,
        }
