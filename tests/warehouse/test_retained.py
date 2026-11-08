"""RED tests for SLICE-3 batch 6c: the retained-source rule.

CONTRACT AUTHORITY RECORD:
- File: contracts/warehouse_contract.py (CONTRACT_RETAINED)
- Authority: AUTHORITATIVE for the warehouse and its Ingest (SLICE-3)
- Clauses covered: POST-RET-1, ERRORS-RET-1, POST-REG-3, ERRORS-REG-3, POST-RET-2, ERRORS-RET-2
- Requirements: REQ-25, REQ-26, REQ-48

The implementations are src/warehouse/retained.py and src/warehouse/registry.py. They do not
import the contract (CL11-F); these tests import both.

FOUR-CRITERIA TEST VALIDITY GATE (both tests):
  C1 VALID: every assertion cites a clause present in CONTRACT_RETAINED.
  C2 VALUABLE: the exact candidate list from a built repository tree, exact refusals by name
     for bad manifest records, unregistered candidates, stale entries and bad listings.
  C3 NON-DUPLICATIVE: test 1 pins which files are candidates; test 2 pins how candidates are
     split and when the split stops the Ingest.
  C4 NOT FUTURE-EDIT: every assertion enforces a current clause.
"""

import json
import tomllib
from pathlib import Path

import pytest
from contracts import warehouse_contract as contract
from src.warehouse import registry as reg_impl
from src.warehouse import retained as impl

# Risk tier: HIGH. A wrong candidate rule silently drops a listed source (as DS-B4, DS-B5 and
# DS-B9 were dropped) or loads code and configuration as data.


def _touch(root: Path, rel: str, text: str = "x") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _manifest(root: Path, records: list[dict[str, object]]) -> None:
    _touch(root, contract.MANIFEST_FILE, "\n".join(json.dumps(r) for r in records) + "\n")


def test_candidates_come_from_the_manifest_and_the_source_folders(tmp_path: Path):
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract expected_cache_key(), MANIFEST_FILE, CANDIDATE_ROOTS,
      EXCLUDED_DIRS
    - Enforces: POST-RET-1, ERRORS-RET-1
    - Category: positive, negative, boundary
    - Risk tier: HIGH
    - Pyramid level: Integration (a repository tree on disk)
    - Equivalence partition: manifest ok, ok-then-blocked, error; a cache file with no record;
      files under data/, docs/, excluded folders, hidden files and __pycache__; manifest records
      with an absolute path, a '..' path and no path.
    """
    _manifest(
        tmp_path,
        [
            {"path": "sba/a.csv", "status": "ok"},
            {"path": "cbpp/terms.md", "status": "ok"},
            {"path": "cbpp/terms.md", "status": "blocked"},
            {"path": "x/failed.csv", "status": "error"},
        ],
    )
    for rel in (
        "data/cache/sba/a.csv",
        "data/cache/unlisted.csv",
        "data/hackathon/b.csv",
        "data/external/tool.py",
        "data/warehouse/source_registry.toml",
        "data/.hidden.csv",
        "data/__pycache__/x.pyc",
        "docs/brief.md",
        "docs/resources/r.pdf",
        "docs/mockups/m.md",
        "docs/.notes/n.md",
    ):
        _touch(tmp_path, rel)
    got = impl.candidate_sources(tmp_path)
    want = (
        "cache:sba/a.csv",
        "repo:data/external/tool.py",
        "repo:data/hackathon/b.csv",
        "repo:docs/brief.md",
        "repo:docs/resources/r.pdf",
    )
    assert got == want, (
        "test_candidates_come_from_the_manifest_and_the_source_folders FAILED\n"
        "POST-RET-1 violation: the candidate files differ\n"
        f"EXPECTED: {want!r}\n"
        f"ACTUAL: {got!r}\n"
        "GUIDANCE: manifest paths whose latest record is ok, plus files under data/ and docs/ "
        "outside the excluded folders, hidden files and __pycache__, sorted"
    )
    assert contract.expected_cache_key({"path": "sba/a.csv", "status": "ok"}) == want[0]

    for label, record in (
        ("absolute", {"path": "/Users/someone/data/cache/sba/a.csv", "status": "ok"}),
        ("dot-dot", {"path": "../outside.csv", "status": "ok"}),
        ("no path", {"status": "ok", "url": "https://example.org/a.csv"}),
    ):
        with pytest.raises(contract.ManifestError):
            contract.expected_cache_key(record)
        _manifest(tmp_path, [record])
        with pytest.raises(impl.ManifestError) as caught:
            impl.candidate_sources(tmp_path)
        assert "ERRORS-RET-1" in str(caught.value), (
            "test_candidates_come_from_the_manifest_and_the_source_folders FAILED\n"
            f"ERRORS-RET-1 violation for {label}: the refusal does not cite the clause\n"
            "EXPECTED: ManifestError citing ERRORS-RET-1 and naming the record\n"
            f"ACTUAL: {caught.value!s}\n"
            "GUIDANCE: an ok manifest record needs a path relative to the cache folder"
        )

    assert (
        impl.MANIFEST_FILE,
        impl.CACHE_DIR,
        tuple(impl.CANDIDATE_ROOTS),
        tuple(impl.EXCLUDED_DIRS),
        impl.CACHE_PREFIX,
        impl.REPO_PREFIX,
    ) == (
        contract.MANIFEST_FILE,
        contract.CACHE_DIR,
        contract.CANDIDATE_ROOTS,
        contract.EXCLUDED_DIRS,
        contract.CACHE_PREFIX,
        contract.REPO_PREFIX,
    ), (
        "test_candidates_come_from_the_manifest_and_the_source_folders FAILED\n"
        "POST-RET-1 violation: candidate rule constants differ from the contract\n"
        "EXPECTED: the contract's manifest file, cache folder, roots, excluded folders, prefixes\n"
        "ACTUAL: different values\n"
        "GUIDANCE: the candidate rule's locations equal the contract's"
    )


REGISTRY_TEXT = """
[[source]]
path = "repo:docs/brief.md"
ds = "DS-B1"
group = "docs"
file_format = "text"

