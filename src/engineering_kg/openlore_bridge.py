"""Compact, provider-neutral semantic bridge for OpenLore.

The bridge owns only repository/revision/file/symbol identities, routing
references, statuses, and reason codes.  It deliberately has no transport,
credential, index, source-body, or OpenLore graph dependency.  An integration
implements :class:`OpenLoreProvider` and translates its own wire format at
that boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Sequence

from engineering_kg.compact_identity import (
    is_complete_symbol_identity,
    is_immutable_revision,
    require_immutable_revision,
    safe_identity,
    safe_relative_file,
    safe_repository,
    safe_routing_reference,
)
from engineering_kg.ingest.pr_code_candidates import ChangedSymbolMapping, MappingOutcome
from engineering_kg.ontology import CodeLocator, stable_id
from engineering_kg.project import WorkspaceRegistry


class BridgeValidationError(ValueError):
    """A compact bridge DTO could not be constructed safely."""


class ProviderUnavailableError(RuntimeError):
    """A provider port could not service a resolution request."""


class ResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"
    PROVIDER_UNAVAILABLE = "provider-unavailable"
    INVALID_PROVIDER_RESPONSE = "invalid-provider-response"
    INVALID_CONTEXT = "invalid-context"


class ProviderResponseStatus(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"


FROZEN_BRIDGE_DIAGNOSTIC_REASONS = frozenset(
    {
        "invalid-request",
        "unknown-repository",
        "missing-federation-index",
        "mutable-revision",
        "evidence-repository-mismatch",
        "evidence-revision-mismatch",
        "conflicting-changed-file-identity",
        "provider-unavailable",
        "incomplete-locator",
        "invalid-locator",
        "incomplete-symbol",
        "invalid-evidence",
        "malformed-provider-response",
        "unsupported-provider-status",
        "provider-context-mismatch",
        "duplicate-provider-response",
        "no-symbol",
        "multiple-symbols",
        "malformed-symbol",
    }
)


def _safe(value: object, field_name: str, validator) -> str:
    try:
        return validator(value, field_name)
    except ValueError as exc:
        raise BridgeValidationError(str(exc)) from None


def _validated_locator(locator: object, field_name: str) -> CodeLocator:
    """Return a normalized, bridge-safe complete locator for public DTOs."""

    if not isinstance(locator, CodeLocator):
        raise BridgeValidationError(f"{field_name} must be CodeLocator")
    try:
        repository = safe_repository(locator.repository, f"{field_name}.repository")
        revision = safe_identity(locator.revision, f"{field_name}.revision")
        file = safe_relative_file(locator.file, f"{field_name}.file")
    except ValueError as exc:
        raise BridgeValidationError(str(exc)) from None
    if not is_immutable_revision(revision):
        raise BridgeValidationError(f"{field_name}.revision must be immutable")
    if not is_complete_symbol_identity(locator.symbol):
        raise BridgeValidationError(f"{field_name}.symbol must be a complete symbol identity")
    return CodeLocator(repository, revision, file, locator.symbol)


@dataclass(frozen=True)
class ChangedFileReference:
    """A stable changed-file identity and repository-relative path."""

    stable_file_id: str
    file: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "stable_file_id", _safe(self.stable_file_id, "changed_file.stable_file_id", safe_identity))
        object.__setattr__(self, "file", _safe(self.file, "changed_file.file", safe_relative_file))

    @property
    def id(self) -> str:
        """Short alias useful to provider adapters."""

        return self.stable_file_id

    def as_dict(self) -> dict[str, str]:
        return {"file": self.file, "stable_file_id": self.stable_file_id}


@dataclass(frozen=True)
class ImplementationEvidenceContext:
    """The compact evidence identity to which a bridge request is bound."""

    evidence_id: str
    repository: str
    revision: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", _safe(self.evidence_id, "evidence_id", safe_identity))
        object.__setattr__(self, "repository", _safe(self.repository, "evidence.repository", safe_repository))
        object.__setattr__(self, "revision", _safe(self.revision, "evidence.revision", safe_identity))

    def as_dict(self) -> dict[str, str]:
        return {
            "evidence_id": self.evidence_id,
            "repository": self.repository,
            "revision": self.revision,
        }

    @property
    def implementation_evidence_id(self) -> str:
        return self.evidence_id


@dataclass(frozen=True)
class ChangedFileResolutionRequest:
    """A payload-free, evidence-bound batch resolution request."""

    evidence: ImplementationEvidenceContext
    repository: str
    revision: str
    changed_files: tuple[ChangedFileReference, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.evidence, ImplementationEvidenceContext):
            raise BridgeValidationError("request.evidence must be ImplementationEvidenceContext")
        object.__setattr__(self, "repository", _safe(self.repository, "request.repository", safe_repository))
        object.__setattr__(self, "revision", _safe(self.revision, "request.revision", safe_identity))
        if not isinstance(self.changed_files, (tuple, list)) or not self.changed_files:
            raise BridgeValidationError("request.changed_files must be a non-empty sequence")
        files = tuple(self.changed_files)
        if not all(isinstance(item, ChangedFileReference) for item in files):
            raise BridgeValidationError("request.changed_files must contain ChangedFileReference records")
        object.__setattr__(self, "changed_files", files)

    @property
    def id(self) -> str:
        return stable_id("openlore-resolution", self.evidence.evidence_id, self.repository, self.revision)

    @property
    def implementation_evidence(self) -> ImplementationEvidenceContext:
        return self.evidence

    @property
    def files(self) -> tuple[ChangedFileReference, ...]:
        return self.changed_files

    def as_dict(self) -> dict[str, object]:
        return {
            "changed_files": [item.as_dict() for item in self.changed_files],
            "evidence": self.evidence.as_dict(),
            "repository": self.repository,
            "revision": self.revision,
        }


@dataclass(frozen=True)
class RoutingReference:
    """The registry-selected compact route to an OpenLore index."""

    route_kind: str
    reference: str

    def __post_init__(self) -> None:
        if self.route_kind not in {"federation-index", "repository-index-path"}:
            raise BridgeValidationError("routing.route_kind is unsupported")
        try:
            reference = safe_routing_reference(
                self.reference,
                "routing.reference",
                allow_absolute=True,
            )
        except ValueError as exc:
            raise BridgeValidationError(str(exc)) from None
        object.__setattr__(self, "reference", reference)

    @property
    def kind(self) -> str:
        return self.route_kind

    @property
    def value(self) -> str:
        return self.reference

    def as_dict(self) -> dict[str, str]:
        return {"reference": self.reference, "route_kind": self.route_kind}


@dataclass(frozen=True)
class ProviderResolutionRequest:
    """The only request shape exposed to an injected provider port."""

    repository: str
    revision: str
    routing: RoutingReference
    changed_files: tuple[ChangedFileReference, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "repository", _safe(self.repository, "provider.repository", safe_repository))
        object.__setattr__(
            self,
            "revision",
            _safe(self.revision, "provider.revision", require_immutable_revision),
        )
        if not isinstance(self.routing, RoutingReference):
            raise BridgeValidationError("provider.routing must be RoutingReference")
        if not isinstance(self.changed_files, tuple) or not self.changed_files:
            raise BridgeValidationError("provider.changed_files must be a non-empty tuple")
        if not all(isinstance(item, ChangedFileReference) for item in self.changed_files):
            raise BridgeValidationError(
                "provider.changed_files must contain ChangedFileReference records"
            )
        object.__setattr__(
            self,
            "changed_files",
            tuple(ChangedFileReference(item.stable_file_id, item.file) for item in self.changed_files),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "changed_files": [item.as_dict() for item in self.changed_files],
            "repository": self.repository,
            "revision": self.revision,
            "routing": self.routing.as_dict(),
        }


@dataclass(frozen=True)
class ProviderFileResolution:
    """Provider-neutral response for one changed file.

    The bridge validates symbols and context.  Keeping this response DTO
    permissive enough to represent malformed provider output lets the bridge
    classify it without leaking provider exception or payload text.
    """

    stable_file_id: str
    repository: str
    revision: str
    file: str
    symbols: tuple[object, ...] = ()
    status: str = ProviderResponseStatus.OK.value

    def __post_init__(self) -> None:
        if isinstance(self.symbols, list):
            object.__setattr__(self, "symbols", tuple(self.symbols))


@dataclass(frozen=True)
class ProviderResolutionResponse:
    """Provider-neutral batch response accepted by the bridge port."""

    entries: tuple[ProviderFileResolution, ...]
    status: str = ProviderResponseStatus.OK.value

    def __post_init__(self) -> None:
        if isinstance(self.entries, list):
            object.__setattr__(self, "entries", tuple(self.entries))


class OpenLoreProvider(Protocol):
    """Minimal provider port; transport and provider models stay outside EKG."""

    def resolve_symbols(
        self, request: ProviderResolutionRequest
    ) -> ProviderResolutionResponse:
        """Resolve the requested files at exactly the supplied route/revision."""


@dataclass(frozen=True)
class BridgeDiagnostic:
    """A deterministic, payload-safe reason code."""

    reason_code: str
    stable_file_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.reason_code, str) or self.reason_code not in FROZEN_BRIDGE_DIAGNOSTIC_REASONS:
            raise BridgeValidationError("diagnostic.reason_code is unsupported")
        if self.stable_file_id:
            object.__setattr__(
                self,
                "stable_file_id",
                _safe(self.stable_file_id, "diagnostic.stable_file_id", safe_identity),
            )

    def as_dict(self) -> dict[str, str]:
        result = {"reason_code": self.reason_code}
        if self.stable_file_id:
            result["stable_file_id"] = self.stable_file_id
        return result


@dataclass(frozen=True)
class ChangedFileResolutionOutcome:
    """One deterministic result for one changed file."""

    stable_file_id: str
    file: str
    status: ResolutionStatus | str
    locator: CodeLocator | None = None
    diagnostic: BridgeDiagnostic | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "stable_file_id",
            _safe(self.stable_file_id, "outcome.stable_file_id", safe_identity),
        )
        object.__setattr__(self, "file", _safe(self.file, "outcome.file", safe_relative_file))
        try:
            status = ResolutionStatus(self.status)
        except (TypeError, ValueError):
            raise BridgeValidationError("outcome.status is unsupported") from None
        object.__setattr__(self, "status", status)
        if status is ResolutionStatus.RESOLVED and self.locator is None:
            raise BridgeValidationError("resolved outcome requires locator")
        if status is not ResolutionStatus.RESOLVED and self.locator is not None:
            raise BridgeValidationError("non-resolved outcome must not carry locator")
        if self.locator is not None:
            object.__setattr__(self, "locator", _validated_locator(self.locator, "outcome.locator"))
        if self.diagnostic is not None and not isinstance(self.diagnostic, BridgeDiagnostic):
            raise BridgeValidationError("outcome.diagnostic must be BridgeDiagnostic")

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "file": self.file,
            "stable_file_id": self.stable_file_id,
            "status": str(self.status),
        }
        if self.locator is not None:
            result["locator"] = self.locator.as_dict()
        if self.diagnostic is not None:
            result["diagnostic"] = self.diagnostic.as_dict()
        return result


@dataclass(frozen=True)
class ResolutionResult:
    """Ephemeral bridge output; it performs no graph or persistence writes."""

    request_id: str
    status: str
    routing: RoutingReference | None
    outcomes: tuple[ChangedFileResolutionOutcome, ...]
    diagnostics: tuple[BridgeDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _safe(self.request_id, "result.request_id", safe_identity))
        if not isinstance(self.status, str) or self.status not in {"admitted", "invalid-context"}:
            raise BridgeValidationError("result.status is unsupported")
        if self.status == "invalid-context" and self.routing is not None:
            raise BridgeValidationError("invalid-context result must not carry routing")
        if self.status == "admitted" and self.routing is None:
            raise BridgeValidationError("admitted result requires routing")
        if self.routing is not None and not isinstance(self.routing, RoutingReference):
            raise BridgeValidationError("result.routing must be RoutingReference")
        if isinstance(self.outcomes, list):
            object.__setattr__(self, "outcomes", tuple(self.outcomes))
        if not isinstance(self.outcomes, tuple) or not all(
            isinstance(item, ChangedFileResolutionOutcome) for item in self.outcomes
        ):
            raise BridgeValidationError("result.outcomes must contain ChangedFileResolutionOutcome records")
        if isinstance(self.diagnostics, list):
            object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if not isinstance(self.diagnostics, tuple) or not all(
            isinstance(item, BridgeDiagnostic) for item in self.diagnostics
        ):
            raise BridgeValidationError("result.diagnostics must contain BridgeDiagnostic records")

    @property
    def resolved_locators(self) -> tuple[CodeLocator, ...]:
        return tuple(item.locator for item in self.outcomes if item.locator is not None)

    @property
    def file_outcomes(self) -> tuple[ChangedFileResolutionOutcome, ...]:
        return self.outcomes

    def as_dict(self) -> dict[str, object]:
        return {
            "diagnostics": [item.as_dict() for item in self.diagnostics],
            "outcomes": [item.as_dict() for item in self.outcomes],
            "request_id": self.request_id,
            "routing": self.routing.as_dict() if self.routing else None,
            "status": self.status,
        }


@dataclass(frozen=True)
class NavigationHandoff:
    """Compact input for an OpenLore navigation integration."""

    locator: CodeLocator
    routing: RoutingReference

    def __post_init__(self) -> None:
        object.__setattr__(self, "locator", _validated_locator(self.locator, "handoff.locator"))
        if not isinstance(self.routing, RoutingReference):
            raise BridgeValidationError("handoff.routing must be RoutingReference")

    def as_dict(self) -> dict[str, object]:
        return {"locator": self.locator.as_dict(), "routing": self.routing.as_dict()}


@dataclass(frozen=True)
class NavigationHandoffResult:
    """Successful handoff or payload-free admission diagnostics."""

    status: str
    handoff: NavigationHandoff | None = None
    diagnostics: tuple[BridgeDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, str) or self.status not in {"ready", "invalid-context"}:
            raise BridgeValidationError("handoff.result.status is unsupported")
        if self.status == "ready" and self.handoff is None:
            raise BridgeValidationError("ready handoff result requires handoff")
        if self.status != "ready" and self.handoff is not None:
            raise BridgeValidationError("non-ready handoff result must not carry handoff")
        if self.handoff is not None and not isinstance(self.handoff, NavigationHandoff):
            raise BridgeValidationError("handoff.result.handoff must be NavigationHandoff")
        if isinstance(self.diagnostics, list):
            object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if not isinstance(self.diagnostics, tuple) or not all(
            isinstance(item, BridgeDiagnostic) for item in self.diagnostics
        ):
            raise BridgeValidationError("handoff.result.diagnostics must contain BridgeDiagnostic records")

    def as_dict(self) -> dict[str, object]:
        return {
            "diagnostics": [item.as_dict() for item in self.diagnostics],
            "handoff": self.handoff.as_dict() if self.handoff else None,
            "status": self.status,
        }


class OpenLoreSemanticBridge:
    """Resolve exact changed-file symbols and build compact navigation handoffs."""

    def __init__(self, registry: WorkspaceRegistry, provider: OpenLoreProvider) -> None:
        if not isinstance(registry, WorkspaceRegistry):
            raise TypeError("registry must be a WorkspaceRegistry")
        if not hasattr(provider, "resolve_symbols"):
            raise TypeError("provider must implement resolve_symbols")
        self.registry = registry
        self.provider = provider

    def resolve(self, request: ChangedFileResolutionRequest) -> ResolutionResult:
        """Admit a request, invoke the provider once, and map it strictly."""

        if not isinstance(request, ChangedFileResolutionRequest):
            return ResolutionResult(
                "invalid-request",
                "invalid-context",
                None,
                (),
                (BridgeDiagnostic("invalid-request"),),
            )

        files, duplicate_diagnostics = _deduplicate_files(request.changed_files)
        request_id = request.id
        repository = self._repository(request.repository)
        if repository is None:
            return self._invalid_result(request_id, files, "unknown-repository", duplicate_diagnostics)

        routing, route_diagnostic = self._routing(repository)
        if route_diagnostic is not None:
            return self._invalid_result(request_id, files, route_diagnostic, duplicate_diagnostics)

        context_reason = self._context_reason(request)
        if context_reason is not None:
            return self._invalid_result(request_id, files, context_reason, duplicate_diagnostics)
        if duplicate_diagnostics:
            return self._invalid_result(request_id, files, "conflicting-changed-file-identity", duplicate_diagnostics)

        provider_request = ProviderResolutionRequest(
            request.repository,
            request.revision,
            routing,
            tuple(sorted(files, key=lambda item: item.stable_file_id)),
        )
        try:
            response = self.provider.resolve_symbols(provider_request)
        except ProviderUnavailableError:
            return self._provider_failure(request_id, files, "provider-unavailable", routing)
        except Exception:
            # Exception details are intentionally never retained or serialized.
            return self._provider_failure(request_id, files, "provider-unavailable", routing)
        return self._map_response(request, files, routing, response)

    def resolve_changed_files(self, request: ChangedFileResolutionRequest) -> ResolutionResult:
        """Descriptive alias for :meth:`resolve`."""

        return self.resolve(request)

    def build_navigation_handoff(
        self,
        locator: CodeLocator,
        evidence: ImplementationEvidenceContext | None = None,
    ) -> NavigationHandoffResult:
        """Validate a locator and return only its registry-selected route."""

        if not isinstance(locator, CodeLocator):
            return NavigationHandoffResult("invalid-context", diagnostics=(BridgeDiagnostic("incomplete-locator"),))
        try:
            repository_id = safe_repository(locator.repository, "locator.repository")
            revision = safe_identity(locator.revision, "locator.revision")
            file = safe_relative_file(locator.file, "locator.file")
        except ValueError:
            return NavigationHandoffResult("invalid-context", diagnostics=(BridgeDiagnostic("invalid-locator"),))
        if not is_immutable_revision(revision):
            return NavigationHandoffResult("invalid-context", diagnostics=(BridgeDiagnostic("mutable-revision"),))
        if not is_complete_symbol_identity(locator.symbol):
            return NavigationHandoffResult("invalid-context", diagnostics=(BridgeDiagnostic("incomplete-symbol"),))
        repository = self._repository(repository_id)
        if repository is None:
            return NavigationHandoffResult("invalid-context", diagnostics=(BridgeDiagnostic("unknown-repository"),))
        routing, route_diagnostic = self._routing(repository)
        if route_diagnostic is not None:
            return NavigationHandoffResult("invalid-context", diagnostics=(BridgeDiagnostic(route_diagnostic),))
        if evidence is not None:
            if not isinstance(evidence, ImplementationEvidenceContext):
                return NavigationHandoffResult("invalid-context", diagnostics=(BridgeDiagnostic("invalid-evidence"),))
            if not is_immutable_revision(evidence.revision):
                return NavigationHandoffResult("invalid-context", diagnostics=(BridgeDiagnostic("mutable-revision"),))
            if evidence.repository != repository_id:
                return NavigationHandoffResult("invalid-context", diagnostics=(BridgeDiagnostic("evidence-repository-mismatch"),))
            if evidence.revision != revision:
                return NavigationHandoffResult("invalid-context", diagnostics=(BridgeDiagnostic("evidence-revision-mismatch"),))
        exact_locator = CodeLocator(repository_id, revision, file, locator.symbol)
        return NavigationHandoffResult("ready", NavigationHandoff(exact_locator, routing))

    def navigation_handoff(
        self,
        locator: CodeLocator,
        evidence: ImplementationEvidenceContext | None = None,
    ) -> NavigationHandoffResult:
        """Alias for callers naming the operation rather than its builder."""

        return self.build_navigation_handoff(locator, evidence)

    def _repository(self, repository_id: str):
        return next((item for item in self.registry.repositories if item.id == repository_id), None)

    def _routing(self, repository):
        if self.registry.openlore.federation_enabled and repository.openlore.include_in_federation:
            index_location = repository.openlore.index_location.strip()
            if not index_location:
                return None, "missing-federation-index"
            try:
                return RoutingReference("federation-index", index_location), None
            except BridgeValidationError:
                return None, "invalid-request"
        try:
            return RoutingReference("repository-index-path", str(repository.resolved_path)), None
        except BridgeValidationError:
            return None, "invalid-request"

    @staticmethod
    def _context_reason(request: ChangedFileResolutionRequest) -> str | None:
        if not is_immutable_revision(request.revision):
            return "mutable-revision"
        if request.repository != request.evidence.repository:
            return "evidence-repository-mismatch"
        if request.revision != request.evidence.revision:
            return "evidence-revision-mismatch"
        return None

    def _invalid_result(
        self,
        request_id: str,
        files: tuple[ChangedFileReference, ...],
        reason: str,
        additional: tuple[BridgeDiagnostic, ...] = (),
    ) -> ResolutionResult:
        diagnostics = tuple(sorted((*additional, BridgeDiagnostic(reason)), key=lambda item: (item.stable_file_id, item.reason_code)))
        outcomes = tuple(
            ChangedFileResolutionOutcome(
                item.stable_file_id,
                item.file,
                ResolutionStatus.INVALID_CONTEXT,
                diagnostic=BridgeDiagnostic(reason, item.stable_file_id),
            )
            for item in sorted(files, key=lambda value: value.stable_file_id)
        )
        return ResolutionResult(request_id, "invalid-context", None, outcomes, diagnostics)

    @staticmethod
    def _provider_failure(
        request_id: str,
        files: tuple[ChangedFileReference, ...],
        reason: str,
        routing: RoutingReference | None = None,
    ) -> ResolutionResult:
        outcomes = tuple(
            ChangedFileResolutionOutcome(
                item.stable_file_id,
                item.file,
                ResolutionStatus.PROVIDER_UNAVAILABLE,
                diagnostic=BridgeDiagnostic(reason, item.stable_file_id),
            )
            for item in sorted(files, key=lambda value: value.stable_file_id)
        )
        return ResolutionResult(
            request_id,
            "admitted",
            routing,
            outcomes,
            tuple(BridgeDiagnostic(reason, item.stable_file_id) for item in outcomes),
        )

    def _map_response(
        self,
        request: ChangedFileResolutionRequest,
        files: tuple[ChangedFileReference, ...],
        routing: RoutingReference,
        response: object,
    ) -> ResolutionResult:
        ordered_files = tuple(sorted(files, key=lambda item: item.stable_file_id))
        if not isinstance(response, ProviderResolutionResponse):
            return self._invalid_provider_result(request.id, ordered_files, "malformed-provider-response", routing)
        if response.status == ProviderResponseStatus.UNAVAILABLE.value:
            return self._provider_failure(request.id, ordered_files, "provider-unavailable", routing)
        if response.status != ProviderResponseStatus.OK.value:
            return self._invalid_provider_result(request.id, ordered_files, "unsupported-provider-status", routing)
        entries = response.entries
        if not isinstance(entries, tuple) or not all(isinstance(item, ProviderFileResolution) for item in entries):
            return self._invalid_provider_result(request.id, ordered_files, "malformed-provider-response", routing)
        entry_by_id: dict[str, ProviderFileResolution] = {}
        duplicate = False
        for entry in entries:
            if not isinstance(entry.stable_file_id, str):
                return self._invalid_provider_result(request.id, ordered_files, "malformed-provider-response", routing)
            if entry.stable_file_id in entry_by_id:
                duplicate = True
            entry_by_id[entry.stable_file_id] = entry
        requested_ids = {item.stable_file_id for item in ordered_files}
        if duplicate or set(entry_by_id) != requested_ids:
            reason = "duplicate-provider-response" if duplicate else "malformed-provider-response"
            return self._invalid_provider_result(request.id, ordered_files, reason, routing)
        for file_ref in ordered_files:
            entry = entry_by_id[file_ref.stable_file_id]
            if (
                entry.repository != request.repository
                or entry.revision != request.revision
                or entry.file != file_ref.file
            ):
                return self._invalid_provider_result(request.id, ordered_files, "provider-context-mismatch", routing)
            if not isinstance(entry.status, str):
                return self._invalid_provider_result(request.id, ordered_files, "malformed-provider-response", routing)
            if entry.status not in {
                ProviderResponseStatus.OK.value,
                ProviderResponseStatus.UNAVAILABLE.value,
            }:
                return self._invalid_provider_result(request.id, ordered_files, "unsupported-provider-status", routing)

        outcomes: list[ChangedFileResolutionOutcome] = []
        diagnostics: list[BridgeDiagnostic] = []
        for file_ref in ordered_files:
            entry = entry_by_id[file_ref.stable_file_id]
            if entry.status == ProviderResponseStatus.UNAVAILABLE.value:
                diagnostic = BridgeDiagnostic("provider-unavailable", file_ref.stable_file_id)
                outcomes.append(
                    ChangedFileResolutionOutcome(
                        file_ref.stable_file_id,
                        file_ref.file,
                        ResolutionStatus.PROVIDER_UNAVAILABLE,
                        diagnostic=diagnostic,
                    )
                )
                diagnostics.append(diagnostic)
                continue
            symbols = entry.symbols
            if not isinstance(symbols, tuple) or not all(isinstance(symbol, str) for symbol in symbols):
                diagnostic = BridgeDiagnostic("malformed-provider-response", file_ref.stable_file_id)
                outcomes.append(ChangedFileResolutionOutcome(file_ref.stable_file_id, file_ref.file, ResolutionStatus.INVALID_PROVIDER_RESPONSE, diagnostic=diagnostic))
                diagnostics.append(diagnostic)
                continue
            if any(not is_complete_symbol_identity(symbol) for symbol in symbols):
                diagnostic = BridgeDiagnostic("malformed-symbol", file_ref.stable_file_id)
                outcomes.append(ChangedFileResolutionOutcome(file_ref.stable_file_id, file_ref.file, ResolutionStatus.INVALID_PROVIDER_RESPONSE, diagnostic=diagnostic))
                diagnostics.append(diagnostic)
                continue
            if len(symbols) == 0:
                diagnostic = BridgeDiagnostic("no-symbol", file_ref.stable_file_id)
                outcomes.append(ChangedFileResolutionOutcome(file_ref.stable_file_id, file_ref.file, ResolutionStatus.UNRESOLVED, diagnostic=diagnostic))
                diagnostics.append(diagnostic)
            elif len(symbols) > 1:
                diagnostic = BridgeDiagnostic("multiple-symbols", file_ref.stable_file_id)
                outcomes.append(ChangedFileResolutionOutcome(file_ref.stable_file_id, file_ref.file, ResolutionStatus.AMBIGUOUS, diagnostic=diagnostic))
                diagnostics.append(diagnostic)
            else:
                locator = CodeLocator(request.repository, request.revision, file_ref.file, symbols[0])
                outcomes.append(ChangedFileResolutionOutcome(file_ref.stable_file_id, file_ref.file, ResolutionStatus.RESOLVED, locator=locator))
        return ResolutionResult(request.id, "admitted", routing, tuple(outcomes), tuple(diagnostics))

    @staticmethod
    def _invalid_provider_result(
        request_id: str,
        files: tuple[ChangedFileReference, ...],
        reason: str,
        routing: RoutingReference | None = None,
    ) -> ResolutionResult:
        outcomes = tuple(
            ChangedFileResolutionOutcome(
                item.stable_file_id,
                item.file,
                ResolutionStatus.INVALID_PROVIDER_RESPONSE,
                diagnostic=BridgeDiagnostic(reason, item.stable_file_id),
            )
            for item in files
        )
        return ResolutionResult(
            request_id,
            "admitted",
            routing,
            outcomes,
            tuple(item.diagnostic for item in outcomes if item.diagnostic is not None),
        )


def adapt_resolution_to_changed_symbol_mappings(
    result: ResolutionResult,
) -> tuple[ChangedSymbolMapping, ...]:
    """Explicitly adapt compact outcomes to the existing EKG-14 input seam.

    The source stable file identity is reused as the mapping identity.  Only
    the singleton resolved outcome carries a symbol; every other bridge
    status maps to a non-resolved EKG-14 classification and therefore cannot
    emit a candidate.
    """

    mappings: list[ChangedSymbolMapping] = []
    for outcome in sorted(result.outcomes, key=lambda item: item.stable_file_id):
        if outcome.status == ResolutionStatus.RESOLVED and outcome.locator is not None:
            mapping_outcome = MappingOutcome.RESOLVED
            symbol = outcome.locator.symbol
        elif outcome.status == ResolutionStatus.UNRESOLVED:
            mapping_outcome = MappingOutcome.UNRESOLVED
            symbol = None
        elif outcome.status == ResolutionStatus.AMBIGUOUS:
            mapping_outcome = MappingOutcome.AMBIGUOUS
            symbol = None
        else:
            mapping_outcome = MappingOutcome.UNSUPPORTED
            symbol = None
        mappings.append(ChangedSymbolMapping(outcome.stable_file_id, outcome.file, mapping_outcome, symbol))
    return tuple(mappings)


def _deduplicate_files(
    files: Sequence[ChangedFileReference],
) -> tuple[tuple[ChangedFileReference, ...], tuple[BridgeDiagnostic, ...]]:
    by_id: dict[str, ChangedFileReference] = {}
    conflicting_ids: set[str] = set()
    for item in files:
        previous = by_id.get(item.stable_file_id)
        if previous is None:
            by_id[item.stable_file_id] = item
        elif previous.file != item.file:
            conflicting_ids.add(item.stable_file_id)
            # A conflict is invalid, but the diagnostic result must not expose
            # whichever path happened to arrive first.
            if item.file < previous.file:
                by_id[item.stable_file_id] = item
    return (
        tuple(by_id[item] for item in sorted(by_id)),
        tuple(
            BridgeDiagnostic("conflicting-changed-file-identity", item)
            for item in sorted(conflicting_ids)
        ),
    )


# Short aliases make the contract convenient without exposing provider internals.
ChangedFileRequest = ChangedFileResolutionRequest
ChangedFileOutcome = ChangedFileResolutionOutcome
ImplementationEvidence = ImplementationEvidenceContext
