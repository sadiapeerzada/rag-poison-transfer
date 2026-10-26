"""Protocol/profile integration with synthetic inputs and generators only."""
import copy
import json
from pathlib import Path
import sys
import pytest
from scripts import run_week9_protocol_poison_matrix as base
from src.attacks import semantic_profiles as profiles
from src.experiments import week9_construction as protocol
from src.pipelines.generator import GenerationResult


class Backend:
    def __init__(self):self.calls=0
    def generate(self,prompt,max_tokens):
        self.calls+=1
        if 'Who wrote' in prompt:text='Bob Writer wrote The Example Historical Chronicle.'
        elif 'Copy the exact reference answer' in prompt:text='Yes, both Example Central Station and Other Example Station are located in the same country.'
        else:text='Both Example Central Station and Other Example Station are located in the same country.'
        return GenerationResult(text,.1,10,20)


@pytest.fixture
def setup(tmp_path,monkeypatch):
    clean={'queries':[
        {'query_id':'person','question':'Who wrote The Example Historical Chronicle?','gold_answer':'Alice Author','gold_doc_ids':['clean']},
        {'query_id':'binary','question':'Are both Example Central Station and Other Example Station located in the same country?','gold_answer':'no','gold_doc_ids':['clean']}],
        'corpus':[{'doc_id':'clean','text':'Synthetic clean corpus.'}]}
    pool=[{'query_id':'source-person','question':'Who wrote The Other Example Book?','gold_answer':'Bob Writer'},
          {'query_id':'source-binary','question':'Are both A Station and B Station in the same country?','gold_answer':'yes'}]
    binding={'scope':'development','query_ids':['person','binary'],'matrix':[list(c) for c in protocol.cells('development')],'model_identity':'fixture'}
    backend=Backend()
    monkeypatch.setattr(base,'context_metadata',lambda *a:(binding,{}, {},pool))
    monkeypatch.setattr(base,'environment',lambda:{'python':'fixture'})
    monkeypatch.setattr(base,'code_binding',lambda:{'git_commit_sha':'fixture','code_fingerprint':'code'})
    monkeypatch.setattr(base,'model_binding',lambda *a:{'revision':'fixture'})
    monkeypatch.setattr(base,'load_clean',lambda *a:clean)
    monkeypatch.setattr(base,'runtime_seed',lambda *a:None)
    monkeypatch.setattr(base,'generator',lambda *a:backend)
    path=tmp_path/'namespace'/'protocol.json'
    replication={'schema':'rag-poison-transfer.2wiki-replication-inputs/v2'}
    def freeze(identifier=profiles.DEVELOPMENT):
        return base.freeze_protocol(path,'development',tmp_path/'snapshot',replication,semantic_profile=identifier)['protocol_sha256']
    return path,freeze,backend,clean,pool


def test_explicit_profile_freeze_and_load_records_versions_and_hashes(setup):
    path,freeze,backend,_,_=setup;pin=freeze();value,*_=base.load_protocol(path,pin)
    assert value['schema']==base.PROFILE_PROTOCOL_SCHEMA and backend.calls==0
    profile=value['semantic_profile'];assert profile==profiles.descriptor(profiles.DEVELOPMENT,'development')
    assert value['rules']['semantic_validator']==profile['validation_version']
    assert profile['max_attempts']==2 and profile['implementation_sha256']


@pytest.mark.parametrize('identifier',[profiles.LEGACY,profiles.DEVELOPMENT])
def test_both_explicit_profiles_are_supported_without_default_changes(setup,identifier):
    path,freeze,*_=setup;pin=freeze(identifier);value,*_=base.load_protocol(path,pin)
    assert value['semantic_profile']['identifier']==identifier
    assert protocol.rules()['semantic_validator']=='conservative-text-heuristic/v4'


