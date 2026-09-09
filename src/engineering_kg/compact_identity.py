"""Payload-safe identity validation shared by external evidence adapters.

This module deliberately contains no provider or graph types.  It is the
small common boundary for repository-relative files, immutable revisions, and
fully-qualified symbol identities.
"""

from __future__ import annotations

import json
import re


_QUALIFIED_SYMBOL_IDENTITY = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$"
)
_SAFE_IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_SAFE_REPOSITORY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")
_SAFE_RELATIVE_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,1023}$")
_SAFE_ROUTING_REFERENCE = re.compile(r"^[^\x00-\x1f\x7f]{1,1024}$")
_SAFE_ROUTING_PATH = re.compile(r"^[^\x00-\x1f\x7f]+$")
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_ROUTING_CODE_STATEMENT = re.compile(
    r"^\s*(?:def|class|function|return|yield|import|from|if|else|elif|for|while|"
    r"try|except|raise|pass|with|await|async|const|let|var)\s+\S",
    re.IGNORECASE,
)
_ROUTING_CALL = re.compile(
    r"(?<![A-Za-z0-9_])[A-Za-z_][A-Za-z0-9_.]*\s*\(",
    re.IGNORECASE,
)
_ROUTING_FILENAME_PAREN_VALUE = re.compile(r"^\s*[0-9]+(?:[._-][0-9]+)*\s*$")
_ROUTING_ASSIGNMENT = re.compile(
    r"^\s*[A-Za-z_][A-Za-z0-9_.-]*\s*=\s*.*$",
    re.IGNORECASE,
)
_ROUTING_HEADER = re.compile(
    r"^\s*[A-Za-z][A-Za-z0-9_.-]*\s*:\s+\S.*$",
    re.IGNORECASE,
)
_ROUTING_AUTHORIZATION = re.compile(
    r"^\s*authorization\s*:\s*\S.*$",
    re.IGNORECASE,
)
_ROUTING_AUTH_HEADER = re.compile(
    r"^\s*(?:bearer|basic|token)\s+\S.*$",
    re.IGNORECASE,
)
_ROUTING_COMPACT_AUTH = re.compile(
    r"^\s*(?:bearer|basic)(?:[A-Za-z0-9_+/=.]+|<[^<>/\\\s]+>)\s*$",
    re.IGNORECASE,
)
_ROUTING_INTERPOLATION = re.compile(r"(?:\$\{|#\{|\$\()")
_ROUTING_PAYLOAD_SHAPE = re.compile(
    r"^\s*(?:source\s+body|artifact\s+content|provider[_ -]?payload|"
    r"navigation[_ -]?response|response\s+body|secret\s+payload)\s*$",
    re.IGNORECASE,
)
_ROUTING_OBJECT_MEMBER = re.compile(
    r"(?:^|,)\s*(?:[\"'][^\"']*[\"']|[A-Za-z_][A-Za-z0-9_.-]*)\s*:\s*\S",
)
_ROUTING_PLACEHOLDER = re.compile(r"^\s*<[^<>/\\\s]+>\s*$")
_ROUTING_SCP_REFERENCE = re.compile(
    r"^[^/\\\s:@]+@[^/\\\s:@]+:.+$",
    re.IGNORECASE,
)
_ROUTING_CREDENTIAL_AUTHORITY = re.compile(
    r"^[^/\\\s:@]+:[^/\\\s@]+@[^/\\\s]+(?:[\\/].*)?$",
    re.IGNORECASE,
)
_URI_SCHEME = re.compile(r"^(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*):(?P<value>.*)$")
_HIERARCHICAL_URL_SCHEMES = frozenset({"http", "https", "ssh", "git", "s3", "vscode"})


def safe_identity(value: object, field_name: str) -> str:
    """Validate and return a compact opaque identity."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    text = value.strip()
    if is_url_like_identity(text):
        raise ValueError(f"{field_name} must not be URL-like")
    if not _SAFE_IDENTITY.fullmatch(text):
        raise ValueError(f"{field_name} must be a safe identity")
    return text


def safe_repository(value: object, field_name: str = "repository") -> str:
    """Validate and return a repository identity, never a repository URL."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    text = value.strip()
    if not _SAFE_REPOSITORY.fullmatch(text):
        raise ValueError(f"{field_name} must be a safe identity")
    return text


