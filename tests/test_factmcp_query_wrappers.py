from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from engineering_kg.mcp.factmcp_server import register_query_tools
from engineering_kg.query import EngineeringKgQuery
from tests.test_local_ekg_query_api import _graph


class _Server:
    def __init__(self): self.tools = {}
    def tool(self):
        def decorator(function): self.tools[function.__name__] = function; return function
        return decorator


class FactMcpQueryWrappersTest(unittest.TestCase):
    def test_requirement_tool_delegates_canonical_result(self) -> None:
        server = _Server()
        _, _, _, graph = _graph()
        register_query_tools(server, graph_store_path=".", query_factory=lambda _: EngineeringKgQuery.from_snapshot(graph))
        result = server.tools["list_requirements"]()
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"][0]["kind"], "requirement")
        self.assertNotIn("openspec-requirement", str(result))

    def test_traceability_tool_delegates_canonical_result(self) -> None:
        server = _Server()
        change, _, _, graph = _graph()
        register_query_tools(server, graph_store_path=".", query_factory=lambda _: EngineeringKgQuery.from_snapshot(graph))
        result = server.tools["get_traceability"](change.id)
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["object_id"], change.id)
        self.assertTrue(any(edge["kind"] == "traces_to" for edge in result["result"]["relationships"]))


if __name__ == "__main__":
    unittest.main()
