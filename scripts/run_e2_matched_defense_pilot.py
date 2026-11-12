#!/usr/bin/env python3
"""Matched E2 native reuse + fixed rewrite preparation. Private inputs stay private.

No Qwen is loaded here. Under resource warning, publish only genuine saved
Dense/Reranker/RCD observations and explicit missing D2 outcomes.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.hotpotqa_native_reuse import read,normalize
from scripts.audit_hotpotqa_transfer_raw_offline import COMPLETION_PIN
from scripts.audit_e1_e2_reuse import digest,sha,binding_key,compare
from scripts.aggregate_e1_bounded_pilot import summarize,intervals
from scripts.bounded_pilot_resources import mac_health
from src.experiments.execution_reliability import atomic,once
from src.experiments import week9_construction as old
from src.experiments.protocol import corpus_fingerprint
from src.evaluation.metrics import exact_match,f1_score

REWRITE_TEMPLATE='Background evidence about: {question}'
ARMS={'D1':'dense','D2':'fixed_rewrite_dense','D3':'reranker','D4':'rcd'}


class TextEmbeddingCache:
    """Cache the unchanged normalized text encoder; never cache model answers."""
    def __init__(self,encoder):
        self.encoder=encoder;self.cache={};self.lookups=0;self.unique_encoded=0;self.encoder_calls=0
    def encode(self,texts):
        import numpy as np
        if not texts:raise ValueError('Nonempty text batch required')
        missing=list(dict.fromkeys(t for t in texts if t not in self.cache))
        self.lookups+=len(texts)
        if missing:
            values=self.encoder.encode(missing)
            if len(values)!=len(missing):raise ValueError('Embedding count mismatch')
            self.encoder_calls+=1;self.unique_encoded+=len(missing)
            self.cache.update(zip(missing,values))
        return np.stack([self.cache[t] for t in texts])
    def statistics(self):
        return {'text_lookups':self.lookups,'unique_texts_encoded':self.unique_encoded,
                'cache_hits':self.lookups-self.unique_encoded,'encoder_method_calls':self.encoder_calls}


class FixedRewriteDense:
    """One non-generative rewrite + dense lookup; final QA retains original question."""
    def __init__(self,dense):self.dense=dense;self.last_diagnostics=None
    def build(self,corpus):self.dense.build(corpus)
    def retrieve(self,question,top_k=3):
        if top_k!=3:raise ValueError('Frozen generator-visible k=3 required')
        started=time.monotonic()
        docs=self.dense.retrieve(REWRITE_TEMPLATE.format(question=question),top_k=3)
        self.last_diagnostics={'wrapper_calls':1,'inner_dense_searches':1,'rewrite_model_calls':0,
                               'elapsed_seconds':time.monotonic()-started}
        return docs


def paired(rows,ids):
    result=[]
    by={}
    for r in rows:by.setdefault((r['family'],r['intensity'],r['source'],r['pipeline']),[]).append(r)
    for family,intensity,source in sorted({k[:3] for k in by}):
        a=by[(family,intensity,source,'D4')]
        for other in ('D1','D2','D3'):
            b=by[(family,intensity,source,other)]
            row={'family':family,'intensity':intensity,'source':source,'contrast':'D4-'+other,'metric':'population_target_match'}
            if any(r['status']==old.VALID and not r['complete'] for r in a+b):
                result.append({**row,'status':'INCOMPLETE','estimate':None});continue
            vectors=[]
            for qid in ids:
                aa=[r for r in a if r['query_id']==qid];bb=[r for r in b if r['query_id']==qid]
                if len(aa)!=len(bb):raise ValueError('Unmatched defense denominator')
                vectors.append([sum(r.get('target_match',False) for r in aa)-sum(r.get('target_match',False) for r in bb),len(aa)])
            den=sum(v[1] for v in vectors)
            result.append({**row,'status':('DESCRIPTIVE_EXPLORATORY' if any(r['status']==old.VALID for r in a+b) else 'NO_VALID_CONSTRUCTIONS'),
                           'estimate':sum(v[0] for v in vectors)/den if den else None,
                           'ci95_question_cluster':intervals(vectors)})
    return result


def execute(root,native_root,output,snapshot=None):
    root,native_root,output=Path(root),Path(native_root),Path(output)
    if root.resolve().is_relative_to(ROOT):raise ValueError('Private pilot must remain outside repository')
    freeze=read(root/'pilot.freeze.json');adapter=read(root/'native-adapter.complete.json')
    if sha(root/'history.private.json')!=adapter['history_sha256']:raise ValueError('Verified native export changed')
    history=read(root/'history.private.json')
    compare(history,history)
    by_id={r['observation_id']:r for r in history}
    clean=read(root/'clean.private.json');queries={q['query_id']:q for q in clean['queries']}
    seal=read(root/'selection.seal.json');ids=freeze['active_smoke_ids']
    native_spec=read(native_root/'protocol.json')
    if sha(native_root/'protocol.json')!=freeze['native_protocol_sha256']:raise ValueError('Native protocol differs')
    config={'pilot_sha256':sha(root/'pilot.freeze.json'),'selection_sha256':sha(root/'selection.seal.json'),
            'arms':ARMS,'generator_visible_k':3,'D2_rewrite_template':REWRITE_TEMPLATE,
            'D3_candidate_pool':20,'D3_ties':'stable dense order',
            'D2_embedding_cache':'per-text normalized pinned encoder/v1; model/rewriter/scoring unchanged',
            'D4_frozen_config':native_spec['configs']['rcd'],'scope':'M3 fixed original source-selected union corpora',
            'limits':freeze['limits'],'code_sha256':sha(__file__),'resource_guard_sha256':sha(ROOT/'scripts/bounded_pilot_resources.py'),'historically_exposed':True}
    once(root/'e2.freeze.json',config)
    blocked=False;blocker=None
    try:mac_health()
    except RuntimeError as exc:blocked=True;blocker=str(exc)
    if (root/'RESOURCE_STOP.json').exists() and not (root/'prepare.complete.json').exists():
        blocked=True;blocker='Unresolved E1 resource stop; generator-input budget incomplete'
    # Read-only historical traces are authenticated against completion inventory.
    if sha(native_root/'execution/evaluation/transfer.complete.json')!=COMPLETION_PIN:raise ValueError('Native completion pin differs')
    completion=read(native_root/'execution/evaluation/transfer.complete.json')
    trace_cache={};traces=[];rows=[];new_plan={};e2logical=[]
    used_physical=set();historical_logical=0;guard=None;new_retrieval_traces=[]
    dense=None;tokenizer=None
    existing_plan=read(root/'e2.plan.private.json') if (root/'e2.plan.private.json').exists() else []
    existing_logical=read(root/'e2.logical.private.json') if (root/'e2.logical.private.json').exists() else []
    planned_by_id={r['observation_id']:r for r in existing_plan}
    logical_by_key={(r['cell'],r['source'],r['query_id'],r['condition']):r['input'] for r in existing_logical}
    for key,choices in seal['selections'].items():
        cid,source,method=key.split('|')
        if method!='M3':continue
        family,rest=cid.split('.intensity-');intensity,seed=map(int,rest.split('.seed-'))
        cell=old.replay(clean,{'records':choices});cfp=corpus_fingerprint(cell['corpus'])
        rewrite=None
        for choice in choices:
            qid=choice['query_id']
            if qid not in ids:continue
            for arm,pipeline in ARMS.items():
                row={'family':family,'intensity':intensity,'seed':seed,'source':source,'method':'M3',
                     'pipeline':arm,'query_id':qid,'status':choice['status'],'complete':False}
                if choice['status']!=old.VALID:rows.append(row);continue
                if arm!='D2':
                    native={c:by_id.get(digest([cid,source,pipeline,qid,c])) for c in ('clean','poisoned')}
                    if not all(native.values()):raise ValueError('Missing native matched defense pair')
                    used_physical.update(r['physical_call_id'] for r in native.values())
                    historical_logical+=2
                    poison=native['poisoned']
                    if poison['poison_corpus_sha256']!=cfp or poison['candidate_sha256']!=digest({'documents':choice['documents'],'target':choice['target_answer']}):
                        raise ValueError('Defense corpus/poison mismatch')
                    ca=native['clean']['generation']['extracted_answer'];pa=poison['generation']['extracted_answer'];gold=queries[qid]['gold_answer']
                    source_row=by_id[digest([cid,source,source,qid,'poisoned'])]
                    row.update(complete=True,target_match=bool(exact_match(pa,choice['target_answer'])),
                        source_success=bool(exact_match(source_row['generation']['extracted_answer'],choice['target_answer'])),
                        clean_em=exact_match(ca,gold),poison_em=exact_match(pa,gold),clean_f1=f1_score(ca,gold),poison_f1=f1_score(pa,gold),
                        poison_exposure=bool(set(d['doc_id'] for d in choice['documents'])&set(d['doc_id'] for d in poison['retrieval_evidence'])))
                    tkey=(cid,source,pipeline)
                    if tkey not in trace_cache:
                        rel=Path('rows')/cid/source/(pipeline+'.json');path=native_root/'execution/evaluation'/rel
                        if sha(path)!=completion['files_sha256'][rel.as_posix()]:raise ValueError('Historical trace file changed')
                        trace_cache[tkey]={r['query_id']:r for r in read(path)}
                    m=trace_cache[tkey][qid]['measurement']
                    for c in ('clean','poisoned'):
                        obs=m[c+'_condition']
                        traces.append({'arm':arm,'condition':c,'latency_seconds':obs['retrieval_elapsed_seconds'],
                                       'accounting':obs['retrieval_call_accounting']})
                elif existing_plan:
                    pair={}
                    for condition in ('clean','poisoned'):
                        pid=logical_by_key.get((cid,source,qid,condition))
                        response=root/'qwen/calls'/(str(pid)+'.response.json')
                        intent=root/'qwen/calls'/(str(pid)+'.intent.json')
                        if response.exists():
                            saved=read(response);request=read(intent)
                            if saved.get('request_sha256')!=digest(request) or request['binding_sha256']!=pid or request['input']!=planned_by_id[pid]:raise ValueError('D2 response provenance differs')
                            if 'generation' in saved:
                                from src.evaluation.qa_records import validate_qa
                                g=saved['generation'];validate_qa(g,g['extracted_answer'])
                                if saved['generation_sha256']!=digest(g) or g['backend_prompt']!=planned_by_id[pid]['backend_prompt']:raise ValueError('D2 generation differs')
                                pair[condition]=g
                    if len(pair)==2:
                        ca=pair['clean']['extracted_answer'];pa=pair['poisoned']['extracted_answer'];gold=queries[qid]['gold_answer']
                        source_row=by_id[digest([cid,source,source,qid,'poisoned'])]
                        ev=planned_by_id[logical_by_key[(cid,source,qid,'poisoned')]]['retrieval_evidence']
                        row.update(complete=True,target_match=bool(exact_match(pa,choice['target_answer'])),
                            source_success=bool(exact_match(source_row['generation']['extracted_answer'],choice['target_answer'])),
                            clean_em=exact_match(ca,gold),poison_em=exact_match(pa,gold),clean_f1=f1_score(ca,gold),poison_f1=f1_score(pa,gold),
                            poison_exposure=bool(set(d['doc_id'] for d in choice['documents'])&set(d['doc_id'] for d in ev)))
                elif not blocked:
                    # Full E1 preparation must pass before allocating models for E2.
                    if not (root/'prepare.complete.json').is_file():blocked=True;blocker='E1 generator-input preparation incomplete'
                    else:
                        from scripts.run_source_selection_transfer import retrieval_config
                        from src.attacks.asr import build_prompt
                        if dense is None:
                            from scripts.bounded_pilot_resources import Guard
                            from src.experiments.execution_reliability import acquire_model_lease
                            acquire_model_lease()
                            import mlx.core as mx
                            import torch
                            class MetalUsage:
                                def get_active_memory(self):return mx.get_active_memory()+(torch.mps.driver_allocated_memory() if torch.backends.mps.is_available() else 0)
                                def get_cache_memory(self):return mx.get_cache_memory()
                            guard=Guard(freeze['limits'],root,metal=MetalUsage());guard.start()
                            from scripts.run_week9_protocol_poison_matrix import model_binding
                            if snapshot is None:raise ValueError('Explicit pinned Qwen snapshot required')
                            model_path=Path(snapshot)
                            if model_binding(model_path,native_spec['model']['repository'])!=native_spec['model']:raise ValueError('E2 model snapshot differs')
                            for entry in native_spec['retrieval_snapshots'].values():
                                if model_binding(entry['path'],entry['binding']['repository'])!=entry['binding']:raise ValueError('Retrieval model snapshot differs')
                            from transformers import AutoTokenizer
                            tokenizer=AutoTokenizer.from_pretrained(str(model_path),local_files_only=True)
                            from src.retrieval.dense import DenseRetriever,SentenceTransformerEmbedder
                            dense=DenseRetriever(TextEmbeddingCache(SentenceTransformerEmbedder(native_spec['retrieval_snapshots']['embedder']['path'])))
                        cfg={**retrieval_config(native_spec,'dense'),'retriever':'fixed_rewrite_dense','rewrite_template':REWRITE_TEMPLATE,'embedding_cache':'normalized-per-text/v1'}
                        for condition,corpus in (('clean',clean['corpus']),('poisoned',cell['corpus'])):
                            mac_health();rewrite=FixedRewriteDense(dense)
                            build_start=time.monotonic();rewrite.build(corpus);build_seconds=time.monotonic()-build_start
                            docs=rewrite.retrieve(queries[qid]['question'],3)
                            trace={'cell':cid,'source':source,'query_id':qid,'condition':condition,
                                   'build_seconds':build_seconds,**rewrite.last_diagnostics}
                            new_retrieval_traces.append(trace)
                            once(root/'e2.retrieval-traces'/(digest([cid,source,qid,condition])+'.json'),trace)
                            evidence=[{'doc_id':d.doc_id,'text':d.text,'score':d.score} for d in docs]
                            prompt=build_prompt(queries[qid]['question'],[d['text'] for d in evidence])
                            backend=tokenizer.apply_chat_template([{'role':'user','content':prompt}],tokenize=False,add_generation_prompt=True)
                            planned=normalize(native_spec,queries[qid],choice,condition,cfg,corpus_fingerprint(corpus),evidence,prompt,backend,'pending')
                            pid=binding_key(planned);planned['observation_id']=pid;new_plan.setdefault(pid,planned)
                            once(root/'e2.retrieval-checkpoints'/(pid+'.json'),planned)
                            e2logical.append({'cell':cid,'source':source,'query_id':qid,'condition':condition,'input':pid})
                rows.append(row)
    if new_plan:
        atomic(root/'e2.plan.private.json',list(new_plan.values()))
        atomic(root/'e2.logical.private.json',e2logical)
        reuse=compare(list(new_plan.values()),history)
        if reuse['new_call_estimate']=='UNKNOWN':raise ValueError('E2 budget unverified')
        atomic(root/'e2.prepare.complete.json',{'pilot_sha256':sha(root/'pilot.freeze.json'),
               'plan_sha256':sha(root/'e2.plan.private.json'),'history_sha256':sha(root/'history.private.json'),'e2_freeze_sha256':sha(root/'e2.freeze.json'),'reuse':reuse})
    if guard:guard.close()
    new_cost={'wrapper_calls':len(new_retrieval_traces),'inner_dense_searches':len(new_retrieval_traces),
              'rewrite_model_calls':0,'build_seconds':sum(t['build_seconds'] for t in new_retrieval_traces),
              'retrieval_seconds':sum(t['elapsed_seconds'] for t in new_retrieval_traces),
              'embedding_cache':dense.embedder.statistics() if dense else None,
              'max_rss_bytes':guard.max_rss if guard else None,'max_metal_bytes':guard.max_metal if guard else None}
    grouped=summarize(rows,ids)
    for g in grouped:
        g['metrics']={k:v for k,v in g['metrics'].items() if k not in ('source_success','atr')}
    timing=[]
    for arm in ('D1','D3','D4'):
        selected=[t for t in traces if t['arm']==arm]
        timing.append({'arm':arm,'logical_retrieval_observations':len(selected),
                       'historical_retrieval_seconds':sum(t['latency_seconds'] for t in selected),
                       'accounting_totals':{k:(sum(t['accounting'][k] for t in selected) if all(type(t['accounting'].get(k)) in (int,float) for t in selected) else 'UNKNOWN') for k in sorted({k for t in selected for k in t['accounting']})},
                       'provenance':'historical descriptive timings; no fresh/historical paired speedup claim'})
    pending_d2=sum(r['pipeline']=='D2' and r['status']==old.VALID and not r['complete'] for r in rows)
    stage=('ACTIVE_SMOKE_INPUTS_COMPLETE_FULL_25_INCOMPLETE' if not pending_d2
           else ('PARTIAL_HISTORICAL_THREE_ARM_ANALYSIS_D2_BLOCKED' if blocked
                 else ('D2_INPUTS_PREPARED_AWAITING_REMAINING_RESPONSES' if new_plan or existing_plan
                       else 'D2_PREPARATION_INCOMPLETE')))
    result={'status':stage,
            'development_manifest_questions':len(freeze['development_ids']),'active_smoke_questions':len(ids),
            'full_four_arm_pilot_complete':False,'historically_exposed':True,'new_physical_qwen_calls':sum(read(p).get('experiment')=='E2' for p in (root/'qwen/calls').glob('*.intent.json')),
            'D2_rewrite_model_calls':0,'D2_distinct_new_input_estimate':len(existing_plan) if existing_plan else ('UNKNOWN' if blocked else len(new_plan)),
            'verified_historical_physical_responses':len(used_physical),'verified_historical_logical_QA_observations':historical_logical,
            'assigned_defense_positions':len(rows),'valid_defense_positions':sum(r['status']==old.VALID for r in rows),
            'completed_valid_defense_positions':sum(r['complete'] for r in rows),
            'pending_D2_valid_positions':sum(r['pipeline']=='D2' and r['status']==old.VALID and not r['complete'] for r in rows),
            'metrics':grouped,'paired_contrasts':paired(rows,ids),'historical_timing':timing,'new_D2_retrieval_work':new_cost,
            'pilot_sha256':sha(root/'pilot.freeze.json'),'e2_freeze_sha256':sha(root/'e2.freeze.json'),
            'selection_sha256':sha(root/'selection.seal.json'),'native_history_sha256':sha(root/'history.private.json'),
            'blocker':blocker if blocked else None}
    if output.exists():raise FileExistsError('New aggregate file required')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('metrics','paired_contrasts','historical_timing')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True);p.add_argument('--native-root',required=True);p.add_argument('--output',required=True);p.add_argument('--snapshot');a=p.parse_args();execute(a.root,a.native_root,a.output,a.snapshot)
