"""Outcome-independent Week 9 construction and failure-aware paired accounting.

No reviewed rows, approvals, dataset loading or model loading are created here.
"""
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import random

from src.attacks import development_targets_v2 as v2
from src.attacks.development_targets_v3 import nominate
from src.attacks.reviewed_target_artifact import _normalized
from src.attacks.lexical import LexicalInfluentialTokenAttack
from src.attacks.semantic_fluent import (SemanticFluentFalseEvidenceAttack, SemanticQualityError,
    SEMANTIC_PROMPT_VERSION, SEMANTIC_VALIDATION_VERSION, SEMANTIC_RETRY_POLICY)
from src.attacks.base import poison_doc_id
from src.attacks import semantic_profiles
from src.evaluation.metrics import exact_match, f1_score
from src.evaluation.qa_records import validate_qa, summarize_observations
from src.experiments.protocol import corpus_fingerprint, query_set_fingerprint

VERSION = "week9-outcome-independent-construction/v1"
CELL_SCHEMA = "rag-poison-transfer.week9-protocol-construction-cell/v1"
ROW_SCHEMA = "rag-poison-transfer.week9-protocol-evaluation-row/v1"
VALID = "valid_construction"
TARGET_FAILED = "target_construction_failed"
SEMANTIC_FAILED = "semantic_construction_failed"
ATTACKS = ("lexical_influential_token", "semantic_fluent_false_evidence")
SEEDS = (42, 43, 44)
INTENSITIES = (1, 3)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def cells(scope="heldout"):
    return [(a, i, s) for a in ATTACKS for i in (INTENSITIES if scope == "heldout" else (1,))
            for s in (SEEDS if scope == "heldout" else (42,))]


def cell_id(family, intensity, seed):
    return f"{family}.intensity-{intensity}.seed-{seed}"


def rules():
    return {"version": VERSION, "heldout_population": 300, "query_selection_seed": 42,
        "attacks": list(ATTACKS), "intensities": list(INTENSITIES), "poison_seeds": list(SEEDS),
        "target_method": "frozen-development-v3-mechanics-promoted-label-conditioned/v1",
        "candidate_pool": "exact-pinned-development-artifact-only",
        "candidate_order": "canonical UTF-8 JSON order; SHA256(seed,query_id,target-selection) modulo candidate count",
        "target_scope": "same query/seed target across both families and intensities; no replacement on generation failure",
        "gold_exclusion": "normalized gold plus explicitly supplied aliases; completeness not assumed",
        "factual_limit": "label-conditioned non-gold/type-compatible nominations, not independently established factual falsehood",
        "lexical_repeat_factor": 4, "semantic_max_tokens": 150, "semantic_max_attempts_per_document": 2,
        "semantic_prompt": SEMANTIC_PROMPT_VERSION, "semantic_validator": SEMANTIC_VALIDATION_VERSION,
        "retry_policy": SEMANTIC_RETRY_POLICY, "decoding": {"temperature": 0.0, "sampler": "explicit greedy"},
        "seed_derivation": "first 8 SHA256 bytes of canonical [version,poison_seed,query_id,stage,index], modulo 2**32",
        "qa_seed": 42, "semantic_generation": "greedy; model/backend numerical reproducibility not guaranteed; retain exact outputs",
        "partial_documents": "all declared indices attempted; partials archived but NONE injected if count differs from intensity",
        "infrastructure_errors": "abort, preserve progress; never relabel as scientific construction failure",
        "failure_policy": "Option2: failed zero end-to-end successes; no fake QA, retrieval or defense-success values",
        "barrier": "seal every declared construction cell before any final Dense/RCD generation or retrieval",
        "uncertainty": "paired query-cluster bootstrap across all poison seeds; 2000 replicates; seed 20261025; percentile 95%",
        "outcome_adaptation": "forbidden; frozen failures never retried as a new scientific attempt"}


def derived_seed(seed, qid, stage, index=0):
    return int.from_bytes(hashlib.sha256(canonical([VERSION, seed, qid, stage, index])).digest()[:8], "big") % 2**32


