#!/usr/bin/env python3
"""Validate complete private E4 ledgers and publish counts/checksums only.

Provenance/schema validation is not independent factual adjudication.
"""
import argparse
from collections import Counter
from pathlib import Path
from scripts.prepare_e4_case_review import digest, encode, read
from scripts.summarize_e4_review import summarize

ORIGINAL_PACKET = '8e0a4d54977dc44d4a4259d359e11f5228827ef15bd1496cc073eb98497b1f12'
ORIGINAL_LEDGER = 'e45a969d98bf30ad561060eab5340a754a5644d9327ee4a1bc56a39afa450a6a'
FAILURE_PACKET = '2a0475cc674cb9a9a6e344c16d49c6535909579c1acc1ba785a34bebff277da3'


def require_complete(cases, reviews):
    if len(reviews) != len(cases) or {r['case_id'] for r in reviews} != {c['case_id'] for c in cases}:
        raise ValueError('Incomplete review coverage')


def preserve_annotations(original, completed):
    indexed = {r['case_id']: r for r in completed}
    if any(indexed.get(r['case_id']) != r for r in original):
        raise ValueError('Original annotation changed or absent')


def summarize_complete(cases, reviews, old, packet_sha, ledger_sha):
    require_complete(cases, reviews)
    preserve_annotations(old, reviews)
    result = summarize(cases, reviews, packet_sha, ledger_sha)
    indexed = {r['case_id']: r for r in reviews}
    groups = {}
    for c in cases:
        key = f'{c["family"]}/I{c["intensity"]}/{c["outcome_bin"]}'
        groups.setdefault(key, Counter())[indexed[c['case_id']]['verdict']] += 1
    result.update(original_annotations_preserved=len(old), added_annotations=len(reviews)-len(old),
                  sample_cells={k: dict(v) for k, v in sorted(groups.items())},
                  completion_scope='Source-assisted central-proposition review complete; uncertainty is a finding, not independent truth.')
    return result


def summarize_failures(cases, reviews, packet_sha, ledger_sha):
    require_complete(cases, reviews)
    result = summarize(cases, reviews, packet_sha, ledger_sha)
    indexed = {r['case_id']: r for r in reviews}
    statuses, outcomes = Counter(), Counter()
    assigned_bands = generated = partial = 0
    for c in cases:
        r = indexed[c['case_id']]
        if r.get('reviewed_candidate_bands') != [0, 1, 2] or len(c['candidate_records']) != 3:
            raise ValueError('Failure review omits candidate bands')
        attempts = [a for b in c['candidate_records'] for ar in b['attempt_records'] for a in ar['attempts']]
        if r['reviewed_attempts'] != len(attempts):
            raise ValueError('Failure review attempt count mismatch')
        assigned = any(b['target_answer'] is not None for b in c['candidate_records'])
        if (r['target_validity'] == 'absent_not_reviewable') != (not assigned):
            raise ValueError('Absent target misclassified')
        if not assigned and r['verdict'] != 'unadjudicated':
            raise ValueError('Cannot adjudicate nonexistent target')
        for b in c['candidate_records']:
            statuses[b['status']] += 1
            assigned_bands += b['target_answer'] is not None
            partial += len(b['partial_documents'])
            if b['documents']:
                raise ValueError('Supplementary failure unexpectedly has accepted documents')
        outcomes.update(a['outcome'] for a in attempts)
        generated += len(attempts)
    result.update(selected_statuses=dict(Counter(c['status'] for c in cases)),
                  candidate_band_statuses=dict(statuses), reviewed_candidate_bands=len(cases)*3,
                  assigned_target_bands=assigned_bands, retained_generation_attempts=generated,
                  retained_attempt_outcomes=dict(outcomes), retained_partial_documents=partial,
                  failure_mechanisms=dict(Counter(r['failure_mechanism'] for r in reviews)),
                  target_validity=dict(Counter(r['target_validity'] for r in reviews)),
                  limitations=result['limitations']+['Absent targets have no target-factuality verdict.',
                      'Rejected semantic attempts may contain fluent assertions or truthful corrections; failure status is not factuality.',
                      'No failed construction is converted into a victim response or successful attack.'])
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('original-packet', 'original-ledger', 'completed-ledger', 'failure-packet', 'failure-ledger', 'output'):
        p.add_argument('--'+n, required=True, type=Path)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('Refusing to overwrite completed review receipt')
    cases = read(a.original_packet, ORIGINAL_PACKET)
    old = read(a.original_ledger, ORIGINAL_LEDGER)
    reviews = read(a.completed_ledger)
    failures, fr = read(a.failure_packet, FAILURE_PACKET), read(a.failure_ledger)
    if len(cases) != 100 or len(old) != 20 or len(failures) != 24:
        raise ValueError('Frozen sample or annotation cardinality mismatch')
    if {c['query_id'] for c in cases} & {c['query_id'] for c in failures}:
        raise ValueError('Supplementary cases overlap original questions')
    result = dict(schema='e4-completed-source-assisted-review/v1',
                  valid_constructions=summarize_complete(cases, reviews, old, ORIGINAL_PACKET, digest(a.completed_ledger.read_bytes())),
                  construction_failures=summarize_failures(failures, fr, digest(a.failure_packet.read_bytes()), digest(a.failure_ledger.read_bytes())),
                  original_ledger_sha256=ORIGINAL_LEDGER, new_qwen_calls=0,
                  independent_human_adjudications=0, e5_decision='unchanged: execution deferred')
    a.output.write_bytes(encode(result))
    print('Complete source-assisted coverage: 100 frozen valid cases + 24 separate failures; original 20 unchanged.')


if __name__ == '__main__':
    main()
