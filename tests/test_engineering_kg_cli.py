from __future__ import annotations

import sys
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from engineering_kg.cli import main
from engineering_kg.mcp.startup import McpGraphStoreResolution


class EngineeringKgCliTest(unittest.TestCase):
    def test_mcp_command_resolves_graph_store_and_runs_server(self) -> None:
        server = _FakeServer()

        with (
            patch("engineering_kg.cli.resolve_mcp_graph_store") as resolve,
            patch("engineering_kg.cli.create_factmcp_server") as create_server,
        ):
            resolve.return_value = McpGraphStoreResolution(
                graph_store_path=Path("/tmp/graph-store"),
                source="graph-store-override",
            )
            create_server.return_value = server

            code = main(["mcp", "--graph-store", "/tmp/graph-store", "--require-validation"])

        self.assertEqual(code, 0)
        self.assertTrue(server.ran)
        create_server.assert_called_once_with(
            graph_store_path=Path("/tmp/graph-store"),
            require_validation=True,
        )

    def test_mcp_command_exposes_unambiguous_startup_options(self) -> None:
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as raised:
                main(["mcp", "--store", "ambiguous"])

        self.assertNotEqual(raised.exception.code, 0)


class _FakeServer:
    def __init__(self) -> None:
        self.ran = False

    def run(self) -> None:
        self.ran = True


if __name__ == "__main__":
    unittest.main()
