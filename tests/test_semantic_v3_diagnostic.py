"""Synthetic diagnostic admission only: no real identities, content or model calls."""
import copy
import json
from pathlib import Path

import pytest
from test_semantic_v3_pilot_prep import (inputs, raw, healthy_resources, Stub,
                                         synthetic_authorization)
from src.attacks.semantic_quality_targets_v3 import digest
from src.experiments import semantic_v3_diagnostic as diagnostic
from src.experiments.semantic_v3_pilot import implementation_pins, preflight, run
from src.experiments.semantic_v3_checkpoint import ResumeBlocked


def diagnostic_inputs(tmp_path, monkeypatch):
    ref, _, output = inputs(tmp_path)
    manifest = json.loads(Path(ref['path']).read_text())
    artifacts = manifest['artifacts']
    cohort = json.loads(Path(artifacts['cohort']['path']).read_text())
    ids = cohort['query_ids']
    parent = {'schema':'rag-poison-transfer.semantic-development-protocol/v2',
        'development_study':{'identifier':'semantic-quality-25/v1'},
        'binding':{'scope':'development','query_ids':ids,
                   'complete_historical_nonoverlap_certified':False,
                   'development_artifact_sha256':'a'*64}}
    artifacts['historical_protocol'] = raw(tmp_path/'historical.json',parent)
    monkeypatch.setattr(diagnostic,'PARENT_SHA256',artifacts['historical_protocol']['sha256'])
    registry = json.loads(Path(artifacts['registry']['path']).read_text())
    registry.update(historical_gaps=['SYNTHETIC unknown sweep'],certification=None,
                    excluded_query_ids=sorted(set(registry['excluded_query_ids'])|set(ids)))
    artifacts['registry'] = raw(tmp_path/'registry.json',registry)
    data = json.loads(Path(artifacts['data']['path']).read_text())
    by_id = {q['query_id']:q for q in data['queries']}
    data.update(queries=[by_id[q] for q in ids],historical_source_sha256='a'*64)
    artifacts['data'] = raw(tmp_path/'data.json',data)
    artifacts['pool_ids'] = raw(tmp_path/'pool.json',ids)
    cohort = {'schema':diagnostic.RULE+'/cohort','scope':'development','query_ids':ids,
        'query_count':25,'selection_rule':'reuse-exact-documented-v2-order-no-replacement',
        'historical_protocol_sha256':diagnostic.PARENT_SHA256,'historical_data_sha256':'a'*64,
        'dataset_sha256':artifacts['data']['sha256'],'prospective_evidence':False}
    artifacts['cohort'] = raw(tmp_path/'cohort.json',cohort)
    receipt = {'schema':diagnostic.RULE+'/reuse-receipt','frozen_at':'2026-11-04T00:00:00Z',
        'pre_content_prospective_freeze':False,
        'input_sha256':{k:artifacts[k]['sha256'] for k in ('cohort','registry','pool_ids','data','historical_protocol')}}
    artifacts['cohort_receipt'] = raw(tmp_path/'cohort-receipt.json',receipt)
    targets = json.loads(Path(artifacts['targets']['path']).read_text())
    for row in targets:row['cohort_receipt_sha256']=artifacts['cohort_receipt']['sha256']
    artifacts['targets'] = raw(tmp_path/'targets.json',targets)
    manifest.update(schema='semantic-v3-diagnostic-manifest/v1',study_kind=diagnostic.KIND,
                    prospective_evidence=False,historical_exposure_risk_acknowledged=True)
    return repin(tmp_path,manifest)


def repin(tmp_path, manifest, *, mutate_review=None):
    artifacts=manifest['artifacts']
    payload={'input_sha256':{k:v['sha256'] for k,v in artifacts.items() if k not in ('protocol','study_review')},
        'driver_implementation_sha256':implementation_pins(),
        'output_namespace':manifest['output_namespace'],'study_kind':diagnostic.KIND}
    signatures=[]
    for role in sorted(diagnostic.REVIEW_ROLES):
        record={'role':role,'signer_id':'SYNTHETIC '+role,'signed_at':'2026-11-05T00:00:00Z'}
        record['signed_evidence']=raw(tmp_path/(role+'.json'),{
            **record,'review_payload_sha256':digest(payload),'decision':'approve'})
        signatures.append(record)
    review={'schema':diagnostic.RULE+'/human-study-review',
        'review_payload_sha256':digest(payload),'signatures':signatures,
        'acknowledgments':dict.fromkeys(diagnostic.ACKNOWLEDGMENTS,True)}
    if mutate_review:mutate_review(review)
    artifacts['study_review']=raw(tmp_path/'study-review.json',review)
    protocol=json.loads(Path(artifacts['protocol']['path']).read_text())
    protocol.update(schema=diagnostic.RULE+'/protocol',selection_rule=diagnostic.RULE,
        acceptance_criteria=copy.deepcopy(diagnostic.ACCEPTANCE_CRITERIA),
        input_sha256={k:v['sha256'] for k,v in artifacts.items() if k!='protocol'})
    artifacts['protocol']=raw(tmp_path/'protocol.json',protocol)
    ref=raw(tmp_path/'manifest.json',manifest)
    auth=synthetic_authorization(ref)
    value=json.loads(Path(auth['path']).read_text())
    value.update(study_kind=diagnostic.KIND,prospective_evidence=False,
                 historical_exposure_risk_acknowledged=True)
    auth=raw(Path(auth['path']),value)
    return ref,auth,Path(manifest['output_namespace'])


