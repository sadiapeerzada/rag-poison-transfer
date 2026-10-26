import copy
import json
from pathlib import Path
import pytest
from test_source_selection_transfer_workflow import fixture
from scripts import run_source_selection_transfer as t
from scripts import run_week9_protocol_poison_matrix as base
from src.experiments import execution_reliability as r
from src.pipelines.generator import GenerationResult


def setup(monkeypatch):
    fixture(monkeypatch)
    original=t.load
    spec,dense,rcd,dev=original(None)
    spec['execution']={**r.DEFAULTS,'batch_size':1};spec['rules']={'decoding':{'temperature':0}}
    monkeypatch.setattr(t,'load',lambda *a:(spec,dense,rcd,dev))
    monkeypatch.setattr(r,'release_idle_memory',lambda:None)
    class Backend:
        def __init__(self):self.calls=0
        def format_prompt(self,p):return '<fixture>'+p
        def generate(self,prompt,max_tokens):
            self.calls+=1
            target=prompt.split('Reference answer: "')[1].split('"')[0] if 'Reference answer: "' in prompt else 'Bob Writer'
            text=f'{target} is the documented answer to this question. The entry gives a direct identifying relation.' if 'Reference answer:' in prompt else target
            return GenerationResult(text,.1,10,4,self.format_prompt(prompt))
    backend=Backend();monkeypatch.setattr(base,'generator',lambda *a:backend)
    return spec,backend


def run(monkeypatch,tmp,cache,resume):
    spec,b=setup(monkeypatch);spec['execution']['clean_qa_cache']=cache
    lib=tmp/'lib';sel=tmp/'selection';ev=tmp/'evaluation'
    args=(Path('unused'),'a'*64)
    if resume:
        with pytest.raises(r.PauseExecution):t.materialize(*args,lib,Path('snapshot'),max_batches=1)
    lp=t.materialize(*args,lib,Path('snapshot'))['candidate_completion_sha256'];after_lib=b.calls
    assert t.materialize(*args,lib,Path('snapshot'))['candidate_completion_sha256']==lp and b.calls==after_lib
    if resume:
        with pytest.raises(r.PauseExecution):t.source_select(*args,lib,lp,sel,Path('snapshot'),max_batches=1)
    sp=t.source_select(*args,lib,lp,sel,Path('snapshot'))['selection_seal_sha256'];before_eval=b.calls
    if resume:
        with pytest.raises(r.PauseExecution):t.final_evaluate(*args,sel,sp,ev,Path('snapshot'),max_batches=1)
    result=t.final_evaluate(*args,sel,sp,ev,Path('snapshot'));assert result['source_target_cells']==40
    calls=b.calls-before_eval
    t.aggregate(*args,ev,base.sha(ev/'transfer.complete.json'),sel,sp,tmp/'aggregate.json',replicates=8)
    before=b.calls;t.final_evaluate(*args,sel,sp,ev,Path('snapshot'));assert b.calls==before
    audit=json.loads((tmp/'aggregate.json').read_text())
    assert audit['execution_accounting']['actual_backend_calls']==calls
    assert audit['execution_accounting']['clean_cache_hits']==(35 if cache else 0)
    metrics=json.loads((ev/'transfer_summary.json').read_text())
    answers=[]
    for p in sorted((ev/'rows').rglob('*.json')):
        for row in json.loads(p.read_text()):
            if row['measurement']:
                m=row['measurement'];answers.append(tuple(m[c+'_condition'][k] for c in ('clean','poisoned') for k in ('answer','em','f1','targeted_asr','poison_retrieved')))
    return metrics,answers,calls,ev


def test_independent_cached_uncached_and_resumed_answers_metrics_pairing(monkeypatch,tmp_path):
    uncached=run(monkeypatch,tmp_path/'uncached',False,False)
    cached=run(monkeypatch,tmp_path/'cached',True,True)
    assert uncached[:2]==cached[:2]
    assert uncached[2]==80 and cached[2]==45 # 40 poison calls + five distinct clean pipeline inputs.
    # Full corpus is bound on every query batch, not truncated to its one query.
    plans=list((cached[3]/'batches').rglob('plan.json'))
    assert len(plans)==40 and all(len(json.loads(p.read_text())['query_ids'])==2 for p in plans)
    # A complete manifest cannot be silently reopened after extra data appears.
    (cached[3]/'extra.json').write_text('{}')
    with pytest.raises(ValueError,match='integrity'):
        t.final_evaluate(Path('unused'),'a'*64,tmp_path/'cached/selection',base.sha(tmp_path/'cached/selection/selection.seal.json'),cached[3],Path('snapshot'))


def test_query_checkpoint_corruption_during_resume_fails_closed(monkeypatch,tmp_path):
    setup(monkeypatch)
    with pytest.raises(r.PauseExecution):t.materialize(Path('unused'),'a'*64,tmp_path/'lib',Path('snapshot'),max_batches=1)
    p=next((tmp_path/'lib/query-checkpoints').rglob('*.json'));obj=json.loads(p.read_text());obj['data']['target_answer']='tampered';p.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='integrity'):t.materialize(Path('unused'),'a'*64,tmp_path/'lib',Path('snapshot'))


@pytest.mark.parametrize('stage',['construction','source-screen'])
def test_transfer_unresolved_generation_is_never_repeated(monkeypatch,tmp_path,stage):
    spec,backend=setup(monkeypatch);args=(Path('unused'),'a'*64)
    lib=tmp_path/'library';out=tmp_path/'selection'
    if stage=='source-screen':lp=t.materialize(*args,lib,Path('snapshot'))['candidate_completion_sha256']
    original=backend.generate
    def interrupt(*args,**kwargs):
        backend.calls+=1
        raise KeyboardInterrupt('Injected backend interruption')
    backend.generate=interrupt
    def invoke():
        if stage=='construction':return t.materialize(*args,lib,Path('snapshot'))
        return t.source_select(*args,lib,lp,out,Path('snapshot'))
    with pytest.raises(KeyboardInterrupt):invoke()
    consumed=backend.calls;backend.generate=original
    with pytest.raises(RuntimeError,match='Unresolved'):invoke()
    assert backend.calls==consumed
