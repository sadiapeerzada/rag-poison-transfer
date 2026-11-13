#!/usr/bin/env python3
"""Read-only sealed E1/E2 accounting. No MLX imports, retrieval or model loading."""
import argparse
from collections import Counter
import json
from pathlib import Path
from scripts.audit_e1_e2_reuse import binding_key, classify, complete, compare, digest, sha
from scripts.hotpotqa_native_reuse import read
from src.evaluation.qa_records import validate_qa

PINS = {
    'pilot.freeze.json': '26d055e46a09307f92ddb2e3ba7b14cc2d03abf01bcd82da7a40cbaba16a5e49',
    'selection.seal.json': 'daa6e6cb42a9d6a11334728ae34953fd3711320be0e65d76609c6c60cb7a4a31',
    'plan.private.json': 'b1c41c4c2ba10b951f28bd3f340e1cb8aa7a41b6376fdead301a8adfff125e84',
    'history.private.json': '5b5729d3750fec98d3dab478984d69186d5423e6593ddbc7c8532c30d9f52298',
    'e2.plan.private.json': '6a769dc60373ea616e52c04fed4fee1febcd4fea465d9cd08b8a03febf4ef91e',
    'e2.freeze.json': '83c51a7e36c2647f5d7642ed447644b7aa919ab3fb6874134112ba0c707455eb',
}
COMPLETION_PIN = '72343b04134f8d6f24815d731af52c644d517dba042754236f9e7f089316c191'


def reconcile(e1, e2, history, ids, logical, cap=200):
    combined = compare(e1+e2, history)
    uncertain = combined['new_call_estimate'] == 'UNKNOWN'
    historical = {binding_key(r) for r in history if classify(r, r) == 'REUSABLE'}
    a, b = [{binding_key(r) for r in rows if complete(r)} for rows in (e1, e2)]
    missing = (a | b)-historical
    if any(r['query_id'] not in ids for r in e1+e2):
        raise ValueError('Prepared question outside frozen active cohort')
    blocks = []
    cumulative = 0
    for ordinal, q in enumerate(ids, 1):
        aa, bb = [{binding_key(r) for r in rows if r['query_id'] == q and complete(r)}-historical for rows in (e1, e2)]
        cumulative += len(aa | bb)
        block = dict(question_ordinal=ordinal, missing_e1=len(aa), missing_e2=len(bb),
                           shared_missing=len(aa & bb), complete_question_cost=len(aa | bb),
                           cumulative_prefix_cost=cumulative,
                           all_assigned_constructions_failed=bool([r for r in logical if r['query_id'] == q]) and all(r['status'] != 'valid_construction' for r in logical if r['query_id'] == q))
        if uncertain:
            for k in ('missing_e1', 'missing_e2', 'complete_question_cost', 'cumulative_prefix_cost'):
                block[k] = 'UNKNOWN'
        blocks.append(block)
    return dict(schema='e1-e2-readiness-accounting/v1', reuse=combined,
                complete_bindings=len(a | b), shared_complete_bindings=len(a & b),
                missing_e1=len(a-historical) if not uncertain else 'UNKNOWN',
                missing_e2=len(b-historical) if not uncertain else 'UNKNOWN',
                shared_missing_bindings=len((a & b)-historical),
                minimum_successful_new_calls_under_frozen_binding_contract=len(missing) if not uncertain else 'UNKNOWN',
                previous_cap=cap, deficit=max(0, len(missing)-cap) if not uncertain else 'UNKNOWN',
                question_blocks=blocks, full_25_question_budget='UNKNOWN: only five-question inputs materialized',
                retry_allowance='none assumed; failed/indeterminate reservations consume approved attempts',
                broader_prompt_equivalence_authorizes_reuse=False)


def verify_origins(history, native):
    evaluation = Path(native)/'execution/evaluation'
    manifest = evaluation/'transfer.complete.json'
    if sha(manifest) != COMPLETION_PIN:
        raise ValueError('Native completion changed')
    pins = read(manifest)['files_sha256']
    origins = set()
    for row in history:
        rel = row['native_observation_id']
        path = evaluation/rel
        if not path.resolve().is_relative_to(evaluation.resolve()) or path.is_symlink():
            raise ValueError('Unsafe origin path')
        intent_rel = rel.replace('.response.', '.intent.')
        if sha(path) != pins[rel] or sha(evaluation/intent_rel) != pins[intent_rel]:
            raise ValueError('Native origin hash mismatch')
        response, intent = read(path), read(evaluation/intent_rel)
        generation = response['generation']
        if (not response['execution'].get('backend_call_executed')
                or response['request_fingerprint'] != digest(intent)
                or response['generation_sha256'] != digest(generation)
                or row['physical_call_id'] != digest(['native-evaluation', sha(path), rel])):
            raise ValueError('Physical origin not completed and verified')
        validate_qa(generation, generation['extracted_answer'])
        if any(row[k] != generation[k] for k in ('prompt', 'backend_prompt', 'raw_response')):
            raise ValueError('Export differs from physical response')
        if (row['retrieval_evidence'] != intent['evidence']
                or row['retrieval_config'] != intent['effective']['retriever_config']
                or row['poison_corpus_sha256'] != intent['effective']['corpus_fingerprint']
                or row['backend_environment'] != intent['effective']['environment']):
            raise ValueError('Export differs from physical effective input')
        origins.add(row['physical_call_id'])
    return dict(logical_records=len(history), verified_physical_origins=len(origins))


