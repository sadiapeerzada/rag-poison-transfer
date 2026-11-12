#!/usr/bin/env python3
"""Aggregate actual E1 observations, retaining pending work and construction failures."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import numpy as np
from scripts.hotpotqa_native_reuse import read
from scripts.audit_e1_e2_reuse import digest,binding_key,sha
from src.experiments.protocol import corpus_fingerprint
from src.experiments import week9_construction as old
from src.evaluation.metrics import exact_match,f1_score
from src.evaluation.qa_records import validate_qa


def intervals(vectors,seed=20261112):
    """Question-cluster percentile CI, retaining all repeated seeds per cluster."""
    a=np.array(vectors,dtype=float);n=len(a)
    weights=np.random.default_rng(seed).multinomial(n,[1/n]*n,size=2000)
    totals=weights@a;ok=totals[:,1]>0
    samples=totals[ok,0]/totals[ok,1]
    return {'lower':float(np.quantile(samples,.025)) if len(samples) else None,
            'upper':float(np.quantile(samples,.975)) if len(samples) else None,
            'undefined_replicates':int((~ok).sum())}


def summarize(rows,ids):
    """Return no numeric outcome rate when any valid assigned pair is pending."""
    groups=defaultdict(list)
    for r in rows:groups[(r['family'],r['intensity'],r['method'],r['source'],r['pipeline'])].append(r)
    result=[]
    for key,items in groups.items():
        family,intensity,method,source,pipeline=key
        failures=Counter(r['status'] for r in items if r['status']!=old.VALID)
        valid=[r for r in items if r['status']==old.VALID]
        pending=sum(not r.get('complete',False) for r in valid)
        metrics={}
        for name in ('coverage','end_to_end_target_match','valid_target_match','source_success','atr','clean_correct_to_wrong','clean_em','poison_em','clean_f1','poison_f1','poison_exposure'):
            values={qid:[0.,0.] for qid in ids}
            for r in items:
                v=r['status']==old.VALID;completed=v and r.get('complete',False)
                if name=='coverage':num,den=v,1
                elif name=='end_to_end_target_match':num,den=(r['target_match'] if completed else 0),1
                elif not completed:continue
                elif name=='valid_target_match':num,den=r['target_match'],1
                elif name=='source_success':num,den=r['source_success'],1
                elif name=='atr':num,den=r['source_success'] and r['target_match'],r['source_success']
                elif name=='clean_correct_to_wrong':num,den=r['clean_em'] and not r['poison_em'],r['clean_em']
                else:num,den=r[name],1
                values[r['query_id']][0]+=float(num);values[r['query_id']][1]+=float(den)
            numerator=sum(v[0] for v in values.values());denominator=sum(v[1] for v in values.values())
            if pending and name!='coverage':metrics[name]={'status':'INCOMPLETE','estimate':None};continue
            metrics[name]={'numerator':numerator,'denominator':denominator,
                           'estimate':numerator/denominator if denominator else None,
                           'ci95_question_cluster':intervals(list(values.values()))}
        result.append(dict(family=family,intensity=intensity,method=method,source=source,pipeline=pipeline,
                           assigned=len(items),valid=len(valid),pending=pending,construction_failures=dict(failures),metrics=metrics))
    return result


def paired_contrasts(rows,ids):
    result=[]
    by={}
    for r in rows:by.setdefault((r['family'],r['intensity'],r['source'],r['pipeline'],r['method']),[]).append(r)
    bases=sorted({key[:4] for key in by})
    for family,intensity,source,pipeline in bases:
        for baseline in ('M1','M2'):
            a=by.get((family,intensity,source,pipeline,'M3'),[])
            b=by.get((family,intensity,source,pipeline,baseline),[])
            row=dict(family=family,intensity=intensity,source=source,pipeline=pipeline,contrast='M3-'+baseline)
            if not a or not b or any(r['status']==old.VALID and not r.get('complete') for r in a+b):
                result.append({**row,'status':'INCOMPLETE','estimate':None});continue
            vectors=[]
            for qid in ids:
                aa=[r for r in a if r['query_id']==qid];bb=[r for r in b if r['query_id']==qid]
                if len(aa)!=len(bb):raise ValueError('Unmatched policy denominators')
                vectors.append([sum(r.get('target_match',False) for r in aa)-sum(r.get('target_match',False) for r in bb),len(aa)])
            num=sum(v[0] for v in vectors);den=sum(v[1] for v in vectors)
            result.append({**row,'status':('COMPLETE_EXPLORATORY' if any(r['status']==old.VALID for r in a+b) else 'COMPLETE_ZERO_CONSTRUCTION_COVERAGE'),'estimate':num/den if den else None,
                           'ci95_question_cluster':intervals(vectors)})
    return result


def aggregate(root,out):
    root,out=Path(root),Path(out)
    freeze=read(root/'pilot.freeze.json');seal=read(root/'selection.seal.json')
    adapter=read(root/'native-adapter.complete.json')
    if sha(root/'history.private.json')!=adapter['history_sha256']:raise ValueError('Native export changed')
    history=read(root/'history.private.json');by_id={r['observation_id']:r for r in history}
    by_binding={binding_key(r):r for r in history}
    clean=read(root/'clean.private.json');queries={q['query_id']:q for q in clean['queries']}
    ids=freeze['active_smoke_ids'];observations={};rows=[]
    # If a prepared input/response exists, prefer its exact binding; no guessing.
    logical_index={}
    if (root/'logical.private.json').is_file():
        plan={r['observation_id']:r for r in read(root/'plan.private.json')}
        for l in read(root/'logical.private.json'):
            logical_index[(l['cell'],l['source'],l['method'],l['pipeline'],l['query_id'])]=l
        for k,row in plan.items():
            if k in by_binding:observations[k]=by_binding[k]['generation']
            p=root/'qwen/calls'/(k+'.response.json')
            if p.exists():
                saved=read(p)
                if 'generation' in saved:
                    g=saved['generation'];validate_qa(g,g['extracted_answer']);observations[k]=g
    for key,choices in seal['selections'].items():
        cid,source,method=key.split('|')
        family,rest=cid.split('.intensity-');intensity,seed=map(int,rest.split('.seed-'))
        corpus=old.replay(clean,{'records':choices})['corpus'];cfp=corpus_fingerprint(corpus)
        for choice in choices:
            qid=choice['query_id']
            if qid not in ids:continue
            pair_by_pipeline={}
            for pipeline in sorted({'dense','reranker','rcd',source}):
                pair={}
                for condition in ('clean','poisoned'):
                    l=logical_index.get((cid,source,method,pipeline,qid),{})
                    if l.get(condition+'_input') in observations:pair[condition]=observations[l[condition+'_input']]
                    else:
                        old_row=by_id.get(digest([cid,source,pipeline,qid,condition]))
                        if old_row is not None and (condition=='clean' or (old_row['poison_corpus_sha256']==cfp and old_row['candidate_sha256']==digest({'documents':choice['documents'],'target':choice['target_answer']}))):
                            pair[condition]=old_row['generation']
                pair_by_pipeline[pipeline]=pair
            for pipeline in ('dense','reranker','rcd'):
                row={'family':family,'intensity':intensity,'seed':seed,'query_id':qid,'source':source,'method':method,
                     'pipeline':pipeline,'status':choice['status'],'complete':False}
                pair=pair_by_pipeline[pipeline];source_pair=pair_by_pipeline[source]
                if choice['status']==old.VALID and all(c in pair for c in ('clean','poisoned')) and 'poisoned' in source_pair:
                    ca=pair['clean']['extracted_answer'];pa=pair['poisoned']['extracted_answer'];gold=queries[qid]['gold_answer']
                    old_row=by_id.get(digest([cid,source,pipeline,qid,'poisoned']))
                    l=logical_index.get((cid,source,method,pipeline,qid),{})
                    evidence=(plan[l['poisoned_input']]['retrieval_evidence'] if l.get('poisoned_input') else old_row['retrieval_evidence'])
                    row.update(complete=True,target_match=bool(exact_match(pa,choice['target_answer'])),
                               source_success=bool(exact_match(source_pair['poisoned']['extracted_answer'],choice['target_answer'])),
                               clean_em=exact_match(ca,gold),poison_em=exact_match(pa,gold),clean_f1=f1_score(ca,gold),poison_f1=f1_score(pa,gold),
                               poison_exposure=bool(set(d['doc_id'] for d in choice['documents']) & set(d['doc_id'] for d in evidence)))
                rows.append(row)
    all_calls=list((root/'qwen/calls').glob('*.intent.json'))
    calls=[p for p in all_calls if read(p).get('experiment')=='E1']
    session_results=[]
    sessions=root.parent/'e1-e2-20261112-authorized-session/sessions'
    for intent in sorted(sessions.glob('*.intent.json')):
        request=read(intent)
        if request.get('pilot_sha256')!=sha(root/'pilot.freeze.json') or request.get('experiment')!='E1':continue
        end=intent.with_name(intent.name.replace('.intent.','.complete.'))
        session_results.append(read(end) if end.exists() else {'status':'UNRESOLVED_SESSION','elapsed_seconds':None})
    failed_init=sum(s.get('failed_initializations',0) for s in session_results)
    model_resource_stops=list((root/'qwen').rglob('RESOURCE_STOP.json'))
    completed=failed=indeterminate=0
    for p in calls:
        r=p.with_name(p.name.replace('.intent.','.response.'))
        if not r.exists():indeterminate+=1
        elif 'generation' in read(r):completed+=1
        else:failed+=1
    grouped=summarize(rows,ids)
    output={'status':'PARTIAL_EXPLORATORY_HISTORICAL_REUSE' if not calls else 'PARTIAL_EXPLORATORY_BOUNDED_EXECUTION',
            'development_manifest_questions':len(freeze['development_ids']),'active_smoke_questions':len(ids),
            'historically_exposed':True,'full_25_pilot_complete':False,
            'metrics':grouped,'paired_policy_contrasts':paired_contrasts(rows,ids),'logical_assigned_target_positions':len(rows),
            'valid_target_positions':sum(r['status']==old.VALID for r in rows),
            'completed_valid_target_positions':sum(r['complete'] for r in rows),
            'new_physical_qwen_attempts':len(calls),'combined_root_physical_attempts':len(all_calls),
            'model_initialization_attempts':len(session_results),'failed_initializations':failed_init,
            'inference_execution_seconds_charged':sum(s['elapsed_seconds'] for s in session_results if s.get('elapsed_seconds') is not None),
            'session_states':[s['status'] for s in session_results],
            'model_resource_stop_receipts':len(model_resource_stops),'new_completed_calls':completed,'failed_calls':failed,
            'indeterminate_calls':indeterminate,'retries':0,
            'historical_physical_responses_verified':adapter['verified_historical_physical_calls'],
            'screening':seal['screening'],'new_call_estimate':read(root/'prepare.complete.json')['reuse']['new_call_estimate'] if (root/'prepare.complete.json').exists() else 'UNKNOWN',
            'resource_blocked':any((root/name).exists() for name in ('PREPARATION_RESOURCE_STOP.json','RESOURCE_STOP.json')) or bool(session_results and session_results[-1]['status'] in ('RESOURCE_STOP_DURING_MODEL_INITIALIZATION','UNRESOLVED_SESSION','STOPPED')),
            'resource_stop':read(root/'RESOURCE_STOP.json') if (root/'RESOURCE_STOP.json').exists() else (read(root/'PREPARATION_RESOURCE_STOP.json') if (root/'PREPARATION_RESOURCE_STOP.json').exists() else (read(sorted(model_resource_stops,key=lambda p:p.stat().st_mtime)[-1]) if model_resource_stops else None)),
            'new_retrieval_checkpoints':len(list((root/'retrieval-checkpoints').glob('*.json'))),
            'pilot_sha256':sha(root/'pilot.freeze.json'),'selection_sha256':sha(root/'selection.seal.json'),
            'native_history_sha256':sha(root/'history.private.json'),
            'policy_comparison':'INCOMPLETE until all matched valid M1/M2/M3 observations resolve; no incomplete-case superiority claim'}
    if out.exists():raise FileExistsError('New aggregate file required')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k not in ('metrics','screening','paired_policy_contrasts')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True);p.add_argument('--output',required=True);a=p.parse_args();aggregate(a.root,a.output)
