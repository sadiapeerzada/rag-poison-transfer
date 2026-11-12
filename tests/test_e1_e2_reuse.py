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