def test_diagnostic_retains_uncertainty_and_same_method(tmp_path,monkeypatch):
    ref,auth,output=diagnostic_inputs(tmp_path,monkeypatch)
    _,values,selection,_=preflight(ref,authorization_reference=auth)
    assert values['registry']['historical_gaps'] and values['registry']['certification'] is None
    assert len(selection)==25 and all(x['target'] for x in selection.values())
    stub=Stub()
    assert run(ref,authorization_reference=auth,backend_factory=lambda:stub,max_cells=1)['status']=='paused_after_complete_cell'
    assert len(stub.calls)==1
    assert not json.loads(next((output/'records').glob('*.json')).read_text())['payload']['is_prospective_evidence']


@pytest.mark.parametrize('failure', ['disclosure','parent','order','certificate','receipt','acknowledgment',
    'signatures','signed-evidence','self-review','review-hash','acceptance'])
def test_invalid_diagnostic_metadata_zero_content_reads_and_factory(tmp_path,monkeypatch,failure):
    ref,auth,output=diagnostic_inputs(tmp_path,monkeypatch)
    manifest=json.loads(Path(ref['path']).read_text());artifacts=manifest['artifacts']
    if failure=='disclosure':manifest['prospective_evidence']=True
    elif failure=='parent':monkeypatch.setattr(diagnostic,'PARENT_SHA256','0'*64)
    elif failure=='order':
        cohort=json.loads(Path(artifacts['cohort']['path']).read_text());cohort['query_ids'].reverse()
        artifacts['cohort']=raw(tmp_path/'cohort.json',cohort)
    elif failure=='certificate':
        registry=json.loads(Path(artifacts['registry']['path']).read_text());registry['certification']={'fake':True}
        artifacts['registry']=raw(tmp_path/'registry.json',registry)
    elif failure=='receipt':
        receipt=json.loads(Path(artifacts['cohort_receipt']['path']).read_text());receipt['pre_content_prospective_freeze']=True
        artifacts['cohort_receipt']=raw(tmp_path/'cohort-receipt.json',receipt)
    mutators={
        'acknowledgment':lambda r:r['acknowledgments'].update(nonprospective_only=False),
        'signatures':lambda r:r['signatures'].pop(),
        'signed-evidence':lambda r:Path(r['signatures'][0]['signed_evidence']['path']).write_text('{}'),
        'self-review':lambda r:next(x for x in r['signatures'] if x['role']=='supervisor').update(signer_id='SYNTHETIC responsible_researcher'),
        'review-hash':lambda r:r.update(review_payload_sha256='0'*64)}
    ref,auth,output=repin(tmp_path,manifest,mutate_review=mutators.get(failure))
    if failure=='acceptance':
        p=Path(manifest['artifacts']['protocol']['path']);value=json.loads(p.read_text())
        value['acceptance_criteria']['independent_confirmation']=True
        manifest['artifacts']['protocol']=raw(p,value)
        ref=raw(Path(ref['path']),manifest);auth=synthetic_authorization(ref)
    content={Path(artifacts[k]['path']) for k in ('data','targets')};reads=[];factories=[]
    original=Path.open
    def spy(path,*a,**kw):
        if path in content:reads.append(str(path))
        return original(path,*a,**kw)
    monkeypatch.setattr(Path,'open',spy)
    with pytest.raises((ValueError,PermissionError,KeyError)):
        run(ref,authorization_reference=auth,backend_factory=lambda:factories.append(1))
    assert reads==[] and factories==[] and not output.exists()


