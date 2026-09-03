"""Executable, versioned relationship contract for canonical EKG graphs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engineering_kg.ontology import CodeLocator, Node


CATALOG_REVISION = "2"


class RelationshipKind(StrEnum):
    CONTAINS = "contains"
    TRACES_TO = "traces_to"
    IMPLEMENTS = "implements"
    VERIFIED_BY = "verified_by"
    TOUCHES = "touches"
    DEPENDS_ON = "depends_on"
    REFERENCES = "references"
    OWNED_BY = "owned_by"
    PROVIDES = "provides"


@dataclass(frozen=True)
class RelationshipDefinition:
    kind: RelationshipKind
    semantics: str
    source_kinds: frozenset[str]
    target_kinds: frozenset[str]
    permits_code_locator: bool = False
    max_targets_per_source: int | None = None
    classification: str = "semantic"

    def as_dict(self) -> dict[str, object]:
        return {"classification": self.classification, "kind": self.kind.value,
                "max_targets_per_source": self.max_targets_per_source,
                "permits_code_locator": self.permits_code_locator,
                "semantics": self.semantics, "source_kinds": sorted(self.source_kinds),
                "target_kinds": sorted(self.target_kinds)}


@dataclass(frozen=True)
class SourceMapping:
    """One approved adapter input mapping and its fail-closed fallback."""

    source: str
    kind: str
    classification: str
    unsupported_behavior: str = "diagnose-and-skip"

    def as_dict(self) -> dict[str, str]:
        return {
            "classification": self.classification,
            "kind": self.kind,
            "source": self.source,
            "unsupported_behavior": self.unsupported_behavior,
        }


_ANY = frozenset({"*"})
_CHANGE = frozenset({"openspec-active-change", "openspec-archived-change"})
_TRACE = _CHANGE | frozenset({"requirement", "scenario", "jira_story"})
_IMPLEMENTER = frozenset({"jira_story", "pull_request", "service", "repository", "contract", "business_process"})
_DEPENDENCY = _IMPLEMENTER | frozenset({"specification", "requirement", "scenario"})

RELATIONSHIP_CATALOG: tuple[RelationshipDefinition, ...] = (
    RelationshipDefinition(RelationshipKind.CONTAINS, "Structural containment.", frozenset({"specification", "requirement"}) | _CHANGE, frozenset({"requirement", "scenario", "openspec-artifact"}), classification="structural"),
    RelationshipDefinition(RelationshipKind.TRACES_TO, "Traceability relationship.", _TRACE, frozenset({"specification", "requirement", "scenario", "jira_story"})),
    RelationshipDefinition(RelationshipKind.IMPLEMENTS, "Implementation relationship.", _IMPLEMENTER, frozenset({"service", "repository", "contract", "business_process"}), True),
    RelationshipDefinition(RelationshipKind.VERIFIED_BY, "Verification relationship.", frozenset({"requirement", "scenario", "jira_story", "contract", "service", "business_process"}), frozenset({"scenario", "pull_request", "contract"}), True),
    RelationshipDefinition(RelationshipKind.TOUCHES, "Change touches an implementation target.", frozenset({"jira_story", "pull_request"}), frozenset({"service", "repository", "contract", "business_process"}), True),
    RelationshipDefinition(RelationshipKind.DEPENDS_ON, "Directed dependency.", _DEPENDENCY, _DEPENDENCY),
    RelationshipDefinition(RelationshipKind.REFERENCES, "Non-owning reference.", _ANY, _ANY, True),
    RelationshipDefinition(RelationshipKind.OWNED_BY, "Single ownership assignment.", frozenset({"service", "repository", "contract", "business_process", "specification", "adr"}), frozenset({"workspace", "service", "external_system"}), max_targets_per_source=1),
    RelationshipDefinition(RelationshipKind.PROVIDES, "Provider exposes a capability.", frozenset({"service", "repository", "external_system"}), frozenset({"contract", "business_process", "external_system"})),
)
CATALOG_BY_KIND = {entry.kind.value: entry for entry in RELATIONSHIP_CATALOG}

# Source labels intentionally live here rather than in producers.
SOURCE_MAPPINGS = (
    SourceMapping("openspec-hierarchy", "contains", "structural"),
    SourceMapping("openspec-assertion", "asserts", "support"),
    SourceMapping("openspec-related", "references", "non-confident"),
    SourceMapping("merged-pr-changed-symbol", "touches", "candidate"),
)


def catalog_as_dict() -> dict[str, object]:
    return {"revision": CATALOG_REVISION, "relationships": [entry.as_dict() for entry in RELATIONSHIP_CATALOG],
            "source_mappings": [entry.as_dict() for entry in SOURCE_MAPPINGS]}


def relationship_error(kind: object, source: "Node | None", target: "Node | CodeLocator | None") -> str | None:
    """Return a stable admission rule id; callers attach record identity."""
    value = getattr(kind, "value", kind)
    entry = CATALOG_BY_KIND.get(value)
    if entry is None:
        return "relationship-vocabulary-kind"
    if source is None or target is None:
        return "relationship-endpoint-exists"
    source_kind = getattr(getattr(source, "kind", None), "value", getattr(source, "kind", None))
    # Wildcard catalog alternatives mean every *canonical* node kind, never an
    # arbitrary adapter-provided string.
    if source_kind not in _CANONICAL_NODE_KINDS:
        return "relationship-endpoint-contract"
    if "*" not in entry.source_kinds and source_kind not in entry.source_kinds:
        return "relationship-endpoint-contract"
    # CodeLocator has no node kind and is deliberately only admitted where explicit.
    if target.__class__.__name__ == "CodeLocator":
        if not entry.permits_code_locator or not complete_code_locator(target):
            return "relationship-code-locator-contract"
    else:
        target_kind = getattr(getattr(target, "kind", None), "value", getattr(target, "kind", None))
        if target_kind not in _CANONICAL_NODE_KINDS:
            return "relationship-endpoint-contract"
        if "*" not in entry.target_kinds and target_kind not in entry.target_kinds:
            return "relationship-endpoint-contract"
        if value == RelationshipKind.CONTAINS.value and (source_kind, target_kind) not in {
            ("specification", "requirement"), ("requirement", "scenario"),
            ("openspec-active-change", "openspec-artifact"),
            ("openspec-archived-change", "openspec-artifact"),
        }:
            return "relationship-endpoint-contract"
    return None


# Kept local to avoid an ontology import cycle: vocabulary is imported by the
# ontology's cross-graph claim admission boundary.
_CANONICAL_NODE_KINDS = frozenset({
    "workspace", "service", "repository", "specification", "requirement",
    "scenario", "jira_story", "pull_request", "contract",
    "external_system", "business_process", "adr", "openspec-active-change",
    "openspec-archived-change", "openspec-artifact",
})


def complete_code_locator(target: object) -> bool:
    return all(isinstance(getattr(target, name, None), str) and getattr(target, name).strip()
               for name in ("repository", "revision", "file", "symbol"))


def eligible_for_trusted_cross_graph_projection(
    claim: object,
    observations: tuple[object, ...],
    lifecycle: object,
    lifecycle_support: tuple[object, ...] = (),
) -> bool:
    """Apply evidence eligibility only after catalog admission at the caller.

    Confidence is deliberately absent: it is opaque metadata, never a trust score.
    """
    if getattr(lifecycle, "state", None) != "trusted":
        return False
    if getattr(lifecycle, "trust_disposition", None) != "trusted":
        return False
    if getattr(claim, "relation_kind", None) != RelationshipKind.IMPLEMENTS.value:
        return True
    has_authoritative_declared_observation = any(
        getattr(item, "origin", None) == "declared"
        and getattr(item, "status", None) == "authoritative"
        and getattr(item, "trust_disposition", None) == "trusted"
        for item in observations
    )
    # Every support record is part of the implementation support chain. A
    # merged PR/file observation must not become implementation proof merely
    # because separately supplied declared support and lifecycle revisions are
    # trusted.
    has_observed_or_inferred_observation_support = any(
        getattr(item, "origin", None) in {"observed", "inferred"}
        for item in observations
    )
    has_observed_or_inferred_lifecycle_support = any(
        getattr(item, "origin", None) in {"observed", "inferred"}
        for item in lifecycle_support
    )
    return (
        has_authoritative_declared_observation
        and not has_observed_or_inferred_observation_support
        and not has_observed_or_inferred_lifecycle_support
    )
