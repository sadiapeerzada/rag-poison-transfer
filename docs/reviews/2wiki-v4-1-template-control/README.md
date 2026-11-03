# 2Wiki v4.1 structured-template control — train/development only

Parent: `675398bb03bd216b200361f1e8615a6bed41fbd2`.

## Purpose

This is a **separate, deterministic diagnostic condition**, not a replacement for v4 Qwen generation (historical **0/5 accepted**). Earlier v3's one supported director-birth query and the frozen Week 9/10 held-out runner are unchanged.

- `src/attacks/semantic_typed_evidence_v4_1.py` checks pinned supporting-document IDs and SHA-256 hashes against a caller-provided independent dataset manifest, then checks narrow film → director → person chains and explicit gold labels. It covers country/nationality comparisons and director birthplace/death-place questions. It requires exact gold source membership and refuses unsupported questions.
- `src/attacks/semantic_template_control_v4_1.py` produces three exact deterministic candidate sentence forms and checks normalized-text diversity, **not independent evidence**. C05's third form is revised to the fluent *“Yes, the directors of [A] and [B] are of the same nationality.”*
- Neither module sets `construction_eligible`, `factual_approval`, `injection_approved`, or `heldout_authorized` to true, including when reviewer metadata is supplied.
- Raw training dataset, external review packet and review transcripts are **not committed**. Their hashes and source passages must be verified locally against the frozen training dataset; computing expected hashes from the same untrusted input defeats the integrity check.

## Reviewed development cases

C02 (film directors' country labels), C05 (directors' nationalities), C09 and C13 (director death places), and C11 (director birthplace) were provisionally supported by two AI content reviews based on supplied train documents. This agreement is **not independently authenticated reviewer provenance, truth verification, or injection approval**.

In particular, C02 has two name-variant caveats (Franklin J./James Schaffner, Edward/Edward M. Zwick) and uses **nationality labels** to answer a question worded *“same country”*. Do not erase or reinterpret those caveats. C09 requires the Chrissie White cross-document cue to distinguish the Henry Edwards referent.

The second AI output reported **no run ID or timestamp**; the existing two-AI source-bound gate therefore remains blocked. A subsequently supplied timestamp/run ID would still be self-reported rather than cryptographically authenticated. Do not forge retrospective metadata or silently bypass that gate.

## Tests, limitations and next step

Run `python -m pytest -q tests/test_twowiki_v4_1_template_control.py`, plus the existing v3/v4 regression suite. Tests cover the five supported relation shapes, title/name drift, source substitution, source hashes, negation, duplicate normalized texts, alias conflicts, unsupported forms, missing provenance and held-out refusal.

This is a **review-only diagnostic adapter**. No Qwen model calls, RCD/Dense evaluation, injection or held-out execution. Before any development-only paired evaluation, a separate experiment runner, trustworthy reviewer provenance, and explicit authorization are required. Preserve the v4 0/5 result and treat deterministic templates as a distinct control group.
