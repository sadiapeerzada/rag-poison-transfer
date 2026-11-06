"""Synthetic admission and monitoring tests. No MLX import or model weights."""
import copy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path

import pytest

from test_semantic_v3_pilot_prep import (inputs, raw, re_pin_manifest, synthetic_authorization,
    healthy_resources, Stub, TEXT, PowerLoss)
from src.experiments import semantic_v3_pilot as pilot
from src.experiments import semantic_v3_resources as resources
from src.experiments.semantic_v3_checkpoint import read_record, ResumeBlocked, atomic_record


def content_spy(monkeypatch, manifest):
    paths={manifest['artifacts'][key]['path'] for key in ('data','targets')}
    reads=[];original=Path.read_bytes
    def spy(path):
        if str(path) in paths:reads.append(str(path))
        return original(path)
    monkeypatch.setattr(Path,'read_bytes',spy)
    return reads


@pytest.mark.parametrize('case',[
    'missing_auth','denied_auth','expired_auth','wrong_scope','wrong_manifest','wrong_policy',
    'driver_pin','protocol_pin','profile_hash','history_gap','certificate','cohort','receipt',
    'runtime_python','runtime_kind','missing_policy','invalid_policy','alias','missing_file',
    'bad_reference','bad_protocol_input','wrong_namespace','dataset_identity','dataset_revision','dataset_split'])
def test_bad_admission_never_reads_content_or_creates_backend(tmp_path,monkeypatch,case):
    ref,auth,output=inputs(tmp_path)
    if case in ('history_gap','certificate','cohort','receipt','runtime_python','runtime_kind','missing_policy','invalid_policy'):
        artifact={'history_gap':'registry','certificate':'registry','cohort':'cohort','receipt':'cohort_receipt'}.get(case,'runtime')
        def mutate(value):
            if case=='history_gap':value['historical_gaps']=['SYNTHETIC unresolved history']
            elif case=='certificate':value['certification']=None
            elif case=='cohort':value['query_ids'].reverse()
            elif case=='receipt':value['input_sha256']['registry']='0'*64
            elif case=='runtime_python':value['environment']['python']='wrong'
            elif case=='runtime_kind':value['execution_kind']='unknown'
            elif case=='missing_policy':value.pop('resource_policy')
            else:value['resource_policy']['max_elapsed_seconds']=-1
        ref=re_pin_manifest(tmp_path,ref,artifact,mutate)
        auth=synthetic_authorization(ref)
    manifest=json.loads(Path(ref['path']).read_text())
    if case in ('driver_pin','protocol_pin','profile_hash','alias','missing_file','bad_reference','bad_protocol_input','wrong_namespace','dataset_identity','dataset_revision','dataset_split'):
        if case.startswith('dataset_'):
            key={'dataset_identity':'name','dataset_revision':'revision','dataset_split':'split'}[case]
            manifest['dataset'][key]='wrong'
        elif case=='driver_pin':manifest['driver_implementation_sha256']={}
        elif case=='protocol_pin':manifest['artifacts']['protocol']['sha256']='0'*64
        elif case=='profile_hash':Path(manifest['artifacts']['profile']['path']).write_text('{}')
        elif case=='alias':manifest['artifacts']['registry']=manifest['artifacts']['data']
        elif case=='missing_file':Path(manifest['artifacts']['data']['path']).unlink()
        elif case=='bad_reference':manifest['artifacts']['data']['sha256']='not-a-sha'
        elif case=='bad_protocol_input':
            p=Path(manifest['artifacts']['protocol']['path']);v=json.loads(p.read_text());v['input_sha256']={}
            manifest['artifacts']['protocol']=raw(p,v)
        else:manifest['output_namespace']='relative/path'
        ref=raw(Path(ref['path']),manifest)
        auth=synthetic_authorization(ref)
    if case=='missing_auth':auth=None
    elif case in ('denied_auth','expired_auth','wrong_scope','wrong_manifest','wrong_policy'):
        value=json.loads(Path(auth['path']).read_text())
        key,changed={'denied_auth':('allow_model_calls',False),'expired_auth':('expires_at','2020-01-01T00:00:00Z'),
            'wrong_scope':('scope','heldout'),'wrong_manifest':('manifest_sha256','0'*64),
            'wrong_policy':('resource_policy_sha256','0'*64)}[case]
        value[key]=changed;auth=raw(Path(auth['path']),value)
    reads=content_spy(monkeypatch,manifest);calls=[]
    with pytest.raises((ValueError,PermissionError,FileNotFoundError)):
        pilot.run(ref,authorization_reference=auth,backend_factory=lambda:calls.append('factory'))
    assert reads==calls==[] and not output.exists()


