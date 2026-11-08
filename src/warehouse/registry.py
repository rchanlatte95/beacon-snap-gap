"""Committed source registry: the stated facts for every retained source, matched exactly.

Specification: contracts/warehouse_contract.py, CONTRACT_REGISTRY (SLICE-3 batch 6b).
Requirements: REQ-25, REQ-26, REQ-29. Runtime declarations are independent of that module;
tests bridge the specification and this implementation (CL11-F).
"""

import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Final

from .provenance import NOT_RECORDED
from .scope import FORMAT_RANK

REGISTRY_FILE: Final = "data/warehouse/source_registry.toml"  # relative to the repository root
_DATE_PATTERN: Final = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class RegistryError(Exception):
    """ERRORS-REG-1: a source registry entry is outside the contracted domain."""


class UnregisteredSourceError(RegistryError):
    """ERRORS-REG-2 / FORBIDDEN-REG-1: a retained file or archive member has no exact entry."""


class ArchiveMemberError(RegistryError):
    """ERRORS-ARCH-1..2: an archive member has no contracted format or cannot be opened."""


MEMBER_FORMAT_BY_EXTENSION: Final[Mapping[str, str]] = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".dat": "dat",
    ".pl": "pl",
    ".txt": "text",
    ".md": "text",
    ".xlsx": "xlsx",
    ".xls": "xls",
    ".json": "json",
    ".geojson": "geojson",
    ".pdf": "pdf",
    ".pptx": "pptx",
    ".shp": "shapefile",
    ".sas7bdat": "sas",
}


@dataclass(frozen=True, slots=True)
class RegistryMember:
    """Scope facts for one member of a series archive."""

    name: str
    file_format: str
    reference_end: str | None
    reference_basis: str


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    """Stated facts for one retained source file."""

    path: str
    ds: str
    group: str
    file_format: str
    reference_end: str | None
    reference_basis: str
    is_base_geography: bool
    release_id: str | None
    publisher: str
    license: str
    as_of: str
    members: tuple[RegistryMember, ...]


def _reference(where: str, raw: Mapping[str, object]) -> tuple[str | None, str]:
    end = raw.get("reference_end")
    if end is None:
        return None, NOT_RECORDED
    if not isinstance(end, str) or not _DATE_PATTERN.match(end):
        raise RegistryError(f"ERRORS-REG-1 violation: {where} reference_end {end!r} is not a date")
    try:
        date.fromisoformat(end)
    except ValueError as exc:
        raise RegistryError(
            f"ERRORS-REG-1 violation: {where} reference_end {end!r} is not a real date"
        ) from exc
    basis = raw.get("reference_basis")
    if not isinstance(basis, str) or not basis.strip():
        raise RegistryError(
            f"ERRORS-REG-1 violation: {where} has reference_end but no reference_basis"
        )
    return end, basis.strip()


def _text(raw: Mapping[str, object], key: str) -> str:
    value = raw.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else NOT_RECORDED


def _required(raw: Mapping[str, object], key: str, path: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"ERRORS-REG-1 violation: entry {path!r} has no {key}")
    return value.strip()


def _format(value: object, where: str) -> str:
    if not isinstance(value, str) or value not in FORMAT_RANK:
        raise RegistryError(
            f"ERRORS-REG-1 violation: {where} file_format {value!r} is not one of "
            f"{sorted(FORMAT_RANK)}"
        )
    return value


def _members(raw: Mapping[str, object], path: str) -> tuple[RegistryMember, ...]:
    listed = raw.get("member", [])
    if not isinstance(listed, list):
        raise RegistryError(f"ERRORS-REG-1 violation: entry {path!r} member is not a list")
    members: list[RegistryMember] = []
    names: set[str] = set()
    for item in listed:
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str) or not name or name in names:
            raise RegistryError(
                f"ERRORS-REG-1 violation: entry {path!r} member name {name!r} is empty or repeated"
            )
        names.add(name)
        where = f"member {name!r} of {path!r}"
        fmt = _format(item.get("file_format"), where)
        end, basis = _reference(where, item)
        members.append(RegistryMember(name, fmt, end, basis))
    return tuple(members)


