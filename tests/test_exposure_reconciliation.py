import copy
import json
from pathlib import Path

import pytest
from scripts.reconcile_twowiki_exposure import (project,inspect_bytes,inspect_file,reconcile,assess_pool,sha)
from src.experiments.semantic_v3_preparation import verify_registry

A='a'*32
B='b'*32


def test_typed_projection_discards_question_answer_prompt_and_text_content():
    value={'query_id':A,'question':{'query_id':B},'gold_answer':{'query_id':B},
           'text':{'query_id':B},'prompt':{'query_id':B},'backend_prompt':{'query_id':B},
           'generated_text':{'query_id':B},'dataset_revision':'c'*40}
    assert project(value)==([A],['c'*40])


def test_nested_evidence_id_metadata_is_retained_without_prose():
    ids,_=project({'evidence':[{'source_query_id':A,'text':'ignored'}],
                   'records':[{'query_ids':[B,'not-a-query','d'*64]}]})
    assert ids==[A,B]


def test_empty_and_unparsed_are_not_nonexposure():
    for raw in (b'',b'not JSON; missing execution log'):
        result=inspect_bytes(raw,'.json')
        assert 'not_' in result['status'] and result['query_ids']==[]
    with pytest.raises(FileNotFoundError):inspect_file('/nonexistent/exposure-ledger.json')


def test_jsonl_and_csv_only_project_explicit_ids():
    raw=(json.dumps({'query_id':A,'question':'not inspected'})+'\n'+json.dumps({'query_id':B})+'\n').encode()
    assert inspect_bytes(raw,'.jsonl')['query_ids']==[A,B]
    assert inspect_bytes(b'attack,n_attacked_queries\nsemantic,25\n','.csv')['query_ids']==[]
    assert inspect_bytes(('query_id,n\n'+A+',1\n').encode(),'.csv')['query_ids']==[A]


def test_parent_provenance_and_exclusions_never_removed_or_certified():
    parent={'source_records':[{'provenance':'old','original_sha256':'f'*64,'query_ids':[A]}],
            'excluded_query_ids':[A],'certification':None,'status':'incomplete_not_certified',
            'historical_gaps':['unknown sweep']}
    before=copy.deepcopy(parent)
    result=reconcile(parent,[{'query_ids':[B],'sha256':'e'*64}],parent_sha256='d'*64)
    assert parent==before and result['source_records']==parent['source_records']
    assert result['excluded_query_ids']==[A,B] and result['new_query_ids']==[B]
    assert result['certification'] is None and result['historical_gaps']==parent['historical_gaps']


def test_cardinality_is_not_go_and_no_ids_are_sampled_or_returned():
    pool=[f'{n:032x}' for n in range(50)]
    result=assess_pool(pool,pool[:20],provenance='synthetic IDs only',history_complete=True)
    assert result['potentially_id_eligible_count']==30 and result['at_least_25_by_id']
    assert result['prospective_go'] is False and result['cohort_selected'] is False
    assert not any(isinstance(x,list) for x in result.values())
    with pytest.raises(ValueError):assess_pool(pool+pool[:1],[],provenance='fixture')
    with pytest.raises(ValueError):assess_pool(['not-an-id'],[],provenance='fixture')


def test_actual_reconciliation_retains_all_30_source_decisions_and_blocks_selection():
    parent=json.loads(Path('pilot_prep/twowiki_semantic_v3/known_exclusions/registry.json').read_text())
    result=json.loads(Path('reports/twowiki_v3_exposure_reconciliation/reconciled_registry.json').read_text())
    assert result['source_records']==parent['source_records'] and len(result['source_records'])==30
    assert result['parent_registry_sha256']==sha(Path('pilot_prep/twowiki_semantic_v3/known_exclusions/registry.json').read_bytes())
    assert set(parent['excluded_query_ids'])<=set(result['excluded_query_ids'])
    assert result['excluded_query_ids']==parent['excluded_query_ids'] and result['new_query_ids']==[]
    assert result['certification'] is None
    with pytest.raises(ValueError):verify_registry(result)


def test_available_pool_assessments_are_exhausted_without_cohort_output():
    value=json.loads(Path('reports/twowiki_v3_exposure_reconciliation/metadata_eligibility.json').read_text())
    assert value['cohort_selected'] is False and value['unique_available_pool_ids']==300
    assert len(value['assessments'])==3
    for row in value['assessments']:
        assert row['pool_count']==row['excluded_count']==300
        assert row['potentially_id_eligible_count']==0 and row['prospective_go'] is False


def test_missing_sweep_ids_stay_unknown_not_baseline_reconstruction():
    value=json.loads(Path('reports/twowiki_v3_exposure_reconciliation/search_summary.json').read_text())
    assert value['historical_sweep_query_ids'] is None
    assert value['actual_sweep_runtime_revision_binding']=='missing'
    assert value['old_sweep_membership_in_900'].startswith('unknown')
    assert value['no_historical_resampling_or_ID_guessing_performed'] is True
