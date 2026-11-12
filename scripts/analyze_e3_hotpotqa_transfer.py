#!/usr/bin/env python3
"""Execute aggregate-only E3 analysis of verified native HotpotQA records. No inference."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import numpy as np
from scripts import audit_hotpotqa_transfer_raw_offline as native
from src.evaluation.metrics import exact_match

CANDIDATE_PIN = '97960932066b24f172fc566dd29808dc191cb85aa08cf995ffbd04c91d809f23'
SOURCES = ('bm25', 'dense', 'hybrid', 'reranker')
TARGETS = (*SOURCES, 'rcd')
SEEDS = (42, 43, 44)
FAMILIES = ('lexical_influential_token', 'semantic_fluent_false_evidence')
REPLICATES = 10000
BOOTSTRAP_SEED = 20261112


def read(path):
    return json.loads(Path(path).read_text())


def load_verified(root):
    root = Path(root)
    candidates, selected, evaluation = [root / 'execution' / s for s in ('candidates', 'selection', 'evaluation')]
    native.require_pin(candidates / 'candidates.complete.json', CANDIDATE_PIN)
    receipt = native.audit(root / 'protocol.json', selected, evaluation,
                           root / 'execution/aggregate.json',
                           ROOT / 'paper/results/hotpotqa_transfer_43f3f652460a/aggregate_public.json', candidates)
    seal = read(selected / 'selection.seal.json')
    if seal.get('candidate_library_completion_sha256') != CANDIDATE_PIN:
        raise ValueError('Candidate-selection lineage mismatch')
    population = None
    groups, coverage = {}, []
    for family in FAMILIES:
        for intensity in (1, 3):
            for source in SOURCES:
                rows_by_target = defaultdict(list)
                statuses = Counter()
                for seed in SEEDS:
                    cid = f'{family}.intensity-{intensity}.seed-{seed}'
                    choices = read(selected / 'selected' / cid / f'{source}.json')['records']
                    ids = [x['query_id'] for x in choices]
                    if population is None:
                        population = ids
                    if ids != population:
                        raise ValueError('Cohort/order differs across strata')
                    source_rows = read(evaluation / 'rows' / cid / source / f'{source}.json')
                    statuses.update(x['status'] for x in choices)
                    for target in TARGETS:
                        targets = read(evaluation / 'rows' / cid / source / f'{target}.json')
                        for choice, sr, tr in zip(choices, source_rows, targets):
                            valid = choice['status'] == 'valid_construction'
                            item = {'query_id': choice['query_id'], 'seed': seed, 'valid': valid}
                            if valid:
                                sm, tm = sr['measurement'], tr['measurement']
                                clean, poison = tm['clean_condition'], tm['poisoned_condition']
                                pids = set(tm['poison_doc_ids'])
                                evidence = poison['generation_evidence_doc_ids']
                                exposed = bool(pids.intersection(evidence))
                                if exposed != poison['poison_retrieved']:
                                    raise ValueError('Generator-depth exposure mismatch')
                                source_success = bool(sm['poisoned_condition']['targeted_asr'])
                                target_success = bool(poison['targeted_asr'])
                                clean_target = bool(exact_match(clean['answer'], tm['poison_target_answer']))
                                cc, pc = bool(clean['em']), bool(poison['em'])
                                item.update(source_success=source_success, target_success=target_success,
                                            exposed=exposed, clean_target=clean_target,
                                            clean_correct=cc, poison_correct=pc,
                                            clean_em=clean['em'], poison_em=poison['em'],
                                            clean_f1=clean['f1'], poison_f1=poison['f1'])
                            rows_by_target[target].append(item)
                coverage.append({'family': family, 'intensity': intensity, 'source': source,
                                 'population': len(population) * len(SEEDS), 'status_counts': dict(statuses)})
                for target, rows in rows_by_target.items():
                    groups[(family, intensity, source, target)] = rows
    return population, groups, coverage, receipt


def rate_vectors(rows, ids):
    """Add repeated seeds inside question clusters; no answer imputation on failures."""
    index = {qid: i for i, qid in enumerate(ids)}
    metrics = defaultdict(lambda: np.zeros((len(ids), 2), dtype=float))
    failures = Counter()
    def add(name, i, num, den):
        metrics[name][i] += (float(num), float(den))
    for r in rows:
        i, valid = index[r['query_id']], r['valid']
        add('coverage', i, valid, 1)
        add('end_to_end_target_match', i, valid and r.get('target_success', False), 1)
        if not valid:
            continue
        ss, ts, ex, ct = [r[k] for k in ('source_success', 'target_success', 'exposed', 'clean_target')]
        cc, pc = r['clean_correct'], r['poison_correct']
        for name, num, den in (
            ('source_success_valid', ss, 1), ('target_match_valid', ts, 1),
            ('atr', ss and ts, ss), ('target_given_source_failure', ts and not ss, not ss),
            ('poison_exposure', ex, 1), ('target_given_exposure', ts and ex, ex),
            ('target_given_no_exposure', ts and not ex, not ex),
            ('clean_correct_to_wrong', cc and not pc, cc),
            ('clean_correct_to_target', cc and ts, cc),
            ('clean_incorrect_to_correct', not cc and pc, not cc),
            ('induced_target_match', not ct and ts, not ct),
            ('preexisting_target_persistence', ct and ts, ct),
            ('corruption_given_exposure', cc and not pc and ex, cc and ex),
            ('corruption_given_no_exposure', cc and not pc and not ex, cc and not ex),
            ('clean_em', r['clean_em'], 1), ('poison_em', r['poison_em'], 1),
            ('clean_f1', r['clean_f1'], 1), ('poison_f1', r['poison_f1'], 1),
            ('em_delta', r['poison_em'] - r['clean_em'], 1),
            ('f1_delta', r['poison_f1'] - r['clean_f1'], 1)):
            add(name, i, num, den)
        failures['exposed_target_not_matched'] += int(ex and not ts)
        failures['target_matched_without_visible_poison'] += int(ts and not ex)
        failures['clean_correct_to_wrong_exposed'] += int(cc and not pc and ex)
        failures['clean_correct_to_wrong_unexposed'] += int(cc and not pc and not ex)
        failures['preexisting_target_match'] += int(ct)
        failures['clean_correct_poison_correct'] += int(cc and pc)
        failures['clean_wrong_poison_wrong'] += int(not cc and not pc)
        failures['clean_wrong_poison_correct'] += int(not cc and pc)
    # Ensure undefined metrics survive even if all constructions fail.
    for name in ('atr', 'source_success_valid', 'target_match_valid'):
        _ = metrics[name]
    return dict(metrics), dict(failures)


def ratio(values):
    return np.divide(values[..., 0], values[..., 1],
                     out=np.full(values.shape[:-1], np.nan), where=values[..., 1] != 0)


def interval(samples, level=.95):
    finite = samples[np.isfinite(samples)]
    return {'level': level, 'lower': float(np.quantile(finite, (1-level)/2)) if len(finite) else None,
            'upper': float(np.quantile(finite, (1+level)/2)) if len(finite) else None,
            'undefined_replicates': int(len(samples) - len(finite))}


def bootstrap_weights(n, replicates=REPLICATES, seed=BOOTSTRAP_SEED):
    return np.random.default_rng(seed).multinomial(n, [1/n] * n, size=replicates)


def summarize(ids, groups, coverage, receipt, *, replicates=REPLICATES):
    weights = bootstrap_weights(len(ids), replicates)
    tables, failures, arrays = [], [], {}
    for key, rows in groups.items():
        family, intensity, source, target = key
        conditions = dict(family=family, intensity=intensity, source=source, target=target)
        vectors, taxonomy = rate_vectors(rows, ids)
        arrays[key] = vectors
        failures.append({**conditions, 'counts': taxonomy})
        # One matrix product per group; BLAS overhead dominates tiny products.
        names = list(vectors)
        cube = np.stack([vectors[k] for k in names], axis=1)
        sampled = np.einsum('bq,qmc->bmc', weights, cube, optimize=False)
        total = cube.sum(axis=0)
        for m, name in enumerate(names):
            value = ratio(total[m])
            tables.append({**conditions, 'metric': name, 'numerator': float(total[m, 0]),
                           'denominator': int(total[m, 1]),
                           'estimate': float(value) if np.isfinite(value) else None,
                           'ci': interval(ratio(sampled[:, m]))})
    contrasts = []
    for family in FAMILIES:
        for intensity in (1, 3):
            a = arrays[(family, intensity, 'bm25', 'dense')]['atr']
            b = arrays[(family, intensity, 'dense', 'bm25')]['atr']
            av, bv = ratio(a.sum(axis=0)), ratio(b.sum(axis=0))
            samples = ratio(weights @ a) - ratio(weights @ b)
            contrasts.append({'family': family, 'intensity': intensity,
                              'contrast': 'ATR(bm25->dense) - ATR(dense->bm25)',
                              'estimate': float(av-bv) if np.isfinite(av-bv) else None,
                              'ci': interval(samples, .9875), 'multiplicity': 'Bonferroni family of 4'})
    return {'status': 'EXECUTED_EXISTING_RECORDS_NO_NEW_INFERENCE', 'unique_questions': len(ids),
            'replicates': replicates, 'bootstrap_seed': BOOTSTRAP_SEED,
            'new_qwen_calls': 0, 'raw_verification': receipt,
            'coverage': coverage, 'metrics': tables, 'directional_contrasts': contrasts,
            'failure_case_counts': failures}


def write_outputs(result, output, *, heatmaps=True):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'aggregate.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    with (output / 'metrics.csv').open('w', newline='') as f:
        fields = ['family', 'intensity', 'source', 'target', 'metric', 'numerator', 'denominator', 'estimate', 'ci_lower', 'ci_upper', 'undefined_replicates']
        w = csv.DictWriter(f, fields, lineterminator="\n"); w.writeheader()
        for row in result['metrics']:
            w.writerow({**{k:v for k,v in row.items() if k != 'ci'},
                        'ci_lower': row['ci']['lower'], 'ci_upper': row['ci']['upper'],
                        'undefined_replicates': row['ci']['undefined_replicates']})
    if heatmaps:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        for metric in ('atr', 'end_to_end_target_match', 'poison_exposure', 'clean_correct_to_wrong'):
            fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
            for ax, (family, intensity) in zip(axes.flat, ((f,i) for f in FAMILIES for i in (1,3))):
                lookup = {(r['source'],r['target']):r['estimate'] for r in result['metrics']
                          if r['family']==family and r['intensity']==intensity and r['metric']==metric}
                values = np.array([[lookup.get((s,t)) if lookup.get((s,t)) is not None else np.nan for t in TARGETS] for s in SOURCES])
                im=ax.imshow(values, vmin=0, vmax=1, cmap='viridis')
                ax.set_xticks(range(5), TARGETS); ax.set_yticks(range(4), SOURCES)
                ax.set_title(f'{"Lexical" if family==FAMILIES[0] else "Semantic-fluent"}, intensity {intensity}')
                for i in range(4):
                    for j in range(5):
                        ax.text(j,i,'—' if np.isnan(values[i,j]) else f'{values[i,j]:.1%}',ha='center',va='center',color='white' if values[i,j]<.65 else 'black',fontsize=9)
            fig.suptitle(metric.replace('_',' ') + ' — historical HotpotQA (descriptive)')
            fig.colorbar(im, ax=axes, shrink=.7)
            fig.savefig(output / (metric + '.png'), dpi=180); plt.close(fig)
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
    (output / 'files.sha256.json').write_text(json.dumps(files, indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a=p.parse_args()
    if a.output.exists():
        p.error('Output must be a new directory')
    ids, groups, coverage, receipt=load_verified(a.native_root)
    result=summarize(ids,groups,coverage,receipt)
    result['analysis_spec_sha256']=native.sha256(ROOT/'docs/protocols/E3_TRANSFER_MECHANISMS_ANALYSIS.md')
    write_outputs(result,a.output)
    print(json.dumps({'status':result['status'],'questions':len(ids),'new_qwen_calls':0}))


if __name__=='__main__':
    main()
