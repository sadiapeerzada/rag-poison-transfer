"""Poison injection: apply a PoisonAttack to a clean dataset.

Guarantees enforced here (not just documented, but checked):
  - gold_doc_ids and gold_answer are never modified for any query.
  - poison doc IDs never collide with clean corpus doc IDs.
  - unattacked queries get poison_doc_ids = [] (explicit, not absent).

This is what makes the result usable directly by the existing retrieval/
generation/metrics pipeline: it is a superset of a clean dataset, with
extra corpus entries and one extra field per query.
"""
import random


def inject_poisons(
    data: dict,
    attack,
    n_poison: int = 1,
    poison_rate: float = 1.0,
    seed: int = 42,
) -> dict:
    """Inject poison documents into a clean {corpus, queries} dataset.

    Args:
        data: clean dataset, as returned by src/data/loaders.py
            (must have "corpus": list[{doc_id, text}] and
            "queries": list[{query_id, question, gold_answer,
            gold_doc_ids, ...}]).
        attack: a PoisonAttack instance.
        n_poison: number of poison documents per attacked query
            (the "attack intensity" -- 1, 3, or 5 per the research plan).
        poison_rate: fraction of queries to attack (1.0 = all; a lower
            value simulates the "low global poison-rate setting" from
            the research plan).
        seed: for reproducible query selection and attack content.

    Returns:
        New dataset dict (does not mutate the input). Every query keeps
        its original gold_doc_ids/gold_answer unchanged, plus a new
        "poison_doc_ids" field (empty list if this query wasn't
        attacked) and "attack_family" (None if not attacked).
    """
    rng = random.Random(seed)
    queries = data["queries"]
    # Deep-copy each corpus dict, not just the list -- otherwise poisoned
    # and clean corpora share the same dict objects, and mutating one
    # (e.g. in a downstream pipeline step) silently corrupts the other.
    corpus = [dict(d) for d in data["corpus"]]
    existing_ids = {d["doc_id"] for d in corpus}

    n_to_attack = round(len(queries) * poison_rate)
    attacked_ids = set(
        rng.sample([q["query_id"] for q in queries], n_to_attack)
    ) if n_to_attack > 0 else set()

    new_queries = []
    for query in queries:
        query_copy = dict(query)  # shallow copy -- gold_doc_ids/gold_answer
                                    # values are never reassigned below,
                                    # so they remain byte-identical to the
                                    # input.
        if query["query_id"] in attacked_ids:
            poison_ids_for_query = []
            for i in range(n_poison):
                doc = attack.generate(query, queries, rng, poison_index=i)
                if doc.doc_id in existing_ids:
                    raise ValueError(
                        f"Poison doc ID collision: {doc.doc_id!r} already "
                        "exists in corpus (clean or previously-injected "
                        "poison). This should not happen with correctly "
                        "query-scoped poison IDs -- investigate the attack "
                        "implementation."
                    )
                existing_ids.add(doc.doc_id)
                corpus.append({"doc_id": doc.doc_id, "text": doc.text})
                poison_ids_for_query.append(doc.doc_id)
            query_copy["poison_doc_ids"] = poison_ids_for_query
            query_copy["attack_family"] = attack.name
        else:
            query_copy["poison_doc_ids"] = []
            query_copy["attack_family"] = None
        new_queries.append(query_copy)

    return {"corpus": corpus, "queries": new_queries}


def validate_poisoned_dataset(
    clean_data: dict,
    poisoned_data: dict,
    expected_n_poison: int | None = None,
    expected_poison_rate: float | None = None,
    poison_rate_tolerance: float = 0.05,
) -> dict:
    """Validate a poisoned dataset against its clean source.

    This is the "benchmark validation report" the research plan requires
    before poisoned data can be used in real experiments: proof that
    injection did not corrupt ground truth and behaved as configured.

    Returns a dict: {"valid": bool, "checks": {check_name: bool}, "details": {...}}.
    "valid" is True only if every check passes.
    """
    checks = {}
    details = {}

    clean_by_id = {q["query_id"]: q for q in clean_data["queries"]}
    poisoned_by_id = {q["query_id"]: q for q in poisoned_data["queries"]}

    # 1. Same set of queries, nothing added or dropped.
    checks["same_query_set"] = set(clean_by_id) == set(poisoned_by_id)

    # 2. Gold labels byte-identical for every query.
    gold_mismatches = []
    for qid, clean_q in clean_by_id.items():
        poisoned_q = poisoned_by_id.get(qid)
        if poisoned_q is None:
            continue
        if poisoned_q.get("gold_answer") != clean_q.get("gold_answer"):
            gold_mismatches.append((qid, "gold_answer"))
        if poisoned_q.get("gold_doc_ids") != clean_q.get("gold_doc_ids"):
            gold_mismatches.append((qid, "gold_doc_ids"))
    checks["gold_labels_untouched"] = len(gold_mismatches) == 0
    details["gold_mismatches"] = gold_mismatches

    # 3. Every clean corpus doc still present, unmodified, in the poisoned corpus.
    clean_corpus_by_id = {d["doc_id"]: d["text"] for d in clean_data["corpus"]}
    poisoned_corpus_by_id = {d["doc_id"]: d["text"] for d in poisoned_data["corpus"]}
    clean_docs_missing_or_changed = [
        doc_id for doc_id, text in clean_corpus_by_id.items()
        if poisoned_corpus_by_id.get(doc_id) != text
    ]
    checks["clean_corpus_preserved"] = len(clean_docs_missing_or_changed) == 0
    details["clean_docs_missing_or_changed"] = clean_docs_missing_or_changed

    # 4. No poison doc_id collides with a clean doc_id.
    poison_ids_all = [
        pid for q in poisoned_data["queries"] for pid in q.get("poison_doc_ids", [])
    ]
    collisions = [pid for pid in poison_ids_all if pid in clean_corpus_by_id]
    checks["no_poison_clean_id_collisions"] = len(collisions) == 0
    details["id_collisions"] = collisions

    # 5. No duplicate poison doc_ids anywhere.
    checks["no_duplicate_poison_ids"] = len(poison_ids_all) == len(set(poison_ids_all))

    # 6. Poison count per attacked query matches expected_n_poison, if given.
    if expected_n_poison is not None:
        wrong_counts = [
            (qid, len(q["poison_doc_ids"]))
            for qid, q in poisoned_by_id.items()
            if q.get("poison_doc_ids") and len(q["poison_doc_ids"]) != expected_n_poison
        ]
        checks["poison_count_matches_intensity"] = len(wrong_counts) == 0
        details["wrong_poison_counts"] = wrong_counts

    # 7. Global poison rate matches expected_poison_rate, if given.
    if expected_poison_rate is not None:
        n_attacked = sum(1 for q in poisoned_data["queries"] if q.get("poison_doc_ids"))
        actual_rate = n_attacked / len(poisoned_data["queries"]) if poisoned_data["queries"] else 0.0
        checks["poison_rate_matches_request"] = abs(actual_rate - expected_poison_rate) <= poison_rate_tolerance
        details["actual_poison_rate"] = actual_rate

    details["checks"] = checks
    return {"valid": all(checks.values()), "checks": checks, "details": details}