@pytest.mark.parametrize('field,value',[
    ('free_disk_bytes',0),('output_bytes',10**12),('available_memory_bytes',0),
    ('process_rss_bytes',10**12),('memory_pressure','critical'),('memory_pressure','warning')])
def test_resource_failure_precedes_content(tmp_path,monkeypatch,healthy_resources,field,value):
    ref,auth,output=inputs(tmp_path);healthy_resources[field]=value
    manifest=json.loads(Path(ref['path']).read_text());reads=content_spy(monkeypatch,manifest)
    with pytest.raises(resources.ResourceAdmissionDenied):
        pilot.run(ref,authorization_reference=auth,backend_factory=lambda:pytest.fail('factory'))
    assert reads==[] and not output.exists()


@pytest.mark.parametrize('sample',[None,{}, {'free_disk_bytes':-1}])
def test_missing_or_invalid_telemetry_denies(tmp_path,monkeypatch,sample):
    ref,auth,output=inputs(tmp_path)
    monkeypatch.setattr(resources,'system_sample',lambda root:sample)
    reads=content_spy(monkeypatch,json.loads(Path(ref['path']).read_text()))
    with pytest.raises(resources.ResourceAdmissionDenied):pilot.run(ref,authorization_reference=auth)
    assert reads==[] and not output.exists()


def test_probe_error_denies_before_content(tmp_path,monkeypatch):
    ref,auth,output=inputs(tmp_path)
    def unavailable(root):raise OSError('SYNTHETIC probe failure')
    monkeypatch.setattr(resources,'system_sample',unavailable)
    reads=content_spy(monkeypatch,json.loads(Path(ref['path']).read_text()))
    with pytest.raises(resources.ResourceAdmissionDenied,match='unavailable'):
        pilot.run(ref,authorization_reference=auth)
    assert reads==[] and not output.exists()


@pytest.mark.parametrize('content_key',['data','targets'])
def test_bad_content_hash_never_decodes_either_content_or_loads_model(tmp_path,monkeypatch,content_key):
    ref,auth,output=inputs(tmp_path);m=json.loads(Path(ref['path']).read_text())
    Path(m['artifacts'][content_key]['path']).write_text('SYNTHETIC tampered bytes')
    monkeypatch.setattr(pilot,'_decode_content',lambda raw:pytest.fail('must not decode content'))
    with pytest.raises(ValueError,match='fingerprint'):
        pilot.run(ref,authorization_reference=auth,backend_factory=lambda:pytest.fail('factory'))
    assert not output.exists()


def test_expiry_between_calls_does_not_reserve_second_intent(tmp_path,monkeypatch):
    ref,auth,output=inputs(tmp_path);base=datetime(2026,11,6,tzinfo=timezone.utc);clock=[base]
    a=json.loads(Path(auth['path']).read_text());a['expires_at']=(base+timedelta(seconds=1)).isoformat()
    auth=raw(Path(auth['path']),a)
    monkeypatch.setattr(pilot,'utc_now',lambda:clock[0])
    monkeypatch.setattr(resources,'utc_now',lambda:clock[0])
    class Expiring(Stub):
        def generate(self,*args,**kwargs):
            result=super().generate(*args,**kwargs);clock[0]+=timedelta(seconds=2);return result
    stub=Expiring(['born on Avignon',TEXT])
    with pytest.raises(PermissionError):pilot.run(ref,authorization_reference=auth,backend_factory=lambda:stub)
    assert len(stub.calls)==1 and len(list((output/'calls').glob('*.intent.json')))==1
    assert len(list((output/'calls').glob('*.response.json')))==1
    assert not list((output/'infrastructure').glob('*'))
    proof=read_record(next((output/'calls').glob('*.intent.json')))['admission']
    assert proof['authorization_sha256']==auth['sha256']


def test_tampered_authorization_between_calls_never_reserves_next_call(tmp_path):
    ref,auth,output=inputs(tmp_path)
    class Tampering(Stub):
        def generate(self,*args,**kwargs):
            result=super().generate(*args,**kwargs);Path(auth['path']).write_text('{}');return result
    stub=Tampering(['born on Avignon',TEXT])
    with pytest.raises(PermissionError):pilot.run(ref,authorization_reference=auth,backend_factory=lambda:stub)
    assert len(stub.calls)==1 and len(list((output/'calls').glob('*.intent.json')))==1


