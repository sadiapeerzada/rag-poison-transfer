#!/usr/bin/env python3
"""Read-only paired-case census and reproducible human semantic-review sampling.

Reads frozen 2Wiki construction/evaluation rows and aggregate. Writes only into
a new EXTERNAL output directory. Never regenerates, filters or changes the study.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

AGGREGATE_SHA = "721d22157920a1d07e124321c6fec999fe02ff23a2bc4af9501bf920d5214b96"
VALID = "valid_construction"

def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for piece in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(piece)
    return digest.hexdigest()

def jread(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)

def measurement(row):
    return row.get("measurement")

def category_cases(d, r, status, family):
    if status != VALID:
        return ["semantic_failure"] if status == "semantic_construction_failed" else ["target_failure"]
    a, b = measurement(d), measurement(r)
    ds, rs = bool(a["poisoned_condition"]["targeted_asr"]), bool(b["poisoned_condition"]["targeted_asr"])
    dc, rc = bool(a["clean_condition"]["answer_correct"]), bool(b["clean_condition"]["answer_correct"])
    de, re = bool(a["poisoned_condition"]["poison_retrieved"]), bool(b["poisoned_condition"]["poison_retrieved"])
    result = ["both_target" if ds and rs else
              "dense_only_target" if ds else "rcd_only_target" if rs else "neither_target"]
    if dc and not rc:
        result.append("dense_only_clean_correct")
    if rc and not dc:
        result.append("rcd_only_clean_correct")
    if de != re:
        result.append("exposure_disagreement")
    if family.startswith("semantic"):
        result.append("semantic_valid")
    return result

def run_audit(run, output, per_stratum):
    run = Path(run).expanduser().resolve(strict=True)
    output = Path(output).expanduser().absolute()
    if run == output or run in output.parents:
        raise ValueError("Output must be outside the frozen run directory")
    if output.exists():
        raise FileExistsError("Audit output already exists; never overwrite")
    aggregate_path = run / "execution/aggregate.json"
    if hash_file(aggregate_path) != AGGREGATE_SHA:
        raise ValueError("Aggregate SHA-256 mismatch")
    agg = jread(aggregate_path)
    if len(agg["cells"]) != 12:
        raise ValueError("Expected 12 frozen cells")
    evaluated = []
    candidates = defaultdict(list)
    counts = Counter()
    for cellname, arms in sorted(agg["cells"].items()):
        family, suffix = cellname.split(".intensity-", 1)
        intensity = int(suffix.split(".seed-")[0])
        seed = int(suffix.split(".seed-")[1])
        ledger = jread(run / "execution/construction" / cellname / "construction.json")
        rows = jread(run / "execution/evaluation" / cellname / "rows.json")
        records = {r["query_id"]: r for r in ledger["records"]}
        by_arm = {(r["pipeline"], r["query_id"]): r for r in rows}
        if len(records) != 300 or len(rows) != 600 or len(by_arm) != 600:
            raise ValueError("Incomplete or duplicated query-arm rows in " + cellname)
        if {key[1] for key in by_arm} != set(records):
            raise ValueError("Query mismatch between construction/evaluation")
        valid_count = sum(1 for r in records.values() if r["status"] == VALID)
        if valid_count != arms["dense"]["valid"] or valid_count != arms["rcd"]["valid"]:
            raise ValueError("Aggregate valid-count mismatch for " + cellname)
        for qid, construction in records.items():
            dense, rcd = by_arm[("dense", qid)], by_arm[("rcd", qid)]
            status = construction["status"]
            if dense["construction_status"] != status or rcd["construction_status"] != status:
                raise ValueError("Paired construction status disagreement")
            a, b = measurement(dense), measurement(rcd)
            if (status == VALID) != (a is not None and b is not None):
                raise ValueError("Malformed missing QA observation")
            cats = category_cases(dense, rcd, status, family)
            row = {
                "cell": cellname,
                "family": family,
                "intensity": intensity,
                "seed": seed,
                "query_id": qid,
                "construction_status": status,
                "categories": ";".join(cats),
                "target_answer": construction.get("target_answer") or "",
                "gold_answer": a.get("gold_answer", "") if a else "",
                "dense_clean_correct": a["clean_condition"]["answer_correct"] if a else "",
                "rcd_clean_correct": b["clean_condition"]["answer_correct"] if b else "",
                "dense_target_success": a["poisoned_condition"]["targeted_asr"] if a else "",
                "rcd_target_success": b["poisoned_condition"]["targeted_asr"] if b else "",
                "dense_poison_visible": a["poisoned_condition"]["poison_retrieved"] if a else "",
                "rcd_poison_visible": b["poisoned_condition"]["poison_retrieved"] if b else "",
                "dense_clean_answer": a["clean_condition"]["answer"] if a else "",
                "rcd_clean_answer": b["clean_condition"]["answer"] if b else "",
                "dense_poisoned_answer": a["poisoned_condition"]["answer"] if a else "",
                "rcd_poisoned_answer": b["poisoned_condition"]["answer"] if b else "",
            }
            evaluated.append(row)
            for cat in cats:
                counts[(family, intensity, cat)] += 1
                candidates[(family, intensity, cat)].append((row, construction, a, b))
        for arm in ("dense", "rcd"):
            computed = sum(bool(by_arm[(arm, qid)]["measurement"]["poisoned_condition"]["targeted_asr"])
                           for qid, record in records.items() if record["status"] == VALID)
            if computed != arms[arm]["end_to_end_targeted_asr"]["numerator"]:
                raise ValueError("Aggregate targeted-ASR numerator mismatch in " + cellname)
    output.mkdir(parents=True)
    with (output / "paired_census.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(evaluated[0]))
        writer.writeheader()
        writer.writerows(evaluated)
    chosen = []
    used_query_ids = set()
    selected_cases = set()
    categories = ("rcd_only_target", "dense_only_target", "dense_only_clean_correct",
                  "rcd_only_clean_correct", "exposure_disagreement", "semantic_valid",
                  "semantic_failure", "neither_target", "both_target", "target_failure")
    for family, intensity in sorted({(r["family"], r["intensity"]) for r in evaluated}):
        for cat in categories:
            pool = candidates.get((family, intensity, cat), [])
            pool = sorted(pool, key=lambda p: hashlib.sha256(
                (f"2wiki-review-v1|{family}|{intensity}|{cat}|"
                 f"{p[0]['query_id']}|{p[0]['seed']}").encode()).hexdigest())
            available = [p for p in pool if (p[0]["cell"], p[0]["query_id"]) not in selected_cases]
            picked = [p for p in available if p[0]["query_id"] not in used_query_ids][:per_stratum]
            if len(picked) < per_stratum:
                picked.extend(p for p in available if p not in picked)
                picked = picked[:per_stratum]
            for row, construction, a, b in picked:
                selected_cases.add((row["cell"], row["query_id"]))
                case_id = hashlib.sha256(
                    (row["cell"] + "|" + row["query_id"]).encode()).hexdigest()[:18]
                used_query_ids.add(row["query_id"])
                attempts = [
                    {"poison_index": item.get("poison_index"),
                     "attempts": [{"outcome": h.get("outcome"), "reason": h.get("reason"),
                                   "generated_text": h.get("generated_text"),
                                   "prompt": h.get("prompt")} for h in item.get("attempts", [])]}
                    for item in construction.get("attempt_records", [])
                ]
                packet = {
                    "case_id": case_id,
                    "sampling_stratum": cat,
                    "family": family,
                    "intensity": intensity,
                    "seed": row["seed"],
                    "query_id": row["query_id"],
                    "construction_status": row["construction_status"],
                    "source_construction_path": "execution/construction/" + row["cell"] + "/construction.json",
                    "source_evaluation_path": "execution/evaluation/" + row["cell"] + "/rows.json",
                    "target_answer": construction.get("target_answer"),
                    "gold_answer": row["gold_answer"],
                    "selection_metadata": construction.get("selection"),
                    "accepted_poison_documents": construction.get("documents", []),
                    "discarded_partial_documents": construction.get("partial_documents", []),
                    "semantic_generation_attempts": attempts,
                    "clean_dense_prompt_including_question": a["clean_condition"]["generation"].get("prompt") if a else None,
                    "dense": {
                        "clean_correct": row["dense_clean_correct"],
                        "clean_answer": row["dense_clean_answer"],
                        "poisoned_answer": row["dense_poisoned_answer"],
                        "target_success": row["dense_target_success"],
                        "poison_visible": row["dense_poison_visible"],
                        "poison_visible_evidence_ids": a["poisoned_condition"].get("generation_evidence_doc_ids") if a else None,
                    },
                    "rcd": {
                        "clean_correct": row["rcd_clean_correct"],
                        "clean_answer": row["rcd_clean_answer"],
                        "poisoned_answer": row["rcd_poisoned_answer"],
                        "target_success": row["rcd_target_success"],
                        "poison_visible": row["rcd_poison_visible"],
                        "poison_visible_evidence_ids": b["poisoned_condition"].get("generation_evidence_doc_ids") if b else None,
                    },
                }
                chosen.append(packet)
    with (output / "review_packet.jsonl").open("w", encoding="utf-8") as f:
        for case in chosen:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
    decision_fields = [
        "case_id", "reviewer_identifier", "review_date", "independent_source_citation",
        "target_is_factually_false_yes_no_uncertain",
        "poison_text_explicitly_asserts_target_yes_no_uncertain",
        "question_constraints_satisfied_yes_no_uncertain",
        "gold_alias_or_comparative_conflict_yes_no_uncertain",
        "answer_extraction_issue_yes_no_uncertain",
        "notes",
    ]
    with (output / "human_review_template.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=decision_fields)
        writer.writeheader()
        for case in chosen:
            writer.writerow({"case_id": case["case_id"]})
    summary = {
        "schema": "rag-poison-transfer.2wiki-read-only-paired-audit/v1",
        "aggregate_sha256": AGGREGATE_SHA,
        "population_query_seed_records": len(evaluated),
        "selected_review_cases": len(chosen),
        "selected_distinct_query_ids": len(used_query_ids),
        "sample_seed": "deterministic SHA-256 2wiki-review-v1",
        "stratum_counts": {"|".join(map(str, k)): v for k, v in sorted(counts.items())},
        "limitations": [
            "No automatic fact-checking or semantic-validity certification",
            "Review packet is local and outcome-revealing, not blinded",
            "Reviewer must examine independent evidence and original question constraints",
            "Three seeds repeat query IDs; no independent-cohort claims",
            "Qualitative review is post hoc and cannot justify modifying frozen results",
            "Do not publish raw prompts, case-level text or IDs before licensing/privacy review",
        ],
    }
    (output / "audit_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("PASS: read-only 3600 construction-record / paired-arm census")
    print("Full paired census:", output / "paired_census.csv")
    print("Human review packet:", output / "review_packet.jsonl")
    print("Human adjudication template:", output / "human_review_template.csv")
    print("Cases selected:", len(chosen), "Distinct query IDs:", len(used_query_ids))
    print("No human semantic judgments have been performed or implied.")

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--per-stratum", type=int, default=4)
    a = p.parse_args()
    if not 1 <= a.per_stratum <= 50:
        p.error("per-stratum must be between 1 and 50")
    run_audit(a.run, a.output, a.per_stratum)

if __name__ == "__main__":
    main()
