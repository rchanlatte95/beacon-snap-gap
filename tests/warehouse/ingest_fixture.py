"""Test fixture: a small repository the Ingest can build a warehouse from.

Cache files are listed in data/cache/MANIFEST.jsonl (the downloader's record), repository files
sit under data/ and docs/, and data/warehouse/source_registry.toml registers every one.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

LOANS = b"LoanID,BorrState,GrossApproval\nL1,FL,100\nL2,TX,200\nL5,FL,500,extra\nL4,NY,400\n"
OLD = b"a,b\n1,2\n"
DICTIONARY = (
    b"Field Name,Definition\nBorrState,Borrower state\nGrossApproval,Amount approved\n , \n"
)
TRACTS = b"GEO_ID,Pop\n1400000US12095016510,4200\n1400000US48001000100,900\n"
NOTES = b"Notes inside the archive.\n"
README = "# Fixture readme\n\nA repository document.\n"
URL = "https://example.org/fixture/loans.csv"
TS = "2026-11-07T10:00:00Z"

REGISTRY = """
[[source]]
path = "cache:grp/loans.csv"
ds = "DS-T1"
group = "grp"
file_format = "csv"
reference_end = "2025-09-30"
reference_basis = "fixture"
publisher = "Fixture Agency"
license = "CC0"
as_of = "2025-09-30"

[[source]]
path = "cache:grp/loans_copy.csv"
ds = "DS-T1"
group = "grp"
file_format = "csv"
reference_end = "2025-09-30"
reference_basis = "fixture"

[[source]]
path = "cache:grp/old.csv"
ds = "DS-T2"
group = "grp"
file_format = "csv"
reference_end = "2020-01-01"
reference_basis = "fixture"

[[source]]
path = "cache:grp/dictionary.csv"
ds = "DS-T1"
group = "grp"
file_format = "csv"

[[source]]
path = "cache:grp/bundle.zip"
ds = "DS-T3"
group = "grp"
file_format = "csv"
reference_end = "2024-12-31"
reference_basis = "fixture"

[[source]]
path = "repo:docs/readme.md"
ds = "REPO-DOC"
group = "docs"
file_format = "text"

[[not_a_source]]
path = "repo:data/external/tool.py"
reason = "fixture code"

[[glossary]]
path = "cache:grp/dictionary.csv"
term = "Field Name"
definition = "Definition"
"""


def build_repo(root: Path) -> Path:
    """Write the fixture repository at root and return root."""
    cache = root / "data" / "cache" / "grp"
    cache.mkdir(parents=True)
    (cache / "loans.csv").write_bytes(LOANS)
    (cache / "loans_copy.csv").write_bytes(LOANS)
    (cache / "old.csv").write_bytes(OLD)
    (cache / "dictionary.csv").write_bytes(DICTIONARY)
    with zipfile.ZipFile(cache / "bundle.zip", "w") as z:
        z.writestr("tracts.csv", TRACTS)
        z.writestr("notes.txt", NOTES)
        z.writestr("__MACOSX/._tracts.csv", b"\x00")
    records = [
        {
            "path": f"grp/{n}",
            "status": "ok",
            "url": URL if n == "loans.csv" else f"https://example.org/{n}",
            "ts": TS,
        }
        for n in ("loans.csv", "loans_copy.csv", "old.csv", "dictionary.csv", "bundle.zip")
    ]
    (root / "data" / "cache" / "MANIFEST.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8"
    )
    (root / "data" / "external").mkdir(parents=True)
    (root / "data" / "external" / "tool.py").write_text("print('fixture')\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "readme.md").write_text(README, encoding="utf-8")
    (root / "data" / "warehouse").mkdir(parents=True)
    (root / "data" / "warehouse" / "source_registry.toml").write_text(REGISTRY, encoding="utf-8")
    return root
