"""Retained-source rule: which files the Ingest reads, decided from disk and the registry.

Specification: contracts/warehouse_contract.py, CONTRACT_RETAINED (SLICE-3 batch 6c).
Requirements: REQ-25, REQ-26, REQ-48. Runtime declarations are independent of that module;
tests bridge the specification and this implementation (CL11-F).
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from .registry import NotASource, RegistryEntry, RegistryError, UnregisteredSourceError

MANIFEST_FILE: Final = "data/cache/MANIFEST.jsonl"  # relative to the repository root
CACHE_DIR: Final = "data/cache"
CANDIDATE_ROOTS: Final[tuple[str, ...]] = ("data", "docs")
EXCLUDED_DIRS: Final[tuple[str, ...]] = ("data/cache", "data/warehouse", "docs/mockups")
CACHE_PREFIX: Final = "cache:"
REPO_PREFIX: Final = "repo:"
_OK: Final = "ok"
_PYCACHE: Final = "__pycache__"

__all__ = [
    "CACHE_DIR",
    "CACHE_PREFIX",
    "CANDIDATE_ROOTS",
    "EXCLUDED_DIRS",
    "MANIFEST_FILE",
    "REPO_PREFIX",
    "ManifestError",
    "RegistryError",
    "RetainedSources",
    "UnregisteredSourceError",
    "candidate_sources",
    "retained_sources",
]


class ManifestError(Exception):
    """ERRORS-RET-1: an 'ok' download manifest record does not name a cache-relative file."""


@dataclass(frozen=True)
class RetainedSources:
    """Candidates split into registered sources and listed non-sources (POST-RET-2)."""

    sources: tuple[str, ...]
    not_sources: tuple[NotASource, ...]


def _cache_key(record: Mapping[str, object]) -> str:
    path = record.get("path")
    if not isinstance(path, str) or not path:
        raise ManifestError(f"ERRORS-RET-1 violation: manifest record {record!r} has no path")
    rel = PurePosixPath(path)
    if rel.is_absolute() or ".." in rel.parts:
        raise ManifestError(
            f"ERRORS-RET-1 violation: manifest path {path!r} in record {record!r} is not "
            f"relative to {CACHE_DIR}"
        )
    return f"{CACHE_PREFIX}{rel}"


def _manifest_candidates(repo_root: Path) -> set[str]:
    """Paths whose latest manifest record is 'ok' (the manifest is append-only, later wins)."""
    latest: dict[str, Mapping[str, object]] = {}
    unkeyed: list[Mapping[str, object]] = []
    with (repo_root / MANIFEST_FILE).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            path = record.get("path")
            if isinstance(path, str) and path:
                latest[path] = record
            else:
                unkeyed.append(record)
    for record in unkeyed:
        if record.get("status") == _OK:
            _cache_key(record)  # raises ERRORS-RET-1: an ok record must name its file
    return {_cache_key(r) for r in latest.values() if r.get("status") == _OK}


def _is_excluded(rel: PurePosixPath) -> bool:
    text = rel.as_posix()
    if any(text == d or text.startswith(f"{d}/") for d in EXCLUDED_DIRS):
        return True
    return any(part.startswith(".") or part == _PYCACHE for part in rel.parts)


def _repo_candidates(repo_root: Path) -> set[str]:
    found: set[str] = set()
    for root_name in CANDIDATE_ROOTS:
        root = repo_root / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = PurePosixPath(path.relative_to(repo_root).as_posix())
            if not _is_excluded(rel):
                found.add(f"{REPO_PREFIX}{rel}")
    return found


def candidate_sources(repo_root: Path) -> tuple[str, ...]:
    """Every file the Ingest must account for, sorted (POST-RET-1).

    Raises:
        ManifestError: ERRORS-RET-1, an 'ok' manifest record has no path, an absolute path or
            a path containing '..'; the message names the record.
        OSError, json.JSONDecodeError: the manifest is missing or malformed (propagated).
    """
    return tuple(sorted(_manifest_candidates(repo_root) | _repo_candidates(repo_root)))


def retained_sources(
    candidates: Sequence[str],
    entries: Sequence[RegistryEntry],
    not_sources: Sequence[NotASource],
) -> RetainedSources:
    """Split candidates into registered sources and listed non-sources (POST-RET-2).

    Raises:
        UnregisteredSourceError: ERRORS-RET-2, a candidate is neither registered nor listed.
        RegistryError: ERRORS-RET-2, a registry entry or listing names no candidate file.
        Both stop the Ingest; the message names the path.
    """
    registered = {entry.path for entry in entries}
    listed = {item.path: item for item in not_sources}
    wanted = set(candidates)
    for path in sorted(wanted - registered - set(listed)):
        raise UnregisteredSourceError(
            f"ERRORS-RET-2 violation: candidate {path!r} is neither a registered source nor "
            "listed as not a source in the registry"
        )
    for path in sorted((registered | set(listed)) - wanted):
        raise RegistryError(
            f"ERRORS-RET-2 violation: the registry names {path!r}, which is not a candidate file"
        )
    return RetainedSources(
        sources=tuple(sorted(wanted & registered)),
        not_sources=tuple(listed[p] for p in sorted(wanted & set(listed))),
    )
