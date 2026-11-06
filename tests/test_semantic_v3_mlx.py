"""Mock-loader integration only. Dummy .safetensors files are not model weights."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_semantic_v3_pilot_prep import (inputs, re_pin_manifest, synthetic_authorization,
    healthy_resources, TEXT)
from src.experiments import semantic_v3_mlx as mlx
from src.experiments import semantic_v3_pilot as pilot
from src.experiments.semantic_v3_preparation import file_sha
from src.attacks.semantic_quality_targets_v3 import digest
from src.experiments.semantic_v3_checkpoint import read_record


def runtime_fixture(tmp_path):
    snapshot=tmp_path/'models--synthetic--fixture'/'snapshots'/('a'*40)
    snapshot.mkdir(parents=True)
    for name in ('config.json','tokenizer.json','tokenizer_config.json'):
        (snapshot/name).write_text('{}')
    (snapshot/'model.safetensors').write_bytes(b'NOT WEIGHTS: SYNTHETIC HASH FIXTURE')
    hashes={p.name:file_sha(p) for p in snapshot.iterdir()}
    return {'execution_kind':'authorized_model','snapshot_path':str(snapshot),
            'model_files':[{'path':str(snapshot/k),'sha256':v} for k,v in hashes.items()],
            'model_provenance':{'model_identity':'synthetic/fixture','revision':'a'*40,
                'model_files_sha256':hashes,'decoding':{'sampler':'explicit greedy','temperature':0.0}}}


def fake_imports(monkeypatch):
    events=[];sampler=object();model=object()
    class Tokenizer:
        def apply_chat_template(self,messages,**kwargs):
            events.append(('template',messages,kwargs));return 'FORMATTED\n'+messages[0]['content']
        def encode(self,text,**kwargs):return list(text.encode())
    tokenizer=Tokenizer()
    def load(path,**kwargs):events.append(('load',path,kwargs));return model,tokenizer
    def generate(m,t,**kwargs):
        assert m is model and t is tokenizer and kwargs['sampler'] is sampler
        events.append(('generate',kwargs));return TEXT
    def make_sampler(**kwargs):events.append(('sampler',kwargs));return sampler
    modules={'mlx.core':SimpleNamespace(random=SimpleNamespace(seed=lambda seed:events.append(('seed',seed)))),
        'mlx_lm':SimpleNamespace(load=load,generate=generate),
        'mlx_lm.sample_utils':SimpleNamespace(make_sampler=make_sampler)}
    def importer(name):
        events.append(('import',name));return modules[name]
    monkeypatch.setattr(mlx.importlib,'import_module',importer)
    return events


def test_adapter_is_lazy_and_uses_exact_seed_sampler_prompt_and_counts(tmp_path,monkeypatch):
    runtime=runtime_fixture(tmp_path);events=fake_imports(monkeypatch)
    adapter=mlx.LazyMLXAdapter(runtime)
    assert events==[] and adapter.model is None
    adapter.set_runtime_seed(42);assert events==[]
    result=adapter.generate('SYNTHETIC prompt',150)
    assert [e[0] for e in events].count('load')==1
    assert ('sampler',{'temp':0.0}) in events and ('seed',42) in events
    assert next(e for e in events if e[0]=='load')[2]=={
        'lazy':True,'tokenizer_config':{'local_files_only':True,'trust_remote_code':False}}
    assert result.text==TEXT and result.backend_prompt=='FORMATTED\nSYNTHETIC prompt'
    assert result.prompt_tokens==len(result.backend_prompt.encode())
    assert result.completion_tokens==len(TEXT.encode())
    adapter.set_runtime_seed(43);adapter.generate('second prompt',150)
    assert [e[0] for e in events].count('load')==1 and ('seed',43) in events
    assert adapter.model_provenance==runtime['model_provenance']


@pytest.mark.parametrize('change',['weight','tokenizer','extra','omitted','provenance','revision','identity','remote'])
def test_changed_or_incomplete_inventory_never_imports_mlx(tmp_path,monkeypatch,change):
    runtime=runtime_fixture(tmp_path);snapshot=Path(runtime['snapshot_path'])
    if change=='weight':(snapshot/'model.safetensors').write_bytes(b'changed fixture')
    elif change=='tokenizer':(snapshot/'tokenizer.json').write_text('changed')
    elif change=='extra':(snapshot/'unexpected.json').write_text('{}')
    elif change=='omitted':runtime['model_files'].pop()
    elif change=='provenance':runtime['model_provenance']['model_files_sha256']={}
    elif change=='revision':runtime['model_provenance']['revision']='b'*40
    elif change=='identity':runtime['model_provenance']['model_identity']='wrong/repository'
    else:runtime['snapshot_path']='synthetic/remote-model'
    events=fake_imports(monkeypatch);adapter=mlx.LazyMLXAdapter(runtime);adapter.set_runtime_seed(42)
    with pytest.raises(ValueError):adapter.generate('SYNTHETIC prompt',150)
    assert events==[]


def test_file_change_after_factory_creation_is_checked_at_load_boundary(tmp_path,monkeypatch):
    runtime=runtime_fixture(tmp_path);adapter=mlx.LazyMLXAdapter(runtime)
    (Path(runtime['snapshot_path'])/'model.safetensors').write_bytes(b'changed after constructor')
    events=fake_imports(monkeypatch);adapter.set_runtime_seed(42)
    with pytest.raises(ValueError):adapter.generate('SYNTHETIC',150)
    assert events==[]


@pytest.mark.parametrize('seed',[-1,2**32,True,None])
def test_seed_and_token_budget_are_explicit(tmp_path,monkeypatch,seed):
    events=fake_imports(monkeypatch);adapter=mlx.LazyMLXAdapter(runtime_fixture(tmp_path))
    with pytest.raises(ValueError):adapter.set_runtime_seed(seed)
    with pytest.raises(ValueError):adapter.generate('SYNTHETIC',150)
    adapter.set_runtime_seed(42)
    with pytest.raises(ValueError):adapter.generate('SYNTHETIC',151)
    assert events==[]


def test_default_driver_factory_is_mocked_and_journals_full_provenance(tmp_path,monkeypatch):
    ref,_,output=inputs(tmp_path)
    model_runtime=runtime_fixture(tmp_path)
    def update(runtime):
        runtime.update(model_runtime)
        runtime['environment']['packages']={p:'synthetic-version' for p in (
            'mlx','mlx-lm','numpy','transformers','tokenizers','psutil')}
        runtime['inventory_certification']={'inventory_sha256':digest(runtime),
            'complete_model_and_tokenizer_inventory':True,'complete_environment_inventory':True,
            'reviewer_id':'SYNTHETIC TEST REVIEWER ONLY'}
    ref=re_pin_manifest(tmp_path,ref,'runtime',update);auth=synthetic_authorization(ref)
    monkeypatch.setattr(pilot.importlib.metadata,'version',lambda name:'synthetic-version')
    events=fake_imports(monkeypatch)
    pilot.run(ref,authorization_reference=auth,max_cells=1)
    assert [e[0] for e in events].count('generate')==1
    request=read_record(next((output/'calls').glob('*.intent.json')))
    assert request['context']['model_provenance']==model_runtime['model_provenance']
    assert request['context']['environment']['packages']['mlx']=='synthetic-version'
    assert request['context']['runtime_sha256'] and request['context']['driver_implementation_sha256']
    assert request['admission']['authorization_sha256']==auth['sha256']
    assert ('seed',request['seed']) in events
    response=read_record(next((output/'calls').glob('*.response.json')))
    assert response['result']['backend_prompt'].startswith('FORMATTED\n')


def test_authorized_model_bad_inventory_stops_before_content_or_loader(tmp_path,monkeypatch):
    ref,_,output=inputs(tmp_path);model_runtime=runtime_fixture(tmp_path)
    def update(runtime):
        runtime.update(model_runtime)
        runtime['environment']['packages']={'mlx':'synthetic'}
        runtime['inventory_certification']=None
    ref=re_pin_manifest(tmp_path,ref,'runtime',update);auth=synthetic_authorization(ref)
    monkeypatch.setattr(pilot.importlib.metadata,'version',lambda name:'synthetic')
    events=fake_imports(monkeypatch)
    monkeypatch.setattr(pilot,'_content_values',lambda refs:pytest.fail('No content access'))
    with pytest.raises(ValueError):pilot.run(ref,authorization_reference=auth)
    assert events==[] and not output.exists()


def test_runtime_model_hash_mismatch_is_denied_before_content(tmp_path,monkeypatch):
    ref,_,output=inputs(tmp_path);model_runtime=runtime_fixture(tmp_path)
    def update(runtime):
        runtime.update(model_runtime)
        runtime['environment']['packages']={p:'synthetic' for p in (
            'mlx','mlx-lm','numpy','transformers','tokenizers','psutil')}
        runtime['inventory_certification']={'inventory_sha256':digest(runtime),
            'complete_model_and_tokenizer_inventory':True,'complete_environment_inventory':True,
            'reviewer_id':'SYNTHETIC TEST REVIEWER ONLY'}
    ref=re_pin_manifest(tmp_path,ref,'runtime',update);auth=synthetic_authorization(ref)
    (Path(model_runtime['snapshot_path'])/'model.safetensors').write_bytes(b'changed synthetic bytes')
    monkeypatch.setattr(pilot.importlib.metadata,'version',lambda name:'synthetic')
    events=fake_imports(monkeypatch)
    monkeypatch.setattr(pilot,'_content_values',lambda refs:pytest.fail('No content access'))
    with pytest.raises(ValueError,match='inventory'):pilot.run(ref,authorization_reference=auth)
    assert events==[] and not output.exists()


def test_authorized_runtime_cannot_substitute_unpinned_factory_before_content(tmp_path,monkeypatch):
    ref,_,output=inputs(tmp_path)
    ref=re_pin_manifest(tmp_path,ref,'runtime',lambda r:r.update(execution_kind='authorized_model'))
    monkeypatch.setattr(pilot,'_content_values',lambda refs:pytest.fail('No content access'))
    with pytest.raises(ValueError,match='factory overrides'):
        pilot.run(ref,authorization_reference=synthetic_authorization(ref),backend_factory=lambda:pytest.fail('factory'))
    assert not output.exists()
