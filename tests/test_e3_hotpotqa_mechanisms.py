"""Synthetic statistical checks, never research evidence or inference."""
import json
import numpy as np
import pytest
from scripts import analyze_e3_hotpotqa_transfer as e3


def row(q='private-q', seed=42, **changes):
    return dict(query_id=q, seed=seed, valid=True, source_success=True, target_success=True,
                exposed=True, clean_target=False, clean_correct=True, poison_correct=False,
                clean_em=1., poison_em=0., clean_f1=1., poison_f1=0., **changes)


def test_seeds_remain_inside_question_cluster_and_failure_denominators():
    rows=[row(seed=s) for s in (42,43,44)] + [{'query_id':'failed-q','seed':42,'valid':False}]
    vectors,tax=e3.rate_vectors(rows,['private-q','failed-q'])
    assert vectors['atr'].tolist()==[[3.,3.],[0.,0.]]
    assert vectors['coverage'].tolist()==[[3.,3.],[0.,1.]]
    assert vectors['end_to_end_target_match'].sum(axis=0).tolist()==[3.,4.]
    assert vectors['clean_correct_to_wrong'].sum(axis=0).tolist()==[3.,3.]
    assert tax['clean_correct_to_wrong_exposed']==3
    weights=e3.bootstrap_weights(2,100)
    assert np.array_equal(weights,e3.bootstrap_weights(2,100))
    assert (weights.sum(axis=1)==2).all()
    # A sampled question contributes all three seed records, never one seed.
    assert set((weights @ vectors['atr'])[:,0]).issubset({0.,3.,6.})


def test_undefined_conditional_transfer_is_not_zero():
    r=row();r['source_success']=False
    vectors,_=e3.rate_vectors([r],['private-q'])
    assert np.isnan(e3.ratio(vectors['atr'].sum(axis=0)))
    assert e3.interval(np.array([np.nan,np.nan]))['undefined_replicates']==2
    assert e3.interval(np.array([np.nan]))['lower'] is None
    assert e3.ratio(vectors['target_given_source_failure'].sum(axis=0))==1.


def test_exposure_is_separate_from_answer_matching():
    r=row();r['exposed']=False
    vectors,tax=e3.rate_vectors([r],['private-q'])
    assert vectors['target_given_no_exposure'].tolist()==[[1.,1.]]
    assert tax['target_matched_without_visible_poison']==1
    assert tax['clean_correct_to_wrong_unexposed']==1


def test_paired_directional_contrasts_and_aggregate_only_exports(tmp_path):
    groups={}
    for f in e3.FAMILIES:
        for i in (1,3):
            for s in e3.SOURCES:
                for t in e3.TARGETS:
                    r=row()
                    if (s,t)==('dense','bm25'):r['target_success']=False
                    groups[(f,i,s,t)]=[r]
    result=e3.summarize(['private-q'],groups,[],{},replicates=20)
    assert len(result['directional_contrasts'])==4
    assert all(x['estimate']==1. for x in result['directional_contrasts'])
    assert all(x['ci']['level']==.9875 for x in result['directional_contrasts'])
    assert all(x['ci']['lower']==1. for x in result['directional_contrasts'])
    output=tmp_path/'aggregate'
    e3.write_outputs(result,output,heatmaps=False)
    assert 'private-q' not in (output/'aggregate.json').read_text()
    assert json.loads((output/'files.sha256.json').read_text())['aggregate.json']
    with pytest.raises(FileExistsError):e3.write_outputs(result,output,heatmaps=False)
