#!/usr/bin/env python3
"""Run only pinned private development inputs with hard combined session limits.

Completed/failed/indeterminate intent files all consume the physical-call cap.
No automatic retry. This entrypoint imports no retriever or torch model.
"""
import argparse
from datetime import datetime,timezone
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.audit_e1_e2_reuse import digest,sha,binding_key,classify,compare
from scripts.hotpotqa_native_reuse import read
from src.experiments.execution_reliability import atomic,acquire_model_lease
from scripts.bounded_pilot_resources import Guard
from src.evaluation.qa_records import capture_generation,validate_qa


def count_attempts(root):
    return len(list((Path(root)/'qwen/calls').glob('*.intent.json')))


def available_calls(attempts,limits,e1_max,experiment):
    records=[read(p) for p in Path(attempts).glob('*.json')]
    total=limits['new_physical_calls']-len(records)
    e1=e1_max-sum(r['experiment']=='E1' for r in records)
    return max(0,min(total,e1 if experiment=='E1' else total))


def validate_journals(root):
    directory=Path(root)/'qwen/calls'
    for intent in directory.glob('*.intent.json'):
        response=intent.with_name(intent.name.replace('.intent.','.response.'))
        if not response.is_file():raise RuntimeError('Unresolved physical intent; no automatic retry')
        saved=read(response);request=read(intent)
        if saved.get('request_sha256')!=digest(request) or 'generation' not in saved:
            raise RuntimeError('Failed or inconsistent physical call; no automatic retry')
        g=saved['generation'];validate_qa(g,g['extracted_answer'])
        if saved.get('generation_sha256')!=digest(g) or g['prompt']!=request['input']['prompt'] or g['backend_prompt']!=request['input']['backend_prompt']:
            raise RuntimeError('Response/input verification failed')


