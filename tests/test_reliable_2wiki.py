import copy
import json
from pathlib import Path
import pytest
from test_reliable_workflows import setup
from test_twowiki_replication_adapter import prepared
from scripts import run_source_selection_transfer as transfer
from scripts import run_week9_protocol_poison_matrix as base
from scripts import materialize_2wiki_execution_inputs as materializer
from src.experiments import execution_reliability as r
from src.experiments import twowiki_replication as two
from src.experiments import week9_construction as old


def test_local_inputs_pin_data_scope_and_retrieval_weights(prepared,monkeypatch,tmp_path):
    spec,manifest,dev=prepared
    parent={'schema':base.REPLICATION_PROTOCOL_SCHEMA,'rules':{**old.rules(),'dataset_replication':'risk-disclosed-2wiki/v1'},'replication':spec,'binding':{'dataset':{'revision':two.REVISION},'scope':'heldout','cohort_manifest_sha256':spec['cohort_manifest_sha256'],
        'query_ids':[row['query_id'] for row in manifest['cohorts']['dev']]}}
    pp=tmp_path/'parent.json';pp.write_text(json.dumps(parent));sp=tmp_path/'spec.json';sp.write_text(json.dumps(spec))
    monkeypatch.setattr(base,'model_binding',lambda path,name:{'repository':name,'snapshot':str(Path(path).resolve())})
    monkeypatch.setattr(two,'fetch_selected',lambda *a:pytest.fail('Development materialization must not fetch heldout'))
    result=materializer.materialize(sp,base.sha(sp),pp,base.sha(pp),'development',tmp_path/'local',Path('embed'),Path('rerank'))
    path=tmp_path/'local/replication_inputs.json';local=json.loads(path.read_text())
    assert result['model_calls']==0 and local['schema']==two.LOCAL_SCHEMA
    got=two.load_clean({'replication':local,'binding':{'scope':'development'}})
    assert got['queries']==dev['queries'][:2] and got['corpus']==dev['corpus']
    binding,_,rcd,_=two.metadata('development',local,{}, {'generator_model':'fixture','generator_backend':'mlx','rcd_consistency_weight':.45})
    assert rcd['rcd_consistency_weight']==.45 and rcd['embedder_model']==str(Path('embed').resolve())
    monkeypatch.setattr(base,'model_binding',lambda *a:{'changed':True})
    with pytest.raises(ValueError,match='snapshot'):two.metadata('development',local,{}, {'generator_model':'fixture','generator_backend':'mlx'})
    data_path=tmp_path/'local/dataset.json';data_path.write_text('{}')
    with pytest.raises(ValueError,match='SHA|fingerprint'):two.load_clean({'replication':local,'binding':{'scope':'development'}})


def test_replication_evaluation_resume_pairing_and_aggregate(monkeypatch,tmp_path):
    import run
    spec,backend=setup(monkeypatch);_,dense,rcd,development=transfer.load(None)
    clean=transfer.clean_data(spec,rcd);cells={}
    for family,intensity,seed in old.cells('development'):
        records=[old.construct_query(q,development,family,intensity,seed,backend,set_runtime_seed=lambda seed:None) for q in clean['queries']]
        cells[old.cell_id(family,intensity,seed)]=base.make_cell(clean,family,intensity,seed,'a'*64,records)
    value={'execution':spec['execution'],'binding':{'scope':'development','query_ids':[q['query_id'] for q in clean['queries']],'model_identity':'fixture'},
        'source':spec['source'],'model':spec['model'],'rules':old.rules()}
    monkeypatch.setattr(base,'load_sealed',lambda *a:(value,dense,rcd,clean,cells))
    monkeypatch.setattr(base,'load_protocol',lambda *a:(value,dense,rcd,development))
    monkeypatch.setattr(base,'code_binding',lambda:value['source'])
    monkeypatch.setattr(base,'model_binding',lambda *a:value['model'])
    monkeypatch.setattr(run,'build_retriever',transfer.build_retriever)
    out=tmp_path/'evaluation';before=backend.calls
    with pytest.raises(r.PauseExecution):base.evaluate(Path('protocol'),'a'*64,tmp_path/'construction','b'*64,out,Path('model'),max_batches=1)
    complete=base.evaluate(Path('protocol'),'a'*64,tmp_path/'construction','b'*64,out,Path('model'))
    assert backend.calls-before==6 # Two distinct clean arm inputs plus four poisoned observations.
    frozen=backend.calls;base.evaluate(Path('protocol'),'a'*64,tmp_path/'construction','b'*64,out,Path('model'));assert backend.calls==frozen
    result=base.aggregate(Path('protocol'),'a'*64,tmp_path/'construction','b'*64,out,complete['evaluation_completion_sha256'],tmp_path/'aggregate.json')
    assert result['status']=='validated_aggregate_written'
    before_hash=base.sha(tmp_path/'aggregate.json')
    base.aggregate(Path('protocol'),'a'*64,tmp_path/'construction','b'*64,out,complete['evaluation_completion_sha256'],tmp_path/'aggregate.json')
    assert base.sha(tmp_path/'aggregate.json')==before_hash
    got=json.loads((tmp_path/'aggregate.json').read_text())
    assert len(got['cells'])==2 and all(row['unique_queries']==2 for row in got['paired_query_cluster_uncertainty'].values())


def test_replication_construction_honors_batch_pause_and_replays_completed_calls(monkeypatch,tmp_path):
    spec,backend=setup(monkeypatch);_,dense,rcd,development=transfer.load(None)
    clean=transfer.clean_data(spec,rcd)
    value={'execution':spec['execution'],'binding':{'scope':'development','query_ids':[q['query_id'] for q in clean['queries']]},
        'source':spec['source'],'model':spec['model'],'rules':old.rules()}
    monkeypatch.setattr(base,'load_protocol',lambda *a:(value,dense,rcd,development))
    monkeypatch.setattr(base,'load_clean',lambda *a:clean)
    monkeypatch.setattr(base,'code_binding',lambda:value['source'])
    out=tmp_path/'construction'
    with pytest.raises(r.PauseExecution):base.construct(Path('protocol'),'a'*64,out,Path('model'),max_batches=1)
    assert not (out/'construction.seal.json').exists() and backend.calls==0
    result=base.construct(Path('protocol'),'a'*64,out,Path('model'))
    assert result['status']=='all_construction_frozen_no_evaluation' and backend.calls==1
    before=backend.calls
    with pytest.raises(ValueError,match='Already sealed'):base.construct(Path('protocol'),'a'*64,out,Path('model'))
    assert backend.calls==before
