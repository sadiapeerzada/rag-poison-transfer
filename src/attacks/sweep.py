"""Systematic attack x intensity x retriever sweep.

One script that runs the fixed protocol every time: inject poison at a
given attack/intensity/rate, validate it, evaluate against all
retrievers, record results as flat rows. Running this instead of ad-hoc
interactive calls means every number in a comparison table came from
the exact same procedure -- same validation gate, same evaluation code
path -- so differences between rows reflect real differences in
attack/intensity, not accidental inconsistency in how each one was run.
"""
from src.attacks.injection import inject_poisons, validate_poisoned_dataset
from src.attacks.evaluate import evaluate_poison_across_retrievers


def run_attack_intensity_sweep(
    clean_data: dict,
    attacks: dict,
    retrievers: dict,
    n_poison_values: tuple = (1, 3, 5),
    poison_rate: float = 1.0,
    seed: int = 42,
    top_k: int = 10,
) -> list[dict]:
    """
    Run a frozen, reproducible attack-intensity sweep.

    The same attacked query IDs are used for every attack family and
    poison intensity within this sweep. Clean gold labels and clean
    corpus documents are verified before results are recorded.
    """
    import time

    rows = []
    total_conditions = len(attacks) * len(n_poison_values)
    condition_num = 0

    # Freeze the attacked query set ONCE for this sweep.
    n_attacked_queries = round(len(clean_data["queries"]) * poison_rate)

    if n_attacked_queries > 0:
        from src.experiments.protocol import freeze_attack_query_ids

        attacked_query_ids, attacked_query_fingerprint = (
            freeze_attack_query_ids(
                    clean_data["queries"],
                    n_queries=n_attacked_queries,
                    seed=seed,
                )
        )
    else:
        attacked_query_ids = []
        attacked_query_fingerprint = None

    from src.experiments.protocol import (
        corpus_fingerprint,
        query_set_fingerprint,
        assert_same_corpus,
    )

    clean_corpus_fp = corpus_fingerprint(clean_data["corpus"])
    query_set_fp = query_set_fingerprint(clean_data["queries"])

    for attack_name, attack in attacks.items():
        for n_poison in n_poison_values:
            condition_num += 1
            t0 = time.time()

            print(
                f"[{condition_num}/{total_conditions}] "
                f"{attack_name}, n_poison={n_poison}: injecting poison...",
                flush=True,
            )

            poisoned = inject_poisons(
                clean_data,
                attack,
                n_poison=n_poison,
                poison_rate=poison_rate,
                seed=seed,
                attacked_query_ids=attacked_query_ids,
            )

            validation = validate_poisoned_dataset(
                clean_data,
                poisoned,
                expected_n_poison=n_poison,
                expected_poison_rate=poison_rate,
            )

            if not validation["valid"]:
                raise ValueError(
                    f"Poisoned dataset failed validation for "
                    f"attack={attack_name!r}, n_poison={n_poison}, "
                    f"poison_rate={poison_rate}: {validation['checks']}"
                )

            # Verify the frozen attack set was actually respected.
            actual_attacked_ids = sorted(
                q["query_id"]
                for q in poisoned["queries"]
                if q["poison_doc_ids"]
            )

            if actual_attacked_ids != sorted(attacked_query_ids):
                raise ValueError(
                    "Frozen attacked-query set was not respected. "
                    f"Expected {sorted(attacked_query_ids)}, "
                    f"got {actual_attacked_ids}."
                )

            # Verify that clean documents were not modified.
            assert_same_corpus(
                clean_data["corpus"],
                poisoned["corpus"],
            )

            n_attacked = len(actual_attacked_ids)

            print(
                f"    injected ({time.time()-t0:.1f}s), "
                f"evaluating {n_attacked} attacked queries against "
                f"{len(retrievers)} retrievers...",
                flush=True,
            )

            results = evaluate_poison_across_retrievers(
                poisoned,
                retrievers,
                top_k=top_k,
            )

            print(
                f"    done ({time.time()-t0:.1f}s total for this condition)",
                flush=True,
            )

            poisoned_corpus_fp = corpus_fingerprint(
                poisoned["corpus"]
            )

            for retriever_name, r in results.items():
                generator = getattr(attack, "generator", None)

                if generator is not None:
                    generator_model = (
                        getattr(generator, "model_name", None)
                        or generator.__class__.__name__
                    )
                else:
                    generator_model = None

                row = {
                    "attack": attack_name,
                    "n_poison": n_poison,
                    "poison_rate": poison_rate,
                    "retriever": retriever_name,
                    "n_attacked_queries": n_attacked,
                    "n_total_queries": len(poisoned["queries"]),
                    "seed": seed,
                    "top_k": top_k,
                    "generator_model": generator_model,

                    # Frozen experiment identity.
                    "query_set_fingerprint": query_set_fp,
                    "attacked_query_ids": attacked_query_ids,
                    "attacked_query_fingerprint": attacked_query_fingerprint,
                    "clean_corpus_fingerprint": clean_corpus_fp,
                    "poisoned_corpus_fingerprint": poisoned_corpus_fp,

                    "timestamp": __import__("datetime").datetime.now().isoformat(
                        timespec="seconds"
                    ),
                }

                row.update({
                    f"prr@{k}": v
                    for k, v in r["mean_prr"].items()
                })

                rows.append(row)

    return rows