def test_prospective_authorization_cannot_authorize_diagnostic(tmp_path,monkeypatch):
    ref,auth,output=diagnostic_inputs(tmp_path,monkeypatch)
    value=json.loads(Path(auth['path']).read_text());value.pop('study_kind')
    auth=raw(Path(auth['path']),value)
    calls=[]
    with pytest.raises(PermissionError,match='diagnostic authorization'):
        run(ref,authorization_reference=auth,backend_factory=lambda:calls.append(1))
    assert not calls and not output.exists()


def test_diagnostic_cannot_be_relabelled_prospective(tmp_path,monkeypatch):
    ref,auth,_=diagnostic_inputs(tmp_path,monkeypatch)
    value=json.loads(Path(ref['path']).read_text());value['schema']='semantic-v3-pilot-manifest/v1'
    ref=raw(Path(ref['path']),value)
    with pytest.raises(ValueError,match='preparation inputs'):
        preflight(ref,authorization_reference=auth)


def test_diagnostic_durable_response_replay_and_unresolved_intent(tmp_path,monkeypatch):
    from test_semantic_v3_pilot_prep import PowerLoss
    ref,auth,output=diagnostic_inputs(tmp_path,monkeypatch);stub=Stub()
    def cut(event,key):
        if event=='after_response':raise PowerLoss()
    with pytest.raises(PowerLoss):
        run(ref,authorization_reference=auth,backend_factory=lambda:stub,interrupt=cut)
    unexpected=[]
    run(ref,authorization_reference=auth,backend_factory=lambda:unexpected.append(1),max_cells=1)
    assert len(stub.calls)==1 and not unexpected
    # An ambiguous later intent still halts before another backend is created.
    from src.experiments.semantic_v3_checkpoint import atomic_record
    atomic_record(output/'calls/ambiguous.intent.json',{})
    with pytest.raises(ResumeBlocked):
        run(ref,authorization_reference=auth,backend_factory=lambda:unexpected.append(1))
    assert not unexpected


@pytest.mark.parametrize('alias',['signed_evidence','authorization'])
def test_metadata_references_cannot_alias_content(tmp_path,monkeypatch,alias):
    ref,auth,output=diagnostic_inputs(tmp_path,monkeypatch)
    manifest=json.loads(Path(ref['path']).read_text());artifacts=manifest['artifacts']
    if alias=='signed_evidence':
        ref,auth,output=repin(tmp_path,manifest,mutate_review=lambda r:r['signatures'][0].update(signed_evidence=artifacts['data']))
    else:auth=artifacts['data']
    content={Path(artifacts[k]['path']) for k in ('data','targets')};reads=[]
    original=Path.open
    def spy(path,*a,**kw):
        if path in content:reads.append(str(path))
        return original(path,*a,**kw)
    monkeypatch.setattr(Path,'open',spy)
    with pytest.raises(PermissionError):preflight(ref,authorization_reference=auth)
    assert not reads and not output.exists()