def project_old_dispatch(root, e1, e2, history, ids):
    historical = {binding_key(r) for r in history}
    selected = set()
    costs = []
    for experiment, plan, cap in [('E1', e1, 160), ('E2', e2, 200)]:
        by_id = {r['observation_id']: r for r in plan}
        prior = len(selected)
        for block in read(root/(experiment+'.dispatch.freeze.json'))['blocks']:
            keys = {binding_key(by_id[k]) for k in block}-historical
            if len(selected | keys) > cap:
                break
            selected |= keys
        costs.append(len(selected)-prior)
    needs = [{binding_key(r) for r in e1+e2 if r['query_id']==q}-historical for q in ids]
    return dict(E1_funded_attempts=costs[0], E2_funded_attempts=costs[1],
                complete_valid_question_ordinals=[i for i,n in enumerate(needs,1) if n and n <= selected],
                incomplete_valid_question_ordinals=[i for i,n in enumerate(needs,1) if n-selected],
                zero_construction_question_ordinals=[i for i,n in enumerate(needs,1) if not n],
                remaining_unfunded_by_question_ordinal=[len(n-selected) for n in needs], executable=False,
                note='Projection of frozen dispatch only; superseded authorization remains revoked. Do not choose/drop questions or treatments to fit the cap.')


def audit(root, native):
    root = Path(root)
    before = {n: sha(root/n) for n in PINS}
    if before != PINS:
        raise ValueError('Frozen checkpoint changed')
    freeze, prep, ep = [read(root/n) for n in ('pilot.freeze.json', 'prepare.complete.json', 'e2.prepare.complete.json')]
    e1, e2, history = [read(root/n) for n in ('plan.private.json', 'e2.plan.private.json', 'history.private.json')]
    logical, el = [read(root/n) for n in ('logical.private.json', 'e2.logical.private.json')]
    if sha(root/'logical.private.json') != prep['logical_sha256']:
        raise ValueError('E1 logical assignments changed')
    dispatches = {}
    for experiment, plan, links in [('E1', e1, logical), ('E2', e2, el)]:
        d = read(root/(experiment+'.dispatch.freeze.json'))
        if d['plan_sha256'] != digest(plan) or d['logical_sha256'] != digest(links):
            raise ValueError('Dispatch input seal differs')
        flat = [k for block in d['blocks'] for k in block]
        if len(flat) != len(set(flat)) or set(flat) != {r['observation_id'] for r in plan}:
            raise ValueError('Dispatch does not cover exact plan')
        by_id = {r['observation_id']: r for r in plan}
        historical = {binding_key(r) for r in history}
        costs = [sum(binding_key(by_id[k]) not in historical for k in block) for block in d['blocks']]
        dispatches[experiment] = dict(blocks=len(costs), missing_block_costs=costs,
                                     dispatch_sha256=sha(root/(experiment+'.dispatch.freeze.json')))
    if ep['plan_sha256'] != sha(root/'e2.plan.private.json') or ep['history_sha256'] != sha(root/'history.private.json'):
        raise ValueError('E2 preparation seal differs')
    origins = verify_origins(history, native)
    result = reconcile(e1, e2, history, freeze['active_smoke_ids'], logical)
    result['superseded_200_attempt_dispatch_projection'] = project_old_dispatch(root, e1, e2, history, freeze['active_smoke_ids'])
    result.update(input_sha256=before, origins=origins, frozen_dispatch=dispatches,
                  e1_logical_assigned=len(logical), e1_logical_valid=sum(r['status']=='valid_construction' for r in logical),
                  e2_d2_logical_references=len(el),
                  missing_e1_by_pipeline=dict(Counter(r['retrieval_config']['retriever'] for r in e1 if binding_key(r) not in {binding_key(h) for h in history})))
    ledger = root.parent/'e1-e2-20261112-authorized-session'
    sessions = []
    for intent in sorted((ledger/'sessions').glob('*.intent.json')):
        complete = intent.with_name(intent.name.replace('.intent.', '.complete.'))
        if not complete.is_file():
            raise ValueError('Unreconciled historical session')
        sessions.append(read(complete))
    reservations = list((ledger/'attempts').glob('*.json'))
    intents = list((root/'qwen/calls').glob('*.intent.json'))
    result['physical_ledger'] = dict(shared_reservations=len(reservations), pilot_generation_intents=len(intents),
        completed_new_calls=sum(s['completed_new_calls'] for s in sessions),
        reconciled_initialization_sessions=len(sessions), charged_elapsed_seconds=sum(s['elapsed_seconds'] for s in sessions))
    if reservations or intents or result['physical_ledger']['completed_new_calls']:
        raise ValueError('Execution ledger changed; completed/failed/indeterminate calls require fresh reconciliation')
    result['authorization_status'] = read(root/'completion-authorization-20261113.revoked.json')['status']
    if before != {n: sha(root/n) for n in PINS}:
        raise ValueError('Audit mutated frozen inputs')
    result.update(frozen_inputs_unchanged=True, new_qwen_calls_in_this_audit=0, readiness='BLOCKED: approval, safe initialization and full-scope input coverage unresolved')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--native-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = audit(a.root, a.native_root)
    with a.output.open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps({k: result[k] for k in ('missing_e1', 'missing_e2', 'deficit', 'readiness')}))


if __name__ == '__main__':
    main()