def load_registry(registry_path: Path) -> tuple[RegistryEntry, ...]:
    """Load the committed registry into one entry per [[source]] (POST-REG-1).

    Raises:
        RegistryError: ERRORS-REG-1, the registry or one of its entries is malformed; the
            message names the entry.
        OSError, tomllib.TOMLDecodeError: the registry file is missing or not TOML (propagated).
    """
    with registry_path.open("rb") as handle:
        data = tomllib.load(handle)
    sources = data.get("source")
    if not isinstance(sources, list) or not sources:
        raise RegistryError("ERRORS-REG-1 violation: the registry has no [[source]] entries")
    entries: list[RegistryEntry] = []
    seen: set[str] = set()
    for raw in sources:
        path = raw.get("path") if isinstance(raw, dict) else None
        if not isinstance(path, str) or not path.strip():
            raise RegistryError(f"ERRORS-REG-1 violation: entry {raw!r} has no path")
        if path in seen:
            raise RegistryError(f"ERRORS-REG-1 violation: path {path!r} is listed twice")
        seen.add(path)
        ds = _required(raw, "ds", path)
        group = _required(raw, "group", path)
        fmt = _format(raw.get("file_format"), f"entry {path!r}")
        end, basis = _reference(f"entry {path!r}", raw)
        release = raw.get("release_id")
        if release is not None and (not isinstance(release, str) or not release.strip()):
            raise RegistryError(f"ERRORS-REG-1 violation: entry {path!r} has an empty release_id")
        entries.append(
            RegistryEntry(
                path=path,
                ds=ds,
                group=group,
                file_format=fmt,
                reference_end=end,
                reference_basis=basis,
                is_base_geography=raw.get("base_geography") is True,
                release_id=release,
                publisher=_text(raw, "publisher"),
                license=_text(raw, "license"),
                as_of=_text(raw, "as_of"),
                members=_members(raw, path),
            )
        )
    return tuple(entries)


def registry_entry(entries: Sequence[RegistryEntry], path: str) -> RegistryEntry:
    """Return the entry whose path equals the retained file's path (POST-REG-2).

    Raises:
        UnregisteredSourceError: ERRORS-REG-2 / FORBIDDEN-REG-1, no entry has this exact path.
    """
    for entry in entries:
        if entry.path == path:
            return entry
    raise UnregisteredSourceError(
        f"ERRORS-REG-2 violation: retained file {path!r} has no exact entry in {REGISTRY_FILE}"
    )


def member_scope(entry: RegistryEntry, member: str) -> tuple[str, str | None]:
    """Return (file_format, reference_end) for an archive member (POST-REG-2).

    Raises:
        ArchiveMemberError: ERRORS-ARCH-1, the member's extension has no contracted format.
        UnregisteredSourceError: ERRORS-REG-2 / FORBIDDEN-REG-1, the entry lists members but
            not this exact one.
    """
    if not entry.members:
        ext = PurePosixPath(member).suffix.lower()
        if ext not in MEMBER_FORMAT_BY_EXTENSION:
            raise ArchiveMemberError(
                f"ERRORS-ARCH-1 violation: member {member!r} of {entry.path!r} has extension "
                f"{ext!r}, which has no contracted format"
            )
        return MEMBER_FORMAT_BY_EXTENSION[ext], entry.reference_end
    for listed in entry.members:
        if listed.name == member:
            return listed.file_format, listed.reference_end
    raise UnregisteredSourceError(
        f"ERRORS-REG-2 violation: member {member!r} of {entry.path!r} has no exact entry in "
        f"{REGISTRY_FILE}"
    )


@dataclass(frozen=True)
class NotASource:
    """A candidate file the registry lists as not a source, with the reason (POST-REG-3)."""

    path: str
    reason: str


def load_not_sources(
    registry_path: Path, entries: Sequence[RegistryEntry]
) -> tuple[NotASource, ...]:
    """Load the registry's [[not_a_source]] listings (POST-REG-3).

    Raises:
        RegistryError: ERRORS-REG-3, a listing has no path or no reason, repeats a path, or
            names a path also registered as a source; the message names the listing.
        OSError, tomllib.TOMLDecodeError: the registry file is missing or not TOML (propagated).
    """
    with registry_path.open("rb") as handle:
        data = tomllib.load(handle)
    listed = data.get("not_a_source", [])
    if not isinstance(listed, list):
        raise RegistryError("ERRORS-REG-3 violation: not_a_source is not a list of tables")
    registered = {entry.path for entry in entries}
    seen: set[str] = set()
    out: list[NotASource] = []
    for raw in listed:
        path = raw.get("path") if isinstance(raw, dict) else None
        reason = raw.get("reason") if isinstance(raw, dict) else None
        if not isinstance(path, str) or not path.strip():
            raise RegistryError(f"ERRORS-REG-3 violation: not_a_source {raw!r} has no path")
        if not isinstance(reason, str) or not reason.strip():
            raise RegistryError(f"ERRORS-REG-3 violation: not_a_source {path!r} has no reason")
        if path in seen:
            raise RegistryError(f"ERRORS-REG-3 violation: not_a_source {path!r} is listed twice")
        if path in registered:
            raise RegistryError(
                f"ERRORS-REG-3 violation: {path!r} is listed as not a source and also registered"
            )
        seen.add(path)
        out.append(NotASource(path=path, reason=reason.strip()))
    return tuple(out)
