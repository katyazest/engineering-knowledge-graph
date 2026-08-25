"""Command line entry points for Engineering KG."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from engineering_kg.mcp.factmcp_server import create_factmcp_server
from engineering_kg.mcp.startup import (
    McpStartupOptions,
    McpStartupResolutionError,
    resolve_mcp_graph_store,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "mcp":
        return _run_mcp(args)
    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="engineering-kg")
    subparsers = parser.add_subparsers(dest="command")

    mcp = subparsers.add_parser("mcp", help="Start the Engineering KG MCP server")
    mcp.add_argument("--graph-store", help="Use a known LadybugDB-compatible graph store path")
    mcp.add_argument("--registry", help="Load graph store configuration from repo-index.yaml")
    mcp.add_argument("--openspec-store", help="Use a registered OpenSpec store id")
    mcp.add_argument("--openspec-command", help="Absolute path to the OpenSpec executable")
    mcp.add_argument("--git-command", help="Absolute path to the Git executable")
    mcp.add_argument(
        "--require-validation",
        action="store_true",
        help="Validate graph integrity before traceability queries",
    )
    return parser


def _run_mcp(args: argparse.Namespace) -> int:
    try:
        resolution = resolve_mcp_graph_store(
            McpStartupOptions(
                graph_store=args.graph_store,
                registry=args.registry,
                openspec_store=args.openspec_store,
                cwd=Path.cwd(),
                openspec_command=args.openspec_command,
                git_command=args.git_command,
            )
        )
    except McpStartupResolutionError as exc:
        raise SystemExit(str(exc)) from exc

    server = create_factmcp_server(
        graph_store_path=resolution.graph_store_path,
        require_validation=args.require_validation,
    )
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
