from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from engineering_kg.ontology import (
    CodeLocator,
    Edge,
    EdgeKind,
    Evidence,
    GraphSnapshot,
    Node,
    NodeKind,
    OpenSpecLocator,
    stable_id,
)
from engineering_kg.persistence import initialize_ladybugdb_store
from engineering_kg.query import (
    EngineeringKgQuery,
    GraphObjectNotFoundError,
    GraphQueryValidationError,
)


class LocalEkgQueryApiTest(unittest.TestCase):
    def test_constructs_from_snapshot_and_lists_requirements_locally(self) -> None:
        graph = _query_graph(include_forbidden=False)

        result = EngineeringKgQuery.from_snapshot(graph).list_requirements()

        self.assertEqual([item["name"] for item in result], ["Payment is submitted"])
        self.assertEqual(result[0]["properties"]["capability"], "payments")
        self.assertIn("locators", result[0])

    def test_constructs_from_store_through_persistence_readback(self) -> None:
        graph = _query_graph(include_forbidden=False)
        with tempfile.TemporaryDirectory() as tmp:
            initialize_ladybugdb_store(Path(tmp) / "ladybugdb").write_snapshot(graph)

            result = EngineeringKgQuery.from_store(Path(tmp) / "ladybugdb").list_services()

        self.assertEqual([item["name"] for item in result], ["Payment Service"])
        self.assertEqual(result[0]["properties"]["repository_ids"], [_repository_id()])

    def test_filters_requirements_by_explicit_graph_facts(self) -> None:
        graph = _query_graph()
        query = EngineeringKgQuery.from_snapshot(graph)

        by_capability = query.list_requirements(capability="payments")
        by_service = query.list_requirements(service="Payment Service")
        by_change = query.list_requirements(change="JIRA-123-add-refund")
        by_evidence = query.list_requirements(evidence_ref=_evidence_id("requirement"))

        self.assertEqual([item["name"] for item in by_capability], ["Payment is submitted"])
        self.assertEqual([item["name"] for item in by_service], ["Payment is submitted"])
        self.assertEqual([item["name"] for item in by_change], ["Payment is submitted"])
        self.assertEqual([item["name"] for item in by_evidence], ["Payment is submitted"])
        self.assertEqual(query.list_requirements(capability="settlement"), [])

    def test_lists_changes_with_missing_durable_spec_links_explicitly(self) -> None:
        result = EngineeringKgQuery.from_snapshot(_query_graph(include_trace=False)).list_changes()

        self.assertEqual([item["name"] for item in result], ["JIRA-123-add-refund"])
        self.assertEqual(result[0]["properties"]["touched_spec_ids"], [_active_spec_id()])
        self.assertEqual(result[0]["properties"]["traceability_spec_ids"], [])
        self.assertEqual(result[0]["properties"]["missing_durable_spec_links"], [_active_spec_id()])

    def test_traceability_preserves_confidence_and_returns_missing_explicitly(self) -> None:
        result = EngineeringKgQuery.from_snapshot(_query_graph()).get_traceability(_durable_spec_id())

        relationships = result["relationships"]

        self.assertFalse(result["missing"])
        self.assertTrue(any(item["confidence"] == "non-confident" for item in relationships))
        self.assertTrue(
            any(item["kind"] == EdgeKind.OPENSPEC_CHANGE_TRACES_TO_SPEC.value for item in relationships)
        )
        self.assertEqual(
            EngineeringKgQuery.from_snapshot(_query_graph()).get_traceability("missing-node"),
            {"missing": True, "object_id": "missing-node", "relationships": []},
        )
        with self.assertRaises(GraphObjectNotFoundError):
            EngineeringKgQuery.from_snapshot(_query_graph()).get_traceability(
                "missing-node",
                missing_ok=False,
            )

    def test_validation_required_blocks_invalid_traceability(self) -> None:
        graph = GraphSnapshot(
            nodes=(
                Node(
                    id=_durable_spec_id(),
                    kind=NodeKind.OPENSPEC_SPEC,
                    name="payments",
                    properties={"scope": "durable"},
                ),
            ),
            edges=(
                Edge(
                    id=stable_id("edge", "broken", _durable_spec_id(), "missing-target"),
                    kind=EdgeKind.TRACES_TO,
                    source_id=_durable_spec_id(),
                    target_id="missing-target",
                ),
            ),
        )

        with self.assertRaises(GraphQueryValidationError):
            EngineeringKgQuery.from_snapshot(graph).get_traceability(
                _durable_spec_id(),
                require_validation=True,
            )

    def test_output_excludes_source_owned_payloads_and_sensitive_fields(self) -> None:
        result = EngineeringKgQuery.from_snapshot(_query_graph()).list_requirements()[0]
        serialized = str(result)

        locators = {item["source"]: item["locator"] for item in result["locators"]}
        self.assertEqual(
            locators["openspec"],
            {
                "artifact_type": "spec",
                "openspec_identity": "payments",
                "relative_file_path": "openspec/specs/payments/spec.md",
            },
        )
        self.assertEqual(
            locators["openlore"],
            {
                "file": "src/app.py",
                "repository": "payment-service",
                "revision": "abc123",
                "symbol": "create_payment",
            },
        )
        for forbidden in (
            "source_code",
            "call_graph",
            "dependency_graph",
            "symbol_body",
            "openlore_analysis",
            "api_response",
            "credentials",
            "tokens",
            "page_content",
        ):
            self.assertNotIn(forbidden, serialized)


