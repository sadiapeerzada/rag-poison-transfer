"""Synthetic fixed-defense controls and explicit missing-arm aggregation."""
import json
from pathlib import Path
import pytest
from scripts import run_e2_matched_defense_pilot as e2
from scripts.hotpotqa_native_reuse import normalize
from scripts.audit_e1_e2_reuse import digest,sha
from src.experiments.protocol import corpus_fingerprint
from src.experiments.week9_construction import VALID


class Dense:
    def __init__(self):self.calls=[]
    def build(self,corpus):self.corpus=corpus
    def retrieve(self,q,top_k):self.calls.append((q,top_k));return ['synthetic-evidence']


def test_fixed_rewrite_one_lookup_and_original_question_not_mutated():
    dense=Dense();r=e2.FixedRewriteDense(dense);corpus=[{'doc_id':'doc','text':'synthetic'}]
    r.build(corpus);question='Original question?'
    assert r.retrieve(question)==['synthetic-evidence']
    assert dense.calls==[('Background evidence about: Original question?',3)]
    assert question=='Original question?'
    assert dense.corpus is corpus
    assert r.last_diagnostics['rewrite_model_calls']==0
    assert r.last_diagnostics['inner_dense_searches']==1
    with pytest.raises(ValueError):r.retrieve(question,top_k=4)


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))


def test_resource_block_preserves_actual_three_arms_and_missing_fourth(tmp_path,monkeypatch):
    root=tmp_path/'private';native=tmp_path/'native';output=tmp_path/'public.json'
    q={'query_id':'private-native-q','question':'private synthetic question','gold_answer':'gold'}
    c={'query_id':q['query_id'],'query_fingerprint':'hash','target_answer':'target',
       'documents':[{'doc_id':'poison','text':'private synthetic evidence'}],'status':VALID}
    clean={'queries':[q],'corpus':[{'doc_id':'clean','text':'clean synthetic text'}]}
    cid='lexical_influential_token.intensity-1.seed-42'
    spec={'model':{'repository':'synthetic','revision':'x','files_sha256':{'tokenizer.json':'synthetic'}},
          'environment':{'python':'synthetic'},'configs':{'rcd':{'top_k':3,'rcd_candidate_k':10}}}
    save(native/'protocol.json',spec)
    freeze={'active_smoke_ids':[q['query_id']],'development_ids':[q['query_id']],
            'native_protocol_sha256':sha(native/'protocol.json'),'limits':{'new_physical_calls':200}}
    save(root/'pilot.freeze.json',freeze);save(root/'clean.private.json',clean)
    save(root/'selection.seal.json',{'selections':{cid+'|dense|M3':[c]}})
    history=[];files={}
    corpus_sha=corpus_fingerprint(clean['corpus']+[{'doc_id':'poison','text':'private synthetic evidence'}])
    for pipeline in ('dense','reranker','rcd'):
        for condition in ('clean','poisoned'):
            evidence=[{'doc_id':'poison','text':'private synthetic evidence','score':1.}]
            row=normalize(spec,q,c,condition,{'retriever':pipeline},corpus_sha if condition=='poisoned' else corpus_fingerprint(clean['corpus']),
                          evidence,'private synthetic prompt','private synthetic backend',digest([cid,'dense',pipeline,q['query_id'],condition]))
            row.update(provenance='physical_completed',physical_call_id=pipeline+condition,raw_response='target',
                       generation={'extracted_answer':'target'})
            history.append(row)
        trace={k+'_condition':{'retrieval_elapsed_seconds':.01,'retrieval_call_accounting':{'normal_inner_retrieval_operations':2}} for k in ('clean','poisoned')}
        rel=Path('rows')/cid/'dense'/(pipeline+'.json');path=native/'execution/evaluation'/rel
        save(path,[{'query_id':q['query_id'],'measurement':trace}]);files[rel.as_posix()]=sha(path)
    save(root/'history.private.json',history)
    save(root/'native-adapter.complete.json',{'history_sha256':sha(root/'history.private.json')})
    save(native/'execution/evaluation/transfer.complete.json',{'files_sha256':files})
    monkeypatch.setattr(e2,'COMPLETION_PIN',sha(native/'execution/evaluation/transfer.complete.json'))
    def blocked():raise RuntimeError('pressure')
    monkeypatch.setattr(e2,'mac_health',blocked)
    e2.execute(root,native,output)
    result=json.loads(output.read_text())
    assert result['new_physical_qwen_calls']==0
    assert result['completed_valid_defense_positions']==3
    assert result['pending_D2_valid_positions']==1
    assert result['D2_distinct_new_input_estimate']=='UNKNOWN'
    d2=next(g for g in result['metrics'] if g['pipeline']=='D2')
    assert d2['metrics']['end_to_end_target_match']['estimate'] is None
    assert next(c for c in result['paired_contrasts'] if c['contrast']=='D4-D2')['status']=='INCOMPLETE'
    assert 'private-native-q' not in output.read_text()
    assert 'private synthetic evidence' not in output.read_text()
