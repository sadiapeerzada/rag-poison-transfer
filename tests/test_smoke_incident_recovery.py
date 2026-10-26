import copy
import hashlib
import json
from pathlib import Path
import pytest
from scripts import run_week9_protocol_poison_matrix as base
from scripts import audit_2wiki_smoke_incident as diag
from scripts import prepare_2wiki_recovery_smoke as fresh
from src.experiments import execution_reliability as reliable
from src.pipelines.generator import GenerationResult


class Fake:
    def __init__(self,fail=None):self.calls=0;self.fail=fail
    def generate(self,prompt,max_tokens):
        self.calls+=1
        if self.fail:raise self.fail
        return GenerationResult('A. B. Example',.1,4,4)


def record(tmp_path,backend=None,provenance=None):
    backend=backend or Fake();provenance=provenance or {'model':{'revision':'fixture'}}
    base.JournalGenerator(backend,tmp_path,provenance).generate('Fixture prompt',64)
    return backend,provenance


def test_completed_replay_does_not_execute_backend_or_rewrite_response(tmp_path):
    b,p=record(tmp_path);before=base.sha(tmp_path/'00.response.json')
    assert base.JournalGenerator(b,tmp_path,p).generate('Fixture prompt',64).text=='A. B. Example'
    assert b.calls==1 and base.sha(tmp_path/'00.response.json')==before


@pytest.mark.parametrize('failure',['missing','error','provenance','corrupt_text','wrong_prompt','content_hash','orphan'])
def test_invalid_legacy_journals_refuse_before_any_new_call(tmp_path,failure):
    b,p=record(tmp_path)
    response=tmp_path/'00.response.json';intent=tmp_path/'00.intent.json';saved=json.loads(response.read_text())
    if failure=='missing':response.unlink()
    elif failure=='error':saved={'request_fingerprint':saved['request_fingerprint'],'error':'Recorded backend failure','error_type':'RuntimeError'};response.write_text(json.dumps(saved))
    elif failure=='provenance':p={'model':{'revision':'changed'}}
    elif failure=='corrupt_text':saved['generation']['raw_response']='Tampered';response.write_text(json.dumps(saved))
    elif failure=='wrong_prompt':
        saved['generation']['prompt']='Other';saved['generation']['prompt_sha256']=hashlib.sha256(b'Other').hexdigest();saved['generation_sha256']=base.protocol.fingerprint(saved['generation']);response.write_text(json.dumps(saved))
    elif failure=='content_hash':saved['generation_sha256']='0'*64;response.write_text(json.dumps(saved))
    elif failure=='orphan':intent.unlink()
    with pytest.raises((ValueError,RuntimeError)):base.JournalGenerator(b,tmp_path,p).generate('Fixture prompt',64)
    assert b.calls==1
    if failure=='orphan':assert not intent.exists()


def test_legacy_completed_response_without_new_hash_remains_replayable(tmp_path):
    b,p=record(tmp_path);f=tmp_path/'00.response.json';saved=json.loads(f.read_text());saved.pop('generation_sha256');f.write_text(json.dumps(saved))
    assert base.JournalGenerator(b,tmp_path,p).generate('Fixture prompt',64).text=='A. B. Example' and b.calls==1


@pytest.mark.parametrize('error',[KeyboardInterrupt('fixture interruption'),SystemExit('fixture termination')])
def test_interruption_after_intent_is_preserved_and_never_retried(tmp_path,error):
    b=Fake(error)
    with pytest.raises(type(error)):base.JournalGenerator(b,tmp_path,{'model':'fixture'}).generate('Fixture prompt',64)
    assert (tmp_path/'00.intent.json').exists() and not (tmp_path/'00.response.json').exists()
    b.fail=None
    with pytest.raises(RuntimeError,match='Indeterminate'):base.JournalGenerator(b,tmp_path,{'model':'fixture'}).generate('Fixture prompt',64)
    assert b.calls==1


def test_error_response_is_refused_without_next_backend_attempt(tmp_path):
    b=Fake(RuntimeError('fixture backend failure'))
    with pytest.raises(RuntimeError,match='backend failure'):record(tmp_path,b)
    b.fail=None
    with pytest.raises(RuntimeError,match='Failed/inconsistent'):base.JournalGenerator(b,tmp_path,{'model':{'revision':'fixture'}}).generate('Fixture prompt',64)
    assert b.calls==1


def test_reliable_qa_journal_orphan_is_also_refused(tmp_path):
    b=Fake();j=reliable.Journal(b,tmp_path,{'model':'fixture'});j.generate('Fixture prompt',64)
    (tmp_path/'00.intent.json').unlink()
    with pytest.raises(RuntimeError,match='Orphan'):reliable.Journal(b,tmp_path,{'model':'fixture'}).generate('Fixture prompt',64)
    with pytest.raises(RuntimeError,match='Orphan'):reliable.validate_store(tmp_path)
    assert b.calls==1


