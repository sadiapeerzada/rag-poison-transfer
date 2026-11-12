"""Synthetic preparation checks; no model imports or inference."""
import copy
import json
import subprocess
import sys
from pathlib import Path
import pytest
from scripts.audit_e1_e2_reuse import FIELDS, classify, compare, inventory, select, sha


def observation():
    return {**{k: 'synthetic-' + k for k in FIELDS}, 'observation_id': 'slot',
            'provenance': 'physical_completed', 'physical_call_id': 'call', 'raw_response': 'synthetic'}


def test_exact_reuse_and_missing():
    row = observation()
    assert classify(row, copy.deepcopy(row)) == 'REUSABLE'
    assert classify(row, None) == 'MISSING'
    assert compare([row], [row])['verified_reusable_physical_calls'] == 1


@pytest.mark.parametrize('field', FIELDS)
def test_each_condition_must_match(field):
    row = observation(); old = copy.deepcopy(row); old[field] = 'different'
    assert classify(row, old) == 'INCOMPATIBLE'


@pytest.mark.parametrize('field', FIELDS)
def test_missing_evidence_is_unverified(field):
    row = observation(); old = copy.deepcopy(row); del old[field]
    assert classify(row, old) == 'UNVERIFIED'


def test_provenance_and_no_double_counting():
    row = observation(); old = copy.deepcopy(row); old['provenance'] = 'cached'
    assert classify(row, old) == 'UNVERIFIED'
    second = {**row, 'observation_id': 'slot2'}
    result = compare([row, second], [row, second])
    assert result['verified_reusable_physical_calls'] == 1
    assert result['reused_responses_are_new_independent_inference'] is False
    with pytest.raises(ValueError):
        compare([row], [row, row])
    with pytest.raises(ValueError):
        compare([row], [row, {**second, 'prompt': 'other'}])


def test_deterministic_random_and_budget_parity():
    library = [{'candidate_id': str(i), 'valid': i != 0} for i in range(3)]
    before = copy.deepcopy(library)
    assert select(library, 'M1', 42, budget=3) == '1'
    assert select(library, 'M2', 42, budget=3) == select(library, 'M2', 42, budget=3)
    assert select(library, 'M3', 42, budget=3, feedback={'1': False, '2': True}) == '2'
    assert select(library, 'M3', 42, budget=3, feedback={'1': False, '2': False}) == '1'
    assert library == before
    for method in ['M1', 'M2', 'M3']:
        with pytest.raises(ValueError, match='parity'):
            select(library[:2], method, 42, budget=3)
    with pytest.raises(ValueError):
        select(library, 'M3', 42, budget=3, feedback={'target_outcome': True})


def test_inventory_is_read_only_and_rejects_tampering(tmp_path):
    data = tmp_path / 'record.json'; data.write_text('{}')
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'files_sha256': {'record.json': sha(data)}}))
    pin = sha(manifest)
    assert inventory(tmp_path, manifest, pin)['files_verified'] == 1
    assert sha(manifest) == pin
    data.write_text('{"changed":true}')
    with pytest.raises(ValueError): inventory(tmp_path, manifest, pin)
    with pytest.raises(ValueError): inventory(tmp_path, manifest, '0' * 64)