def select_target(query, development, seed, *, target_method=None, scope=None):
    if target_method is None:
        nomination = nominate(query, development, v2.build_pool(development))
    else:
        from src.attacks.development_targets_v5 import method_module
        method = method_module(target_method.get("identifier"))
        method.validate(target_method,scope)
        nomination = method.nominate(query,development)
    candidates = sorted(nomination["candidates"], key=canonical)
    if not candidates:
        return None, {"reason": nomination["reason"], "method_family": nomination["method_family"]}
    candidate = candidates[derived_seed(seed, query["query_id"], "target-selection") % len(candidates)]
    aliases = { _normalized(query["gold_answer"]), *(_normalized(a) for a in query.get("gold_aliases", [])) }
    if _normalized(candidate["answer"]) in aliases:
        raise ValueError("Nomination violated gold/alias exclusion")
    # v3 was development-only. Explicitly relabel question-local constructions,
    # without pretending the held-out destination is a verified development row.
    provenance = dict(candidate["provenance"])
    provenance["source_kind"] = {
        "verified_development_question_options": "protocol_destination_question_options",
        "verified_development_gold_transformation": "protocol_destination_label_transformation",
        "verified_development_gold_set_and_country_label": "destination_label_set_and_development_country_source",
    }.get(provenance["source_kind"], provenance["source_kind"])
    return candidate["answer"], {"method_family": nomination["method_family"], "mechanism": candidate["mechanism"],
        "answer_category": candidate["answer_category"], "provenance": provenance,
        "validation_status": "mechanical_label_conditioned_not_independently_verified"}


def construct_query(query, development, family, intensity, seed, generator, *, set_runtime_seed, semantic_profile=None, scope=None, target_method=None):
    if semantic_profile is not None:semantic_profiles.validate(semantic_profile,scope)
    target, selection = select_target(query, development, seed,**({"target_method":target_method,"scope":scope} if target_method is not None else {}))
    record = {"query_id": query["query_id"], "query_fingerprint": fingerprint(query), "target_answer": target,
              "selection": selection, "documents": [], "partial_documents": [], "attempt_records": [],
              "declared_document_seeds":{str(i):derived_seed(seed,query["query_id"],family,i) for i in range(intensity)}}
    if semantic_profile is not None:record["semantic_profile_sha256"]=fingerprint(semantic_profile)
    if target_method is not None:record["target_method_sha256"]=fingerprint(target_method)
    if target is None:
        return {**record, "status": TARGET_FAILED}
    attack = (LexicalInfluentialTokenAttack(repeat_factor=4) if family == ATTACKS[0]
              else semantic_profiles.attack(generator,semantic_profile,scope))
    if family == ATTACKS[1]:
        attack.capture_smoke_diagnostics = True
    documents = []
    for index in range(intensity):
        runtime_seed = derived_seed(seed, query["query_id"], family, index)
        set_runtime_seed(runtime_seed)
        try:
            document = attack.generate(query, [query], random.Random(runtime_seed), index, target)
            documents.append(asdict(document))
        except SemanticQualityError:
            # Predetermined budget exhausted; do not select a different target.
            pass
    if family == ATTACKS[1]:
        record["attempt_records"] = attack.export_attempt_records()
    if len(documents) != intensity:
        return {**record, "status": SEMANTIC_FAILED, "partial_documents": documents}
    return {**record, "status": VALID, "documents": documents}


