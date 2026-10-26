"""Immutable local execution checkpoints; no scientific selection or approval logic."""
import contextlib
import copy
import fcntl
import functools
import hashlib
import inspect
import json
import os
from pathlib import Path
import tempfile
import time

from src.experiments.week9_construction import fingerprint
from src.experiments.protocol import corpus_fingerprint
from src.evaluation.qa_records import capture_generation, validate_qa
from src.pipelines.generator import GenerationResult

VERSION = 'atomic-batched-clean-cache/v1'
DEFAULTS = {'version': VERSION, 'batch_size': 25, 'clean_qa_cache': True,
            'unresolved_intent': 'halt-no-regeneration', 'poisoned_corpus': 'complete-condition-corpus',
            'cache_timing': 'actual-lookup-time; original-generation-retained-separately',
            'qa_seed': 42, 'concurrency': 'one-writer-per-stage; one-local-model-process'}


def read(path):
    path=Path(path)
    if path.is_symlink(): raise ValueError('Checkpoint symlinks forbidden')
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic(path,value):
    """Fsync then exclusive atomic publication; never replace an existing file."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.atomic-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            json.dump(value,stream,sort_keys=True,ensure_ascii=False,allow_nan=False,indent=2)
            stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.link(tmp,path)  # EEXIST rather than overwriting another writer.
        directory=os.open(path.parent,os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def once(path,value):
    if Path(path).exists():
        if read(path)!=value: raise ValueError('Immutable checkpoint mismatch: '+str(path))
    else: atomic(path,value)


def exclusive(argument):
    """OS lock is external to sealed artifacts and released on process exit."""
    def decorate(fn):
        @functools.wraps(fn)
        def wrapped(*args,**kwargs):
            root=Path(inspect.signature(fn).bind(*args,**kwargs).arguments[argument])
            from scripts.run_week9_heldout_poison_matrix import _ensure_output_outside_repository
            root=_ensure_output_outside_repository(root)
            root.parent.mkdir(parents=True,exist_ok=True)
            with open(root.with_name(root.name+'.writer.lock'),'a') as lock:
                try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError: raise RuntimeError('Another stage writer is active') from None
                return fn(*args,**kwargs)
        return wrapped
    return decorate


def resume_root(root,binding):
    root=Path(root)
    if root.is_symlink(): raise ValueError('Output root symlink forbidden')
    plan=root/'execution.plan.json'
    if root.exists() and not plan.exists() and any(root.iterdir()):
        raise ValueError('Unrecognized existing execution directory')
    once(plan,{'schema':VERSION,'binding':binding})
    validate_store(root)


def checkpoint(path,binding,produce):
    if Path(path).exists():
        obj=read(path)
        if obj.get('binding')!=binding or obj.get('data_sha256')!=fingerprint(obj.get('data')):
            raise ValueError('Checkpoint integrity/provenance mismatch: '+str(path))
        return obj['data']
    data=produce()
    atomic(path,{'schema':VERSION,'binding':binding,'data':data,'data_sha256':fingerprint(data)})
    return data


def validate_store(root):
    """Fail closed on incomplete backend calls, corruption, symlinks or temp debris."""
    root=Path(root)
    for p in root.rglob('*'):
        if p.is_symlink(): raise ValueError('Execution symlink forbidden')
        if p.name.startswith('.atomic-'): raise RuntimeError('Unpublished atomic checkpoint needs explicit recovery')
        if not p.is_file() or p.suffix!='.json': continue
        obj=read(p)
        if not isinstance(obj,dict): continue
        if obj.get('schema')==VERSION and 'data_sha256' in obj:
            if obj['data_sha256']!=fingerprint(obj.get('data')): raise ValueError('Checkpoint data integrity mismatch')
        if p.name.endswith('.intent.json'):
            response=p.with_name(p.name.replace('.intent.json','.response.json'))
            if not response.exists(): raise RuntimeError('Unresolved generation intent; no silent regeneration')
            saved=read(response)
            if saved.get('request_fingerprint')!=fingerprint(obj) or 'error' in saved:
                raise RuntimeError('Failed or inconsistent generation journal')
            g=saved['generation'];validate_qa(g,g['extracted_answer'])
            if g['prompt']!=obj['prompt']:raise ValueError('Journal prompt differs from intent')
            if saved.get('generation_sha256') is not None and saved['generation_sha256']!=fingerprint(g):
                raise ValueError('Generation journal content mismatch')
        if obj.get('schema')=='clean-effective-input-cache/v1':
            if obj['key']!=fingerprint(obj['binding']) or obj['generation_sha256']!=fingerprint(obj['generation']):
                raise ValueError('Clean cache integrity mismatch')
            validate_qa(obj['generation'],obj['generation']['extracted_answer'])
            if obj['generation']['prompt']!=obj['binding']['prompt'] or obj['generation']['backend_prompt']!=obj['binding']['backend_prompt']:
                raise ValueError('Cache effective input mismatch')


class PauseExecution(Exception): pass


class BatchBudget:
    def __init__(self,maximum=None):
        if maximum is not None and maximum<1: raise ValueError('Batch maximum must be positive')
        self.maximum=maximum;self.used=0
    def begin(self):
        if self.maximum is not None and self.used>=self.maximum: raise PauseExecution('Batch budget reached; resume the same stage')
        self.used+=1


class LazyBackend:
    def __init__(self,factory): self.factory=factory;self.value=None
    def get(self):
        if self.value is None: self.value=self.factory()
        return self.value


class Journal:
    """Per-query QA journal with optional exact-input clean cache; poison never cached."""
    def __init__(self,backend,directory,provenance,cache=None,effective=None,corpora=None):
        self.backend=backend;self.directory=Path(directory);self.model_provenance=provenance
        self.cache=Path(cache) if cache else None;self.effective=effective or {}
        self.index=0;self.context={};self.evidence=None;self.last=None;self.corpora=corpora or {}
    def set_observation_context(self,context): self.context=dict(context)
    def set_evidence_context(self,evidence): self.evidence=evidence
    def consume_execution_metadata(self):
        result=self.last;self.last=None;return result
    def generate(self,prompt,max_tokens):
        from src.utils.seeding import set_seed
        index=self.index;self.index+=1
        request={'prompt':prompt,'max_tokens':max_tokens,'provenance':self.model_provenance,
                 'context':self.context,'effective':{**self.effective,'corpus_fingerprint':self.corpora.get(self.context.get('condition'),self.effective.get('corpus_fingerprint'))},'evidence':self.evidence}
        intent=self.directory/f'{index:02d}.intent.json';response=self.directory/f'{index:02d}.response.json'
        if intent.exists():
            if read(intent)!=request: raise ValueError('Generation checkpoint input mismatch')
            if not response.exists(): raise RuntimeError('Unresolved generation intent; no silent regeneration')
            saved=read(response)
            if saved.get('request_fingerprint')!=fingerprint(request) or 'error' in saved: raise RuntimeError('Invalid generation checkpoint')
            g=saved['generation'];validate_qa(g,g['extracted_answer'])
            if saved['generation_sha256']!=fingerprint(g): raise ValueError('Generation checkpoint corruption')
            self.last={'schema':'qa-execution/v1','kind':'journal_replay','backend_call_executed':False,
                       'origin_generation':g,'response_sha256':sha(response)}
            return GenerationResult(g['raw_response'],0.0,g['prompt_tokens'],g['completion_tokens'],g['backend_prompt'])
        atomic(intent,request)
        backend=self.backend.get() if isinstance(self.backend,LazyBackend) else self.backend
        formatter=getattr(backend,'format_prompt',None)
        eligible=(self.cache is not None and self.context.get('condition')=='clean' and
                  self.evidence is not None and formatter is not None)
        binding={**self.effective,'prompt':prompt,'backend_prompt':formatter(prompt) if formatter else None,
                 'max_tokens':max_tokens,'query_id':self.context.get('query_id'),'pipeline':self.context.get('pipeline'),
                 'evidence':self.evidence}
        key=fingerprint(binding);entry=self.cache/(key+'.json') if eligible else None
        try:
            if entry is not None and entry.exists():
                cached=read(entry)
                if (cached.get('schema')!='clean-effective-input-cache/v1' or cached['binding']!=binding or
                    cached['key']!=key or cached['generation_sha256']!=fingerprint(cached['generation'])):
                    raise ValueError('Clean cache provenance mismatch')
                origin=cached['generation'];validate_qa(origin,origin['extracted_answer'])
                if origin['prompt']!=binding['prompt'] or origin['backend_prompt']!=binding['backend_prompt']:raise ValueError('Cache effective input mismatch')
                g={**origin,'elapsed_seconds':0.0,'generator_latency_seconds':0.0}
                self.last={'schema':'qa-execution/v1','kind':'clean_cache_hit','backend_call_executed':False,
                           'cache_key':key,'cache_entry_sha256':sha(entry),'origin_generation':origin}
                result=GenerationResult(g['raw_response'],0.0,g['prompt_tokens'],g['completion_tokens'],g['backend_prompt'])
            else:
                # This seed is already the declared greedy QA seed; never use poison outcomes as a seed.
                set_seed(self.effective.get('qa_seed',42))
                if hasattr(backend,'seed'): backend.seed(self.effective.get('qa_seed',42))
                result,g=capture_generation(backend,prompt,max_tokens)
                if formatter and g['backend_prompt']!=binding['backend_prompt']: raise ValueError('Effective backend input mismatch')
                self.last={'schema':'qa-execution/v1','kind':'backend_call','backend_call_executed':True}
                if entry is not None:
                    atomic(entry,{'schema':'clean-effective-input-cache/v1','binding':binding,'key':key,
                                  'generation':g,'generation_sha256':fingerprint(g)})
            self.last['effective_input_sha256']=fingerprint(binding)
            atomic(response,{'request_fingerprint':fingerprint(request),'generation':g,'generation_sha256':fingerprint(g),
                             'execution':self.last})
            return result
        except Exception as error:
            if not response.exists(): atomic(response,{'request_fingerprint':fingerprint(request),'error':str(error),'error_type':type(error).__name__})
            raise


def evaluate_batches(*,spec,pin,root,key,clean,poisoned,pipeline,config,backend,build_retriever,budget=None):
    """Query shards NEVER change the retriever corpus or the construction population."""
    from scripts.run_week9_matched_poison_comparison import evaluate_pipeline
    from scripts import run_week9_protocol_poison_matrix as base
    settings=spec['execution'];size=settings['batch_size'];root=Path(root);budget=budget or BatchBudget()
    if len({q['query_id'] for q in clean['queries']})!=len(clean['queries']):raise ValueError('Duplicate evaluation query ID')
    cfp=corpus_fingerprint(clean['corpus']);pfp=corpus_fingerprint(poisoned['corpus'])
    binding={'protocol_sha256':pin,'condition_key':key,'pipeline':pipeline,'config':config,
             'clean_corpus_fingerprint':cfp,'poisoned_corpus_fingerprint':pfp,
             'query_ids':[q['query_id'] for q in clean['queries']]}
    directory=root/'batches'/key/pipeline;once(directory/'plan.json',binding)
    attacked={q['query_id']:q for q in poisoned['queries']};clean_r=poison_r=None;observations=[]
    for start in range(0,len(clean['queries']),size):
        queries=clean['queries'][start:start+size];batch=directory/f'{start:06d}.complete.json'
        batch_binding={**binding,'batch_query_ids':[q['query_id'] for q in queries]}
        if batch.exists():
            items=checkpoint(batch,batch_binding,lambda:None)
        else:
            budget.begin();items=[]
            for q in queries:
                qid=q['query_id'];token=hashlib.sha256(qid.encode()).hexdigest()
                qb={'batch_binding_sha256':fingerprint(batch_binding),'query_fingerprint':fingerprint(q),'poisoned_query':attacked.get(qid)}
                def produce(q=q,qid=qid,token=token):
                    nonlocal clean_r,poison_r
                    if qid not in attacked:return None
                    if clean_r is None:
                        clean_r=build_retriever(config);poison_r=build_retriever(config)
                        clean_r.build(copy.deepcopy(clean['corpus']));poison_r.build(copy.deepcopy(poisoned['corpus']))
                    base.runtime_seed(settings['qa_seed'])
                    effective={'model':spec['model'],'environment':spec.get('environment'),
                        'decoding':spec.get('rules',{}).get('decoding',{'temperature':0.0}),
                        'qa_seed':settings['qa_seed'],'corpus_fingerprint':cfp,'retriever_config':config,
                        'execution_version':VERSION,'source':spec.get('source'),
                        'retrieval_models':spec.get('retrieval_snapshots',spec.get('replication',{}).get('retrieval_snapshots'))}
                    journal=Journal(backend,root/'calls'/key/pipeline/token,
                        {'protocol_sha256':pin,'condition_key':key,'query_id':qid,'model':spec['model']},
                        cache=root/'clean-cache' if settings['clean_qa_cache'] else None,effective=effective,corpora={'clean':cfp,'poisoned':pfp})
                    return evaluate_pipeline(pipeline=pipeline,clean_retriever=clean_r,poisoned_retriever=poison_r,
                        clean_data={'corpus':clean['corpus'],'queries':[q]},
                        poisoned_data={'corpus':poisoned['corpus'],'queries':[attacked[qid]]},
                        generator=journal,top_k=int(config['top_k']),max_tokens=int(config['max_tokens']))[0]
                items.append(checkpoint(directory/'queries'/(token+'.json'),qb,produce))
            checkpoint(batch,batch_binding,lambda:items)
        if len(items)!=len(queries): raise ValueError('Batch population mismatch')
        for q,item in zip(queries,items):
            token=hashlib.sha256(q['query_id'].encode()).hexdigest();qpath=directory/'queries'/(token+'.json')
            qb={'batch_binding_sha256':fingerprint(batch_binding),'query_fingerprint':fingerprint(q),'poisoned_query':attacked.get(q['query_id'])}
            if not qpath.exists() or checkpoint(qpath,qb,lambda:None)!=item:raise ValueError('Batch/query checkpoint mismatch')
            if item is not None and item['query_id']!=q['query_id']:raise ValueError('Batch query reassembly mismatch')
            if (q['query_id'] in attacked)!=(item is not None):raise ValueError('Batch failed-construction mismatch')
            if item is not None:validate_measurement_link(root,key,pipeline,item)
        observations.extend(x for x in items if x is not None)
    return observations


def release_idle_memory():
    """Release unused allocator buffers between conditions, never live parameters."""
    import gc
    import sys
    gc.collect()
    torch=sys.modules.get('torch')
    if torch is not None and hasattr(torch,'mps') and torch.backends.mps.is_available():torch.mps.empty_cache()
    mx=sys.modules.get('mlx.core')
    if mx is not None and hasattr(mx,'clear_cache'):mx.clear_cache()


@exclusive('output')
def evaluate_replication(path,pin,construction,seal_pin,output,snapshot,value,dense,rcd,clean,cells,max_batches=None):
    from scripts import run_week9_protocol_poison_matrix as base
    from run import build_retriever
    require_output(value,'evaluation',output)
    root=Path(output)
    if root==Path(construction).resolve() or Path(construction).resolve() in root.parents:raise ValueError('Evaluation cannot write inside construction')
    resume_root(root,{'stage':'2wiki-evaluation','protocol_sha256':pin,'construction_seal_sha256':seal_pin})
    complete=root/'evaluation.complete.json'
    if complete.exists():
        manifest=read(complete);files={p.relative_to(root).as_posix():sha(p) for p in root.rglob('*') if p.is_file() and p!=complete}
        if manifest['files_sha256']!=files:raise ValueError('Completed evaluation integrity mismatch')
        return {'status':'already_complete','evaluation_completion_sha256':sha(complete)}
    once(root/'evaluation.plan.json',{'schema':base.EVALUATION_SCHEMA,'protocol_sha256':pin,
        'construction_seal_sha256':seal_pin,'source':value['source'],'scope':value['binding']['scope']})
    budget=BatchBudget(max_batches);backend=LazyBackend(lambda:base.generator(rcd,snapshot))
    for identity,cell in cells.items():
        if base.code_binding()!=value['source']:raise ValueError('Source changed during evaluation')
        poisoned=base.protocol.replay(clean,cell);paired={}
        for arm,cfg in [('dense',dense),('rcd',rcd)]:
            observations=evaluate_batches(spec=value,pin=pin,root=root,key=identity,clean=clean,poisoned=poisoned,
                pipeline=arm,config=cfg,backend=backend,build_retriever=build_retriever,budget=budget)
            paired[arm]={r['query_id']:r for r in observations};release_idle_memory()
        rows=[{'schema':base.protocol.ROW_SCHEMA,'construction_seal_sha256':seal_pin,
            'cell_fingerprint':fingerprint(cell),'pipeline':arm,'query_id':r['query_id'],
            'construction_status':r['status'],'evaluation_status':'evaluated' if r['status']==base.protocol.VALID else 'not_evaluated_construction_failed',
            'measurement':paired[arm].get(r['query_id'])} for arm in ('dense','rcd') for r in cell['records']]
        base.protocol.validate_evaluation_rows(rows,cell,clean,seal_pin)
        once(root/identity/'rows.json',rows)
        once(root/identity/'summary.json',{arm:base.protocol.summarize([r for r in rows if r['pipeline']==arm]) for arm in ('dense','rcd')})
    base.load_protocol(path,pin,snapshot);validate_store(root)
    atomic(complete,{'schema':base.EVALUATION_SCHEMA,'protocol_sha256':pin,'construction_seal_sha256':seal_pin,
        'scope':value['binding']['scope'],'rows_sha256':{identity:sha(root/identity/'rows.json') for identity in cells},
        'execution':value['execution'],'files_sha256':{p.relative_to(root).as_posix():sha(p) for p in root.rglob('*') if p.is_file()}})
    return {'status':'complete','evaluation_completion_sha256':sha(complete)}


def validate_measurement_link(root,key,pipeline,measurement):
    qid=measurement['query_id'];token=hashlib.sha256(qid.encode()).hexdigest();root=Path(root)
    saved=read(root/'batches'/key/pipeline/'queries'/(token+'.json'))
    if saved.get('data')!=measurement or saved.get('data_sha256')!=fingerprint(measurement):
        raise ValueError('Assembled measurement differs from query checkpoint')
    for index,condition in enumerate(('clean','poisoned')):
        directory=root/'calls'/key/pipeline/token
        request=read(directory/f'{index:02d}.intent.json');response=read(directory/f'{index:02d}.response.json')
        observed=measurement[condition+'_condition']['generation'];actual=response['generation']
        if request['context'].get('condition')!=condition or request['context'].get('query_id')!=qid or request['context'].get('pipeline')!=pipeline or request['prompt']!=observed['prompt']:
            raise ValueError('Measurement generation context mismatch')
        for field in ('prompt','backend_prompt','raw_response','extracted_answer','prompt_tokens','completion_tokens'):
            if observed.get(field)!=actual.get(field):raise ValueError('Measurement differs from generation journal')
        execution=observed.get('execution',{})
        if execution.get('kind')=='journal_replay':
            if execution.get('origin_generation')!=actual or execution.get('response_sha256')!=sha(directory/f'{index:02d}.response.json'):
                raise ValueError('Replay provenance mismatch')
        elif execution!=response.get('execution'):raise ValueError('Execution provenance mismatch')
        if response.get('execution',{}).get('kind')=='clean_cache_hit':
            cache=response['execution'];entry=root/'clean-cache'/(cache['cache_key']+'.json')
            if sha(entry)!=cache['cache_entry_sha256']:raise ValueError('Referenced clean cache mismatch')


def accounting(root):
    result={'logical_generation_observations':0,'actual_backend_calls':0,'clean_cache_hits':0}
    for path in Path(root).rglob('*.response.json'):
        value=read(path)
        if 'generation' not in value:continue
        result['logical_generation_observations']+=1
        event=value.get('execution',{})
        if event.get('kind')=='clean_cache_hit':result['clean_cache_hits']+=1
        elif event.get('backend_call_executed',True):result['actual_backend_calls']+=1
    return result


def planned_outputs(protocol_path,kind):
    root=Path(protocol_path).resolve().parent/'execution'
    stages=('candidates','selection','evaluation','aggregate') if kind=='transfer' else ('construction','evaluation','aggregate')
    return {s:str(root/('aggregate.json' if s=='aggregate' else s)) for s in stages}


def require_output(spec,stage,path):
    expected=spec.get('planned_outputs',{}).get(stage)
    if expected is not None and Path(path).resolve()!=Path(expected).resolve():
        raise ValueError('Output path differs from frozen execution namespace')


_MODEL_LEASE=None


def acquire_model_lease(path=None):
    """One cooperating local model process across transfer and replication stages."""
    global _MODEL_LEASE
    if _MODEL_LEASE is not None:return
    path=Path(path) if path else Path(tempfile.gettempdir())/'rag-poison-transfer-local-model.writer.lock'
    handle=open(path,'a')
    try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close();raise RuntimeError('Another local research model process holds the MLX lease') from None
    _MODEL_LEASE=handle
    import atexit
    atexit.register(handle.close)