[[source]]
path = "cache:sba/a.csv"
ds = "DS-X5"
group = "sba"
file_format = "csv"

[[not_a_source]]
path = "repo:data/external/tool.py"
reason = "project code that produced a committed extract"
"""


def test_every_candidate_is_registered_or_listed_and_no_entry_is_stale(tmp_path: Path):
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract validate_not_sources(), expected_retained()
    - Enforces: POST-REG-3, ERRORS-REG-3, POST-RET-2, ERRORS-RET-2
    - Category: positive, negative
    - Risk tier: HIGH
    - Pyramid level: Unit (TOML file on disk)
    - Equivalence partition: candidates all covered; an unregistered candidate; a stale source
      entry; a stale listing; listings with no reason, repeated, or also registered.
    """
    reg_file = tmp_path / "source_registry.toml"
    reg_file.write_text(REGISTRY_TEXT)
    entries = reg_impl.load_registry(reg_file)
    got_ns = reg_impl.load_not_sources(reg_file, entries)
    c_entries = contract.validate_registry(tomllib.loads(REGISTRY_TEXT))
    want_ns = contract.validate_not_sources(tomllib.loads(REGISTRY_TEXT), c_entries)
    assert [(n.path, n.reason) for n in got_ns] == [(n.path, n.reason) for n in want_ns], (
        "test_every_candidate_is_registered_or_listed_and_no_entry_is_stale FAILED\n"
        "POST-REG-3 violation: not-a-source listings differ from the registry\n"
        f"EXPECTED: {[(n.path, n.reason) for n in want_ns]!r}\n"
        f"ACTUAL: {[(n.path, n.reason) for n in got_ns]!r}\n"
        "GUIDANCE: one listing per [[not_a_source]] with its path and reason"
    )

    candidates = ("cache:sba/a.csv", "repo:data/external/tool.py", "repo:docs/brief.md")
    got = impl.retained_sources(candidates, entries, got_ns)
    want = contract.expected_retained(candidates, c_entries, want_ns)
    assert (got.sources, [n.path for n in got.not_sources]) == (
        want.sources,
        [n.path for n in want.not_sources],
    ), (
        "test_every_candidate_is_registered_or_listed_and_no_entry_is_stale FAILED\n"
        "POST-RET-2 violation: the split into sources and non-sources differs\n"
        f"EXPECTED: {want.sources!r} and {[n.path for n in want.not_sources]!r}\n"
        f"ACTUAL: {got.sources!r} and {[n.path for n in got.not_sources]!r}\n"
        "GUIDANCE: registered candidates are sources; listed candidates are not, with reasons"
    )

    unregistered = (*candidates, "repo:docs/resources/r.pdf")
    with pytest.raises(impl.UnregisteredSourceError) as caught_u:
        impl.retained_sources(unregistered, entries, got_ns)
    assert "repo:docs/resources/r.pdf" in str(caught_u.value), (
        "test_every_candidate_is_registered_or_listed_and_no_entry_is_stale FAILED\n"
        "ERRORS-RET-2 violation: an unregistered candidate was not refused by name\n"
        "EXPECTED: UnregisteredSourceError naming 'repo:docs/resources/r.pdf'\n"
        f"ACTUAL: {caught_u.value!s}\n"
        "GUIDANCE: a candidate must be registered or listed as not a source"
    )
    for stale_label, cands in (
        ("stale source entry", ("repo:data/external/tool.py", "repo:docs/brief.md")),
        ("stale listing", ("cache:sba/a.csv", "repo:docs/brief.md")),
    ):
        with pytest.raises(contract.RegistryError):
            contract.expected_retained(cands, c_entries, want_ns)
        with pytest.raises(reg_impl.RegistryError) as caught_s:
            impl.retained_sources(cands, entries, got_ns)
        assert not isinstance(caught_s.value, reg_impl.UnregisteredSourceError), (
            "test_every_candidate_is_registered_or_listed_and_no_entry_is_stale FAILED\n"
            f"ERRORS-RET-2 violation for {stale_label}: wrong refusal\n"
            "EXPECTED: RegistryError naming the registry line with no file\n"
            f"ACTUAL: {type(caught_s.value).__name__}: {caught_s.value!s}\n"
            "GUIDANCE: a registry line that names no candidate file stops the Ingest"
        )

    base = '[[source]]\npath = "p"\nds = "d"\ngroup = "g"\nfile_format = "csv"\n'
    for label, text in (
        ("no reason", f'{base}[[not_a_source]]\npath = "q"\n'),
        (
            "repeated",
            f'{base}[[not_a_source]]\npath = "q"\nreason = "r"\n'
            '[[not_a_source]]\npath = "q"\nreason = "r"\n',
        ),
        ("also a source", f'{base}[[not_a_source]]\npath = "p"\nreason = "r"\n'),
    ):
        with pytest.raises(contract.RegistryError):
            contract.validate_not_sources(
                tomllib.loads(text), contract.validate_registry(tomllib.loads(text))
            )
        bad = tmp_path / f"bad_{label.replace(' ', '_')}.toml"
        bad.write_text(text)
        with pytest.raises(reg_impl.RegistryError):
            reg_impl.load_not_sources(bad, reg_impl.load_registry(bad))