def validate_cell(cell, clean, development, protocol_sha, *, semantic_profile=None, scope=None, development_study=None, target_method=None):
    if semantic_profile is not None:semantic_profiles.validate(semantic_profile,scope)
    if target_method is not None:
        from src.attacks.development_targets_v5 import method_module
        method = method_module(target_method.get("identifier"))
        method.validate(target_method,scope)
    if cell.get("target_method")!=target_method:raise ValueError("Cell target method mismatch")
    if cell.get("development_study")!=development_study:raise ValueError("Cell development study mismatch")
    if development_study is not None:
        from src.experiments.semantic_development_study import descriptor
        if development_study!=descriptor() or scope!="development":raise ValueError("Invalid development study cell")
    if cell.get("semantic_profile")!=semantic_profile:
        raise ValueError("Construction cell semantic profile mismatch")
    family, intensity, seed = cell["family"], cell["intensity"], cell["seed"]
    if (cell.get("schema") != CELL_SCHEMA or cell.get("protocol_sha256") != protocol_sha or
        family not in ATTACKS or type(intensity) is not int or type(seed) is not int or intensity not in INTENSITIES or seed not in SEEDS or
        cell.get("query_set_fingerprint") != query_set_fingerprint(clean["queries"]) or
        cell.get("clean_corpus_fingerprint") != corpus_fingerprint(clean["corpus"])):
        raise ValueError("Construction cell protocol/data provenance mismatch")
    records = cell.get("records", [])
    if [r["query_id"] for r in records] != [q["query_id"] for q in clean["queries"]]:
        raise ValueError("Construction ledger dropped, duplicated or reordered population IDs")
    for query, row in zip(clean["queries"], records):
        if row.get("target_method_sha256")!=(fingerprint(target_method) if target_method is not None else None):raise ValueError("Query target method mismatch")
        expected_profile=fingerprint(semantic_profile) if semantic_profile is not None else None
        if row.get("semantic_profile_sha256")!=expected_profile:raise ValueError("Query semantic profile mismatch")
        target, selection = select_target(query, development, seed,**({"target_method":target_method,"scope":scope} if target_method is not None else {}))
        if row.get("query_fingerprint") != fingerprint(query) or row.get("target_answer") != target or row.get("selection") != selection:
            raise ValueError("Frozen target/query/selection mismatch")
        status = row.get("status")
        if row.get("declared_document_seeds") != {str(i):derived_seed(seed,query["query_id"],family,i) for i in range(intensity)}:
            raise ValueError("Construction RNG seed provenance mismatch")
        if target is None:
            if status != TARGET_FAILED or row.get("documents") or row.get("partial_documents") or row.get("attempt_records"):
                raise ValueError("Malformed target-construction failure")
            continue
        docs = row.get("documents", [])
        partials = row.get("partial_documents", [])
        if status == VALID:
            if len(docs) != intensity or partials:
                raise ValueError("Intensity requires exactly the declared valid document count")
        elif status == SEMANTIC_FAILED:
            if family != ATTACKS[1] or docs or len(partials) >= intensity:
                raise ValueError("Partial construction must fail without injected documents")
        else:
            raise ValueError("Unknown construction status")
        indices = []
        for doc in [*docs, *partials]:
            index = doc["poison_index"]
            if (type(index) is not int or not 0 <= index < intensity or doc["query_id"] != query["query_id"] or
                doc["target_answer"] != target or doc["attack_family"] != family or
                doc["doc_id"] != poison_doc_id(family, query["query_id"], index, doc["text"])):
                raise ValueError("Poison document identity mismatch")
            indices.append(index)
            if family == ATTACKS[1]:
                semantic_profiles.attack(object(),semantic_profile,scope)._validate_text(doc["text"], query, target)
            else:
                expected = LexicalInfluentialTokenAttack(4).generate(query, [query], random.Random(0), index, target)
                if asdict(expected) != doc:
                    raise ValueError("Lexical bytes differ from frozen construction rules")
        if len(set(indices)) != len(indices):
            raise ValueError("Duplicate document index")
        if family == ATTACKS[1]:
            attempts = row.get("attempt_records", [])
            if len(attempts) != intensity or sorted(a["poison_index"] for a in attempts) != list(range(intensity)):
                raise ValueError("Missing attempt-level semantic construction provenance")
            successful = []
            attack = semantic_profiles.attack(object(),semantic_profile,scope)
            for entry in attempts:
                index = entry["poison_index"]
                history = entry["attempts"]
                if entry["query_id"] != query["query_id"] or not 1 <= len(history) <= 2:
                    raise ValueError("Invalid semantic attempt history")
                for number, event in enumerate(history, 1):
                    prompt = attack._build_prompt(query["question"], target, index)
                    if number > 1:
                        prompt += attack._revision_instruction(history[number-2].get("reason"))
                    if (event.get("attempt") != number or event.get("prompt_revision") != number-1 or
                        event.get("prompt") != prompt or event.get("validation_version") != attack.validation_version or
                        event.get("prompt_version") != attack.prompt_version or
                        event.get("retry_policy") != attack.retry_policy):
                        raise ValueError("Semantic prompt/version/attempt mismatch")
                    try:
                        verdict = attack._validate_text(event["generated_text"].strip(), query, target)
                    except SemanticQualityError as exc:
                        verdict = exc.status
                        if not event.get("reason"):
                            raise ValueError("Rejected attempt lacks rejection reason")
                        if semantic_profile is not None and event["reason"]!=str(exc):
                            raise ValueError("Profiled rejection reason differs from replay")
                    if event.get("outcome") != verdict:
                        raise ValueError("Semantic attempt verdict mismatch")
                    if verdict == "heuristically_supported_unverified":
                        if number != len(history):
                            raise ValueError("Retried after successful construction")
                        successful.append(index)
                        doc = next((d for d in [*docs, *partials] if d["poison_index"] == index), None)
                        if not doc or doc["text"] != event["generated_text"].strip():
                            raise ValueError("Accepted attempt/document mismatch")
                if index not in successful and len(history) != 2:
                    raise ValueError("Failed semantic construction did not exhaust frozen retry budget")
            if set(successful) != set(indices):
                raise ValueError("Semantic successes and retained document indices differ")
    return cell


