from copy import deepcopy
import pytest
from scripts.audit_e1_e2_reuse import FIELDS
from scripts.audit_e1_e2_readiness import reconcile


def row(oid, q='q', **extra):
    return {**dict.fromkeys(FIELDS, 'bound'), 'observation_id': oid, 'query_id': q, **extra}


def test_shared_exact_binding_counted_once_despite_distinct_record_ids():
    a=row('E1'); b=row('E2')
    r=reconcile([a], [b], [], ['q'], [])
    assert r['shared_complete_bindings']==1
    assert r['minimum_successful_new_calls_under_frozen_binding_contract']==1
    assert r['question_blocks'][0]['complete_question_cost']==1
    assert r['question_blocks'][0]['all_assigned_constructions_failed'] is False


def test_history_reuses_physical_origin_and_keeps_condition_changes_distinct():
    h=row('old', provenance='physical_completed', physical_call_id='call', raw_response='actual')
    a=row('E1'); b=row('E2', backend_prompt='changed')
    r=reconcile([a], [b], [h], ['q'], [])
    assert r['reuse']['verified_reusable_physical_calls']==1
    assert r['missing_e1']==0 and r['missing_e2']==1


def test_conflicting_physical_call_rejected():
    h=row('old', provenance='physical_completed', physical_call_id='call', raw_response='actual')
    other={**h, 'observation_id':'other', 'backend_prompt':'conflict'}
    with pytest.raises(ValueError, match='Conflicting physical'):
        reconcile([row('E1')], [], [h,other], ['q'], [])


def test_no_numeric_budget_when_history_or_input_is_unverified():
    h=row('old', provenance='interrupted', physical_call_id='call', raw_response='partial')
    for history, a in [([h],row('E1')), ([], {k:v for k,v in row('E1').items() if k!='backend_prompt'})]:
        r=reconcile([a], [], history, ['q'], [])
        assert r['deficit']==r['missing_e1']=='UNKNOWN'
        assert r['minimum_successful_new_calls_under_frozen_binding_contract']=='UNKNOWN'
        assert r['question_blocks'][0]['complete_question_cost']=='UNKNOWN'


def test_question_ids_never_authorize_reuse_and_failed_question_costs_zero():
    a=row('a', prompt='A'); b=row('b', prompt='B')
    r=reconcile([a], [b], [], ['q','failed'], [{'query_id':'failed','status':'target_construction_failed'}],cap=1)
    assert r['missing_e1']==r['missing_e2']==1 and r['deficit']==1
    assert r['question_blocks'][1]['all_assigned_constructions_failed']
    assert r['question_blocks'][1]['complete_question_cost']==0


def test_cohort_change_rejected():
    with pytest.raises(ValueError, match='outside frozen'):
        reconcile([row('a', q='unapproved')], [], [], ['q'], [])
