#!/usr/bin/env python3
"""Read sealed native artifacts; select an outcome-stratified qualitative review.

No model imports, inference, retrieval, or modifications to native artifacts.
The private packet contains benchmark text; only its aggregate receipt is public.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

FAMILIES = ('lexical_influential_token', 'semantic_fluent_false_evidence')
SOURCES = ('bm25', 'dense', 'hybrid', 'reranker')
TARGETS = ('dense', 'reranker', 'rcd')
BINS = ('all_three_target', 'rcd_only_or_discordant_target',
        'baseline_target_rcd_not', 'no_target_exposed', 'no_target_unexposed')
PINS = {
    'protocol.json': '94e4b6d8fb49a7e662074fb766c92498ad0667abf9cf38233e0f49aa401183aa',
    'execution/selection/selection.seal.json': '3f9217c83a7c1309763468be1cf2e57ebcd0ecd726a44c57b4eaa4d61ab3b750',
    'execution/evaluation/transfer.complete.json': '72343b04134f8d6f24815d731af52c644d517dba042754236f9e7f089316c191',
}
CLEAN_PIN = 'e73b36144364c6c5e9586ea7d3be8a57c69294a2215c0dcd73ed84cac402725b'
DESIGN = {
    'schema': 'e4-qualitative-sampling/v1', 'seed': 20261113,
    'allocation': '25 per family/intensity; 100 total',
    'unit': 'valid source-selected question/family/intensity/seed/source attack instance',
    'targets': list(TARGETS), 'bins': list(BINS), 'desired_per_bin_per_stratum': 5,
    'stratum_order': ['semantic I3', 'semantic I1', 'lexical I3', 'lexical I1'],
    'selection': 'hash order; five per bin; then least-filled available bin until 25',
    'uniqueness': 'one question globally; fail rather than silently relax',
    'scope': 'historically exposed HotpotQA; valid constructions only; qualitative, not prevalence',
    'factuality_blinding': 'selection precedes review; outcomes retained for mechanism analysis',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode()


def read(path, expected=None):
    data = Path(path).read_bytes()
    if expected is not None and digest(data) != expected:
        raise ValueError(f'Artifact hash mismatch: {path.name}')
    return json.loads(data)


def outcome_bin(measurements):
    matches = [bool(measurements[t]['poisoned_condition']['targeted_asr']) for t in TARGETS]
    exposed = any(set(m['poison_doc_ids']) & set(m['poisoned_condition']['generation_evidence_doc_ids'])
                  for m in measurements.values())
    if all(matches):
        return BINS[0]
    if matches[2]:
        return BINS[1]
    if any(matches[:2]):
        return BINS[2]
    return BINS[3] if exposed else BINS[4]


def load_frame(root, clean_path):
    root = Path(root)
    manifests = {p: read(root / p, h) for p, h in PINS.items()}
    selection = manifests['execution/selection/selection.seal.json']
    evaluation = manifests['execution/evaluation/transfer.complete.json']
    if evaluation['selection_seal_sha256'] != PINS['execution/selection/selection.seal.json']:
        raise ValueError('Selection lineage mismatch')
    clean = read(clean_path, CLEAN_PIN)
    queries = {q['query_id']: q for q in clean['queries']}
    corpus = {d['doc_id']: d for d in clean['corpus']}
    pins = dict(PINS)
    pins['clean.private.json'] = digest(Path(clean_path).read_bytes())
    frame = []
    assigned = Counter()
    for family in FAMILIES:
        for intensity in (1, 3):
            for seed in (42, 43, 44):
                cid = f'{family}.intensity-{intensity}.seed-{seed}'
                for source in SOURCES:
                    relative = f'selected/{cid}/{source}.json'
                    selected = read(root / 'execution/selection' / relative, selection['files_sha256'][relative])
                    pins['execution/selection/' + relative] = selection['files_sha256'][relative]
                    rows = {}
                    for target in TARGETS:
                        rel = f'rows/{cid}/{source}/{target}.json'
                        data = read(root / 'execution/evaluation' / rel, evaluation['files_sha256'][rel])
                        rows[target] = {r['query_id']: r for r in data}
                        if len(rows[target]) != len(data):
                            raise ValueError('Duplicate native evaluation query')
                        pins['execution/evaluation/' + rel] = evaluation['files_sha256'][rel]
                    for choice in selected['records']:
                        assigned[choice['status']] += 1
                        if choice['status'] != 'valid_construction':
                            continue
                        qid = choice['query_id']
                        ms = {t: rows[t][qid]['measurement'] for t in TARGETS}
                        if any(m is None or m['poison_target_answer'] != choice['target_answer'] for m in ms.values()):
                            raise ValueError('Missing/mismatched paired measurement')
                        query = queries[qid]
                        case_id = digest(encode([family, intensity, seed, source, qid]))
                        frame.append(dict(case_id=case_id, query_id=qid, family=family, intensity=intensity,
                                          seed=seed, source=source, outcome_bin=outcome_bin(ms),
                                          query=query, poison_documents=choice['documents'],
                                          target_answer=choice['target_answer'],
                                          gold_context=[corpus[d] for d in query['gold_doc_ids']],
                                          measurements=ms))
    return frame, pins, dict(assigned)


def select_cases(frame):
    chosen, used = [], set()
    for family in reversed(FAMILIES):
        for intensity in (3, 1):
            pool = [x for x in frame if x['family'] == family and x['intensity'] == intensity]
            pool.sort(key=lambda x: digest(encode([DESIGN['seed'], x['case_id']])))
            counts = Counter()
            def take(bucket):
                case = next((x for x in pool if x['outcome_bin'] == bucket and x['query_id'] not in used), None)
                if case is None:
                    return False
                chosen.append(case)
                used.add(case['query_id'])
                counts[bucket] += 1
                return True
            for bucket in BINS:
                for _ in range(5):
                    if not take(bucket):
                        break
            while sum(counts.values()) < 25:
                if not any(take(b) for b in sorted(BINS, key=lambda b: (counts[b], BINS.index(b)))):
                    raise ValueError('Insufficient unique questions; allocation requires explicit revision')
    return chosen


def summarize(frame, chosen, pins, assigned):
    cells = []
    for family in FAMILIES:
        for intensity in (1, 3):
            eligible = [x for x in frame if (x['family'], x['intensity']) == (family, intensity)]
            picked = [x for x in chosen if (x['family'], x['intensity']) == (family, intensity)]
            cells.append(dict(family=family, intensity=intensity, eligible_instances=len(eligible),
                              eligible_questions=len({x['query_id'] for x in eligible}), selected=len(picked),
                              eligible_bins=dict(Counter(x['outcome_bin'] for x in eligible)),
                              selected_bins=dict(Counter(x['outcome_bin'] for x in picked)),
                              selected_sources=dict(Counter(x['source'] for x in picked)),
                              selected_seeds=dict(Counter(x['seed'] for x in picked))))
    return dict(schema='e4-selection-receipt/v1', design=DESIGN, design_sha256=digest(encode(DESIGN)),
                input_pins=pins, assigned_status_counts=assigned, eligible_instances=len(frame),
                selected=len(chosen), unique_questions=len({x['query_id'] for x in chosen}), strata=cells,
                factuality_status='unreviewed at selection', new_model_calls=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-root', required=True, type=Path)
    parser.add_argument('--clean', required=True, type=Path)
    parser.add_argument('--private-output', required=True, type=Path)
    parser.add_argument('--public-receipt', required=True, type=Path)
    args = parser.parse_args()
    if args.private_output.exists() or args.public_receipt.exists():
        raise ValueError('Refusing to overwrite an existing review/receipt')
    frame, pins, assigned = load_frame(args.native_root, args.clean)
    chosen = select_cases(frame)
    receipt = summarize(frame, chosen, pins, assigned)
    args.private_output.mkdir(parents=True)
    files = {'design.json': DESIGN, 'cases.private.json': chosen,
             'selection.private.json': [{k: x[k] for k in ('case_id', 'query_id', 'family', 'intensity', 'seed', 'source', 'outcome_bin')} for x in chosen]}
    receipt['output_sha256'] = {name: digest(encode(value)) for name, value in files.items()}
    for name, value in files.items():
        (args.private_output / name).write_bytes(encode(value))
    args.public_receipt.parent.mkdir(parents=True, exist_ok=True)
    args.public_receipt.write_bytes(encode(receipt))
    print(json.dumps({k: receipt[k] for k in ('selected', 'unique_questions', 'eligible_instances', 'new_model_calls')}))


if __name__ == '__main__':
    main()