def replay(clean, cell):
    by_id = {r["query_id"]: r for r in cell["records"]}
    corpus = [dict(d) for d in clean["corpus"]]
    queries = []
    for query in clean["queries"]:
        row = by_id[query["query_id"]]
        if row["status"] != VALID:
            continue
        corpus.extend({"doc_id": d["doc_id"], "text": d["text"]} for d in row["documents"])
        queries.append({**query, "poison_target_answer": row["target_answer"],
                        "poison_doc_ids": [d["doc_id"] for d in row["documents"]]})
    if len({d["doc_id"] for d in corpus}) != len(corpus):
        raise ValueError("Poison/corpus document ID collision")
    return {"corpus": corpus, "queries": queries}


def rate(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator/denominator if denominator else None}


def summarize(rows):
    if not rows:
        raise ValueError("Missing population records")
    valid = [r for r in rows if r["construction_status"] == VALID]
    successes = sum(r["measurement"]["poisoned_condition"]["targeted_asr"] for r in valid)
    clean_correct = sum(r["measurement"]["clean_condition"]["answer_correct"] for r in valid)
    degradation = sum(r["measurement"]["query_untargeted_degradation"] for r in valid)
    exposed = [r for r in valid if r["measurement"]["poisoned_condition"]["poison_retrieved"]]
    return {"attempted": len(rows), "valid": len(valid), "failed": len(rows)-len(valid), "evaluated": len(valid),
        "failure_categories": dict(Counter(r["construction_status"] for r in rows if r["construction_status"] != VALID)),
        "construction_coverage": rate(len(valid), len(rows)), "end_to_end_targeted_asr": rate(successes, len(rows)),
        "conditional_targeted_asr_valid": rate(successes, len(valid)),
        "untargeted_degradation_valid": rate(degradation, len(valid)),
        "untargeted_degradation_clean_correct_valid": rate(degradation, clean_correct),
        "poison_exposure_valid": rate(len(exposed), len(valid)),
        "asr_given_exposure_valid": rate(sum(r["measurement"]["poisoned_condition"]["targeted_asr"] for r in exposed), len(exposed)),
        "clean_em_valid": rate(clean_correct, len(valid)),
        "poisoned_em_valid": rate(sum(r["measurement"]["poisoned_condition"]["answer_correct"] for r in valid), len(valid)),
        "prr_at_k_valid": {str(k): rate(sum(r["measurement"]["poisoned_condition"]["prr_at_k"][str(k)] for r in valid),len(valid)) for k in (1,3,5,10)},
        "clean_f1_valid": rate(sum(r["measurement"]["clean_condition"]["f1"] for r in valid),len(valid)),
        "poisoned_f1_valid": rate(sum(r["measurement"]["poisoned_condition"]["f1"] for r in valid),len(valid)),
        "measurement_records_valid":summarize_observations(
            [r["measurement"]["clean_condition"] for r in valid],
            [r["measurement"]["poisoned_condition"] for r in valid]) if valid else None}


