"""Archive members: the source members of retained zip archives (POST-ARCH-1, POST-ARCH-2).

Specification: contracts/warehouse_contract.py, CONTRACT_DOCUMENTS (SLICE-3 batch 6c-v):
POST-ARCH-1, POST-ARCH-2, ERRORS-ARCH-1, ERRORS-ARCH-2. Requirements: REQ-25, REQ-26, REQ-28.
Runtime declarations are independent of that module; tests bridge the two (CL11-F).
"""

import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from .reader import SourceReadError
from .registry import ArchiveMemberError, RegistryEntry, member_scope

SHAPEFILE_PART_EXTENSIONS: Final[tuple[str, ...]] = (".cpg", ".dbf", ".prj", ".shx", ".sbn", ".sbx")
VSIZIP_PREFIX: Final = "/vsizip/"

__all__ = [
    "SHAPEFILE_PART_EXTENSIONS",
    "VSIZIP_PREFIX",
    "ArchiveMember",
    "ArchiveMemberError",
    "archive_members",
    "member_source",
]


@dataclass(frozen=True, slots=True)
class ArchiveMember:
    """One source member of a retained archive, with its format and reference end."""

    name: str
    file_format: str
    reference_end: str | None


def _is_skipped(name: str) -> bool:
    parts = PurePosixPath(name).parts
    return name.endswith("/") or any(p == "__MACOSX" or p.startswith(".") for p in parts)


def _is_shapefile_part(name: str, shapefiles: set[str]) -> bool:
    path = PurePosixPath(name)
    stem = str(path.with_suffix(""))
    if path.suffix.lower() in SHAPEFILE_PART_EXTENSIONS and f"{stem}.shp".lower() in shapefiles:
        return True
    lowered = name.lower()
    return lowered.endswith(".xml") and any(lowered.startswith(f"{s}.") for s in shapefiles)


def _names(path: Path) -> list[str]:
    if not path.is_file():
        raise SourceReadError(f"ERRORS-ARCH-1 violation: archive {str(path)!r} is missing")
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.namelist()
    except (zipfile.BadZipFile, OSError) as exc:
        raise SourceReadError(
            f"ERRORS-ARCH-1 violation: archive {str(path)!r} is not a zip archive: {exc}"
        ) from exc


def archive_members(path: Path, entry: RegistryEntry) -> tuple[ArchiveMember, ...]:
    """Return one ArchiveMember per source member, in archive order (POST-ARCH-1).

    Raises:
        ArchiveMemberError: ERRORS-ARCH-1, an unlisted member has no contracted format
            (from member_scope).
        SourceReadError: ERRORS-ARCH-1, the archive is missing or not a zip archive.
    """
    kept = [n for n in _names(path) if not _is_skipped(n)]
    shapefiles = {n.lower() for n in kept if n.lower().endswith(".shp")}
    out: list[ArchiveMember] = []
    for name in kept:
        if _is_shapefile_part(name, shapefiles):
            continue
        file_format, reference_end = member_scope(entry, name)
        out.append(ArchiveMember(name, file_format, reference_end))
    return tuple(out)


def member_source(path: Path, member: str, workdir: Path) -> str:
    """Return the reader's source for one member (POST-ARCH-2).

    A shapefile is read in place through VSIZIP_PREFIX; any other member is extracted into
    workdir and its extracted file is returned.

    Raises:
        ArchiveMemberError: ERRORS-ARCH-2, the member is not in the archive or cannot be
            extracted.
    """
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ArchiveMemberError(
            f"ERRORS-ARCH-2 violation: archive {str(path)!r} cannot be opened for {member!r}: {exc}"
        ) from exc
    with archive:
        if member not in archive.namelist():
            raise ArchiveMemberError(
                f"ERRORS-ARCH-2 violation: member {member!r} is not in archive {str(path)!r}"
            )
        if member.lower().endswith(".shp"):
            return f"{VSIZIP_PREFIX}{path}/{member}"
        try:
            # ZipFile.extract drops absolute and '..' parts, so the file stays inside workdir.
            return archive.extract(member, path=workdir)
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            raise ArchiveMemberError(
                f"ERRORS-ARCH-2 violation: member {member!r} of {str(path)!r} cannot be "
                f"extracted: {exc}"
            ) from exc