def test_post_call_pressure_preserves_response_then_replays_without_regeneration(tmp_path,healthy_resources):
    ref,auth,output=inputs(tmp_path)
    class Pressure(Stub):
        def generate(self,*args,**kwargs):
            result=super().generate(*args,**kwargs);healthy_resources['memory_pressure']='critical';return result
    stub=Pressure()
    with pytest.raises(resources.ResourceAdmissionDenied):pilot.run(ref,authorization_reference=auth,backend_factory=lambda:stub)
    assert len(stub.calls)==1 and len(list((output/'calls').glob('*.response.json')))==1
    observation=read_record(next((output/'resources').glob('*.json')))
    assert 'memory pressure' in observation['violations']
    healthy_resources['memory_pressure']='normal'
    pilot.run(ref,authorization_reference=auth,backend_factory=lambda:pytest.fail('replay only'),max_cells=1)
    assert len(stub.calls)==1


def test_elapsed_budget_is_persisted_across_resume_and_checked_before_content(tmp_path,monkeypatch):
    ref,auth,output=inputs(tmp_path);base=datetime(2026,11,6,tzinfo=timezone.utc)
    monkeypatch.setattr(resources,'utc_now',lambda:base)
    monkeypatch.setattr(pilot,'utc_now',lambda:base)
    pilot.run(ref,authorization_reference=auth,backend_factory=Stub,max_cells=1)
    monkeypatch.setattr(resources,'utc_now',lambda:base+timedelta(hours=2))
    reads=content_spy(monkeypatch,json.loads(Path(ref['path']).read_text()))
    with pytest.raises(resources.ResourceAdmissionDenied,match='execution time'):
        pilot.run(ref,authorization_reference=auth,backend_factory=lambda:pytest.fail('factory'))
    assert reads==[]


def test_authorized_resource_call_budget_is_global_across_resume(tmp_path):
    ref,_,output=inputs(tmp_path)
    ref=re_pin_manifest(tmp_path,ref,'runtime',lambda r:r['resource_policy'].update(max_backend_calls=1))
    auth=synthetic_authorization(ref);stub=Stub(['born on Avignon',TEXT])
    for _ in range(2):
        with pytest.raises(resources.ResourceAdmissionDenied,match='call budget'):
            pilot.run(ref,authorization_reference=auth,backend_factory=lambda:stub)
    assert len(stub.calls)==1 and len(list((output/'calls').glob('*.intent.json')))==1


def test_unresolved_intent_blocks_before_content_on_resume(tmp_path,monkeypatch):
    ref,auth,output=inputs(tmp_path)
    def cut(event,key):
        if event=='after_intent':raise PowerLoss()
    with pytest.raises(PowerLoss):pilot.run(ref,authorization_reference=auth,backend_factory=Stub,interrupt=cut)
    reads=content_spy(monkeypatch,json.loads(Path(ref['path']).read_text()))
    with pytest.raises(ResumeBlocked):pilot.run(ref,authorization_reference=auth,backend_factory=lambda:pytest.fail('factory'))
    assert reads==[]


def test_pending_atomic_debris_is_never_silently_recovered(tmp_path):
    from src.experiments.semantic_v3_checkpoint import verify_journal
    (tmp_path/'.pending-fixture').write_text('SYNTHETIC interrupted publication')
    with pytest.raises(ResumeBlocked,match='Unpublished'):verify_journal(tmp_path)


@pytest.mark.parametrize('field,value',[('max_elapsed_seconds',float('nan')),('max_backend_calls',201),
    ('max_memory_pressure','critical'),('deadline','no-timezone'),('min_free_disk_bytes',True)])
def test_policy_limits_fail_closed(field,value):
    from test_semantic_v3_pilot_prep import resource_policy
    policy=resource_policy();policy[field]=value
    with pytest.raises(ValueError):resources.validate_policy(policy)


def test_expiry_during_lazy_loading_is_rechecked_before_generation(tmp_path,monkeypatch):
    ref,auth,output=inputs(tmp_path);base=datetime(2026,11,6,tzinfo=timezone.utc);clock=[base]
    a=json.loads(Path(auth['path']).read_text());a['expires_at']=(base+timedelta(seconds=1)).isoformat()
    auth=raw(Path(auth['path']),a)
    monkeypatch.setattr(pilot,'utc_now',lambda:clock[0]);monkeypatch.setattr(resources,'utc_now',lambda:clock[0])
    class SlowLoad(Stub):
        def prepare(self):clock[0]+=timedelta(seconds=2)
    stub=SlowLoad()
    with pytest.raises(PermissionError):pilot.run(ref,authorization_reference=auth,backend_factory=lambda:stub)
    assert stub.calls==[] and len(list((output/'calls').glob('*.intent.json')))==1
    error=read_record(next((output/'calls').glob('*.error.json')))
    assert error['error_type']=='PermissionError' and error['available_result'] is None
    assert not list((output/'calls').glob('*.response.json'))


