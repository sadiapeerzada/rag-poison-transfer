import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from src.experiments import execution_reliability as r
from src.pipelines.generator import GenerationResult
from src.evaluation.qa_records import generate_qa


class Backend:
    def __init__(self):self.calls=0;self.crash=False
    def format_prompt(self,prompt):return '<fixture>'+prompt
    def generate(self,prompt,max_tokens):
        self.calls+=1
        if self.crash:raise KeyboardInterrupt('injected interruption')
        return GenerationResult('A. B. Example',.1,10,4,self.format_prompt(prompt))


def journal(tmp,backend,name='a',effective=None):
    j=r.Journal(backend,tmp/name,{'model':'fixture'},tmp/'cache',effective or {'model':{'hash':'one'},'qa_seed':42,'corpus_fingerprint':'corpus','decoding':{'temperature':0}})
    j.set_evidence_context([{'doc_id':'doc','text':'Evidence','score':1.0}]);return j


def observe(j,prompt='Answer',tokens=64,condition='clean'):
    return generate_qa(j,prompt,tokens,context={'condition':condition,'query_id':'qid','pipeline':'dense'})


def test_atomic_never_overwrites_or_publishes_partial(tmp_path):
    p=tmp_path/'data.json';r.atomic(p,{'a':1})
    with pytest.raises(FileExistsError):r.atomic(p,{'a':2})
    assert r.read(p)=={'a':1} and not list(tmp_path.glob('.atomic-*'))
    with pytest.raises(ValueError):r.atomic(tmp_path/'bad.json',{'a':float('nan')})
    assert not (tmp_path/'bad.json').exists()


def test_clean_cache_exact_equivalence_and_actual_timing(tmp_path):
    b=Backend();one=observe(journal(tmp_path,b));two=observe(journal(tmp_path,b,'b'))
    assert b.calls==1 and one['raw_response']==two['raw_response']=='A. B. Example'
    assert two['execution']['kind']=='clean_cache_hit' and two['generator_latency_seconds']==0
    assert two['execution']['origin_generation']['generator_latency_seconds']==.1
    r.validate_store(tmp_path)
    replay=observe(journal(tmp_path,b));assert b.calls==1 and replay['execution']['kind']=='journal_replay'


@pytest.mark.parametrize('change',['model','seed','corpus','decoding','prompt','evidence','max_tokens','poisoned'])
def test_cache_misses_on_any_effective_input_change(tmp_path,change):
    b=Backend();observe(journal(tmp_path,b));j=journal(tmp_path,b,'b')
    if change=='model':j.effective['model']={'hash':'other'}
    elif change=='seed':j.effective['qa_seed']=43
    elif change=='corpus':j.effective['corpus_fingerprint']='other'
    elif change=='decoding':j.effective['decoding']={'temperature':.1}
    elif change=='evidence':j.set_evidence_context([{'doc_id':'different','text':'Evidence','score':1.0}])
    observe(j,prompt='Different' if change=='prompt' else 'Answer',tokens=32 if change=='max_tokens' else 64,condition='poisoned' if change=='poisoned' else 'clean')
    assert b.calls==2


def test_unresolved_intent_and_corruption_never_regenerate(tmp_path):
    b=Backend();b.crash=True
    with pytest.raises(KeyboardInterrupt):observe(journal(tmp_path,b))
    b.crash=False
    with pytest.raises(RuntimeError,match='Unresolved'):observe(journal(tmp_path,b))
    assert b.calls==1
    with pytest.raises(RuntimeError,match='Unresolved'):r.validate_store(tmp_path)


def test_checkpoint_and_cache_corruption_rejected(tmp_path):
    binding={'query_id':'q'};p=tmp_path/'checkpoint.json';r.checkpoint(p,binding,lambda:{'answer':'one'})
    obj=r.read(p);obj['data']['answer']='tampered';p.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='integrity'):r.checkpoint(p,binding,lambda:pytest.fail('No regeneration'))
    b=Backend();observe(journal(tmp_path/'other',b));entry=next((tmp_path/'other/cache').glob('*.json'))
    obj=r.read(entry);obj['generation']['raw_response']='tampered';entry.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='cache'):observe(journal(tmp_path/'other',b,'b'))
    assert b.calls==1


def test_writer_lock_rejects_concurrent_stage(tmp_path):
    import fcntl
    path=tmp_path/'run'
    @r.exclusive('root')
    def stage(root):return 'ok'
    with open(path.with_name('run.writer.lock'),'a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(RuntimeError,match='writer'):stage(path)


def test_cache_cannot_rebind_a_valid_generation_from_another_prompt(tmp_path):
    from src.experiments.week9_construction import fingerprint
    import hashlib
    b=Backend();observe(journal(tmp_path,b));entry=next((tmp_path/'cache').glob('*.json'))
    obj=r.read(entry);obj['generation']['prompt']='Other question';obj['generation']['prompt_sha256']=hashlib.sha256(b'Other question').hexdigest()
    obj['generation_sha256']=fingerprint(obj['generation']);entry.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='effective input'):observe(journal(tmp_path,b,'b'))
    assert b.calls==1


def test_output_namespace_and_duplicate_population_are_fail_closed(tmp_path):
    r.require_output({'planned_outputs':{'evaluation':str(tmp_path/'good')}},'evaluation',tmp_path/'good')
    with pytest.raises(ValueError,match='namespace'):r.require_output({'planned_outputs':{'evaluation':str(tmp_path/'good')}},'evaluation',tmp_path/'wrong')
    clean={'corpus':[],'queries':[{'query_id':'q'},{'query_id':'q'}]}
    with pytest.raises(ValueError,match='Duplicate'):
        r.evaluate_batches(spec={'execution':r.DEFAULTS},pin='a',root=tmp_path,key='case',clean=clean,poisoned={'corpus':[],'queries':[]},pipeline='dense',config={},backend=None,build_retriever=None)


def test_local_model_lease_prevents_parallel_model_processes(tmp_path,monkeypatch):
    import fcntl
    monkeypatch.setattr(r,'_MODEL_LEASE',None)
    p=tmp_path/'model.lock'
    with open(p,'a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(RuntimeError,match='MLX lease'):r.acquire_model_lease(p)
    r.acquire_model_lease(p)
    try:assert r._MODEL_LEASE is not None
    finally:r._MODEL_LEASE.close();r._MODEL_LEASE=None


def test_snapshot_hashes_stream_without_reading_entire_weight_file(tmp_path,monkeypatch):
    import hashlib
    from scripts import run_week9_protocol_poison_matrix as base
    payload=b'streaming-provenance'*(128*1024);path=tmp_path/'model.safetensors';path.write_bytes(payload)
    expected=hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(Path,'read_bytes',lambda self:pytest.fail('Whole-file allocation forbidden for model hash'))
    assert base.sha(path)==expected
