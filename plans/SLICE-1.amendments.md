# SLICE-1 amendment ledger (QS6)

| Date | Clause(s) | Requirement IDs | Kind | Rationale |
|---|---|---|---|---|
| 2026-11-08 | POST-APP-1, `PERSONA_LENSES` | REQ-18 | requirement change, Decided By: User | Ketema, Z-20: "I have seen the updated prototype. i agree." The lens labels become "Food bank", "Small business lender" and "Both partners"; REQ-18 was amended first (cycle 15, lint 0 errors). |
| 2026-11-08 | POST-APP-1, `COHORT_CARDS` | REQ-18 | clarification, Decided By: User | Ketema: cohort card wording on screen is "not binding". The counts stay binding; the labels in `COHORT_CARDS` are reference wording only. |
| 2026-11-08 | POST-APP-3, `validateCoordinatedBrief`, `NO_REACH_TEXT` | REQ-21 | relaxation, not thin, Decided By: User | Ketema, Z-21: "A." The brief may show a zero reduction, which must equal without minus with, never be negative, and carry `NO_REACH_TEXT`. The old "positive reduction" rule is removed; it was satisfied by a clamp in `src/wizard/alignmentWizard.ts` that faked 0.1 points. |