def safe_relative_file(value: object, field_name: str = "file") -> str:
    """Validate a repository-relative file identity."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    text = value.strip()
    if (
        not _SAFE_RELATIVE_FILE.fullmatch(text)
        or text.startswith("/")
        or any(part == ".." for part in text.split("/"))
    ):
        raise ValueError(f"{field_name} must be a safe relative locator")
    return text


def safe_routing_reference(
    value: object,
    field_name: str = "routing.reference",
    *,
    allow_absolute: bool = False,
) -> str:
    """Validate a compact, payload-free route reference.

    Both route kinds are compact index paths and may be absolute when the
    registry supplies an absolute local path.  Neither route may carry URI
    authority, credentials, source text, or other payload-bearing characters.
    """

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    text = value.strip()
    path_parts = tuple(part for part in re.split(r"[\\/]", text) if part)
    path_text = text
    if text.startswith("/"):
        path_text = text[1:]
    elif _WINDOWS_ABSOLUTE_PATH.match(text):
        path_text = text[3:]
    structured_payload = any(_structured_routing_component(part) for part in path_parts)
    payload_shape = (
        _ROUTING_CODE_STATEMENT.match(text)
        or _routing_call_shape(text)
        or _ROUTING_ASSIGNMENT.fullmatch(text)
        or _ROUTING_HEADER.fullmatch(text)
        or _ROUTING_AUTHORIZATION.fullmatch(text)
        or _ROUTING_AUTH_HEADER.fullmatch(text)
        or _ROUTING_COMPACT_AUTH.fullmatch(text)
        or _ROUTING_INTERPOLATION.search(text)
        or _ROUTING_PAYLOAD_SHAPE.fullmatch(text)
        or _ROUTING_PLACEHOLDER.fullmatch(text)
        or structured_payload
        or any(
            _ROUTING_CODE_STATEMENT.match(part)
            or _routing_call_shape(part)
            or _ROUTING_ASSIGNMENT.fullmatch(part)
            or _ROUTING_HEADER.fullmatch(part)
            or _ROUTING_AUTHORIZATION.fullmatch(part)
            or _ROUTING_AUTH_HEADER.fullmatch(part)
            or _ROUTING_COMPACT_AUTH.fullmatch(part)
            or _ROUTING_INTERPOLATION.search(part)
            or _ROUTING_PAYLOAD_SHAPE.fullmatch(part)
            or _ROUTING_PLACEHOLDER.fullmatch(part)
            for part in path_parts
        )
    )
    if (
        not _SAFE_ROUTING_REFERENCE.fullmatch(text)
        or any(not character.isprintable() for character in text)
        or text.startswith("\\\\")
        or payload_shape
        or not _SAFE_ROUTING_PATH.fullmatch(path_text)
        or (not _WINDOWS_ABSOLUTE_PATH.match(text) and (
            is_url_like_identity(text)
            or _ROUTING_SCP_REFERENCE.fullmatch(text)
            or _ROUTING_CREDENTIAL_AUTHORITY.fullmatch(text)
            or any(
                is_url_like_identity(part)
                or _ROUTING_SCP_REFERENCE.fullmatch(part)
                or _ROUTING_CREDENTIAL_AUTHORITY.fullmatch(part)
                for part in path_parts
            )
        ))
    ):
        raise ValueError(f"{field_name} must not be URL-like")
    if (text.startswith("/") or _WINDOWS_ABSOLUTE_PATH.match(text)) and not allow_absolute:
        raise ValueError(f"{field_name} must be a compact relative route")
    if any(part == ".." for part in path_parts):
        raise ValueError(f"{field_name} must not contain parent traversal")
    return text


def _structured_routing_component(value: str) -> bool:
    """Reject JSON/object-shaped path components, but retain filename punctuation.

    A route can legitimately contain punctuation such as ``data[@2024]`` or
    ``{cache}``.  Only a component whose root delimiters and contents indicate
    a structured value is rejected; this keeps the predicate structural rather
    than maintaining a token-name or credential-name denylist.
    """

    text = value.strip()
    if len(text) < 2 or text[0] not in "[{" or text[-1] not in "]}":
        return False
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        parsed = None
    if isinstance(parsed, (dict, list)):
        return True

    body = text[1:-1].strip()
    if not body:
        return True
    if text[0] == "{" and text[-1] == "}":
        return bool(
            _ROUTING_OBJECT_MEMBER.search(body)
            or body.startswith(("{", "[", '"', "'"))
            or body.endswith(("}", "]", '"', "'"))
        )
    return bool(
        body.startswith(("{", "[", '"', "'"))
        or ":" in body
    )


def _routing_call_shape(value: str) -> bool:
    """Reject complete source-like calls without rejecting path punctuation.

    Parentheses are valid filename punctuation, so the predicate is narrower
    than a blanket parenthesis check. It recognizes an identifier followed by
    a balanced call body, including nested calls. A single numeric value in
    parentheses is retained as a conventional filename suffix (for example,
    ``record(1)``); empty, identifier-bearing, multi-value, nested, or
    semicolon-separated call expressions remain source-shaped.
    """

    calls: list[tuple[int, int]] = []
    for match in _ROUTING_CALL.finditer(value):
        opening = match.end() - 1
        closing = _balanced_routing_call_end(value, opening)
        if closing is None:
            continue
        body = value[opening + 1 : closing]
        calls.append((match.start(), closing))
        if not _ROUTING_FILENAME_PAREN_VALUE.fullmatch(body):
            return True

    if len(calls) > 1:
        for (_, first_end), (second_start, _) in zip(calls, calls[1:]):
            if ";" in value[first_end + 1 : second_start]:
                return True
    return False


def _balanced_routing_call_end(value: str, opening: int) -> int | None:
    """Return the matching close for a route call's opening parenthesis."""

    depth = 0
    for index in range(opening, len(value)):
        character = value[index]
        if character in "\r\n":
            return None
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def is_url_like_identity(value: str) -> bool:
    """Return whether a value describes a navigable URI rather than an ID."""

    if value.startswith("//"):
        return True
    match = _URI_SCHEME.fullmatch(value)
    if match is None:
        return False
    scheme = match.group("scheme").lower()
    remainder = match.group("value")
    return remainder.startswith("/") or scheme in _HIERARCHICAL_URL_SCHEMES


def is_immutable_revision(value: object) -> bool:
    """Accept only a complete Git SHA-1 or SHA-256 object identifier."""

    return isinstance(value, str) and len(value) in (40, 64) and all(
        character in "0123456789abcdefABCDEF" for character in value
    )


def require_immutable_revision(value: object, field_name: str = "revision") -> str:
    """Validate and return an immutable revision without resolving references."""

    text = safe_identity(value, field_name)
    if not is_immutable_revision(text):
        raise ValueError(f"{field_name} must be an immutable revision")
    return text


def is_complete_symbol_identity(value: object) -> bool:
    """Return whether a value is a qualified, payload-free symbol identity."""

    return isinstance(value, str) and bool(_QUALIFIED_SYMBOL_IDENTITY.fullmatch(value))
