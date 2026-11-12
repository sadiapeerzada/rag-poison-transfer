"""Synthetic native provenance fixtures; never loads Qwen or retrieval models."""
import copy
import json
from pathlib import Path
import pytest
from scripts import hotpotqa_native_reuse as n
from scripts.audit_e1_e2_reuse import compare,digest
from src.evaluation.qa_records import MEASUREMENT_SCHEMA,EXTRACTOR_VERSION


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))


def fixture(tmp_path):
    spec={'model':{'repository':'synthetic','revision':'x','files_sha256':{'tokenizer.json':'token'}},
          'environment':{'python':'synthetic'},'rules':{'decoding':{'temperature':0}}}
    query={'query_id':'private-synthetic'}
    choice={'query_fingerprint':'query-hash','target_answer':'synthetic-target',
            'documents':[{'doc_id':'poison','text':'synthetic-evidence'}]}
    evidence=[{'doc_id':'poison','text':'synthetic-evidence','score':.8}]
    g={'schema':MEASUREMENT_SCHEMA,'extractor_version':EXTRACTOR_VERSION,'prompt':'synthetic prompt',
       'prompt_sha256':__import__('hashlib').sha256(b'synthetic prompt').hexdigest(),
       'backend_prompt':'synthetic backend',
       'backend_prompt_sha256':__import__('hashlib').sha256(b'synthetic backend').hexdigest(),
       'raw_response':'synthetic answer','extracted_answer':'synthetic answer','elapsed_seconds':1.,
       'generator_latency_seconds':1.,'prompt_tokens':2,'completion_tokens':2}
    intent={'prompt':g['prompt'],'max_tokens':64,'context':{'query_id':query['query_id'],'pipeline':'dense','condition':'poisoned'},
            'evidence':evidence,'effective':{'model':spec['model'],'environment':spec['environment'],
            'qa_seed':42,'decoding':spec['rules']['decoding'],'retriever_config':{'retriever':'dense'},'corpus_fingerprint':'corpus'}}
    response={'request_fingerprint':digest(intent),'generation_sha256':digest(g),'generation':g,
              'execution':{'kind':'backend_call','backend_call_executed':True}}
    token=__import__('hashlib').sha256(query['query_id'].encode()).hexdigest()
    directory=tmp_path/'execution/evaluation/calls/cell/bm25/dense'/token
    save(directory/'01.intent.json',intent);save(directory/'01.response.json',response)
    measurement={'poisoned_condition':{'generation':g,'retrieved_evidence':[{'doc_id':'poison','text':'synthetic-evidence'}],
                                      'generation_evidence_doc_ids':['poison']}}
    return spec,query,choice,measurement,directory


def test_real_shape_projection_preserves_journal_scores_and_cross_id_reuse(tmp_path):
    spec,q,c,m,d=fixture(tmp_path)
    row=n.NativeAdapter(tmp_path,spec).observation('cell','bm25','dense',q,c,'poisoned',m)
    assert row['retrieval_evidence'][0]['score']==.8
    assert row['provenance']=='physical_completed'
    assert compare([{**row,'observation_id':'new-observation'}],[row])['classification_counts']['REUSABLE']==1


def test_measurement_evidence_tampering_rejected(tmp_path):
    spec,q,c,m,d=fixture(tmp_path);m['poisoned_condition']['retrieved_evidence'][0]['text']='different'
    with pytest.raises(ValueError,match='evidence/prompt'):
        n.NativeAdapter(tmp_path,spec).observation('cell','bm25','dense',q,c,'poisoned',m)


def test_backend_tampering_rejected(tmp_path):
    spec,q,c,m,d=fixture(tmp_path)
    request=n.read(d/'01.intent.json');request['effective']['qa_seed']=43
    response=n.read(d/'01.response.json');response['request_fingerprint']=digest(request)
    save(d/'01.intent.json',request);save(d/'01.response.json',response)
    with pytest.raises(ValueError,match='backend conditions'):
        n.NativeAdapter(tmp_path,spec).observation('cell','bm25','dense',q,c,'poisoned',m)


def test_unresolved_cache_origin_is_not_physical_inference(tmp_path):
    spec,q,c,m,d=fixture(tmp_path);response=n.read(d/'01.response.json')
    cache={'generation':response['generation']};entry=tmp_path/'execution/evaluation/clean-cache/synthetic.json'
    save(entry,cache)
    response['execution']={'kind':'clean_cache_hit','backend_call_executed':False,'cache_key':'synthetic',
                           'cache_entry_sha256':n.sha(entry),'origin_generation':response['generation']}
    save(d/'01.response.json',response)
    with pytest.raises(ValueError,match='Unresolved physical clean origin'):
        n.NativeAdapter(tmp_path,spec).observation('cell','bm25','dense',q,c,'poisoned',m)


def test_diagnostic_depth_is_not_generator_depth(tmp_path):
    spec,q,c,m,d=fixture(tmp_path)
    m['poisoned_condition']['retrieved_evidence']=[{'doc_id':'diagnostic-only','text':'not generator-visible'}]+m['poisoned_condition']['retrieved_evidence']
    row=n.NativeAdapter(tmp_path,spec).observation('cell','bm25','dense',q,c,'poisoned',m)
    assert [r['doc_id'] for r in row['retrieval_evidence']]==['poison']