def test_cli_rejects_unpinned_history_without_private_diagnostics(tmp_path):
    private = tmp_path / 'private-name.json'; private.write_text('[]')
    result = subprocess.run([sys.executable, str(Path(__file__).parents[1] / 'scripts/audit_e1_e2_reuse.py'),
                             'compare', str(private), str(private), '--history-sha256', '0' * 64],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert str(private) not in result.stderr


def test_complete_binding_matches_across_record_ids_without_mutation():
    required = {**observation(), 'observation_id': 'new-method-slot'}
    historical = {**observation(), 'observation_id': 'historical-slot'}
    before = copy.deepcopy((required, historical))
    result = compare([required], [historical])
    assert result['classification_counts']['REUSABLE'] == 1
    assert result['verified_reusable_physical_calls'] == 1
    assert result['new_call_estimate'] == 0
    assert (required, historical) == before


@pytest.mark.parametrize('field', FIELDS)
def test_same_question_different_binding_never_matches_across_record_ids(field):
    required = {**observation(), 'observation_id': 'new-slot'}
    historical = {**observation(), 'observation_id': 'old-slot', field: 'changed'}
    result = compare([required], [historical])
    assert result['classification_counts']['REUSABLE'] == 0
    assert result['verified_reusable_physical_calls'] == 0
    assert result['nonreusable_distinct_complete_inputs'] == 1


def test_matching_binding_wins_over_mismatched_record_id_and_unverified_duplicate():
    required = observation()
    stale = {**required, 'prompt': 'old prompt', 'physical_call_id': 'other-call'}
    unverified = {**required, 'observation_id': 'unverified', 'provenance': 'cached'}
    exact = {**required, 'observation_id': 'exact'}
    result = compare([required], [stale, unverified, exact])
    assert result['classification_counts']['REUSABLE'] == 1
    assert result['verified_reusable_physical_calls'] == 1
    assert result['new_call_estimate'] == 'UNKNOWN'


def test_duplicate_logical_observations_reuse_one_physical_call():
    required = [{**observation(), 'observation_id': f'new-{i}'} for i in range(3)]
    history = [{**observation(), 'observation_id': f'old-{i}'} for i in range(2)]
    result = compare(required, history)
    assert result['classification_counts']['REUSABLE'] == 3
    assert result['verified_reusable_physical_calls'] == 1
    assert result['nonreusable_distinct_complete_inputs'] == 0
    assert result['new_call_estimate'] == 0


def test_multiple_physical_calls_choose_stable_representative():
    history = [{**observation(), 'observation_id': f'old-{i}', 'physical_call_id': f'call-{i}'}
               for i in range(2)]
    required = [{**observation(), 'observation_id': f'new-{i}'} for i in range(2)]
    assert compare(required, history) == compare(required, list(reversed(history)))
    assert compare(required, history)['verified_reusable_physical_calls'] == 1


@pytest.mark.parametrize('field', ['prompt', 'poison_corpus_sha256', 'backend_environment', 'raw_response'])
def test_conflicting_physical_identity_rejected_even_for_unrequested_records(field):
    original = observation()
    changed = {**original, 'observation_id': 'other-logical-record', field: 'changed'}
    with pytest.raises(ValueError, match='Conflicting physical call provenance'):
        compare([], [original, changed])


def test_incomplete_record_cannot_hide_physical_identity_conflict():
    original = observation()
    changed = {**original, 'observation_id': 'partial', 'prompt': 'changed'}
    del changed['decoding']
    with pytest.raises(ValueError, match='Conflicting physical call provenance'):
        compare([], [original, changed])


@pytest.mark.parametrize('change', [
    {'provenance': 'cached'}, {'physical_call_id': None}, {'raw_response': None},
    {'backend_environment': None}, {'decoding': None},
])
def test_unverified_history_never_yields_numeric_budget(change):
    historical = {**observation(), 'observation_id': 'old', **change}
    result = compare([observation()], [historical])
    assert result['classification_counts']['UNVERIFIED'] == 1
    assert result['new_call_estimate'] == 'UNKNOWN'


def test_incomplete_required_input_never_yields_numeric_budget():
    required = observation(); del required['prompt']
    assert compare([required], [])['new_call_estimate'] == 'UNKNOWN'


def test_distinct_missing_inputs_are_deduplicated_across_logical_ids():
    required = [{**observation(), 'observation_id': f'new-{i}'} for i in range(3)]
    result = compare(required, [])
    assert result['classification_counts']['MISSING'] == 3
    assert result['nonreusable_distinct_complete_inputs'] == 1
    assert result['new_call_estimate'] == 1


def test_structured_bindings_match_independent_of_object_key_order():
    required = {**observation(), 'observation_id': 'new',
                'decoding': {'seed': 42, 'temperature': 0},
                'retrieval_evidence': [{'id': 'synthetic-doc', 'text': 'synthetic text'}]}
    historical = {**required, 'observation_id': 'old',
                  'decoding': {'temperature': 0, 'seed': 42}}
    assert compare([required], [historical])['classification_counts']['REUSABLE'] == 1
    historical['decoding']['temperature'] = 1
    assert compare([required], [historical])['classification_counts']['REUSABLE'] == 0


def test_unverified_different_binding_still_blocks_numeric_budget():
    historical = {**observation(), 'prompt': 'old', 'provenance': 'indeterminate'}
    result = compare([observation()], [historical])
    assert result['classification_counts']['INCOMPATIBLE'] == 1
    assert result['new_call_estimate'] == 'UNKNOWN'