def incident_fixture(tmp_path):
    parent={'schema':base.RELIABLE_REPLICATION_SCHEMA,
        'binding':{'scope':'development','query_ids':['fixture-a','fixture-b'],
            'matrix':[list(c) for c in base.protocol.cells('development')],
            'dataset':{'loader':'load_2wikimultihopqa','split':'train','revision':fresh.two.REVISION},'model_identity':'fixture'},
        'replication':{'schema':fresh.two.LOCAL_SCHEMA,'scope':'development'},
        'execution':copy.deepcopy(reliable.DEFAULTS),
        'rules':{**base.protocol.rules(),'dataset_replication':'risk-disclosed-2wiki/v1'},
        'model':{'revision':'fixture'},'source':{'commit':'fixture'},
        'planned_outputs':{'construction':str(tmp_path/'failed'/'construction')}}
    path=tmp_path/'failed'/'protocol.json';path.parent.mkdir();path.write_text(json.dumps(parent));pin=base.sha(path)
    root=Path(parent['planned_outputs']['construction']);root.mkdir()
    (root/'construction.plan.json').write_text(json.dumps({'protocol_sha256':pin,'binding':parent['binding'],'source':parent['source']}))
    cell=root/'semantic_fluent_false_evidence.intensity-1.seed-42'
    for qid,error in [('fixture-a',None),('fixture-b',KeyboardInterrupt('fixture'))]:
        journal=cell/'generation'/hashlib.sha256(qid.encode()).hexdigest()
        b=Fake(error);g=base.JournalGenerator(b,journal,{'protocol_sha256':pin,'model':parent['model'],'query_id':qid})
        if error:
            with pytest.raises(KeyboardInterrupt):g.generate('Fixture prompt',64)
        else:g.generate('Fixture prompt',64)
    return parent,path,pin,root


