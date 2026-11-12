#!/usr/bin/env python3
"""Freeze E1 selections, then prepare real retrieval inputs and exact native reuse.

Writes PRIVATE versioned artifacts only outside the repository. No Qwen loading.
"""
import argparse
from collections import Counter
import copy
import gc
import hashlib
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.hotpotqa_native_reuse import read,verify,normalize,NativeAdapter,CANDIDATE_PIN
from scripts.audit_e1_e2_reuse import digest,binding_key,classify,compare,select,sha
from src.experiments.execution_reliability import atomic
from src.experiments.protocol import corpus_fingerprint,query_set_fingerprint
from src.experiments import week9_construction as old
from src.evaluation.qa_records import validate_qa
from src.evaluation.metrics import exact_match

FAMILIES=old.ATTACKS
LIMITS={'new_physical_calls':200,'inference_seconds':14400,'rss_bytes':12*2**30,
        'metal_bytes':10*2**30,'min_free_disk_bytes':5*2**30,'concurrency':1}


def private_root(path):
    p=Path(path).resolve()
    if p.is_relative_to(ROOT) or p.is_symlink():raise ValueError('New private directory outside repository required')
    return p


def choose_all(root,spec,ids):
    """Read candidates and source feedback only. No final-target tree is read."""
    chosen={};screen_calls=set();screen_seconds=0.
    for family in FAMILIES:
        for intensity in (1,3):
            for seed in (42,43,44):
                cid=old.cell_id(family,intensity,seed)
                bands=[read(root/'execution/candidates/candidates'/cid/f'{b}.json')['records'] for b in range(3)]
                for b,records in enumerate(bands):
                    if [r['query_id'] for r in records]!=ids:raise ValueError('Candidate cohort mismatch')
                    if any(r['candidate_band']!=b for r in records):raise ValueError('Candidate order mismatch')
                for source in ('bm25','dense'):
                    native=read(root/'execution/selection/selected'/cid/f'{source}.json')['records']
                    if [r['query_id'] for r in native]!=ids:raise ValueError('Selection cohort mismatch')
                    selections={m:[] for m in ('M1','M2','M3')}
                    for i,qid in enumerate(ids):
                        candidates=[band[i] for band in bands]
                        feedback={}
                        for b,candidate in enumerate(candidates):
                            f=native[i]['source_feedback'][b]
                            valid=candidate['status']==old.VALID
                            if f['candidate_index']!=b or f['construction_valid']!=valid or f['source_pipeline']!=source:
                                raise ValueError('Candidate/source feedback mismatch')
                            if valid:
                                g=f['observation'];validate_qa(g,g['extracted_answer'])
                                if f['source_target_match']!=bool(exact_match(g['extracted_answer'],candidate['target_answer'])):
                                    raise ValueError('Source screening success mismatch')
                                token=hashlib.sha256(qid.encode()).hexdigest()
                                directory=root/'execution/selection/calls'/cid/source/str(b)/token
                                request=read(directory/'00.intent.json');response=read(directory/'00.response.json')
                                if response['request_fingerprint']!=digest(request) or response['generation_sha256']!=digest(response['generation']):
                                    raise ValueError('Screen journal mismatch')
                                if request['context']!={'stage':'source-screen','source':source,'query_id':qid,'candidate_band':b}:
                                    raise ValueError('Non-source screening provenance')
                                if request['provenance']['candidate_library_completion_sha256']!=CANDIDATE_PIN or request['provenance']['model']!=spec['model']:
                                    raise ValueError('Screen model/library mismatch')
                                if any(response['generation'].get(k)!=v for k,v in g.items() if k!='elapsed_seconds'):
                                    raise ValueError('Screen response mismatch')
                                key=sha(directory/'00.response.json')
                                if key not in screen_calls:
                                    screen_calls.add(key);screen_seconds+=response['generation']['elapsed_seconds']
                                feedback[str(b)]=f['source_target_match']
                        library=[{'candidate_id':str(b),'valid':c['status']==old.VALID} for b,c in enumerate(candidates)]
                        draw=int(digest(['E1-M2-v1',seed,qid,family,intensity])[:16],16)
                        for method in selections:
                            b=select(library,method,draw,budget=3,feedback=feedback if method=='M3' else None)
                            if b is None:
                                choice={**candidates[0],'documents':[], 'status':old.SEMANTIC_FAILED if any(c['target_answer'] for c in candidates) else old.TARGET_FAILED}
                            else:choice=candidates[int(b)]
                            if method=='M3' and (choice['documents']!=native[i]['documents'] or choice['status']!=native[i]['status']):
                                raise ValueError('M3 differs from sealed historical selection')
                            selections[method].append(choice)
                    for method,records in selections.items():chosen[(cid,source,method)]=records
    return chosen,{'verified_historical_screen_physical_calls':len(screen_calls),
                   'historical_screen_elapsed_seconds':screen_seconds,'new_screen_calls':0}