def _query_graph(*, include_trace: bool = True, include_forbidden: bool = True) -> GraphSnapshot:
    service = Node(
        id=_service_id(),
        kind=NodeKind.SERVICE,
        name="Payment Service",
        properties={
            "repository_id": "payment-service",
            **({"source_code": "forbidden"} if include_forbidden else {}),
        },
    )
    repository = Node(
        id=_repository_id(),
        kind=NodeKind.REPOSITORY,
        name="payment-service",
    )
    durable_spec = Node(
        id=_durable_spec_id(),
        kind=NodeKind.OPENSPEC_SPEC,
        name="Payments",
        properties={"capability": "payments", "scope": "durable"},
    )
    active_spec = Node(
        id=_active_spec_id(),
        kind=NodeKind.OPENSPEC_SPEC,
        name="Payments",
        properties={"capability": "payments", "scope": "active-change"},
    )
    requirement = Node(
        id=_requirement_id(),
        kind=NodeKind.OPENSPEC_REQUIREMENT,
        name="Payment is submitted",
        properties={
            "capability": "payments",
            **(
                {
                    "api_response": {"body": "forbidden"},
                    "source_code": "forbidden",
                }
                if include_forbidden
                else {}
            ),
        },
        evidence_ids=(_evidence_id("requirement"), _evidence_id("code")),
    )
    change = Node(
        id=_change_id(),
        kind=NodeKind.OPENSPEC_ACTIVE_CHANGE,
        name="JIRA-123-add-refund",
        properties={"jira_payload": {"summary": "forbidden"}} if include_forbidden else {},
    )
    artifact = Node(
        id=stable_id("node", NodeKind.OPENSPEC_ARTIFACT, "JIRA-123-add-refund", "proposal"),
        kind=NodeKind.OPENSPEC_ARTIFACT,
        name="proposal.md",
    )
    evidence = (
        Evidence(
            id=_evidence_id("requirement"),
            source="openspec",
            locator=OpenSpecLocator(
                relative_file_path="openspec/specs/payments/spec.md",
                artifact_type="spec",
                openspec_identity="payments",
            ),
            properties={"page_content": "forbidden"} if include_forbidden else {},
        ),
        Evidence(
            id=_evidence_id("code"),
            source="openlore",
            locator=CodeLocator(
                repository="payment-service",
                revision="abc123",
                file="src/app.py",
                symbol="create_payment",
            ),
        ),
    )
    edges = [
        Edge(
            id=stable_id("edge", EdgeKind.OWNS, _service_id(), _repository_id()),
            kind=EdgeKind.OWNS,
            source_id=_service_id(),
            target_id=_repository_id(),
        ),
        Edge(
            id=stable_id("edge", EdgeKind.IMPLEMENTS, _repository_id(), _requirement_id()),
            kind=EdgeKind.IMPLEMENTS,
            source_id=_repository_id(),
            target_id=_requirement_id(),
        ),
        Edge(
            id=stable_id("edge", EdgeKind.OPENSPEC_SPEC_CONTAINS_REQUIREMENT, _durable_spec_id(), _requirement_id()),
            kind=EdgeKind.OPENSPEC_SPEC_CONTAINS_REQUIREMENT,
            source_id=_durable_spec_id(),
            target_id=_requirement_id(),
        ),
        Edge(
            id=stable_id("edge", EdgeKind.OPENSPEC_CHANGE_HAS_ARTIFACT, _change_id(), artifact.id),
            kind=EdgeKind.OPENSPEC_CHANGE_HAS_ARTIFACT,
            source_id=_change_id(),
            target_id=artifact.id,
        ),
        Edge(
            id=stable_id("edge", EdgeKind.OPENSPEC_CHANGE_TOUCHES_SPEC, _change_id(), _active_spec_id()),
            kind=EdgeKind.OPENSPEC_CHANGE_TOUCHES_SPEC,
            source_id=_change_id(),
            target_id=_active_spec_id(),
        ),
        Edge(
            id=stable_id("edge", EdgeKind.OPENSPEC_SPEC_CONTAINS_REQUIREMENT, _active_spec_id(), _requirement_id()),
            kind=EdgeKind.OPENSPEC_SPEC_CONTAINS_REQUIREMENT,
            source_id=_active_spec_id(),
            target_id=_requirement_id(),
        ),
        Edge(
            id=stable_id("edge", EdgeKind.OPENSPEC_RELATED_SPEC, _durable_spec_id(), _active_spec_id()),
            kind=EdgeKind.OPENSPEC_RELATED_SPEC,
            source_id=_durable_spec_id(),
            target_id=_active_spec_id(),
            confidence="non-confident",
        ),
    ]
    if include_trace:
        edges.append(
            Edge(
                id=stable_id("edge", EdgeKind.OPENSPEC_CHANGE_TRACES_TO_SPEC, _change_id(), _durable_spec_id()),
                kind=EdgeKind.OPENSPEC_CHANGE_TRACES_TO_SPEC,
                source_id=_change_id(),
                target_id=_durable_spec_id(),
            )
        )
    return GraphSnapshot(
        nodes=(service, repository, durable_spec, active_spec, requirement, change, artifact),
        edges=tuple(edges),
        evidence=evidence,
    )


def _service_id() -> str:
    return stable_id("node", NodeKind.SERVICE, "payment-service")


def _repository_id() -> str:
    return stable_id("node", NodeKind.REPOSITORY, "payment-service")


def _durable_spec_id() -> str:
    return stable_id("node", NodeKind.OPENSPEC_SPEC, "durable", "payments")


def _active_spec_id() -> str:
    return stable_id("node", NodeKind.OPENSPEC_SPEC, "active-change", "payments")


def _requirement_id() -> str:
    return stable_id("node", NodeKind.OPENSPEC_REQUIREMENT, "payments", "payment is submitted")


def _change_id() -> str:
    return stable_id("node", NodeKind.OPENSPEC_ACTIVE_CHANGE, "JIRA-123-add-refund")


def _evidence_id(name: str) -> str:
    return stable_id("evidence", name)


if __name__ == "__main__":
    unittest.main()