def execute(root,snapshot,experiment='E1'):
    root,snapshot=Path(root).resolve(),Path(snapshot).resolve()
    if root.is_relative_to(ROOT):raise ValueError('Private results outside repository required')
    freeze=read(root/'pilot.freeze.json');prep=read(root/'prepare.complete.json')
    if sha(root/'pilot.freeze.json')!=prep['pilot_sha256'] or sha(root/'selection.seal.json')!=prep['selection_sha256']:
        raise ValueError('Pilot or selection seal changed')
    for name,pin in freeze['source_files_sha256'].items():
        if sha(ROOT/'scripts'/name)!=pin:raise ValueError('Preparation implementation changed')
    for name,key in [('plan.private.json','plan_sha256'),('history.private.json','history_sha256'),('logical.private.json','logical_sha256')]:
        if sha(root/name)!=prep[key]:raise ValueError('Private preparation file changed')
    if experiment=='E1':plan=read(root/'plan.private.json')
    else:
        ep=read(root/'e2.prepare.complete.json')
        if sha(root/'e2.plan.private.json')!=ep['plan_sha256'] or ep['pilot_sha256']!=prep['pilot_sha256']:
            raise ValueError('E2 input seal changed')
        plan=read(root/'e2.plan.private.json')
    history=read(root/'history.private.json')
    receipt=compare(plan,history)
    if receipt['new_call_estimate']=='UNKNOWN':raise ValueError('Unverified input/call budget')
    historical={}
    for row in history:
        if classify(row,row)=='REUSABLE':historical.setdefault(binding_key(row),row)
    limits=freeze['limits'];acquire_model_lease()
    directory=root/'qwen';directory.mkdir(exist_ok=True)
    # All versioned pilots in this private research parent share one authorized
    # session ledger. Changing a pilot directory never resets the call/time cap.
    ledger=root.parent/'e1-e2-20261112-authorized-session'
    ledger.mkdir(exist_ok=True)
    authorization=ledger/'authorization.json'
    if authorization.exists():
        if read(authorization)!=limits:raise ValueError('Shared authorization limits differ')
    else:atomic(authorization,limits)
    attempts=ledger/'attempts';attempts.mkdir(exist_ok=True)
    sessions=ledger/'sessions';sessions.mkdir(exist_ok=True)
    elapsed=0.
    for intent in sessions.glob('*.intent.json'):
        end=intent.with_name(intent.name.replace('.intent.','.complete.'))
        if not end.is_file():raise RuntimeError('Interrupted session requires resource/provenance reconciliation')
        elapsed+=read(end)['elapsed_seconds']
    validate_journals(root)
    already={p.stem.split('.')[0] for p in (directory/'calls').glob('*.response.json')}
    pending=[r for r in plan if binding_key(r) not in historical and binding_key(r) not in already]
    available=available_calls(attempts,limits,freeze['E1_max_new_calls'],experiment)
    if not pending or available<=0:
        print(json.dumps({'status':'NO_NEW_CALLS_OR_BUDGET_EXHAUSTED','pending':len(pending),'physical_attempts':count_attempts(root)}));return
    if elapsed>=limits['inference_seconds']:raise RuntimeError('Combined initialization/inference wall budget exhausted')
    started=time.monotonic()
    sid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    session={'experiment':experiment,'limits':limits,'prior_inference_seconds':elapsed,
             'expected_distinct_new_inputs':len(pending),'available_physical_attempts':available,
             'runner_sha256':sha(__file__),'pilot_sha256':prep['pilot_sha256']}
    atomic(sessions/(sid+'.intent.json'),session)
    result={'status':'STOPPED_BEFORE_MODEL_LOAD','completed_new_calls':0,'retries':0}
    guard=None
    try:
        if snapshot.name!=freeze['model']['revision'] or {p.relative_to(snapshot).as_posix():sha(p) for p in snapshot.rglob('*') if p.is_file()}!=freeze['model']['files_sha256']:
            raise ValueError('Pinned model snapshot differs')
        env=pending[0]['backend_environment']
        if sys.version!=env['python'] or any(importlib.metadata.version(k)!=v for k,v in env.items() if k!='python'):
            raise ValueError('Frozen backend runtime differs')
        import mlx.core as mx
        guard=Guard({**limits,'inference_seconds':limits['inference_seconds']-elapsed},directory,metal=mx)
        guard.started=started;guard.start()
        # Bound cached Metal allocations without changing model parameters.
        mx.set_cache_limit(2*2**30)
        from src.pipelines.generator import MLXGenerator
        from mlx_lm.sample_utils import make_sampler
        backend=MLXGenerator(str(snapshot));original=backend._generate_fn
        backend._generate_fn=lambda *a,**kw:original(*a,**kw,sampler=make_sampler(temp=0.0))
        guard.check()
        for row in pending:
            if result['completed_new_calls']>=available:result['status']='PHYSICAL_CALL_CAP';break
            guard.check();key=binding_key(row)
            if backend.format_prompt(row['prompt'])!=row['backend_prompt']:
                raise ValueError('Effective generator prompt mismatch')
            request={'experiment':experiment,'input':row,'binding_sha256':key,
                     'session':sid,'pilot_sha256':prep['pilot_sha256']}
            calls=directory/'calls';calls.mkdir(exist_ok=True)
            # Reserve an attempt globally before dispatch. A reservation is never
            # reclaimed after failure/interruption, including across pilot versions.
            atomic(attempts/(sid+'-'+key+'.json'),{'experiment':experiment,'input_sha256':key,'pilot_root':str(root)})
            atomic(calls/(key+'.intent.json'),request)
            try:
                backend.seed(42)
                _,g=capture_generation(backend,row['prompt'],64)
                validate_qa(g,g['extracted_answer'])
                if g['backend_prompt']!=row['backend_prompt']:raise ValueError('Actual backend prompt differs')
                atomic(calls/(key+'.response.json'),{'request_sha256':digest(request),'generation':g,
                       'generation_sha256':digest(g),'physical_call_id':digest([sid,key]),'provenance':'physical_completed'})
                result['completed_new_calls']+=1
                print(json.dumps({'experiment':experiment,'completed_new_calls':result['completed_new_calls'],
                                  'combined_physical_attempts':len(list(attempts.glob('*.json'))),'elapsed_seconds':round(time.monotonic()-started,2)}),flush=True)
            except Exception as exc:
                response=calls/(key+'.response.json')
                if not response.exists():atomic(response,{'request_sha256':digest(request),'error_type':type(exc).__name__})
                raise
        else:result['status']='ALL_PREPARED_INPUTS_COMPLETED'
    except Exception as exc:
        result['status']='STOPPED';result['reason']=str(exc)
        raise
    finally:
        if guard:guard.close()
        result.update(elapsed_seconds=time.monotonic()-started,physical_attempts=count_attempts(root),
                      max_rss=guard.max_rss if guard else None,max_metal=guard.max_metal if guard else None)
        atomic(sessions/(sid+'.complete.json'),result)
        print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True);p.add_argument('--snapshot',required=True);p.add_argument('--experiment',choices=['E1','E2'],default='E1');a=p.parse_args()
    execute(a.root,a.snapshot,a.experiment)
