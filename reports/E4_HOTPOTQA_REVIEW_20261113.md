# E4 selection and initial factuality review — 13 November 2026

Completed: a sealed 100-case private review packet, 100 distinct questions,
the operator-approved 25-per-family/intensity allocation, and 20 actual
source-assisted factuality annotations. No model initialization, inference,
retrieval, frozen experiment changes or E3 rerun occurred. E4 factuality review
is **partial**, with 80 selected cases unreviewed and zero independent
adjudications. Original results and negative findings are retained unchanged.

The sampling frame contains 4,100 valid source-selected instances from the
historical HotpotQA cohort. Repeated sources/seeds are eligible provenance,
not independent questions. Each selected case retains its three complete poison
documents or single document, original supporting context, and paired Dense,
Reranker and RCD measurements. Protocol, selection/evaluation completion
manifests, every native input read and private output bytes are SHA-256 bound
in [the selection receipt](E4_HOTPOTQA_SELECTION_20261113.json). Reproduction
and evidence rules are in [the review protocol](../docs/protocols/E4_SOURCE_ASSISTED_CASE_REVIEW.md).

| Family / intensity | Eligible instances / questions | Selected | All three target-match | RCD match, baseline disagreement | Baseline match, RCD not | No target, some exposure |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Lexical I1 | 1,620 / 135 | 25 | 7 | 7 | 4 | 7 |
| Lexical I3 | 1,620 / 135 | 25 | 8 | 3 | 7 | 7 |
| Semantic I1 | 560 / 53 | 25 | 10 | 2 | 3 | 10 |
| Semantic I3 | 300 / 31 | 25 | 23 | 0 | 1 | 1 |

No eligible case fell in the no-target/no-exposure bin. Equal five-per-bin
coverage was infeasible. Semantic I3 has very few discordant outcomes and only
31 eligible distinct questions; source/seed repeats do not create new questions.
Scarcity-first selection and global question uniqueness also constrain later
strata. Source/seed counts and achieved bin counts are fully reported. These
100 are a qualitative coverage sample, not a prevalence or generalization test.
Construction failures remain visible in the receipt's assigned status counts;
they are not relabeled successful attacks or factuality-reviewed cases.

The initial review took the first five retained cases per stratum. Because
the packet orders the all-three-target bin first, **all 20 reviewed cases are
from that bin**. This queue is narrower than the full 100-case selection;
discordant and no-target cases remain to be reviewed. Outcomes were visible
to the assistant. No blinded or independent human review is claimed.

| Evidence and finding | Count |
| --- | ---: |
| Native-context-only source-assisted reviews | 15 |
| Reviews with external primary-source corroboration | 5 |
| Reviewed target propositions contradicted by available sources | 15 |
| Reviewed target proposition supported as a valid alternative | 1 |
| Ambiguous, time-sensitive or insufficiently supported conclusions | 4 |
| Unreviewed cases / independently adjudicated cases | 80 / 0 |

The supported target is a substantive negative finding: a target-string match
can select a true alternative to a nonexclusive benchmark answer. Other
reviewed items contain changing membership/representation, a city-versus-region
question defect, or a negative claim not proved by absence from the supplied
context. Approximate birth dates and month rounding require qualification;
some poisons change the referent or invent an authority. The annotations do
not validate every ancillary sentence in multi-document poison sets.

External corroboration used botanical institutions, a music publisher and work
catalogue, parliamentary records, a sports historical institution and official
court-report scans. Full URLs, short excerpts, supported propositions, access
date and incomplete-hop/access limitations are retained privately. Examples of
the primary reference collections are [Kew's botanical record](https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:23394-1/general-information),
[Royal Botanic Gardens Victoria's flora](https://hortflora.rbg.vic.gov.au/taxon/ad8e41b0-5340-11e7-b82b-005056b0018f),
[Schott's work catalogue](https://www.schott-music.com/en/the-devils-of-loudun-no36400.html),
[the Royal Danish Library catalogue](https://www.kb.dk/dcm/cnw/document.xq?doc=cnw0002.xml),
[Parliament's historical address](https://www.aph.gov.au/About_Parliament/Senate/Powers_practice_n_procedures/~/~/link.aspx?_id=E4E0EF43E8864F80B3DCC9A63186EE48&_z=z)
and [the Baseball Hall of Fame account](https://baseballhall.org/discover/inside-pitch/Boggs-jumpstarts-second-half-of-career-with-Yankees).
These independently published sources are distinct from independent
adjudication. Some corroborate one hop only; one parliamentary page was
available through its search extract while direct access returned 403.

[The factuality summary](E4_HOTPOTQA_FACTUALITY_20261113.json) binds the private
packet and annotation ledger. The offline validator checks provenance and
excerpt consistency, not factual truth. No corrected ASR, independent-fact
rate, inter-rater reliability statistic or extrapolation to the full cohort
is warranted. Next work is review of the remaining 80, fuller source chains,
historical/alias checks and actual independent adjudication where feasible.

E1/E2 remain paused under the latest no-inference instruction; see the
[execution-resumption summary](E1_E2_EXECUTION_RESUMPTION_20261113.md).
