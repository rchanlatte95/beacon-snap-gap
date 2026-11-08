# SLICE-3 amendment ledger (QS6 thin changes)

| Date | Clause(s) | Requirement IDs | Kind | Rationale |
|---|---|---|---|---|
| 2026-11-08 | all of `CONTRACT_SCOPE` (no clause text changed) | REQ-25, REQ-26 | style | Reformatted `contracts/warehouse_contract.py` to pass the python-mastery gates added in `pyproject.toml` (ruff `UP035`, `UP045`, format; `from __future__ import annotations` dropped on Python 3.14). Constants, validators, exceptions and clause texts are unchanged; `check_runtime_enforceable.py` still passes. |