@pytest.mark.parametrize('mutation',[
 lambda v:v['semantic_profile'].update(identifier='unknown'),
 lambda v:v['semantic_profile'].update(validation_version='stale'),
 lambda v:v['semantic_profile'].update(max_attempts=3),
 lambda v:v['semantic_profile']['implementation_sha256'].update({'src/attacks/semantic_fluent.py':'bad'}),
 lambda v:v['rules'].update(semantic_validator='stale'),
 lambda v:v['binding'].update(scope='heldout'),
 lambda v:v.pop('semantic_profile'),
])
def test_profile_corruption_or_scope_change_fails_closed(setup,mutation):
    path,freeze,*_=setup;freeze();value=json.loads(path.read_text());mutation(value);path.write_text(json.dumps(value))
    with pytest.raises(ValueError):base.load_protocol(path,base.sha(path))


def test_development_profile_denied_before_reading_heldout_metadata(tmp_path,monkeypatch):
    monkeypatch.setattr(base,'context_metadata',lambda *a:pytest.fail('Do not inspect heldout data'))
    with pytest.raises(ValueError,match='development-only'):
        base.freeze_protocol(tmp_path/'p.json','heldout',tmp_path/'snapshot',semantic_profile=profiles.DEVELOPMENT)
    assert not (tmp_path/'p.json').exists()


@pytest.mark.parametrize('argv',[
 ['preflight','--semantic-profile','unknown'],
 ['construct','--semantic-profile',profiles.DEVELOPMENT],
 ['evaluate','--semantic-profile',profiles.LEGACY],
 ['aggregate','--semantic-profile',profiles.LEGACY],
])
def test_cli_rejects_unknown_profile_and_post_freeze_override(monkeypatch,argv):
    monkeypatch.setattr(sys,'argv',['runner',*argv])
    with pytest.raises(SystemExit) as exc:base.main()
    assert exc.value.code==2


def test_profiled_construction_seal_replay_and_attempt_metadata(setup):
    path,freeze,backend,clean,_=setup;pin=freeze();value=json.loads(path.read_text());root=Path(value['planned_outputs']['construction'])
    result=base.construct(path,pin,root,Path('fixture'));assert backend.calls==3
    _,_,_,restored,cells=base.load_sealed(path,pin,root,result['construction_seal_sha256'])
    assert restored==clean
    for cell in cells.values():
        assert cell['semantic_profile']==value['semantic_profile']
        assert all(r['semantic_profile_sha256']==protocol.fingerprint(value['semantic_profile']) for r in cell['records'])
        assert len(protocol.replay(clean,cell)['queries'])==2
    semantic=cells[protocol.cell_id(protocol.ATTACKS[1],1,42)]
    attempts=semantic['records'][1]['attempt_records'][0]['attempts']
    assert len(attempts)==2 and attempts[0]['failure_category']=='literal_target_missing'
    assert 'Copy the exact reference answer' in attempts[1]['prompt']
    plan=json.loads((root/'construction.plan.json').read_text());assert plan['semantic_profile']==value['semantic_profile']
    intent=next(root.glob('*/generation/*/*.intent.json'));saved=json.loads(intent.read_text())
    assert saved['provenance']['semantic_profile_sha256']==protocol.fingerprint(value['semantic_profile'])


def test_profiled_complete_response_replay_after_checkpoint_interruption(setup,monkeypatch):
    path,freeze,backend,*_=setup;pin=freeze();value=json.loads(path.read_text());root=Path(value['planned_outputs']['construction'])
    original=base.write;interrupted=False
    def write(path,value):
        nonlocal interrupted
        if not interrupted and Path(path).parent.name=='queries' and 'semantic_fluent' in str(path):
            interrupted=True;raise OSError('fixture checkpoint interruption')
        return original(path,value)
    monkeypatch.setattr(base,'write',write)
    with pytest.raises(OSError):base.construct(path,pin,root,Path('fixture'))
    assert backend.calls==1
    monkeypatch.setattr(base,'write',original)
    result=base.construct(path,pin,root,Path('fixture'))
    assert backend.calls==3 and result['status']=='all_construction_frozen_no_evaluation'