def test_memory_pressure_during_loading_denies_generation_and_blocks_replay(tmp_path,healthy_resources):
    ref,auth,output=inputs(tmp_path)
    class HeavyLoad(Stub):
        def prepare(self):healthy_resources['memory_pressure']='critical'
    stub=HeavyLoad()
    with pytest.raises(resources.ResourceAdmissionDenied):pilot.run(ref,authorization_reference=auth,backend_factory=lambda:stub)
    assert stub.calls==[] and len(list((output/'calls').glob('*.error.json')))==1
    healthy_resources['memory_pressure']='normal'
    with pytest.raises(ResumeBlocked):pilot.run(ref,authorization_reference=auth,backend_factory=lambda:pytest.fail('no replay'))


def test_execution_deadline_denies_content(tmp_path,monkeypatch):
    ref,_,output=inputs(tmp_path)
    ref=re_pin_manifest(tmp_path,ref,'runtime',lambda r:r['resource_policy'].update(deadline='2020-01-01T00:00:00Z'))
    reads=content_spy(monkeypatch,json.loads(Path(ref['path']).read_text()))
    with pytest.raises(resources.ResourceAdmissionDenied,match='deadline'):
        pilot.run(ref,authorization_reference=synthetic_authorization(ref))
    assert reads==[] and not output.exists()


def test_missing_persisted_clock_cannot_reset_budget_on_resume(tmp_path,monkeypatch):
    ref,auth,output=inputs(tmp_path);pilot.run(ref,authorization_reference=auth,backend_factory=Stub,max_cells=1)
    (output/'resource.clock.json').unlink()  # Synthetic corruption only.
    reads=content_spy(monkeypatch,json.loads(Path(ref['path']).read_text()))
    with pytest.raises(ValueError,match='clock missing'):pilot.run(ref,authorization_reference=auth)
    assert reads==[]


def test_sealed_resource_observation_mutation_is_detected(tmp_path):
    ref,auth,output=inputs(tmp_path);pilot.run(ref,authorization_reference=auth,backend_factory=Stub)
    path=next((output/'resources').glob('*.json'))
    value=read_record(path);value['sample']['output_bytes']+=1
    path.chmod(0o644);path.unlink();atomic_record(path,value)  # Synthetic rechecksummed mutation.
    with pytest.raises(ValueError,match='resource telemetry mutated'):
        pilot.run(ref,authorization_reference=auth,backend_factory=lambda:pytest.fail('sealed'))


@pytest.mark.parametrize('level,expected',[(1,'normal'),(2,'warning'),(4,'critical')])
def test_macos_pressure_sensor_uses_kernel_level_with_mocked_os(tmp_path,monkeypatch,level,expected):
    import sys
    from types import SimpleNamespace
    fake=SimpleNamespace(virtual_memory=lambda:SimpleNamespace(available=100,total=1000),
        Process=lambda:SimpleNamespace(memory_info=lambda:SimpleNamespace(rss=20)))
    monkeypatch.setitem(sys.modules,'psutil',fake)
    monkeypatch.setattr(resources.platform,'system',lambda:'Darwin')
    calls=[]
    def pressure(command,**kwargs):calls.append((command,kwargs));return str(level)
    monkeypatch.setattr(resources.subprocess,'check_output',pressure)
    monkeypatch.setattr(resources.shutil,'disk_usage',lambda path:SimpleNamespace(free=123))
    (tmp_path/'fixture').write_bytes(b'12345')
    # The autouse fixture replaces system_sample; call the original implementation saved below.
    sample=ORIGINAL_SYSTEM_SAMPLE(tmp_path)
    assert sample['memory_pressure']==expected and sample['output_bytes']==5
    assert sample['free_disk_bytes']==123 and sample['process_rss_bytes']==20
    assert calls[0][1]['timeout']==5


# Capture before autouse fixtures replace the function at test invocation time.
ORIGINAL_SYSTEM_SAMPLE=resources.system_sample


def test_expiry_during_resource_probe_is_checked_after_probe_before_generate(tmp_path,monkeypatch,healthy_resources):
    ref,auth,output=inputs(tmp_path);base=datetime(2026,11,6,tzinfo=timezone.utc);clock=[base];probes=[0]
    a=json.loads(Path(auth['path']).read_text());a['expires_at']=(base+timedelta(seconds=1)).isoformat()
    auth=raw(Path(auth['path']),a)
    monkeypatch.setattr(pilot,'utc_now',lambda:clock[0]);monkeypatch.setattr(resources,'utc_now',lambda:clock[0])
    def slow_probe(root):
        probes[0]+=1
        if probes[0]==4:clock[0]+=timedelta(seconds=2)
        return dict(healthy_resources)
    monkeypatch.setattr(resources,'system_sample',slow_probe)
    stub=Stub()
    with pytest.raises(PermissionError):pilot.run(ref,authorization_reference=auth,backend_factory=lambda:stub)
    assert stub.calls==[] and len(list((output/'calls').glob('*.error.json')))==1
