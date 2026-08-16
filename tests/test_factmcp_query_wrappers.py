from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from engineering_kg.mcp.factmcp_server import register_query_tools
from engineering_kg.ontology import Edge, EdgeKind, GraphSnapshot, Node, NodeKind, stable_id
from engineering_kg.query import EngineeringKgQuery


class FactMcpQueryWrappersTest(unittest.TestCase):
    def test_registers_query_operations_as_tools_only(self) -> None:
        server = _FakeFactMcpServer()

        register_query_tools(server, graph_store_path="local-store", query_factory=_factory(GraphSnapshot()))

        self.assertEqual(
            sorted(server.tools),
            ["get_traceability", "list_changes", "list_requirements", "list_services"],
        )
        self.assertEqual(server.resources, [])

    def test_requirement_tool_delegates_to_query_api_with_inputs(self) -> None:
        requirement = Node(
            id=stable_id("node", NodeKind.OPENSPEC_REQUIREMENT, "payments", "submit"),
            kind=NodeKind.OPENSPEC_REQUIREMENT,
            name="Submit payment",
            properties={"capability": "payments"},
        )
        query = _RecordingQuery(GraphSnapshot(nodes=(requirement,)))
        server = _FakeFactMcpServer()

        def query_factory(path):
            query.store_path = str(path)
            return query

        register_query_tools(server, graph_store_path="default-store", query_factory=query_factory)

        result = server.tools["list_requirements"](
            graph_store="request-store",
            capability="payments",
            service="Payment Service",
            change="JIRA-1",
            evidence_ref="ev-1",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(query.store_path, "request-store")
        self.assertEqual(
            query.calls,
            [
                (
                    "list_requirements",
                    {
                        "capability": "payments",
                        "change": "JIRA-1",
                        "evidence_ref": "ev-1",
                        "service": "Payment Service",
                    },
                )
            ],
        )

    def test_service_change_and_traceability_tools_delegate_to_query_api(self) -> None:
        query = _RecordingQuery(GraphSnapshot())
        server = _FakeFactMcpServer()
        register_query_tools(server, graph_store_path="default-store", query_factory=lambda path: query)

        self.assertTrue(server.tools["list_services"]()["ok"])
        self.assertTrue(server.tools["list_changes"]()["ok"])
        self.assertTrue(server.tools["get_traceability"]("node-1")["ok"])

        self.assertEqual(
            [call[0] for call in query.calls],
            ["list_services", "list_changes", "get_traceability"],
        )
        self.assertEqual(query.calls[-1][1], {"object_id": "node-1", "require_validation": False})

    def test_missing_graph_store_returns_structured_error(self) -> None:
        server = _FakeFactMcpServer()
        register_query_tools(server, query_factory=_factory(GraphSnapshot()))

        result = server.tools["list_services"]()

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "graph-query-error")
        self.assertNotIn("token", str(result))

    def test_validation_required_traceability_returns_structured_error(self) -> None:
        node = Node(
            id="node-1",
            kind=NodeKind.OPENSPEC_SPEC,
            name="Payments",
            properties={"scope": "durable"},
        )
        graph = GraphSnapshot(
            nodes=(node,),
            edges=(
                Edge(
                    id="edge-1",
                    kind=EdgeKind.TRACES_TO,
                    source_id=node.id,
                    target_id="missing",
                ),
            ),
        )
        server = _FakeFactMcpServer()
        register_query_tools(
            server,
            graph_store_path="local-store",
            query_factory=_factory(graph),
            require_validation=True,
        )

        result = server.tools["get_traceability"]("node-1")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "graph-validation-failed")
        self.assertEqual(result["error"]["validation"]["status"], "invalid")


class _FakeFactMcpServer:
    def __init__(self) -> None:
        self.tools = {}
        self.resources = []

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator

    def resource(self, uri):
        self.resources.append(uri)
        raise AssertionError("Query wrappers must not register resources")


class _RecordingQuery(EngineeringKgQuery):
    def __init__(self, snapshot: GraphSnapshot) -> None:
        super().__init__(snapshot)
        self.calls = []
        self.store_path = ""

    def list_requirements(self, **kwargs):
        self.calls.append(("list_requirements", kwargs))
        return []

    def list_services(self):
        self.calls.append(("list_services", {}))
        return []

    def list_changes(self):
        self.calls.append(("list_changes", {}))
        return []

    def get_traceability(self, object_id: str, *, require_validation: bool = False, missing_ok: bool = True):
        self.calls.append(("get_traceability", {"object_id": object_id, "require_validation": require_validation}))
        return {"missing": False, "object_id": object_id, "relationships": []}


def _factory(graph: GraphSnapshot):
    def query_factory(path):
        query = EngineeringKgQuery.from_snapshot(graph)
        query.store_path = str(path)
        return query

    return query_factory


if __name__ == "__main__":
    unittest.main()