def test_resume_refuses_profile_change_without_reusing_journal(setup,monkeypatch):
    path,freeze,backend,*_=setup;pin=freeze();value=json.loads(path.read_text());root=Path(value['planned_outputs']['construction'])
    original=base.write
    def fail(path,value):
        if Path(path).parent.name=='queries' and 'semantic_fluent' in str(path):raise OSError('fixture interruption')
        return original(path,value)
    monkeypatch.setattr(base,'write',fail)
    with pytest.raises(OSError):base.construct(path,pin,root,Path('fixture'))
    monkeypatch.setattr(base,'write',original);assert backend.calls==1
    value['semantic_profile']=profiles.descriptor(profiles.LEGACY,'development');value['rules']=base.frozen_rules(value['replication'],value['semantic_profile'])
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='recovery provenance'):base.construct(path,base.sha(path),root,Path('fixture'))
    assert backend.calls==1


def test_journal_profile_identity_prevents_cross_profile_replay(tmp_path):
    backend=Backend();g=base.JournalGenerator(backend,tmp_path,{'semantic_profile_sha256':'old'})
    g.generate('Who wrote the book?',150)
    with pytest.raises(ValueError,match='provenance'):base.JournalGenerator(backend,tmp_path,{'semantic_profile_sha256':'new'}).generate('Who wrote the book?',150)
    assert backend.calls==1


def test_manifest_profile_and_attempt_versions_fail_validation(setup):
    path,freeze,backend,clean,pool=setup;pin=freeze();value=json.loads(path.read_text());root=Path(value['planned_outputs']['construction'])
    base.construct(path,pin,root,Path('fixture'));cell=json.loads((root/protocol.cell_id(protocol.ATTACKS[1],1,42)/'construction.json').read_text())
    for field in ('prompt_version','validation_version','retry_policy'):
        changed=copy.deepcopy(cell);changed['records'][0]['attempt_records'][0]['attempts'][0][field]='stale'
        with pytest.raises(ValueError,match='version'):protocol.validate_cell(changed,clean,pool,pin,**base.profile_kwargs(value))
    with pytest.raises(ValueError,match='profile'):protocol.validate_cell(cell,clean,pool,pin)


def test_profiled_evaluation_resume_and_aggregate_keep_pairing(setup,monkeypatch):
    from types import SimpleNamespace
    import run
    from src.experiments import execution_reliability as reliable
    path,freeze,backend,clean,pool=setup
    binding=base.context_metadata('development')[0];cfg={'top_k':3,'max_tokens':64,'retriever':'dense'}
    monkeypatch.setattr(base,'context_metadata',lambda *a:(binding,cfg,cfg,pool))
    class Retriever:
        def build(self,corpus):self.docs=[SimpleNamespace(**d) for d in corpus]
        def retrieve(self,question,top_k):return self.docs[:top_k]
    monkeypatch.setattr(run,'build_retriever',lambda *a:Retriever())
    monkeypatch.setattr(reliable,'release_idle_memory',lambda:None)
    pin=freeze();value=json.loads(path.read_text());root=Path(value['planned_outputs']['construction']);out=Path(value['planned_outputs']['evaluation'])
    seal=base.construct(path,pin,root,Path('fixture'))['construction_seal_sha256']
    with pytest.raises(reliable.PauseExecution):base.evaluate(path,pin,root,seal,out,Path('fixture'),max_batches=1)
    completed=base.evaluate(path,pin,root,seal,out,Path('fixture'))
    calls=backend.calls;base.evaluate(path,pin,root,seal,out,Path('fixture'));assert backend.calls==calls
    aggregate=Path(value['planned_outputs']['aggregate'])
    base.aggregate(path,pin,root,seal,out,completed['evaluation_completion_sha256'],aggregate)
    result=json.loads(aggregate.read_text());assert result['semantic_profile']==value['semantic_profile']
    assert len(result['cells'])==2 and all(v['unique_queries']==2 for v in result['paired_query_cluster_uncertainty'].values())
    for cell in result['cells'].values():
        assert cell['dense']['attempted']==cell['rcd']['attempted']==2
