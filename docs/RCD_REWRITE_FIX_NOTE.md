# RCD query-rewrite fix (branch `fix/rcd-query-rewrites`)

Fixes two defects in `src/defenses/rcd/rewrites.py::_generic_rewrites`:

1. **AUDIT-020** - `"which "` is 6 characters but the code sliced `q[7:]`, so
   "Which city ..." became "what ity ...". Now `"what " + q[len("which "):]`.
2. **Case-sensitive who/where/when/how replacements** - the branches matched on
   `lowered.startswith(...)` but replaced capitalized strings ("Who ", "Where ",
   ...), so lowercase or upper-case inputs produced an unchanged candidate that
   was dropped as a duplicate. They now slice by prefix length and prepend the
   intended replacement, independent of the input's capitalization.

Tests: the strict `xfail` for AUDIT-020 in `tests/test_audit_regressions.py` is
now a normal passing test, with case/whitespace variants and lowercase,
title-case, mixed-case and upper-case coverage of all four branches.

## Research-integrity statement

This changes RCD behaviour. **Historical results produced with the old
implementation (e.g. exp_022-exp_031, including exp_026 and exp_028b) have not
been regenerated, modified, or relabelled.** No experiment was rerun, and no
model/API calls or poison generation were performed. Affected RCD results may
require a protocol-approved rerun before publication. Frozen configs, dataset
manifests, fingerprints and result files are untouched. Not changed (out of
scope): the generic rewrite lowercases only the first character, so an
all-caps input such as "WHICH ..." yields "wHICH ...".
