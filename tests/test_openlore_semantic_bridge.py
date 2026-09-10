from __future__ import annotations

import inspect
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
FIXTURES = REPO_ROOT / "tests" / "fixtures"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from engineering_kg.ingest.pr_code_candidates import (
    MappingOutcome,
    extract_pr_code_candidates,
    normalize_pull_request_evidence,
)
import engineering_kg.openlore_bridge as openlore_bridge_module
from engineering_kg.ontology import GraphSnapshot, Node, NodeKind, CodeLocator
from engineering_kg.openlore_bridge import (
    BridgeDiagnostic,
    BridgeValidationError,
    ChangedFileReference,
    ChangedFileResolutionRequest,
    ChangedFileResolutionOutcome,
    ImplementationEvidenceContext,
    NavigationHandoff,
    NavigationHandoffResult,
    OpenLoreSemanticBridge,
    ProviderFileResolution,
    ProviderResolutionRequest,
    ProviderResolutionResponse,
    ProviderUnavailableError,
    ResolutionResult,
    ResolutionStatus,
    RoutingReference,
    adapt_resolution_to_changed_symbol_mappings,
)
from engineering_kg.project import load_workspace_registry


REVISION = "a" * 40


class FakeProvider:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.requests = []

    def resolve_symbols(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.response


def _request(repository: str = "payment-service", revision: str = REVISION, files=None):
    changed_files = files or (
        ChangedFileReference("graphify:m2", "src/b.py"),
        ChangedFileReference("graphify:m1", "src/a.py"),
    )
    evidence = ImplementationEvidenceContext("evidence:pr-1", repository, revision)
    return ChangedFileResolutionRequest(evidence, repository, revision, changed_files)


def _response(*entries, status="ok"):
    return ProviderResolutionResponse(tuple(entries), status=status)


def _entry(file_id, file, *symbols, repository="payment-service", revision=REVISION, status="ok"):
    return ProviderFileResolution(file_id, repository, revision, file, tuple(symbols), status)


class OpenLoreSemanticBridgeTest(unittest.TestCase):
    def stage_bridge(self, provider):
        registry = load_workspace_registry(FIXTURES / "repo-index-openlore-stage.yaml")
        return OpenLoreSemanticBridge(registry, provider)

    def fallback_bridge(self, provider):
        registry = load_workspace_registry(FIXTURES / "repo-index.yaml")
        return OpenLoreSemanticBridge(registry, provider)

    def test_federated_singletons_are_sorted_and_route_only_compact_request(self):
        provider = FakeProvider(_response(
            _entry("graphify:m2", "src/b.py", "module.Beta"),
            _entry("graphify:m1", "src/a.py", "module.Alpha"),
        ))
        result = self.stage_bridge(provider).resolve(_request())

        self.assertEqual(result.status, "admitted")
        self.assertEqual(result.routing.route_kind, "federation-index")
        self.assertEqual(result.routing.reference, ".openlore/index")
        self.assertEqual([item.stable_file_id for item in result.outcomes], ["graphify:m1", "graphify:m2"])
        self.assertEqual(result.outcomes[0].status, ResolutionStatus.RESOLVED)
        self.assertEqual(result.as_dict()["outcomes"][0]["status"], "resolved")
        self.assertEqual(result.outcomes[0].locator, CodeLocator("payment-service", REVISION, "src/a.py", "module.Alpha"))
        self.assertEqual([item.stable_file_id for item in provider.requests[0].changed_files], ["graphify:m1", "graphify:m2"])
        self.assertNotIn("source", str(result.as_dict()).lower())

    def test_registered_non_federated_and_federation_disabled_repositories_use_fallback(self):
        provider = FakeProvider(_response(_entry("graphify:m1", "src/a.py", "module.Alpha"), _entry("graphify:m2", "src/b.py", "module.Beta")))
        fallback = self.fallback_bridge(provider)
        result = fallback.resolve(_request("workflow-config", REVISION, (ChangedFileReference("graphify:m1", "config/a.yaml"),)))
        self.assertEqual(result.routing.route_kind, "repository-index-path")
        self.assertEqual(result.routing.reference, str(next(repo for repo in fallback.registry.repositories if repo.id == "workflow-config").resolved_path))

        disabled_registry = load_workspace_registry(FIXTURES / "repo-index-openlore-federation-disabled.yaml")
        disabled_provider = FakeProvider(_response(_entry("graphify:m1", "src/a.py", "module.Alpha")))
        disabled = OpenLoreSemanticBridge(disabled_registry, disabled_provider)
        disabled_result = disabled.resolve(_request(files=(ChangedFileReference("graphify:m1", "src/a.py"),)))
        self.assertEqual(disabled_result.routing.route_kind, "repository-index-path")
        self.assertEqual(len(disabled_provider.requests), 1)

    def test_routing_accepts_space_bearing_registry_paths(self):
        registry = load_workspace_registry(FIXTURES / "repo-index-openlore-stage.yaml")
        repository = next(item for item in registry.repositories if item.id == "payment-service")
        federated_repository = replace(
            repository,
            openlore=replace(repository.openlore, index_location=".openlore/index cache"),
        )
        federated_registry = replace(
            registry,
            repositories=tuple(
                federated_repository if item.id == repository.id else item
                for item in registry.repositories
            ),
        )
        federated_provider = FakeProvider(_response(_entry("graphify:m1", "src/a.py", "module.Alpha")))
        federated_result = OpenLoreSemanticBridge(federated_registry, federated_provider).resolve(
            _request(files=(ChangedFileReference("graphify:m1", "src/a.py"),))
        )
        self.assertEqual(federated_result.routing.reference, ".openlore/index cache")
        self.assertEqual(len(federated_provider.requests), 1)

        fallback_repository = next(item for item in registry.repositories if item.id == "workflow-config")
        fallback_registry = replace(
            registry,
            repositories=tuple(
                replace(item, resolved_path=Path("/workspace/Code Projects/service"))
                if item.id == fallback_repository.id else item
                for item in registry.repositories
            ),
        )
        fallback_provider = FakeProvider()
        handoff = OpenLoreSemanticBridge(fallback_registry, fallback_provider).build_navigation_handoff(
            CodeLocator("workflow-config", REVISION, "config/a.yaml", "config.load")
        )
        self.assertEqual(handoff.status, "ready")
        self.assertEqual(handoff.handoff.routing.reference, "/workspace/Code Projects/service")
        self.assertEqual(fallback_provider.requests, [])

    def test_routing_admits_punctuation_and_credential_named_path_components(self):
        registry = load_workspace_registry(FIXTURES / "repo-index-openlore-stage.yaml")
        repository = next(item for item in registry.repositories if item.id == "payment-service")
        punctuation_route = ".openlore/O'Reilly @2024 (cache) [$]{},;"
        punctuation_registry = replace(
            registry,
            repositories=tuple(
                replace(repository, openlore=replace(repository.openlore, index_location=punctuation_route))
                if item.id == repository.id else item
                for item in registry.repositories
            ),
        )
        provider = FakeProvider(_response(_entry("graphify:m1", "src/a.py", "module.Alpha")))
        bridge = OpenLoreSemanticBridge(punctuation_registry, provider)
        resolved = bridge.resolve(_request(files=(ChangedFileReference("graphify:m1", "src/a.py"),)))
        self.assertEqual(resolved.status, "admitted")
        self.assertEqual(resolved.routing.reference, punctuation_route)
        self.assertEqual(len(provider.requests), 1)

        fallback_route = "/workspace/O'Reilly @2024 (cache) [$]{},;"
        fallback_registry = replace(
            registry,
            repositories=tuple(
                replace(item, resolved_path=Path(fallback_route)) if item.id == "workflow-config" else item
                for item in registry.repositories
            ),
        )
        fallback_bridge = OpenLoreSemanticBridge(fallback_registry, FakeProvider())
        handoff = fallback_bridge.build_navigation_handoff(
            CodeLocator("workflow-config", REVISION, "config/a.yaml", "config.load")
        )
        self.assertEqual(handoff.status, "ready")
        self.assertEqual(handoff.handoff.routing.reference, fallback_route)

        named_route = ".openlore/token-service/my-secret-files"
        named_registry = replace(
            registry,
            repositories=tuple(
                replace(repository, openlore=replace(repository.openlore, index_location=named_route))
                if item.id == repository.id else item
                for item in registry.repositories
            ),
        )
        named_provider = FakeProvider(_response(_entry("graphify:m1", "src/a.py", "module.Alpha")))
        named_result = OpenLoreSemanticBridge(named_registry, named_provider).resolve(
            _request(files=(ChangedFileReference("graphify:m1", "src/a.py"),))
        )
        self.assertEqual(named_result.routing.reference, named_route)
        self.assertEqual(len(named_provider.requests), 1)

        named_fallback_route = "/workspace/token-service/my-secret-files"
        named_fallback_registry = replace(
            registry,
            repositories=tuple(
                replace(item, resolved_path=Path(named_fallback_route)) if item.id == "workflow-config" else item
                for item in registry.repositories
            ),
        )
        named_handoff = OpenLoreSemanticBridge(named_fallback_registry, FakeProvider()).build_navigation_handoff(
            CodeLocator("workflow-config", REVISION, "config/a.yaml", "config.load")
        )
        self.assertEqual(named_handoff.status, "ready")
        self.assertEqual(named_handoff.handoff.routing.reference, named_fallback_route)

    def test_invalid_context_never_calls_provider(self):
        provider = FakeProvider(_response())
        bridge = self.stage_bridge(provider)
        cases = (
            (_request("missing-repository"), "unknown-repository"),
            (ChangedFileResolutionRequest(ImplementationEvidenceContext("evidence:pr-1", "other", REVISION), "payment-service", REVISION, (ChangedFileReference("graphify:m1", "src/a.py"),)), "evidence-repository-mismatch"),
            (ChangedFileResolutionRequest(ImplementationEvidenceContext("evidence:pr-1", "payment-service", REVISION), "payment-service", "main", (ChangedFileReference("graphify:m1", "src/a.py"),)), "mutable-revision"),
            (ChangedFileResolutionRequest(ImplementationEvidenceContext("evidence:pr-1", "payment-service", REVISION), "payment-service", "b" * 40, (ChangedFileReference("graphify:m1", "src/a.py"),)), "evidence-revision-mismatch"),
        )
        for request, reason in cases:
            with self.subTest(reason=reason):
                result = bridge.resolve(request)
                self.assertEqual(result.status, "invalid-context")
                self.assertEqual(result.diagnostics[-1].reason_code, reason)
        self.assertEqual(provider.requests, [])

    def test_applicable_blank_federation_index_is_not_a_fallback(self):
        provider = FakeProvider(_response())
        registry = load_workspace_registry(FIXTURES / "repo-index-openlore-missing-index.yaml")
        result = OpenLoreSemanticBridge(registry, provider).resolve(_request(files=(ChangedFileReference("graphify:m1", "src/a.py"),)))
        self.assertEqual(result.diagnostics[-1].reason_code, "missing-federation-index")
        self.assertEqual(provider.requests, [])

    def test_duplicate_request_entries_coalesce_and_conflicts_are_rejected(self):
        provider = FakeProvider(_response(_entry("graphify:m1", "src/a.py", "module.Alpha")))
        request = _request(files=(ChangedFileReference("graphify:m1", "src/a.py"), ChangedFileReference("graphify:m1", "src/a.py")))
        result = self.stage_bridge(provider).resolve(request)
        self.assertEqual(len(provider.requests), 1)
        self.assertEqual(len(provider.requests[0].changed_files), 1)
        self.assertEqual(len(result.outcomes), 1)

        conflict_provider = FakeProvider(_response())
        conflict = _request(files=(ChangedFileReference("graphify:m1", "src/a.py"), ChangedFileReference("graphify:m1", "src/other.py")))
        conflict_result = self.stage_bridge(conflict_provider).resolve(conflict)
        self.assertEqual(conflict_result.status, "invalid-context")
        self.assertEqual(conflict_result.diagnostics[0].reason_code, "conflicting-changed-file-identity")
        self.assertEqual(conflict_provider.requests, [])

        reversed_conflict_provider = FakeProvider(_response())
        reversed_conflict = _request(
            files=(ChangedFileReference("graphify:m1", "src/other.py"), ChangedFileReference("graphify:m1", "src/a.py"))
        )
        reversed_conflict_result = self.stage_bridge(reversed_conflict_provider).resolve(reversed_conflict)
        self.assertEqual(conflict_result.as_dict(), reversed_conflict_result.as_dict())
        self.assertEqual(reversed_conflict_result.diagnostics[0].reason_code, "conflicting-changed-file-identity")
        self.assertEqual(reversed_conflict_provider.requests, [])

        repeated = self.stage_bridge(FakeProvider(_response(_entry("graphify:m1", "src/a.py", "module.Alpha"))))
        one = repeated.resolve(_request(files=(ChangedFileReference("graphify:m1", "src/a.py"),)))
        two = repeated.resolve(_request(files=(ChangedFileReference("graphify:m1", "src/a.py"),)))
        self.assertEqual(one, two)

    def test_zero_multiple_and_invalid_provider_results_never_create_locators(self):
        cases = (
            (_response(_entry("graphify:m1", "src/a.py")), ResolutionStatus.UNRESOLVED, "no-symbol"),
            (_response(_entry("graphify:m1", "src/a.py", "a.One", "a.Two")), ResolutionStatus.AMBIGUOUS, "multiple-symbols"),
            (_response(_entry("graphify:m1", "src/a.py", "def body(): pass")), ResolutionStatus.INVALID_PROVIDER_RESPONSE, "malformed-symbol"),
            (_response(_entry("graphify:m1", "other.py", "a.One")), ResolutionStatus.INVALID_PROVIDER_RESPONSE, "provider-context-mismatch"),
            (_response(_entry("graphify:m1", "src/a.py", "a.One"), status="unsupported"), ResolutionStatus.INVALID_PROVIDER_RESPONSE, "unsupported-provider-status"),
        )
        for response, status, reason in cases:
            with self.subTest(reason=reason):
                result = self.stage_bridge(FakeProvider(response)).resolve(_request(files=(ChangedFileReference("graphify:m1", "src/a.py"),)))
                self.assertEqual(result.outcomes[0].status, status)
                self.assertIsNone(result.outcomes[0].locator)
                self.assertEqual(result.outcomes[0].diagnostic.reason_code, reason)

        duplicate_provider = FakeProvider(_response(
            _entry("graphify:m1", "src/a.py", "module.One"),
            _entry("graphify:m1", "src/a.py", "module.One"),
        ))
        duplicate_result = self.stage_bridge(duplicate_provider).resolve(
            _request(files=(ChangedFileReference("graphify:m1", "src/a.py"),))
        )
        self.assertEqual(duplicate_result.outcomes[0].status, ResolutionStatus.INVALID_PROVIDER_RESPONSE)
        self.assertEqual(duplicate_result.outcomes[0].diagnostic.reason_code, "duplicate-provider-response")

    def test_malformed_symbol_invalidates_multiple_symbol_response_before_cardinality(self):
        mixed = self.stage_bridge(FakeProvider(_response(
            _entry("graphify:m1", "src/a.py", "module.Valid", "def secret(): pass"),
        ))).resolve(_request(files=(ChangedFileReference("graphify:m1", "src/a.py"),)))
        self.assertEqual(mixed.outcomes[0].status, ResolutionStatus.INVALID_PROVIDER_RESPONSE)
        self.assertEqual(mixed.outcomes[0].diagnostic.reason_code, "malformed-symbol")
        self.assertIsNone(mixed.outcomes[0].locator)
        self.assertNotIn("def secret(): pass", str(mixed.as_dict()))

        all_malformed = self.stage_bridge(FakeProvider(_response(
            _entry("graphify:m1", "src/a.py", "def first(): pass", "return body"),
        ))).resolve(_request(files=(ChangedFileReference("graphify:m1", "src/a.py"),)))
        self.assertEqual(all_malformed.outcomes[0].status, ResolutionStatus.INVALID_PROVIDER_RESPONSE)
        self.assertEqual(all_malformed.outcomes[0].diagnostic.reason_code, "malformed-symbol")
        self.assertIsNone(all_malformed.outcomes[0].locator)

    def test_provider_unavailable_or_malformed_batch_is_explicit_and_payload_free(self):
        unavailable = FakeProvider(error=ProviderUnavailableError("secret provider payload"))
        result = self.stage_bridge(unavailable).resolve(_request())
        self.assertEqual({item.status for item in result.outcomes}, {ResolutionStatus.PROVIDER_UNAVAILABLE})
        self.assertEqual(result.routing.route_kind, "federation-index")
        self.assertNotIn("secret", str(result.as_dict()))

        malformed = FakeProvider({"entries": [], "source_code": "do not retain"})
        malformed_result = self.stage_bridge(malformed).resolve(_request())
        self.assertEqual({item.status for item in malformed_result.outcomes}, {ResolutionStatus.INVALID_PROVIDER_RESPONSE})
        self.assertNotIn("source_code", str(malformed_result.as_dict()))

        mixed = self.stage_bridge(FakeProvider(_response(
            _entry("graphify:m1", "src/a.py", "module.Alpha"),
            _entry("graphify:m2", "src/b.py", status="unavailable"),
        ))).resolve(_request())
        self.assertEqual(
            [item.status for item in mixed.outcomes],
            [ResolutionStatus.RESOLVED, ResolutionStatus.PROVIDER_UNAVAILABLE],
        )
        self.assertEqual(
            mixed.outcomes[0].locator,
            CodeLocator("payment-service", REVISION, "src/a.py", "module.Alpha"),
        )
        self.assertEqual(mixed.outcomes[1].diagnostic.reason_code, "provider-unavailable")

    def test_navigation_revalidates_route_without_invoking_provider(self):
        provider = FakeProvider(_response())
        bridge = self.stage_bridge(provider)
        locator = CodeLocator("payment-service", REVISION, "src/a.py", "module.Alpha")
        handoff = bridge.build_navigation_handoff(locator, ImplementationEvidenceContext("evidence:pr-1", "payment-service", REVISION))
        self.assertEqual(handoff.status, "ready")
        self.assertEqual(handoff.handoff.as_dict(), {"locator": locator.as_dict(), "routing": {"reference": ".openlore/index", "route_kind": "federation-index"}})
        self.assertEqual(provider.requests, [])

        invalid = bridge.build_navigation_handoff(CodeLocator("payment-service", "main", "src/a.py", "module.Alpha"))
        self.assertEqual(invalid.diagnostics[0].reason_code, "mutable-revision")
        unknown = bridge.build_navigation_handoff(CodeLocator("unknown", REVISION, "src/a.py", "module.Alpha"))
        self.assertEqual(unknown.diagnostics[0].reason_code, "unknown-repository")

        fallback_provider = FakeProvider(_response())
        fallback = self.fallback_bridge(fallback_provider)
        fallback_locator = CodeLocator("workflow-config", REVISION, "config/a.yaml", "config.load")
        fallback_handoff = fallback.build_navigation_handoff(fallback_locator)
        self.assertEqual(fallback_handoff.handoff.routing.route_kind, "repository-index-path")
        self.assertEqual(fallback_provider.requests, [])

    def test_navigation_handoff_rejects_missing_federation_index_without_provider_call(self):
        missing_index_provider = FakeProvider()
        missing_index_registry = load_workspace_registry(FIXTURES / "repo-index-openlore-missing-index.yaml")
        missing_index_bridge = OpenLoreSemanticBridge(missing_index_registry, missing_index_provider)
        missing_index_handoff = missing_index_bridge.build_navigation_handoff(
            CodeLocator("payment-service", REVISION, "src/a.py", "module.Alpha")
        )
        self.assertEqual(missing_index_handoff.status, "invalid-context")
        self.assertEqual(missing_index_handoff.diagnostics[0].reason_code, "missing-federation-index")
        self.assertIsNone(missing_index_handoff.handoff)
        self.assertEqual(missing_index_provider.requests, [])

    def test_unsafe_federation_route_is_rejected_before_resolution_and_navigation(self):
        registry = load_workspace_registry(FIXTURES / "repo-index-openlore-stage.yaml")
        repository = next(item for item in registry.repositories if item.id == "payment-service")
        unsafe_route = "https://user:secret@example.test/.openlore/index"
        unsafe_repository = replace(
            repository,
            openlore=replace(repository.openlore, index_location=unsafe_route),
        )
        unsafe_registry = replace(
            registry,
            repositories=tuple(
                unsafe_repository if item.id == repository.id else item
                for item in registry.repositories
            ),
        )
        provider = FakeProvider(_response(_entry("graphify:m1", "src/a.py", "module.Alpha")))
        bridge = OpenLoreSemanticBridge(unsafe_registry, provider)

        result = bridge.resolve(_request(files=(ChangedFileReference("graphify:m1", "src/a.py"),)))
        self.assertEqual(result.status, "invalid-context")
        self.assertEqual(result.diagnostics[-1].reason_code, "invalid-request")
        self.assertEqual(provider.requests, [])
        self.assertNotIn(unsafe_route, str(result.as_dict()))

        handoff = bridge.build_navigation_handoff(CodeLocator("payment-service", REVISION, "src/a.py", "module.Alpha"))
        self.assertEqual(handoff.status, "invalid-context")
        self.assertEqual(handoff.diagnostics[0].reason_code, "invalid-request")
        self.assertIsNone(handoff.handoff)
        self.assertNotIn(unsafe_route, str(handoff.as_dict()))

    def test_structural_payload_and_credential_routes_are_rejected_on_both_operations(self):
        registry = load_workspace_registry(FIXTURES / "repo-index-openlore-stage.yaml")
        repository = next(item for item in registry.repositories if item.id == "payment-service")
        unsafe_routes = (
            "Authorization: Bearer example",
            "Authorization:apikey-secret",
            "key=secret",
            "key=",
            "${TOKEN}/index",
            "#{name}",
            "<token>",
            "../workspace/index",
            "index\x00cache",
            "def secret(): pass",
            "return body",
            "result = compute(value)",
            "print(secret_value)",
            "Bearersecret",
            "Basicsecret",
            r"\\host\share\index",
            r"\\?\UNC\host\share\index",
            "git@host.example:index",
        )
        for unsafe_route in unsafe_routes:
            with self.subTest(route=unsafe_route):
                unsafe_repository = replace(
                    repository,
                    openlore=replace(repository.openlore, index_location=unsafe_route),
                )
                unsafe_registry = replace(
                    registry,
                    repositories=tuple(
                        unsafe_repository if item.id == repository.id else item
                        for item in registry.repositories
                    ),
                )
                provider = FakeProvider(_response(_entry("graphify:m1", "src/a.py", "module.Alpha")))
                bridge = OpenLoreSemanticBridge(unsafe_registry, provider)
                result = bridge.resolve(_request(files=(ChangedFileReference("graphify:m1", "src/a.py"),)))
                self.assertEqual(result.status, "invalid-context")
                self.assertEqual(result.diagnostics[-1].reason_code, "invalid-request")
                self.assertEqual(provider.requests, [])
                self.assertNotIn(unsafe_route, str(result.as_dict()))

                handoff = bridge.build_navigation_handoff(
                    CodeLocator("payment-service", REVISION, "src/a.py", "module.Alpha")
                )
                self.assertEqual(handoff.status, "invalid-context")
                self.assertEqual(handoff.diagnostics[0].reason_code, "invalid-request")
                self.assertIsNone(handoff.handoff)
                self.assertNotIn(unsafe_route, str(handoff.as_dict()))

    def test_structural_predicate_admits_word_bearing_and_colon_named_routes(self):
        registry = load_workspace_registry(FIXTURES / "repo-index-openlore-stage.yaml")
        repository = next(item for item in registry.repositories if item.id == "payment-service")
        federation_route = ".openlore/def:cache/source-code-cache/token-service"
        federation_registry = replace(
            registry,
            repositories=tuple(
                replace(repository, openlore=replace(repository.openlore, index_location=federation_route))
                if item.id == repository.id else item
                for item in registry.repositories
            ),
        )
        provider = FakeProvider(_response(_entry("graphify:m1", "src/a.py", "module.Alpha")))
        resolved = OpenLoreSemanticBridge(federation_registry, provider).resolve(
            _request(files=(ChangedFileReference("graphify:m1", "src/a.py"),))
        )
        self.assertEqual(resolved.status, "admitted")
        self.assertEqual(resolved.routing.reference, federation_route)
        self.assertEqual(len(provider.requests), 1)

        fallback_route = "/workspace/def:cache/source-code-cache/secret-token"
        fallback_registry = replace(
            registry,
            repositories=tuple(
                replace(item, resolved_path=Path(fallback_route)) if item.id == "workflow-config" else item
                for item in registry.repositories
            ),
        )
        fallback_bridge = OpenLoreSemanticBridge(fallback_registry, FakeProvider())
        handoff = fallback_bridge.build_navigation_handoff(
            CodeLocator("workflow-config", REVISION, "config/a.yaml", "config.load")
        )
        self.assertEqual(handoff.status, "ready")
        self.assertEqual(handoff.handoff.routing.reference, fallback_route)

    def test_structured_routing_payload_roots_are_rejected_on_resolution_and_navigation(self):
        registry = load_workspace_registry(FIXTURES / "repo-index-openlore-stage.yaml")
        repository = next(item for item in registry.repositories if item.id == "payment-service")
        for unsafe_route in ('{"token":"secret"}', '[{"secret":"x"}]', "key: value"):
            with self.subTest(route=unsafe_route):
                unsafe_repository = replace(
                    repository,
                    openlore=replace(repository.openlore, index_location=unsafe_route),
                )
                unsafe_registry = replace(
                    registry,
                    repositories=tuple(
                        unsafe_repository if item.id == repository.id else item
                        for item in registry.repositories
                    ),
                )
                provider = FakeProvider(_response(_entry("graphify:m1", "src/a.py", "module.Alpha")))
                bridge = OpenLoreSemanticBridge(unsafe_registry, provider)

                result = bridge.resolve(_request(files=(ChangedFileReference("graphify:m1", "src/a.py"),)))
                self.assertEqual(result.status, "invalid-context")
                self.assertEqual(result.diagnostics[-1].reason_code, "invalid-request")
                self.assertEqual(provider.requests, [])
                self.assertNotIn(unsafe_route, str(result.as_dict()))

                handoff = bridge.build_navigation_handoff(
                    CodeLocator("payment-service", REVISION, "src/a.py", "module.Alpha")
                )
                self.assertEqual(handoff.status, "invalid-context")
                self.assertEqual(handoff.diagnostics[0].reason_code, "invalid-request")
                self.assertIsNone(handoff.handoff)
                self.assertNotIn(unsafe_route, str(handoff.as_dict()))

    def test_brace_and_bracket_filename_punctuation_routes_remain_admitted(self):
        registry = load_workspace_registry(FIXTURES / "repo-index-openlore-stage.yaml")
        repository = next(item for item in registry.repositories if item.id == "payment-service")
        for route in ("data[@2024]", "{cache}"):
            with self.subTest(route=route):
                routed_repository = replace(
                    repository,
                    openlore=replace(repository.openlore, index_location=route),
                )
                routed_registry = replace(
                    registry,
                    repositories=tuple(
                        routed_repository if item.id == repository.id else item
                        for item in registry.repositories
                    ),
                )
                provider = FakeProvider(_response(_entry("graphify:m1", "src/a.py", "module.Alpha")))
                bridge = OpenLoreSemanticBridge(routed_registry, provider)
                request = _request(files=(ChangedFileReference("graphify:m1", "src/a.py"),))
                result = bridge.resolve(request)
                self.assertEqual(result.status, "admitted")
                self.assertEqual(result.routing.reference, route)
                self.assertEqual(len(provider.requests), 1)

                handoff = bridge.build_navigation_handoff(
                    CodeLocator("payment-service", REVISION, "src/a.py", "module.Alpha")
                )
                self.assertEqual(handoff.status, "ready")
                self.assertEqual(handoff.handoff.routing.reference, route)

    def test_nested_source_and_call_route_components_are_rejected_on_both_operations(self):
        base_registry = load_workspace_registry(FIXTURES / "repo-index-openlore-stage.yaml")
        payment_repository = next(item for item in base_registry.repositories if item.id == "payment-service")
        unsafe_routes = (
            ("payment-service", ".openlore/print(secret_value)/index"),
            ("payment-service", ".openlore/return body/index"),
            ("payment-service", ".openlore/def secret(): pass/index"),
            ("workflow-config", "/workspace/print(secret_value)/index"),
            ("workflow-config", "/workspace/return body/index"),
            ("workflow-config", "/workspace/def secret(): pass/index"),
        )
        for repository, unsafe_route in unsafe_routes:
            with self.subTest(route=unsafe_route):
                if repository == "payment-service":
                    routed_registry = replace(
                        base_registry,
                        repositories=tuple(
                            replace(
                                payment_repository,
                                openlore=replace(
                                    payment_repository.openlore,
                                    index_location=unsafe_route,
                                ),
                            )
                            if item.id == payment_repository.id else item
                            for item in base_registry.repositories
                        ),
                    )
                else:
                    routed_registry = replace(
                        base_registry,
                        repositories=tuple(
                            replace(item, resolved_path=Path(unsafe_route))
                            if item.id == repository else item
                            for item in base_registry.repositories
                        ),
                    )

                provider = FakeProvider(
                    _response(
                        _entry(
                            "graphify:m1",
                            "src/a.py",
                            "module.Alpha",
                            repository=repository,
                        )
                    )
                )
                bridge = OpenLoreSemanticBridge(routed_registry, provider)
                request = _request(
                    repository,
                    files=(ChangedFileReference("graphify:m1", "src/a.py"),),
                )
                result = bridge.resolve(request)
                self.assertEqual(result.status, "invalid-context")
                self.assertEqual(result.diagnostics[-1].reason_code, "invalid-request")
                self.assertEqual(provider.requests, [])
                self.assertNotIn(unsafe_route, str(result.as_dict()))

                handoff = bridge.build_navigation_handoff(
                    CodeLocator(repository, REVISION, "src/a.py", "module.Alpha")
                )
                self.assertEqual(handoff.status, "invalid-context")
                self.assertEqual(handoff.diagnostics[0].reason_code, "invalid-request")
                self.assertIsNone(handoff.handoff)
                self.assertEqual(provider.requests, [])
                self.assertNotIn(unsafe_route, str(handoff.as_dict()))

    def test_zero_argument_call_components_are_rejected_on_both_routes_and_operations(self):
        base_registry = load_workspace_registry(FIXTURES / "repo-index-openlore-stage.yaml")
        payment_repository = next(item for item in base_registry.repositories if item.id == "payment-service")
        routes = (
            ("payment-service", "reset()"),
            ("payment-service", ".openlore/reset()/index"),
            ("payment-service", ".openlore/foo()/index"),
            ("payment-service", ".openlore/bar ()/index"),
            ("workflow-config", "/workspace/reset()"),
            ("workflow-config", "/workspace/reset()/index"),
        )
        for repository, unsafe_route in routes:
            with self.subTest(route=unsafe_route):
                if repository == "payment-service":
                    routed_registry = replace(
                        base_registry,
                        repositories=tuple(
                            replace(
                                payment_repository,
                                openlore=replace(
                                    payment_repository.openlore,
                                    index_location=unsafe_route,
                                ),
                            )
                            if item.id == payment_repository.id else item
                            for item in base_registry.repositories
                        ),
                    )
                else:
                    routed_registry = replace(
                        base_registry,
                        repositories=tuple(
                            replace(item, resolved_path=Path(unsafe_route))
                            if item.id == repository else item
                            for item in base_registry.repositories
                        ),
                    )

                provider = FakeProvider(
                    _response(
                        _entry(
                            "graphify:m1",
                            "src/a.py",
                            "module.Alpha",
                            repository=repository,
                        )
                    )
                )
                bridge = OpenLoreSemanticBridge(routed_registry, provider)
                result = bridge.resolve(
                    _request(
                        repository,
                        files=(ChangedFileReference("graphify:m1", "src/a.py"),),
                    )
                )
                self.assertEqual(result.status, "invalid-context")
                self.assertEqual(result.diagnostics[-1].reason_code, "invalid-request")
                self.assertEqual(provider.requests, [])
                self.assertNotIn(unsafe_route, str(result.as_dict()))

                handoff = bridge.build_navigation_handoff(
                    CodeLocator(repository, REVISION, "src/a.py", "module.Alpha")
                )
                self.assertEqual(handoff.status, "invalid-context")
                self.assertEqual(handoff.diagnostics[0].reason_code, "invalid-request")
                self.assertIsNone(handoff.handoff)
                self.assertEqual(provider.requests, [])
                self.assertNotIn(unsafe_route, str(handoff.as_dict()))

    def test_call_shape_predicate_does_not_reject_word_bearing_components(self):
        base_registry = load_workspace_registry(FIXTURES / "repo-index-openlore-stage.yaml")
        payment_repository = next(item for item in base_registry.repositories if item.id == "payment-service")
        routes = (
            ("payment-service", ".openlore/reset-cache/index"),
            ("workflow-config", "/workspace/cache/reset/print-cache"),
            ("payment-service", ".openlore/record(1)/index"),
            ("workflow-config", "/workspace/cache/record(1)"),
        )
        for repository, route in routes:
            with self.subTest(route=route):
                if repository == "payment-service":
                    routed_registry = replace(
                        base_registry,
                        repositories=tuple(
                            replace(
                                payment_repository,
                                openlore=replace(payment_repository.openlore, index_location=route),
                            )
                            if item.id == payment_repository.id else item
                            for item in base_registry.repositories
                        ),
                    )
                else:
                    routed_registry = replace(
                        base_registry,
                        repositories=tuple(
                            replace(item, resolved_path=Path(route))
                            if item.id == repository else item
                            for item in base_registry.repositories
                        ),
                    )

                provider = FakeProvider(
                    _response(
                        _entry(
                            "graphify:m1",
                            "src/a.py",
                            "module.Alpha",
                            repository=repository,
                        )
                    )
                )
                bridge = OpenLoreSemanticBridge(routed_registry, provider)
                result = bridge.resolve(
                    _request(
                        repository,
                        files=(ChangedFileReference("graphify:m1", "src/a.py"),),
                    )
                )
                self.assertEqual(result.status, "admitted")
                self.assertEqual(result.routing.reference, route)
                self.assertEqual(len(provider.requests), 1)

                handoff = bridge.build_navigation_handoff(
                    CodeLocator(repository, REVISION, "src/a.py", "module.Alpha")
                )
                self.assertEqual(handoff.status, "ready")
                self.assertEqual(handoff.handoff.routing.reference, route)
                self.assertEqual(len(provider.requests), 1)

    def test_nested_and_multi_statement_call_routes_are_rejected_before_bridge_boundary(self):
        base_registry = load_workspace_registry(FIXTURES / "repo-index-openlore-stage.yaml")
        payment_repository = next(item for item in base_registry.repositories if item.id == "payment-service")
        unsafe_routes = (
            ("payment-service", ".openlore/outer(inner())/index"),
            ("payment-service", ".openlore/a(b(c))/index"),
            ("payment-service", ".openlore/f(x, g(y))/index"),
            ("payment-service", ".openlore/foo(bar)/index"),
            ("payment-service", "reset(); shutdown()"),
            ("payment-service", ".openlore/a(); b()/index"),
            ("workflow-config", "/workspace/outer(inner())"),
            ("workflow-config", "/workspace/a(b(c))"),
            ("workflow-config", "/workspace/f(x, g(y))"),
            ("workflow-config", "/workspace/foo(bar)"),
            ("workflow-config", "/workspace/reset(); shutdown()"),
            ("workflow-config", "/workspace/a(); b()"),
        )
        for repository, unsafe_route in unsafe_routes:
            with self.subTest(route=unsafe_route):
                if repository == "payment-service":
                    routed_registry = replace(
                        base_registry,
                        repositories=tuple(
                            replace(
                                payment_repository,
                                openlore=replace(
                                    payment_repository.openlore,
                                    index_location=unsafe_route,
                                ),
                            )
                            if item.id == payment_repository.id else item
                            for item in base_registry.repositories
                        ),
                    )
                else:
                    routed_registry = replace(
                        base_registry,
                        repositories=tuple(
                            replace(item, resolved_path=Path(unsafe_route))
                            if item.id == repository else item
                            for item in base_registry.repositories
                        ),
                    )

                provider = FakeProvider(
                    _response(
                        _entry(
                            "graphify:m1",
                            "src/a.py",
                            "module.Alpha",
                            repository=repository,
                        )
                    )
                )
                bridge = OpenLoreSemanticBridge(routed_registry, provider)
                request = _request(
                    repository,
                    files=(ChangedFileReference("graphify:m1", "src/a.py"),),
                )

                result = bridge.resolve(request)
                self.assertEqual(result.status, "invalid-context")
                self.assertEqual(result.diagnostics[-1].reason_code, "invalid-request")
                self.assertEqual(provider.requests, [])
                self.assertNotIn(unsafe_route, str(result.as_dict()))

                handoff = bridge.build_navigation_handoff(
                    CodeLocator(repository, REVISION, "src/a.py", "module.Alpha")
                )
                self.assertEqual(handoff.status, "invalid-context")
                self.assertEqual(handoff.diagnostics[0].reason_code, "invalid-request")
                self.assertIsNone(handoff.handoff)
                self.assertEqual(provider.requests, [])
                self.assertNotIn(unsafe_route, str(handoff.as_dict()))

    def test_word_bearing_route_components_remain_admitted_on_both_operations(self):
        base_registry = load_workspace_registry(FIXTURES / "repo-index-openlore-stage.yaml")
        payment_repository = next(item for item in base_registry.repositories if item.id == "payment-service")
        routes = (
            ("payment-service", ".openlore/def:cache/source-code-cache/token-service/print-cache"),
            ("workflow-config", "/workspace/cache/print/def:cache/data[@2024]"),
        )
        for repository, route in routes:
            with self.subTest(route=route):
                if repository == "payment-service":
                    routed_registry = replace(
                        base_registry,
                        repositories=tuple(
                            replace(
                                payment_repository,
                                openlore=replace(payment_repository.openlore, index_location=route),
                            )
                            if item.id == payment_repository.id else item
                            for item in base_registry.repositories
                        ),
                    )
                else:
                    routed_registry = replace(
                        base_registry,
                        repositories=tuple(
                            replace(item, resolved_path=Path(route))
                            if item.id == repository else item
                            for item in base_registry.repositories
                        ),
                    )

                provider = FakeProvider(
                    _response(
                        _entry(
                            "graphify:m1",
                            "src/a.py",
                            "module.Alpha",
                            repository=repository,
                        )
                    )
                )
                bridge = OpenLoreSemanticBridge(routed_registry, provider)
                request = _request(
                    repository,
                    files=(ChangedFileReference("graphify:m1", "src/a.py"),),
                )
                result = bridge.resolve(request)
                self.assertEqual(result.status, "admitted")
                self.assertEqual(result.routing.reference, route)
                self.assertEqual(len(provider.requests), 1)

                handoff = bridge.build_navigation_handoff(
                    CodeLocator(repository, REVISION, "src/a.py", "module.Alpha")
                )
                self.assertEqual(handoff.status, "ready")
                self.assertEqual(handoff.handoff.routing.reference, route)
                self.assertEqual(len(provider.requests), 1)

    def test_provider_request_validates_all_fields_before_serialization(self):
        routing = RoutingReference("repository-index-path", ".openlore/index")
        changed_file = ChangedFileReference("graphify:m1", "src/a.py")

        for repository in ("def leaked(): pass", "https://example.test/repository"):
            with self.subTest(repository=repository), self.assertRaises(BridgeValidationError):
                ProviderResolutionRequest(repository, REVISION, routing, (changed_file,))
        for revision in ("main", "a" * 7, "revision payload"):
            with self.subTest(revision=revision), self.assertRaises(BridgeValidationError):
                ProviderResolutionRequest("payment-service", revision, routing, (changed_file,))
        for changed_files in ((), (object(),), ({"file": "src/a.py"},)):
            with self.subTest(changed_files=changed_files), self.assertRaises(BridgeValidationError):
                ProviderResolutionRequest("payment-service", REVISION, routing, changed_files)
        with self.assertRaises(BridgeValidationError):
            ProviderResolutionRequest(
                "payment-service",
                REVISION,
                routing,
                (ChangedFileReference("def leaked(): pass", "src/a.py"),),
            )

        request = ProviderResolutionRequest("payment-service", REVISION, routing, (changed_file,))
        self.assertEqual(
            request.as_dict(),
            {
                "changed_files": [{"file": "src/a.py", "stable_file_id": "graphify:m1"}],
                "repository": "payment-service",
                "revision": REVISION,
                "routing": routing.as_dict(),
            },
        )

    def test_routing_reference_rejects_unsafe_values_at_construction(self):
        for route_kind in ("federation-index", "repository-index-path"):
            for reference in (
                "https://user:secret@example.test/index",
                "../secrets",
                "index\ncache",
                "def secret(): pass",
            ):
                with self.subTest(route_kind=route_kind, reference=reference), self.assertRaises(BridgeValidationError):
                    RoutingReference(route_kind, reference)

    def test_routing_reference_rejects_credentials_and_source_shaped_values(self):
        unsafe_references = (
            "Authorization: Bearer example",
            "Bearer example",
            "<token>",
            "password=example",
            "secret payload",
            "result = compute(value)",
            "return body",
        )
        serialized = []
        for reference in unsafe_references:
            with self.subTest(reference=reference), self.assertRaises(BridgeValidationError):
                serialized.append(RoutingReference("repository-index-path", reference).as_dict())
        self.assertEqual(serialized, [])

    def test_public_result_dtos_reject_unsafe_direct_construction(self):
        with self.assertRaises(BridgeValidationError):
            BridgeDiagnostic("no-symbol", "def secret(): pass")
        with self.assertRaises(BridgeValidationError):
            ChangedFileResolutionOutcome("graphify:m1", "src/a.py", "not-a-status")
        with self.assertRaises(BridgeValidationError):
            ChangedFileResolutionOutcome(
                "graphify:m1",
                "src/a.py",
                ResolutionStatus.RESOLVED,
                locator=CodeLocator("payment-service", REVISION, "../secret.py", "module.Valid"),
            )
        with self.assertRaises(BridgeValidationError):
            ChangedFileResolutionOutcome(
                "graphify:m1",
                "src/a.py",
                ResolutionStatus.RESOLVED,
                diagnostic="unsafe-diagnostic",
            )
        with self.assertRaises(BridgeValidationError):
            ResolutionResult("request", "admitted", None, ("unsafe-outcome",))
        with self.assertRaises(BridgeValidationError):
            NavigationHandoff(
                CodeLocator("payment-service", REVISION, "src/a.py", "def secret(): pass"),
                RoutingReference("repository-index-path", ".openlore/index"),
            )
        with self.assertRaises(BridgeValidationError):
            NavigationHandoffResult("ready", handoff="unsafe-handoff")
        with self.assertRaises(BridgeValidationError):
            NavigationHandoffResult("ready", diagnostics=("unsafe-diagnostic",))

    def test_public_result_dtos_enforce_status_payload_invariants(self):
        locator = CodeLocator("payment-service", REVISION, "src/a.py", "module.Alpha")
        non_resolved_statuses = (
            ResolutionStatus.UNRESOLVED,
            ResolutionStatus.AMBIGUOUS,
            ResolutionStatus.PROVIDER_UNAVAILABLE,
            ResolutionStatus.INVALID_PROVIDER_RESPONSE,
            ResolutionStatus.INVALID_CONTEXT,
        )
        for status in non_resolved_statuses:
            with self.subTest(status=status):
                with self.assertRaises(BridgeValidationError):
                    ChangedFileResolutionOutcome("graphify:m1", "src/a.py", status, locator=locator)
        with self.assertRaises(BridgeValidationError):
            ChangedFileResolutionOutcome("graphify:m1", "src/a.py", ResolutionStatus.RESOLVED)

        routing = RoutingReference("repository-index-path", ".openlore/index")
        handoff = NavigationHandoff(locator, routing)
        with self.assertRaises(BridgeValidationError):
            ResolutionResult("request", "invalid-context", routing, ())
        with self.assertRaises(BridgeValidationError):
            ResolutionResult("request", "admitted", None, ())
        with self.assertRaises(BridgeValidationError):
            NavigationHandoffResult("invalid-context", handoff)
        with self.assertRaises(BridgeValidationError):
            NavigationHandoffResult("ready")

        resolved = ChangedFileResolutionOutcome("graphify:m1", "src/a.py", ResolutionStatus.RESOLVED, locator=locator)
        self.assertEqual(resolved.as_dict()["locator"], locator.as_dict())
        admitted = ResolutionResult("request", "admitted", routing, (resolved,))
        self.assertEqual(admitted.as_dict()["routing"], routing.as_dict())
        ready = NavigationHandoffResult("ready", handoff)
        self.assertEqual(ready.as_dict()["handoff"], handoff.as_dict())

    def test_unhashable_provider_file_status_is_invalid_without_serialization(self):
        for status in ([], {}):
            with self.subTest(status=status):
                response = _response(_entry("graphify:m1", "src/a.py", status=status))
                result = self.stage_bridge(FakeProvider(response)).resolve(
                    _request(files=(ChangedFileReference("graphify:m1", "src/a.py"),))
                )
                self.assertEqual(result.outcomes[0].status, ResolutionStatus.INVALID_PROVIDER_RESPONSE)
                self.assertIsNone(result.outcomes[0].locator)
                self.assertEqual(result.outcomes[0].diagnostic.reason_code, "malformed-provider-response")
                self.assertNotIn(repr(status), repr(result.as_dict()))

    def test_adapter_preserves_mapping_identity_but_only_resolved_outcomes_can_emit_candidates(self):
        provider = FakeProvider(_response(
            _entry("graphify:m1", "src/a.py", "module.Alpha"),
            _entry("graphify:m2", "src/b.py"),
            _entry("graphify:m3", "src/c.py", "module.One", "module.Two"),
            _entry("graphify:m4", "src/d.py", "def body(): pass"),
        ))
        result = self.stage_bridge(provider).resolve(_request(files=(
            ChangedFileReference("graphify:m1", "src/a.py"),
            ChangedFileReference("graphify:m2", "src/b.py"),
            ChangedFileReference("graphify:m3", "src/c.py"),
            ChangedFileReference("graphify:m4", "src/d.py"),
        )))
        mappings = adapt_resolution_to_changed_symbol_mappings(result)
        self.assertEqual([item.id for item in mappings], ["graphify:m1", "graphify:m2", "graphify:m3", "graphify:m4"])
        self.assertEqual(mappings[-1].outcome, MappingOutcome.UNSUPPORTED)
        subject = Node("story-1", NodeKind.JIRA_STORY, "EKG-1")
        repository = Node("payment-service", NodeKind.REPOSITORY, "payment-service")
        raw_mappings = [{
            "id": item.id,
            "file": item.file,
            "outcome": item.outcome.value,
            "symbol": item.symbol,
            "repository": repository.id,
            "revision": REVISION,
        } for item in mappings]
        change_set = normalize_pull_request_evidence({
            "pull_request_id": "pr:1", "repository_node_id": repository.id,
            "base_revision": "a" * 40, "head_revision": REVISION, "merged": True,
            "observed_at": "2026-09-01T12:00:00+00:00", "provenance": {"pr": "complete"},
            "pr_source_reference": "urn:example.org/pr-1",
            "repository_source_reference": "urn:example.org/repository-1",
            "association": {"id": "link:1", "intended_change_id": subject.id,
                             "intended_change_kind": "jira_story",
                             "source_reference": "urn:example.org/link-1"},
            "mappings": raw_mappings,
        })
        extracted = extract_pr_code_candidates((change_set,), GraphSnapshot(nodes=(subject, repository)))
        self.assertEqual(extracted.metadata.emitted_candidate_count, 1)
        self.assertEqual(extracted.graph.cross_graph_link_claims[0].target.symbol, "module.Alpha")
        self.assertEqual(extracted.graph.trusted_cross_graph_links, ())
        self.assertFalse(any(edge.kind == "implements" for edge in extracted.graph.edges))

        failed = self.stage_bridge(FakeProvider(error=ProviderUnavailableError())).resolve(
            _request(files=(ChangedFileReference("graphify:m1", "src/a.py"),))
        )
        failed_mappings = adapt_resolution_to_changed_symbol_mappings(failed)
        failed_set = normalize_pull_request_evidence({
            "pull_request_id": "pr:2", "repository_node_id": repository.id,
            "base_revision": "a" * 40, "head_revision": REVISION, "merged": True,
            "observed_at": "2026-09-01T12:00:00+00:00", "provenance": {"pr": "complete"},
            "pr_source_reference": "urn:example.org/pr-2",
            "repository_source_reference": "urn:example.org/repository-2",
            "association": {"id": "link:2", "intended_change_id": subject.id,
                             "intended_change_kind": "jira_story",
                             "source_reference": "urn:example.org/link-2"},
            "mappings": [{"id": item.id, "file": item.file, "outcome": item.outcome.value}
                         for item in failed_mappings],
        })
        failed_extracted = extract_pr_code_candidates((failed_set,), GraphSnapshot(nodes=(subject, repository)))
        self.assertEqual(failed_extracted.metadata.emitted_candidate_count, 0)

    def test_bridge_is_ephemeral_and_serializers_are_allowlisted(self):
        provider = FakeProvider(_response(_entry("graphify:m1", "src/a.py", "module.Alpha")))
        bridge = self.stage_bridge(provider)
        snapshot = GraphSnapshot(nodes=(Node("story-1", NodeKind.JIRA_STORY, "EKG-1"),))
        baseline_state = snapshot.as_dict()

        with patch("engineering_kg.ontology.GraphSnapshot", wraps=GraphSnapshot) as snapshot_factory, \
             patch("engineering_kg.persistence.persist_graph_snapshot") as persist_writer, \
             patch("engineering_kg.persistence.read_graph_snapshot") as persistence_reader, \
             patch("engineering_kg.derivation.derive_graph_relationships") as derivation_writer, \
             patch("engineering_kg.query.EngineeringKgQuery") as query_api:
            result = bridge.resolve(_request(files=(ChangedFileReference("graphify:m1", "src/a.py"),)))
            handoff = bridge.navigation_handoff(result.outcomes[0].locator)

        self.assertEqual(snapshot.as_dict(), baseline_state)
        self.assertEqual(snapshot_factory.call_count, 0)
        self.assertEqual(persist_writer.call_count, 0)
        self.assertEqual(persistence_reader.call_count, 0)
        self.assertEqual(derivation_writer.call_count, 0)
        self.assertEqual(query_api.call_count, 0)
        self.assertEqual(handoff.status, "ready")
        bridge_source = inspect.getsource(openlore_bridge_module)
        for forbidden_api in (
            "persist_graph_snapshot",
            "read_graph_snapshot",
            "derive_graph_relationships",
            "EngineeringKgQuery",
            "engineering_kg.persistence",
            "engineering_kg.derivation",
            "engineering_kg.query",
        ):
            self.assertNotIn(forbidden_api, bridge_source)
        serialized = str(result.as_dict())
        for forbidden in ("source_code", "call_graph", "navigation_response", "credentials", "tokens", "provider_payload", "source body"):
            self.assertNotIn(forbidden, serialized)
        with self.assertRaises(BridgeValidationError):
            ChangedFileReference("../../payload", "src/a.py")
        with self.assertRaises(BridgeValidationError):
            BridgeDiagnostic("unsafe-provider-payload")


if __name__ == "__main__":
    unittest.main()
