"""Document-identity poison detection using authentic RCD candidate diagnostics.

Suspicion is a predeclared heuristic, not a learned detector or an NLI
factuality judgement. Threshold is tuned on development *only*.
Do not interpret these labels as verified false statements.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict

SCHEMA = "rag-poison-transfer.rcd-document-poison-detection/v1"
SUSPICION_POLICY = "0.7*(1-mean_agreement_stability)+0.3*year_conflict/v1"


def _rate(value, field):
    if type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Invalid or out-of-range " + field)
    return float(value)


def extract_labeled_candidates(row):
    if not isinstance(row, dict) or not isinstance(row.get("query_id"), (str, int)):
        raise ValueError("Malformed per-question retrieval record")
    qid = str(row["query_id"]).strip()
    if not qid or row.get("condition") != "poisoned":
        raise ValueError("Expected an identifiable poisoned-corpus retrieval query")
    poison_ids = row.get("known_global_poison_doc_ids")
    if not isinstance(poison_ids, list) or any(not isinstance(x, str) or not x for x in poison_ids):
        raise ValueError("Missing authentic global injected-document identity labels")
    if len(poison_ids) != len(set(poison_ids)):
        raise ValueError("Duplicate injected-document identity label")
    diagnostics = row.get("diagnostics")
    if not isinstance(diagnostics, dict):
        raise ValueError("Missing genuine RCD last_diagnostics")
    signals, conflicts, scores = (diagnostics.get("consistency_signals"),
                                  diagnostics.get("conflict_scores"), diagnostics.get("scores"))
    if not isinstance(signals, dict) or not isinstance(conflicts, dict) or not isinstance(scores, dict) or not scores:
        raise ValueError("Incomplete candidate-level RCD diagnostic signals")
    labels = set(poison_ids)
    result = []
    for doc_id in sorted(scores):
        if doc_id not in signals or doc_id not in conflicts or not isinstance(signals[doc_id], dict):
            raise ValueError("Missing diagnostic signal for candidate document")
        signal = signals[doc_id]
        agreement = _rate(signal.get("agreement"), "agreement")
        rank_stability = _rate(signal.get("rank_stability"), "rank_stability")
        rewrite_stability = _rate(signal.get("rewrite_stability"), "rewrite_stability")
        conflict = _rate(conflicts[doc_id], "temporal_conflict")
        mean_consistency = (agreement + rank_stability + rewrite_stability) / 3
        suspicion = 0.7 * (1 - mean_consistency) + 0.3 * conflict
        result.append({"query_id": qid, "doc_id": doc_id,
                       "label": int(doc_id in labels), "score": suspicion})
    return result, len(labels), len(set(scores) & labels)


def _validate_binary(records):
    if not isinstance(records, list) or not records:
        raise ValueError("Empty detection cohort")
    if any(type(x.get("label")) is not int or x["label"] not in (0, 1)
           or type(x.get("score")) not in (int, float) or not math.isfinite(x["score"])
           or not (0 <= x["score"] <= 1) for x in records):
        raise ValueError("Invalid detection labels/scores")
    positive = sum(x["label"] for x in records)
    negatives = len(records) - positive
    if not positive or not negatives:
        raise ValueError("Both poison and clean candidate labels are required")
    return positive, negatives


def auroc(records):
    """Mann-Whitney AUROC with average ranks for equal scores."""
    positive, negative = _validate_binary(records)
    ordered = sorted(records, key=lambda r: r["score"])
    rank_sum = 0.
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and ordered[j]["score"] == ordered[i]["score"]:
            j += 1
        avg_rank = ((i + 1) + j) / 2
        rank_sum += avg_rank * sum(x["label"] for x in ordered[i:j])
        i = j
    return (rank_sum - positive * (positive + 1) / 2) / (positive * negative)


def average_precision(records):
    """Step-wise average precision, deterministic under score ties."""
    positives, _ = _validate_binary(records)
    ordered = sorted(records, key=lambda r: -r["score"])
    total_positive = 0
    accum = 0.
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and ordered[j]["score"] == ordered[i]["score"]:
            j += 1
        new_positives = sum(x["label"] for x in ordered[i:j])
        total_positive += new_positives
        if new_positives:
            accum += new_positives / positives * (total_positive / j)
        i = j
    return accum


def confusion(records, threshold):
    if type(threshold) not in (int, float) or not math.isfinite(threshold):
        raise ValueError("Invalid prediction threshold")
    tp = fp = tn = fn = 0
    for row in records:
        pred = int(row["score"] >= threshold)
        if pred and row["label"]: tp += 1
        elif pred: fp += 1
        elif row["label"]: fn += 1
        else: tn += 1
    precision = tp / (tp + fp) if tp + fp else 0.
    recall = tp / (tp + fn) if tp + fn else 0.
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.
    return {"tp":tp,"fp":fp,"tn":tn,"fn":fn,
            "precision":precision,"recall":recall,"f1":f1,
            "false_positive_rate":fp / (fp + tn) if fp + tn else None}


def choose_threshold(dev_records):
    """Maximize dev F1; ties use highest threshold to reduce false positives."""
    _validate_binary(dev_records)
    candidates = sorted({r["score"] for r in dev_records} | {1.0000000000000002}, reverse=True)
    return max(candidates, key=lambda t: (confusion(dev_records, t)["f1"], t))


def summarize(records, threshold):
    positives, negatives = _validate_binary(records)
    return {"n_candidate_observations": len(records),
            "n_positive_observations": positives,
            "n_negative_observations": negatives,
            "positive_prevalence": positives/len(records),
            "auroc": auroc(records), "average_precision": average_precision(records),
            "threshold": threshold, "at_threshold": confusion(records, threshold)}



def query_cluster_bootstrap(test_rows, threshold, *, reps=2000, seed=20261109):
    """Nominal percentile CIs resampling whole question clusters, not candidate rows.

    The dev-selected threshold stays fixed in every test resample. Some
    resamples can lack a positive or negative, so the defined replicate count
    is reported separately; no unobserved scores or labels are synthesized.
    """
    if type(reps) is not int or not 100 <= reps <= 100000:
        raise ValueError("Bootstrap replicates must be an integer in [100,100000]")
    if type(seed) is not int:
        raise ValueError("Deterministic bootstrap integer seed required")
    groups = []
    seen = set()
    for row in test_rows:
        if row.get("query_id") in seen:
            raise ValueError("Repeated question cluster in test set")
        seen.add(row.get("query_id"))
        items, _, _ = extract_labeled_candidates(row)
        groups.append(items)
    if not groups:
        raise ValueError("Empty test clusters")
    rng = random.Random(seed)
    metrics = {name: [] for name in ("auroc", "average_precision", "f1", "false_positive_rate")}
    for _ in range(reps):
        sample = [item for _ in groups
                  for item in groups[rng.randrange(len(groups))]]
        try:
            _validate_binary(sample)
        except ValueError:
            continue
        cm = confusion(sample, threshold)
        values = {"auroc": auroc(sample), "average_precision": average_precision(sample),
                  "f1": cm["f1"], "false_positive_rate": cm["false_positive_rate"]}
        for name, value in values.items():
            if value is not None:
                metrics[name].append(value)
    output = {}
    for key, values in metrics.items():
        vals = sorted(values)
        if not vals:
            output[key] = {"ci95_percentile": None, "defined_replicates": 0}
        else:
            n = len(vals)
            output[key] = {
                "ci95_percentile": [vals[int((n - 1) * 0.025)],
                                    vals[int((n - 1) * 0.975)]],
                "defined_replicates": n,
            }
    return {"resampling_unit": "whole questions with all candidate observations",
            "bootstrap_replicates": reps, "seed": seed, "threshold_refit_on_test": False,
            "nominal_unadjusted": True, "metrics": output}


def evaluate(dev_rows, test_rows, *, forbid_shared_documents=False,
             bootstrap_replicates=2000, bootstrap_seed=20261109):
    """Evaluate a new corpus-level identity detector. No per-item exports."""
    def build(rows):
        if not isinstance(rows, list) or not rows:
            raise ValueError("Empty dev/test question cohort")
        seen = set()
        samples = []
        total_injected = total_observed_injected = 0
        for row in rows:
            qid = str(row.get("query_id", ""))
            if qid in seen:
                raise ValueError("Duplicate question observation in cohort")
            seen.add(qid)
            items, n_injected, n_observed = extract_labeled_candidates(row)
            samples.extend(items)
            total_injected += n_injected
            total_observed_injected += n_observed
        _validate_binary(samples)
        return samples, seen, total_injected, total_observed_injected

    dev, dev_ids, dev_known, dev_visible = build(dev_rows)
    test, test_ids, test_known, test_visible = build(test_rows)
    if dev_ids & test_ids:
        raise ValueError("Development/test question IDs overlap")
    dev_docids = {x["doc_id"] for x in dev}
    test_docids = {x["doc_id"] for x in test}
    shared_documents = len(dev_docids & test_docids)
    if forbid_shared_documents and shared_documents:
        raise ValueError("Development/test candidate documents overlap; cannot claim document-disjoint holdout")
    threshold = choose_threshold(dev)
    return {"schema":SCHEMA,
            "status":"POISON_IDENTITY_DETECTION_EVALUATED_EXPLORATORY",
            "suspicion_policy":SUSPICION_POLICY,
            "threshold_selected_only_on_development":True,
            "n_development_queries":len(dev_ids),
            "n_test_queries":len(test_ids),
            "n_shared_candidate_document_ids_across_cohorts":shared_documents,
            "document_disjoint":shared_documents == 0,
            "development_injected_poison_query_sum":dev_known,
            "development_visible_injected_poison_query_sum":dev_visible,
            "test_injected_poison_query_sum":test_known,
            "test_visible_injected_poison_query_sum":test_visible,
            "development":summarize(dev,threshold),
            "test":summarize(test,threshold),
            "test_query_cluster_bootstrap_ci95": query_cluster_bootstrap(
                test_rows, threshold, reps=bootstrap_replicates, seed=bootstrap_seed),
            "limitations":[
                "Positive label = known injected poison document identity, NOT independently verified factual falsehood.",
                "Score is a predeclared uncalibrated combination of rank-instability and year-conflict heuristics.",
                "Candidate-only detection excludes injected documents absent from the retrieved candidate pool.",
                "Candidate observations can repeat the same document; count is NOT number of independent documents.",
                "Shared document IDs across cohorts risk leakage and are disclosed; require disjointness for stronger claims.",
                "Test bootstrap resamples questions, keeping candidate rows together; it does not establish document-level independence or external label quality.",
                "Bootstrap intervals are nominal and not multiplicity-adjusted; the dev threshold is held fixed.",
                "No LLM inference or new poison construction is performed by this evaluation."
            ]}
