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
    Args:
        clean_data: clean {corpus, queries} dataset.
        attacks: dict mapping attack_name -> PoisonAttack instance.
        retrievers: dict mapping retriever_name -> UNBUILT retriever
            instance (e.g. from build_standard_retrievers()). Built once
            by the caller, reused across the sweep -- .build() gets
            called again per condition, but model weights (embedder,
            reranker) load only once, so this is far cheaper than
            reconstructing retrievers each iteration.
        n_poison_values: intensities to sweep (e.g. (1, 3, 5) per the
            research plan).
        poison_rate: global poison rate -- pass a low value separately
            to cover the "low global poison-rate setting" condition.
        seed: shared seed for reproducibility across the whole sweep.
        top_k: retrieval depth for PRR computation.

    Returns:
        Flat list of row dicts, one per (attack, n_poison, retriever)
        combination: {"attack", "n_poison", "poison_rate", "retriever",
        "prr@1", "prr@3", "prr@5", "prr@10", "n_attacked_queries"}.
        Suitable for pandas.DataFrame(rows) directly.

    Raises:
        ValueError if any generated poisoned dataset fails validation
        (gold-label corruption, ID collision, wrong intensity/rate) --
        the sweep refuses to report numbers from data it hasn't verified.
    """
    import time
    rows = []
    total_conditions = len(attacks) * len(n_poison_values)
    condition_num = 0
    for attack_name, attack in attacks.items():
        for n_poison in n_poison_values:
            condition_num += 1
            t0 = time.time()
            print(f"[{condition_num}/{total_conditions}] {attack_name}, n_poison={n_poison}: injecting poison...", flush=True)
            poisoned = inject_poisons(clean_data, attack, n_poison=n_poison, poison_rate=poison_rate, seed=seed)
            validation = validate_poisoned_dataset(
                clean_data, poisoned, expected_n_poison=n_poison, expected_poison_rate=poison_rate
            )
            if not validation["valid"]:
                raise ValueError(
                    f"Poisoned dataset failed validation for attack={attack_name!r}, "
                    f"n_poison={n_poison}, poison_rate={poison_rate}: {validation['checks']}"
                )

            n_attacked = sum(1 for q in poisoned["queries"] if q["poison_doc_ids"])
            print(f"    injected ({time.time()-t0:.1f}s), evaluating {n_attacked} attacked queries against {len(retrievers)} retrievers...", flush=True)
            results = evaluate_poison_across_retrievers(poisoned, retrievers, top_k=top_k)
            print(f"    done ({time.time()-t0:.1f}s total for this condition)", flush=True)

            for retriever_name, r in results.items():
                row = {
                    "attack": attack_name,
                    "n_poison": n_poison,
                    "poison_rate": poison_rate,
                    "retriever": retriever_name,
                    "n_attacked_queries": n_attacked,
                }
                row.update({f"prr@{k}": v for k, v in r["mean_prr"].items()})
                rows.append(row)

    return rows
