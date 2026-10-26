# Validated HotpotQA publication exports

All rates are proportions in CSV/LaTeX; figure axes explicitly show percent or percentage points. All 300 unique questions remain in the primary population. Pooled population 900 denotes query/seed observations, not independent queries. Failure records have no invented QA values. Non-gold targets are label-conditioned, not independently verified falsehoods. Mechanically valid is not a factual/linguistic adjudication.

The paired-effect table reproduces the frozen 2,000-query-cluster bootstrap, seed 20261025. Positive Dense-minus-RCD ASR/degradation/exposure means lower adverse rates for RCD. Intervals are unadjusted for multiplicity. Arm-wise intervals were added solely for descriptive plotting, not new confirmatory tests. Every primary paired ASR interval includes zero; do not claim overall RCD superiority.

Utility, retention, latency and retrieval summaries are conditional on valid constructions and represent the actually measured workload. They are not full-population utility estimates. Outer QA timing includes instrumentation; reported backend timing and retrieval timing are separate. Measurements come from sequential local execution, not a controlled hardware benchmark. RCD changes the number of internal retrieval operations; compare it on matched query/cell cohorts.

Construction coverage and failed semantic attempts must accompany ASR figures. Lower semantic end-to-end ASR does not show stronger defense: most attacks were never constructed. Intensity changes also change the surviving semantic subset. Existing artifacts and the scientific audit are unchanged. No new model experiment was executed by this exporter.
