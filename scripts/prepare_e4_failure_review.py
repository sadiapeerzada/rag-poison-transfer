#!/usr/bin/env python3
"""Freeze a separate E4 failure packet from sealed historical artifacts; no inference."""
import argparse
from collections import Counter
from pathlib import Path
from scripts.prepare_e4_case_review import CLEAN_PIN, FAMILIES, PINS, SOURCES, digest, encode, read

CANDIDATE_PIN = '97960932066b24f172fc566dd29808dc191cb85aa08cf995ffbd04c91d809f23'
DESIGN = {
    'schema': 'e4-supplementary-failure-selection/v1', 'seed': '20261113-failures-v1',
    'allocation': 'four per available family/intensity/failure-status cell; six cells; 24 total',
    'statuses': ['semantic_construction_failed', 'target_construction_failed'],
    'order': 'status as listed; semantic then lexical; intensity 3 then 1',
    'selection': 'SHA-256 order; unique questions globally; exclude original 100 questions; fail on shortage',
    'unit': 'failed source-selected instance; all three candidate bands retained',
    'scope': 'supplementary qualitative failure review, not a prevalence sample or replacement',
}


def select_failures(frame, excluded):
    used, chosen = set(excluded), []
    for status in DESIGN['statuses']:
        for family in reversed(FAMILIES):
            if status == 'semantic_construction_failed' and family == FAMILIES[0]:
                continue
            for intensity in (3, 1):
                pool = [c for c in frame if (c['status'], c['family'], c['intensity']) == (status, family, intensity)]
                pool.sort(key=lambda c: digest(encode([DESIGN['seed'], c['case_id']])))
                picked = 0
                for c in pool:
                    if c['query_id'] in used:
                        continue
                    chosen.append(c)
                    used.add(c['query_id'])
                    picked += 1
                    if picked == 4:
                        break
                if picked != 4:
                    raise ValueError('Failure stratum lacks four eligible unique questions')
    return chosen


def prepare(root, clean_path, original_path):
    root = Path(root)
    selection = read(root/'execution/selection/selection.seal.json', PINS['execution/selection/selection.seal.json'])
    candidates = read(root/'execution/candidates/candidates.complete.json', CANDIDATE_PIN)
    if selection['candidate_library_completion_sha256'] != CANDIDATE_PIN:
        raise ValueError('Candidate lineage mismatch')
    original = read(original_path, '8e0a4d54977dc44d4a4259d359e11f5228827ef15bd1496cc073eb98497b1f12')
    clean = read(clean_path, CLEAN_PIN)
    queries = {q['query_id']: q for q in clean['queries']}
    corpus = {d['doc_id']: d for d in clean['corpus']}
    read(root/'protocol.json', PINS['protocol.json'])
    frame, selections, pins = [], {}, {k: v for k, v in PINS.items() if k != 'execution/evaluation/transfer.complete.json'}
    pins['execution/candidates/candidates.complete.json'] = CANDIDATE_PIN
    for family in FAMILIES:
        for intensity in (1, 3):
            for seed in (42, 43, 44):
                cid = f'{family}.intensity-{intensity}.seed-{seed}'
                for source in SOURCES:
                    rel = f'selected/{cid}/{source}.json'
                    rows = read(root/'execution/selection'/rel, selection['files_sha256'][rel])['records']
                    pins['execution/selection/'+rel] = selection['files_sha256'][rel]
                    for row in rows:
                        if row['status'] == 'valid_construction':
                            continue
                        case_id = digest(encode(['E4-failure', cid, source, row['query_id']]))
                        meta = dict(case_id=case_id, query_id=row['query_id'], cid=cid, family=family,
                                    intensity=intensity, seed=seed, source=source, status=row['status'])
                        frame.append(meta)
                        selections[case_id] = row
    chosen = select_failures(frame, {c['query_id'] for c in original})
    packets, cache = [], {}
    for meta in chosen:
        query = queries[meta['query_id']]
        bands = []
        for band in (0, 1, 2):
            rel = f'candidates/{meta["cid"]}/{band}.json'
            if rel not in cache:
                data = read(root/'execution/candidates'/rel, candidates['files_sha256'][rel])
                cache[rel] = {r['query_id']: r for r in data['records']}
                pins['execution/candidates/'+rel] = candidates['files_sha256'][rel]
            bands.append(cache[rel][meta['query_id']])
        packets.append(dict(**meta, query=query, gold_context=[corpus[d] for d in query['gold_doc_ids']],
                            selected_record=selections[meta['case_id']], candidate_records=bands,
                            poison_documents=selections[meta['case_id']]['documents']))
    receipt = dict(schema='e4-failure-selection-receipt/v1', design=DESIGN, design_sha256=digest(encode(DESIGN)),
                   input_pins=pins, clean_sha256=CLEAN_PIN, original_packet_sha256=digest(Path(original_path).read_bytes()),
                   eligible_failure_instances=len(frame), selected=len(chosen), unique_questions=len({c['query_id'] for c in chosen}),
                   excluded_original_questions=100, selected_cells=dict(Counter(f'{c["family"]}/I{c["intensity"]}/{c["status"]}' for c in chosen)),
                   frame_cells=dict(Counter(f'{c["family"]}/I{c["intensity"]}/{c["status"]}' for c in frame)),
                   new_model_calls=0, factuality_status='unreviewed at freeze')
    return packets, chosen, receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('native-root', 'clean', 'original-packet', 'private-output', 'public-receipt'):
        p.add_argument('--'+name, required=True, type=Path)
    a = p.parse_args()
    if a.private_output.exists() or a.public_receipt.exists():
        raise ValueError('Refusing to overwrite prior artifacts')
    packets, selected, receipt = prepare(a.native_root, a.clean, a.original_packet)
    files = {'design.json': DESIGN, 'selection.private.json': selected, 'cases.private.json': packets}
    receipt['output_sha256'] = {n: digest(encode(v)) for n, v in files.items()}
    a.private_output.mkdir(parents=True)
    for n, v in files.items():
        (a.private_output/n).write_bytes(encode(v))
    a.public_receipt.write_bytes(encode(receipt))
    print(f'Frozen {len(selected)} supplementary failures; original sample unchanged.')


if __name__ == '__main__':
    main()