def validate_evaluation_rows(rows, cell, clean, seal_sha):
    from src.attacks.asr import build_prompt
    by_query = {q["query_id"]: q for q in clean["queries"]}
    expected = [(pipeline, r["query_id"]) for pipeline in ("dense", "rcd") for r in cell["records"]]
    if [(r.get("pipeline"),r.get("query_id")) for r in rows] != expected:
        raise ValueError("Evaluation population/pairing incomplete or reordered")
    construction = {r["query_id"]:r for r in cell["records"]}
    clean_text = {d["doc_id"]:d["text"] for d in clean["corpus"]}
    poison_text = {d["doc_id"]:d["text"] for r in cell["records"] for d in r["documents"]}
    for row in rows:
        ledger = construction[row["query_id"]]
        if (row.get("schema") != ROW_SCHEMA or row.get("construction_seal_sha256") != seal_sha or
            row.get("cell_fingerprint") != fingerprint(cell) or row.get("construction_status") != ledger["status"]):
            raise ValueError("Evaluation/construction provenance mismatch")
        paired = row.get("measurement")
        if ledger["status"] != VALID:
            if paired is not None or row.get("evaluation_status") != "not_evaluated_construction_failed":
                raise ValueError("Failed construction must not fabricate evaluation values")
            continue
        if row.get("evaluation_status") != "evaluated" or not isinstance(paired, dict):
            raise ValueError("Valid construction lacks complete evaluation")
        query = by_query[row["query_id"]]
        ids = sorted(d["doc_id"] for d in ledger["documents"])
        if (paired.get("query_id") != row["query_id"] or paired.get("pipeline") != row["pipeline"] or
            paired.get("gold_answer") != query["gold_answer"] or paired.get("poison_target_answer") != ledger["target_answer"] or
            paired.get("poison_doc_ids") != ids):
            raise ValueError("Matched poison/target/gold identity mismatch")
        for key in ("clean_condition", "poisoned_condition"):
            observation = paired[key]
            validate_qa(observation["generation"],observation["answer"])
            answer = observation["generation"]["extracted_answer"]
            correct = bool(exact_match(answer, query["gold_answer"]))
            if (observation["answer"] != answer or observation["answer_correct"] != correct or
                observation["em"] != float(correct) or observation["f1"] != f1_score(answer,query["gold_answer"])):
                raise ValueError("QA metric/raw-response inconsistency")
            texts = clean_text if key == "clean_condition" else {**clean_text,**poison_text}
            retrieved = observation["retrieved_doc_ids"]
            visible = observation["generation_evidence_doc_ids"]
            if (len(set(retrieved)) != len(retrieved) or len(set(visible)) != len(visible) or
                any(d not in texts for d in [*retrieved,*visible])):
                raise ValueError("Unknown/duplicate retrieval evidence IDs")
            if observation["retrieved_evidence"] != [{"doc_id":d,"text":texts[d]} for d in retrieved]:
                raise ValueError("Retrieval evidence bytes differ from matched corpus")
            if observation["generation"]["prompt"] != build_prompt(query["question"],[texts[d] for d in visible]):
                raise ValueError("QA prompt not bound to actual generator-visible evidence")
            # RCD's independent top-3 and diagnostic top-10 need not be prefixes.
            # Validate actual windows separately rather than substituting exposure.
            ranks = [i+1 for i,d in enumerate(retrieved) if d in ids]
            if (observation["poison_retrieved"] != bool(set(ids)&set(visible)) or
                observation["poison_rank"] != (min(ranks) if ranks else None) or
                observation["prr_at_k"] != {str(k):float(bool(set(ids)&set(retrieved[:k]))) for k in (1,3,5,10)}):
                raise ValueError("Retrieval/exposure/rank metric inconsistency")
        poisoned = paired["poisoned_condition"]
        if poisoned["targeted_asr"] != bool(exact_match(poisoned["answer"],ledger["target_answer"])):
            raise ValueError("Targeted outcome mismatch")
        if paired["query_untargeted_degradation"] != (paired["clean_condition"]["answer_correct"] and not poisoned["answer_correct"]):
            raise ValueError("Untargeted outcome mismatch")
    return rows


def bootstrap_paired(by_seed, query_ids, replicates=2000, seed=20261025):
    """Recompute denominators while resampling paired query clusters, never seed rows."""
    if replicates < 1:
        raise ValueError("Bootstrap replicate count must be positive")
    indexed = {s:{(r["pipeline"],r["query_id"]):r for r in rows} for s,rows in by_seed.items()}
    metrics = ("end_to_end_targeted_asr", "conditional_targeted_asr_valid", "untargeted_degradation_valid", "poison_exposure_valid")
    def difference(chosen, metric):
        values = {}
        for p in ("dense","rcd"):
            selected = [indexed[s][(p,q)] for s in sorted(indexed) for q in chosen]
            valid = [r["measurement"] for r in selected if r["construction_status"] == VALID]
            denominator = len(selected) if metric == "end_to_end_targeted_asr" else len(valid)
            if metric in {"end_to_end_targeted_asr","conditional_targeted_asr_valid"}:
                numerator = sum(r["poisoned_condition"]["targeted_asr"] for r in valid)
            elif metric == "untargeted_degradation_valid":
                numerator = sum(r["query_untargeted_degradation"] for r in valid)
            else:
                numerator = sum(r["poisoned_condition"]["poison_retrieved"] for r in valid)
            values[p] = numerator/denominator if denominator else None
        return None if None in values.values() else values["dense"]-values["rcd"]
    rng = random.Random(seed)
    samples = {m:[] for m in metrics}
    for _ in range(replicates):
        chosen = rng.choices(query_ids,k=len(query_ids))
        for m in metrics:
            value = difference(chosen,m)
            if value is not None:
                samples[m].append(value)
    result = {}
    for m,values in samples.items():
        ordered = sorted(values)
        result[m] = {"dense_minus_rcd": difference(query_ids,m),
            "ci95_percentile": [ordered[int((len(ordered)-1)*p)] for p in (.025,.975)] if ordered else None,
            "defined_replicates":len(ordered), "undefined_replicates":replicates-len(ordered)}
    return {"resampling_unit":"query_id cluster retaining all seeds and both arms", "unique_queries":len(query_ids),
            "poison_seeds":sorted(by_seed), "bootstrap_seed":seed, "replicates":replicates, "metrics":result}