def test_preparation_and_freeze_use_only_recorded_material_and_real_review_contract(tmp_path,monkeypatch):
    import importlib.util
    from types import SimpleNamespace
    from test_semantic_v3_mlx import runtime_fixture
    from src.experiments.semantic_v3_preparation import file_sha
    spec=importlib.util.spec_from_file_location('diagnostic_prepare',Path('scripts/prepare_semantic_v3_diagnostic.py'))
    prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
    # CI need not install Apple MLX. This offline contract test uses a complete,
    # synthetic package inventory; production still validates every required pin.
    backend_packages=('mlx','mlx-lm','numpy','transformers','tokenizers','psutil')
    monkeypatch.setattr(prepare.importlib.metadata,'distributions',lambda:[
        SimpleNamespace(metadata={'Name':name},version='synthetic-fixture')
        for name in backend_packages])
    monkeypatch.setattr(prepare.importlib.metadata,'version',lambda name:
        'synthetic-fixture' if name in backend_packages
        else pytest.fail(f'Unexpected synthetic environment lookup: {name}'))
    ref,_,_=diagnostic_inputs(tmp_path,monkeypatch)
    manifest=json.loads(Path(ref['path']).read_text());artifacts=manifest['artifacts']
    parent=json.loads(Path(artifacts['historical_protocol']['path']).read_text())
    data=json.loads(Path(artifacts['data']['path']).read_text())
    original=raw(tmp_path/'original-data.json',{'queries':data['queries'],'corpus':data['corpus']})
    model=runtime_fixture(tmp_path)
    parent['binding']['development_artifact_sha256']=original['sha256']
    parent['model']={'repository':model['model_provenance']['model_identity'],
        'revision':model['model_provenance']['revision'],'files_sha256':model['model_provenance']['model_files_sha256']}
    parentref=raw(tmp_path/'historical.json',parent)
    monkeypatch.setattr(prepare,'PARENT',Path(parentref['path']))
    monkeypatch.setattr(prepare,'PARENT_SHA256',parentref['sha256'])
    monkeypatch.setattr(diagnostic,'PARENT_SHA256',parentref['sha256'])
    monkeypatch.setattr(prepare,'DATA',Path(original['path']))
    monkeypatch.setattr(prepare,'REGISTRY',Path(artifacts['registry']['path']))
    monkeypatch.setattr(prepare,'REGISTRY_SHA',artifacts['registry']['sha256'])
    monkeypatch.setattr(prepare,'SNAPSHOT',Path(model['snapshot_path']))
    packet=tmp_path/'prepared';output=tmp_path/'execution'
    assert prepare.prepare(packet,output)['status']=='NO_GO_HUMAN_EVIDENCE_REQUIRED'
    assert not output.exists() and not (packet/'manifest.frozen.json').exists()
    with pytest.raises(FileExistsError):prepare.prepare(packet,output)
    with pytest.raises(FileNotFoundError):prepare.freeze(packet)
    produced=json.loads((packet/'development_data.json').read_text())
    assert produced['queries']==data['queries'] and produced['corpus']==data['corpus']
    rows=json.loads(Path(artifacts['targets']['path']).read_text())
    receiptsha=file_sha(packet/'reuse_receipt.json')
    for row in rows:
        row['cohort_receipt_sha256']=receiptsha
        for c in row['candidates']:c['packet']['review']['reviewed_at']='2090-01-01T00:00:00Z'
    raw(packet/'targets.reviewed.json',rows)
    runtime=json.loads((packet/'runtime.proposed.json').read_text())
    assert runtime['environment']['packages']==dict.fromkeys(backend_packages,'synthetic-fixture')
    runtime['resource_policy']['deadline']='2099-01-01T00:00:00Z'
    inventory={k:v for k,v in runtime.items() if k!='inventory_certification'}
    runtime['inventory_certification']={'inventory_sha256':digest(inventory),
        'complete_model_and_tokenizer_inventory':True,'complete_environment_inventory':True,
        'reviewer_id':'SYNTHETIC independent inventory reviewer'}
    raw(packet/'runtime.reviewed.json',runtime)
    payload=prepare.review_payload(packet)
    review=json.loads((packet/'study_review.blank.json').read_text())
    review.update(review_payload_sha256=digest(payload),acknowledgments=dict.fromkeys(diagnostic.ACKNOWLEDGMENTS,True))
    for record in review['signatures']:
        record.update(signer_id='SYNTHETIC '+record['role'],signed_at='2090-01-01T00:00:00Z')
        record['signed_evidence']=raw(packet/(record['role']+'.signed.json'),{
            'signer_id':record['signer_id'],'role':record['role'],
            'review_payload_sha256':digest(payload),'decision':'approve'})
    raw(packet/'study_review.signed.json',review)
    frozen=prepare.freeze(packet)
    assert frozen['sha256']==file_sha(packet/'manifest.frozen.json')
    assert not output.exists()
    auth=synthetic_authorization(frozen)
    value=json.loads(Path(auth['path']).read_text())
    value.update(study_kind=diagnostic.KIND,prospective_evidence=False,historical_exposure_risk_acknowledged=True)
    auth=raw(Path(auth['path']),value)
    # Fake snapshot hashes are checked; no model/MLX/tokenizer is ever loaded.
    preflight(frozen,authorization_reference=auth)
    with pytest.raises(FileExistsError):prepare.freeze(packet)


@pytest.mark.parametrize('stamp',[None,'invalid','2026-11-04T00:00:00'])
def test_prospective_receipt_time_still_fails_before_content(tmp_path,monkeypatch,stamp):
    from test_semantic_v3_pilot_prep import re_pin_manifest
    from test_semantic_v3_admission import content_spy
    ref,_,output=inputs(tmp_path)
    def mutate(receipt):
        if stamp is None:receipt.pop('frozen_at')
        else:receipt['frozen_at']=stamp
    ref=re_pin_manifest(tmp_path,ref,'cohort_receipt',mutate)
    auth=synthetic_authorization(ref)
    manifest=json.loads(Path(ref['path']).read_text())
    reads=content_spy(monkeypatch,manifest);factories=[]
    with pytest.raises((ValueError,KeyError)):
        run(ref,authorization_reference=auth,backend_factory=lambda:factories.append(1))
    assert reads==factories==[] and not output.exists()