def prepare(root,snapshot,out):
    root,snapshot,out=Path(root),Path(snapshot),private_root(out)
    if out.exists():raise FileExistsError('Use new private pilot directory')
    spec,receipt=verify(root,snapshot)
    from scripts import run_week9_protocol_poison_matrix as base
    from scripts.run_source_selection_transfer import retrieval_config
    from src.attacks.asr import build_prompt
    from run import build_retriever
    if base.environment()!=spec['environment']:raise ValueError('Current backend environment differs')
    for entry in spec['retrieval_snapshots'].values():
        if base.model_binding(entry['path'],entry['binding']['repository'])!=entry['binding']:
            raise ValueError('Pinned retrieval model bytes differ')
    ids=spec['binding']['query_ids']
    dev=sorted(ids,key=lambda q:digest('E1-dev25-v1:'+q))[:25]
    # Fixed prefix, never selected by target outcomes; retain invalid questions.
    smoke=dev[:5]
    selections,screening=choose_all(root,spec,ids)
    out.mkdir(parents=True)
    config={'schema':'e1-e2-bounded-development/v1','cohort_policy':'25 historical IDs sorted by SHA256(canonical JSON E1-dev25-v1:ID); first 5 smoke',
            'development_ids':dev,'active_smoke_ids':smoke,'historically_exposed':True,
            'families':list(FAMILIES),'intensities':[1,3],'seeds':[42,43,44],
            'sources':['bm25','dense'],'targets':['dense','reranker','rcd'],'candidate_budget':3,
            'limits':LIMITS,'E1_max_new_calls':160,'E2_reserved_new_calls':40,
            'source_selection_barrier':'all complete 300-query selections sealed before final target data access',
            'corpus_scope':'full original clean 300-query corpus plus all full-300 selected poisons; evaluate fixed smoke prefix only',
            'selection_seed_rule':'first 16 hex SHA256 canonical [E1-M2-v1,seed,query_id,family,intensity]',
            'model':spec['model'],'native_protocol_sha256':sha(root/'protocol.json'),
            'source_files_sha256':{name:sha(ROOT/'scripts'/name) for name in ('hotpotqa_native_reuse.py','prepare_e1_native_pilot.py','bounded_pilot_resources.py')}}
    atomic(out/'pilot.freeze.json',config)
    atomic(out/'selection.seal.json',{'pilot_sha256':sha(out/'pilot.freeze.json'),
           'selections':{'|'.join(k):v for k,v in selections.items()},'screening':screening})
    print(json.dumps({'stage':'pilot_and_source_selections_frozen','active_questions':len(smoke)}),flush=True)
    clean=base.load_clean({'binding':spec['binding']},spec['configs']['rcd'])
    library_plan=read(root/'execution/candidates/plan.json')
    if corpus_fingerprint(clean['corpus'])!=library_plan['corpus_fingerprint'] or query_set_fingerprint(clean['queries'])!=library_plan['query_fingerprint']:
        raise ValueError('Native clean dataset/corpus mismatch')
    atomic(out/'clean.private.json',clean)
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(str(snapshot),local_files_only=True)
    adapter=NativeAdapter(root,spec)
    native_observations={};native_by_binding={};native_by_role={}
    queries={q['query_id']:q for q in clean['queries']}
    # Target access begins only after source selection seal exists.
    for (cid,source,method),records in selections.items():
        if method!='M3':continue
        for pipeline in sorted({'dense','reranker','rcd',source}):
            rows=read(root/'execution/evaluation/rows'/cid/source/f'{pipeline}.json')
            for choice,r in zip(records,rows):
                qid=choice['query_id']
                if qid not in smoke or choice['status']!=old.VALID:continue
                for condition in ('clean','poisoned'):
                    row=adapter.observation(cid,source,pipeline,queries[qid],choice,condition,r['measurement'])
                    native_observations[row['observation_id']]=row
                    native_by_binding.setdefault(binding_key(row),row)
                    native_by_role[(cid,source,pipeline,qid,condition)]=row
    # Persist the verified native export before any new retrieval/model allocation.
    history=list(native_observations.values())
    compare(history,history)  # Reject conflicting physical identities.
    atomic(out/'history.private.json',history)
    atomic(out/'native-adapter.complete.json',{'history_sha256':sha(out/'history.private.json'),
        'verified_history_logical_observations':len(history),
        'verified_historical_physical_calls':len({r['physical_call_id'] for r in history}),
        'native_verification':receipt,'screening':screening})
    from scripts.bounded_pilot_resources import mac_health
    try:mac_health()
    except RuntimeError as exc:
        atomic(out/'PREPARATION_RESOURCE_STOP.json',{'reason':str(exc),'new_qwen_calls':0,
            'pending':'new retrieval inputs and exact distinct-call estimate; no Qwen initialized'})
        print(json.dumps({'stage':'RESOURCE_BLOCKED_BEFORE_NEW_RETRIEVAL','new_qwen_calls':0}),flush=True)
        return
    # Guard actual retrieval-model allocations too; Qwen is a separate process.
    from scripts.bounded_pilot_resources import Guard
    from src.experiments.execution_reliability import acquire_model_lease
    acquire_model_lease()
    import mlx.core as mx
    import torch
    class MetalUsage:
        def get_active_memory(self):return mx.get_active_memory()+(torch.mps.driver_allocated_memory() if torch.backends.mps.is_available() else 0)
        def get_cache_memory(self):return mx.get_cache_memory()
    guard=Guard(LIMITS,out,metal=MetalUsage());guard.start()
    required={};logical=[];retrieval=[];corpora_cache={};retrieval_cache={}
    embedder=None;scorer=None
    def retrieve(corpus,config,query):
        nonlocal embedder,scorer
        cfp=corpus_fingerprint(corpus);key=digest([cfp,config,query['question']])
        if key in retrieval_cache:return retrieval_cache[key]
        # Cache exact document embeddings across union corpora; no Qwen model.
        from src.retrieval.dense import SentenceTransformerEmbedder
        from src.retrieval.reranker import CrossEncoderScorer
        if config['retriever']!='bm25' and embedder is None:
            actual=SentenceTransformerEmbedder(config['embedder_model'])
            class Cache:
                def __init__(self):self.cache={}
                def encode(self,texts):
                    import numpy as np
                    missing=list(dict.fromkeys(t for t in texts if t not in self.cache))
                    if missing:
                        for t,v in zip(missing,actual.encode(missing)):self.cache[t]=v
                    return np.stack([self.cache[t] for t in texts])
            embedder=Cache()
        r=build_retriever(config) if config['retriever']=='bm25' else None
        if r is None:
            from src.retrieval.dense import DenseRetriever
            dense=DenseRetriever(embedder)
            if config['retriever']=='dense':r=dense
            elif config['retriever']=='reranker':
                from src.retrieval.reranker import Reranker
                if scorer is None:scorer=CrossEncoderScorer(config['reranker_model'])
                r=Reranker(dense,scorer)
            else:
                from src.defenses.rcd.retriever import RCDRetriever
                from src.retrieval.bm25 import BM25Retriever
                r=RCDRetriever(dense,sparse_retriever=BM25Retriever(),dense_retriever=dense,
                     candidate_k=config['rcd_candidate_k'],output_k=3,rewrite_count=config['rcd_rewrite_count'],
                     consistency_weight=config['rcd_consistency_weight'],redundancy_weight=config['rcd_redundancy_weight'],
                     conflict_weight=config['rcd_conflict_weight'],base_rank_weight=config['rcd_base_rank_weight'])
        started=time.monotonic();r.build(corpus);build_time=time.monotonic()-started
        started=time.monotonic();docs=r.retrieve(query['question'],top_k=3);elapsed=time.monotonic()-started
        evidence=[{'doc_id':d.doc_id,'text':d.text,'score':d.score} for d in docs]
        meta={'pipeline':config['retriever'],'corpus_sha256':cfp,'build_seconds':build_time,
              'retrieve_seconds':elapsed,'wrapper_calls':1,'inner_operations':getattr(r,'last_diagnostics',{}),
              'cross_encoder_pairs':min(20,len(corpus)) if config['retriever']=='reranker' else 0}
        atomic(out/'retrieval-checkpoints'/(key+'.json'),{'evidence':evidence,'metadata':meta})
        retrieval.append(meta);retrieval_cache[key]=(evidence,meta)
        return evidence,meta
    for (cid,source,method),records in selections.items():
        cell=old.replay(clean,{'records':records});cfp=corpus_fingerprint(cell['corpus'])
        corpora_cache['|'.join((cid,source,method))]={'corpus_sha256':cfp,'records':records}
        for choice in records:
            qid=choice['query_id']
            if qid not in smoke:continue
            base_row={'cell':cid,'source':source,'method':method,'query_id':qid,
                      'status':choice['status'],'target_answer':choice['target_answer'],
                      'gold_answer':queries[qid]['gold_answer'],'poison_ids':[d['doc_id'] for d in choice['documents']],
                      'corpus_sha256':cfp}
            for pipeline in sorted({'dense','reranker','rcd',source}):
                item={**base_row,'pipeline':pipeline}
                if choice['status']!=old.VALID:logical.append(item);continue
                for condition in ('clean','poisoned'):
                    old_row=native_by_role.get((cid,source,pipeline,qid,condition))
                    cfg=retrieval_config(spec,pipeline)
                    current_cfp=corpus_fingerprint(clean['corpus']) if condition=='clean' else cfp
                    if old_row is not None and old_row['poison_corpus_sha256']==current_cfp and old_row['candidate_sha256']==digest('clean-no-poison' if condition=='clean' else {'documents':choice['documents'],'target':choice['target_answer']}):
                        evidence=old_row['retrieval_evidence'];prompt=old_row['prompt'];backend_prompt=old_row['backend_prompt']
                    else:
                        evidence,_=retrieve(clean['corpus'] if condition=='clean' else cell['corpus'],cfg,queries[qid])
                        prompt=build_prompt(queries[qid]['question'],[d['text'] for d in evidence])
                        backend_prompt=tokenizer.apply_chat_template([{'role':'user','content':prompt}],tokenize=False,add_generation_prompt=True)
                    row=normalize(spec,queries[qid],choice,condition,cfg,current_cfp,evidence,prompt,backend_prompt,'pending')
                    key=binding_key(row);row['observation_id']=key
                    required.setdefault(key,row);item[condition+'_input']=key
                logical.append(item)
        print(json.dumps({'stage':'retrieval_inputs','cell':cid,'source':source,'method':method,'distinct_inputs':len(required)}),flush=True)
    # Private histories retain provenance IDs and are compared across IDs.
    history=list(native_observations.values());plan=list(required.values())
    reuse=compare(plan,history)
    if reuse['new_call_estimate']=='UNKNOWN':raise ValueError('Input budget/provenance remains unverified')
    atomic(out/'plan.private.json',plan)
    atomic(out/'logical.private.json',logical)
    atomic(out/'corpora.private.json',corpora_cache)
    atomic(out/'retrieval.private.json',retrieval)
    atomic(out/'prepare.complete.json',{'pilot_sha256':sha(out/'pilot.freeze.json'),
        'selection_sha256':sha(out/'selection.seal.json'),'plan_sha256':sha(out/'plan.private.json'),
        'history_sha256':sha(out/'history.private.json'),'logical_sha256':sha(out/'logical.private.json'),
        'reuse':reuse,'screening':screening,'native_verification':receipt,
        'full_25_pilot':'NOT_EXECUTED','smoke_questions':len(smoke)})
    guard.close()
    print(json.dumps({'stage':'PREPARED_NO_QWEN','reuse':reuse,'max_rss':guard.max_rss,'max_metal':guard.max_metal}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--native-root',required=True);p.add_argument('--snapshot',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();prepare(a.native_root,a.snapshot,a.output)