def inventory(root):
    return {str(p.relative_to(root)):(base.sha(p),p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}


def test_incident_diagnostics_are_read_only_and_identify_missing_checkpoints(tmp_path):
    parent,path,pin,root=incident_fixture(tmp_path);before=inventory(tmp_path)
    result=diag.audit(path,pin,root)
    assert result['journal_counts']=={'completed_response':1,'unresolved_intent':1}
    assert result['expected_query_checkpoint_count']==4 and result['present_query_checkpoint_count']==0
    assert len(result['missing_query_checkpoints'])==4 and not result['construction_seal_present']
    assert result['plan_status']=='matches' and not result['automatic_retry_permitted']
    assert all(x['identity_matches'] and x['protocol_reference_matches'] and x['model_reference_matches'] for x in result['journal_events'])
    assert inventory(tmp_path)==before
    with pytest.raises(ValueError,match='SHA-256'):diag.audit(path,'0'*64,root)


def test_diagnostics_report_error_orphan_and_provenance_mismatch(tmp_path):
    parent,path,pin,root=incident_fixture(tmp_path)
    b=Fake(RuntimeError('fixture failure'));journal=root/'error'
    with pytest.raises(RuntimeError):base.JournalGenerator(b,journal,{'model':'wrong'}).generate('Fixture prompt',64)
    (root/'orphan.response.json').write_text('{}')
    result=diag.audit(path,pin,root)
    # Malformed model provenance is reported as invalid, never repaired.
    assert result['journal_counts']['invalid_journal']==1 and result['journal_counts']['orphan_response']==1
    saved=json.loads((journal/'00.intent.json').read_text());saved['provenance']={'model':parent['model'],'protocol_sha256':pin,'query_id':'fixture-a'}
    (journal/'00.intent.json').write_text(json.dumps(saved));response=json.loads((journal/'00.response.json').read_text())
    response['request_fingerprint']=base.protocol.fingerprint(saved);(journal/'00.response.json').write_text(json.dumps(response))
    assert diag.audit(path,pin,root)['journal_counts']['error_response']==1


@pytest.mark.parametrize('change',['heldout','many_ids','duplicate','intensity','seed','split','revision','replica_scope'])
def test_fresh_preparation_rejects_heldout_or_expanded_workloads(tmp_path,change):
    parent,*_=incident_fixture(tmp_path)
    if change=='heldout':parent['binding']['scope']='heldout'
    elif change=='many_ids':parent['binding']['query_ids']=[str(i) for i in range(300)]
    elif change=='duplicate':parent['binding']['query_ids']=['same','same']
    elif change=='intensity':parent['binding']['matrix'][0][1]=3
    elif change=='seed':parent['binding']['matrix'][0][2]=43
    elif change=='split':parent['binding']['dataset']['split']='validation'
    elif change=='revision':parent['binding']['dataset']['revision']='changed'
    elif change=='replica_scope':parent['replication']['scope']='heldout'
    with pytest.raises(ValueError,match='two-query'):fresh.validate_development_parent(parent)


def test_fresh_plan_does_not_write_or_generate_and_dirty_freeze_refused(tmp_path,monkeypatch):
    parent,path,pin,root=incident_fixture(tmp_path);new=tmp_path/'fresh';before=inventory(tmp_path)
    monkeypatch.setattr(base,'context_metadata',lambda *a:(parent['binding'],None,None,None))
    monkeypatch.setattr(base,'model_binding',lambda *a:parent['model'])
    monkeypatch.setattr(base,'generator',lambda *a:pytest.fail('No inference permitted'))
    def dirty():raise ValueError('Dirty source checkout')
    monkeypatch.setattr(base,'code_binding',dirty)
    plan=fresh.prepare(path,pin,root,new,tmp_path/'snapshot')
    assert plan['new_model_calls_executed']==0 and plan['query_ids']==parent['binding']['query_ids']
    assert not new.exists() and inventory(tmp_path)==before
    with pytest.raises(ValueError,match='Dirty'):fresh.prepare(path,pin,root,new,tmp_path/'snapshot',True)
    assert not new.exists() and inventory(tmp_path)==before
    with pytest.raises(ValueError,match='isolated'):fresh.prepare(path,pin,root,path.parent/'nested',tmp_path/'snapshot')


def test_construction_store_refusal_precedes_model_loading(tmp_path,monkeypatch):
    parent,path,pin,root=incident_fixture(tmp_path)
    clean={'queries':[{'query_id':'fixture-a'}],'corpus':[]}
    monkeypatch.setattr(base,'load_protocol',lambda *a:(parent,{}, {},None))
    monkeypatch.setattr(base,'load_clean',lambda *a:clean)
    monkeypatch.setattr(base,'query_set_fingerprint',lambda *a:'queries')
    monkeypatch.setattr(base,'corpus_fingerprint',lambda *a:'corpus')
    plan={'protocol_sha256':pin,'binding':parent['binding'],'source':parent['source'],'query_set_fingerprint':'queries','clean_corpus_fingerprint':'corpus'}
    (root/'construction.plan.json').write_text(json.dumps(plan))
    monkeypatch.setattr(base,'generator',lambda *a:pytest.fail('Backend must not load'))
    with pytest.raises(RuntimeError,match='Unresolved'):base.construct(path,pin,root,tmp_path/'snapshot')


def test_response_publication_interruption_preserves_unknown_call(tmp_path,monkeypatch):
    original_write=base.write;b=Fake()
    def interrupted_write(path,value):
        if Path(path).name.endswith('.response.json'):raise OSError('fixture publication interruption')
        return original_write(path,value)
    monkeypatch.setattr(base,'write',interrupted_write)
    with pytest.raises(OSError,match='publication'):record(tmp_path,b)
    assert b.calls==1 and (tmp_path/'00.intent.json').exists()
    monkeypatch.setattr(base,'write',original_write)
    with pytest.raises(RuntimeError,match='Indeterminate'):base.JournalGenerator(b,tmp_path,{'model':{'revision':'fixture'}}).generate('Fixture prompt',64)
    assert b.calls==1


def test_fresh_metadata_freeze_keeps_scientific_fields_and_old_namespace(tmp_path,monkeypatch):
    parent,path,pin,root=incident_fixture(tmp_path);before=inventory(path.parent);new=tmp_path/'fresh'
    monkeypatch.setattr(base,'context_metadata',lambda *a:(parent['binding'],None,None,None))
    monkeypatch.setattr(base,'model_binding',lambda *a:parent['model'])
    monkeypatch.setattr(base,'code_binding',lambda:{'commit':'reviewed-fixture'})
    monkeypatch.setattr(base,'generator',lambda *a:pytest.fail('No inference permitted'))
    def frozen(output,scope,snapshot,replication):
        assert scope=='development'
        value=copy.deepcopy(parent);value['source']={'commit':'reviewed-fixture'};value['replication']=replication
        value['planned_outputs']={'construction':str(new/'execution'/'construction')}
        reliable.atomic(output,value)
        return {'protocol_sha256':base.sha(output)}
    monkeypatch.setattr(base,'freeze_protocol',frozen)
    result=fresh.prepare(path,pin,root,new,tmp_path/'snapshot',True)
    value=json.loads((new/'protocol.json').read_text());fresh.validate_development_parent(value)
    assert result['new_model_calls_executed']==0 and (new/'incident_reference.json').exists()
    for field in ('binding','rules','model','execution'):assert value[field]==parent[field]
    assert inventory(path.parent)==before
