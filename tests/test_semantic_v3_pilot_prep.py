"""Offline-only synthetic custody/review/auth records; none authorize real calls."""
import copy
import json
from pathlib import Path
import platform

import pytest
from test_semantic_quality_v3 import packet_fixture, rebind
from src.attacks.semantic_quality_profile_v3 import descriptor
from src.attacks.semantic_quality_targets_v3 import digest
from src.experiments.semantic_v3_preparation import (CATEGORIES, select_cohort, verify_registry, build_registry,
                                                    file_sha, blinded_forms, target_review_form)
from src.experiments.semantic_v3_checkpoint import (atomic_record, read_record, CallJournal, ResumeBlocked, writer_lock)
from src.experiments.semantic_v3_pilot import implementation_pins, preflight, run
from src.pipelines.generator import GenerationResult


TEXT="Edward J. Sachar's father died on 10 September 1959."  # Existing V3 scripted regression text.
PROVENANCE={'fixture':True,'decoding':{'sampler':'explicit greedy','temperature':0.0}}


def certified_registry():
    records=[{'category':category,'provenance':'SYNTHETIC OFFLINE FIXTURE ONLY',
              'original_sha256':'0'*64,'query_ids':[f'exposed-{category}']} for category in sorted(CATEGORIES)]
    registry={'schema':'twowiki-semantic-quality-v3-prospective/v1/exposure-registry','source_records':records,
              'excluded_query_ids':sorted(q for r in records for q in r['query_ids']),
              'historical_gaps':[],'status':'certified','certification':None}
    unsigned={k:v for k,v in registry.items() if k not in ('certification','status')}
    registry['certification']={'registry_payload_sha256':digest(unsigned),'historical_inventory_complete':True,
          'heldout_metadata_only':True,'custodian_id':'SYNTHETIC TEST CUSTODIAN',
          'evidence_notes':'Synthetic complete inventory fixture; no real certification.',
          'certified_at':'2026-11-04T10:00:00+05:30'}
    return registry


def raw(path,value):
    path.write_text(json.dumps(value,sort_keys=True,ensure_ascii=False)+'\n')
    return {'path':str(path),'sha256':file_sha(path)}


def inputs(tmp_path, *, abstain=False):
    q,t,packet,corpus,_=packet_fixture()
    queries=[]
    for index in range(40):queries.append({**q,'query_id':f'offline-fixture-{index:02d}'})
    data={'scope':'development','dataset':{'name':'2Wiki-offline-fixture','split':'train'},'queries':queries,'corpus':corpus}
    artifacts={'data':raw(tmp_path/'data.json',data),'registry':raw(tmp_path/'registry.json',certified_registry()),
               'profile':raw(tmp_path/'profile.json',descriptor(scope='development'))}
    pool=[q['query_id'] for q in queries]
    artifacts['pool_ids']=raw(tmp_path/'pool.json',pool)
    cohort=select_cohort(pool,certified_registry(),dataset_sha256=artifacts['data']['sha256'])
    artifacts['cohort']=raw(tmp_path/'cohort.json',cohort)
    artifacts['cohort_receipt']=raw(tmp_path/'cohort-receipt.json',{'schema':'semantic-v3-pre-content-freeze-receipt/v1','frozen_at':'2026-11-04T00:00:00Z',
            'selector_source_sha256':file_sha(Path('src/experiments/semantic_v3_preparation.py')),
            'input_sha256':{k:artifacts[k]['sha256'] for k in ('cohort','registry','pool_ids','data')}})
    by_id={q['query_id']:q for q in queries};targets=[]
    for qid in cohort['query_ids']:
        p=copy.deepcopy(packet);p['payload']['query_sha256']=digest(by_id[qid]);rebind(p)
        p['review']['uncertainty']='Synthetic fixture: none for mechanics; not an actual approval.'
        targets.append({'query_id':qid,'query_sha256':digest(by_id[qid]),
              'cohort_receipt_sha256':artifacts['cohort_receipt']['sha256'],'review_state':'abstain' if abstain else 'reviewed',
              'candidates':[] if abstain else [{'target':t,'packet':p}],
              'abstention_reason':'synthetic missing evidence' if abstain else None})
    artifacts['targets']=raw(tmp_path/'targets.json',targets)
    artifacts['runtime']=raw(tmp_path/'runtime.json',{'execution_kind':'offline_stub','model_provenance':PROVENANCE,
                   'environment':{'python':platform.python_version(),'packages':{}}})
    protocol={'schema':'twowiki-semantic-quality-v3-prospective/v1/protocol','status':'frozen_for_independent_authorization','scope':'development','stage':'construction-only','intensities':[1,3],'seed':42,
              'max_backend_calls':200,'max_attempts_per_document':2,'max_tokens':150,
              'selection_rule':'twowiki-semantic-quality-v3-prospective/v1',
              'input_sha256':{k:v['sha256'] for k,v in artifacts.items()}}
    artifacts['protocol']=raw(tmp_path/'protocol.json',protocol)
    manifest={'schema':'semantic-v3-pilot-manifest/v1','base_implementation_commit':'fba2583ae4569d6e5114052ac1854ad545dc3c16','scope':'development','stage':'construction-only','status':'frozen_ready_for_authorization',
              'driver_implementation_sha256':implementation_pins(),'artifacts':artifacts,
              'output_namespace':str((tmp_path/'fresh-construction').resolve())}
    ref=raw(tmp_path/'manifest.json',manifest)
    authorization={'schema':'semantic-v3-model-call-authorization/v1','allow_model_calls':True,
         'manifest_sha256':ref['sha256'],'protocol_sha256':artifacts['protocol']['sha256'],
         'output_namespace':manifest['output_namespace'],'scope':'development','purpose':'construction-only',
         'max_backend_calls':200,'authorizer_type':'human','authorizer_id':'SYNTHETIC TEST AUTHORIZER',
         'issued_at':'2020-01-01T00:00:00Z','expires_at':'2099-01-01T00:00:00Z'}
    authref=raw(tmp_path/'SYNTHETIC-test-authorization.json',authorization)
    return ref,authref,Path(manifest['output_namespace'])


class Stub:
    model_provenance=PROVENANCE
    def __init__(self,outputs=None):self.outputs=iter(outputs) if outputs is not None else None;self.calls=[];self.seeds=[]
    def set_runtime_seed(self,seed):self.seeds.append(seed)
    def generate(self,prompt,max_tokens):
        self.calls.append((prompt,max_tokens))
        result=next(self.outputs) if self.outputs is not None else TEXT
        if isinstance(result,Exception):raise result
        return GenerationResult(result,0.01,100,10,'scripted backend\n'+prompt)


class PowerLoss(BaseException):pass


def test_deterministic_selection_and_exclusions():
    registry=certified_registry();pool=[f'offline-{i}' for i in range(100)]+registry['excluded_query_ids']
    one=select_cohort(pool,registry,dataset_sha256='a'*64)
    assert len(one['query_ids'])==25 and not set(one['query_ids'])&set(registry['excluded_query_ids'])
    assert one['query_ids']==select_cohort(list(reversed(pool)),registry,dataset_sha256='a'*64)['query_ids']
    assert one['query_ids']==sorted(set(pool)-set(registry['excluded_query_ids']),key=lambda q:(digest(['twowiki-semantic-quality-v3-prospective/v1',42,q]),q))[:25]
    with pytest.raises(ValueError):select_cohort(pool+pool[:1],registry,dataset_sha256='a'*64)
    with pytest.raises(ValueError):select_cohort(pool[:24],registry,dataset_sha256='a'*64)


def test_exposure_gaps_and_missing_certification_stop_selection():
    for mutate in (lambda r:r.update(historical_gaps=['unknown old sweep']),lambda r:r.update(certification=None),
                   lambda r:r['source_records'].pop(),lambda r:r['excluded_query_ids'].pop()):
        r=certified_registry();mutate(r)
        with pytest.raises(ValueError):select_cohort([str(i) for i in range(100)],r,dataset_sha256='a'*64)
    real=json.loads(Path('pilot_prep/twowiki_semantic_v3/known_exclusions/registry.json').read_text())
    assert real['certification'] is None and real['historical_gaps']
    with pytest.raises(ValueError):verify_registry(real)


def test_registry_source_pins_and_ids_only(tmp_path):
    ref=raw(tmp_path/'ids.json',['a','b'])
    r=build_registry([{'category':'heldout_ids','provenance':'metadata-only fixture','original_sha256':'a'*64,'ids_export':ref}],['gap'])
    assert r['excluded_query_ids']==['a','b'] and r['certification'] is None
    raw(tmp_path/'ids.json',[{'query_id':'x','question':'content forbidden'}])
    with pytest.raises(ValueError):build_registry([{'category':'heldout_ids','provenance':'metadata','original_sha256':'a'*64,'ids_export':ref}],[])


def test_no_authorization_no_backend_or_namespace(tmp_path):
    ref,auth,output=inputs(tmp_path);calls=[]
    with pytest.raises(PermissionError):run(ref,backend_factory=lambda:calls.append(1))
    assert not calls and not output.exists()
    authvalue=json.loads(Path(auth['path']).read_text());authvalue['allow_model_calls']=False
    auth=raw(Path(auth['path']),authvalue)
    with pytest.raises(PermissionError):run(ref,authorization_reference=auth,backend_factory=lambda:calls.append(1))
    assert not calls and not output.exists()


def test_fingerprint_tampering_and_pending_review(tmp_path):
    ref,auth,output=inputs(tmp_path)
    value=json.loads(Path(ref['path']).read_text());Path(value['artifacts']['profile']['path']).write_text('{}')
    with pytest.raises(ValueError,match='fingerprint'):preflight(ref)
    assert not output.exists()


def test_exact_resume_after_response_without_regeneration(tmp_path):
    ref,auth,output=inputs(tmp_path);stub=Stub()
    def cut(event,key):
        if event=='after_response':raise PowerLoss()
    with pytest.raises(PowerLoss):run(ref,authorization_reference=auth,backend_factory=lambda:stub,interrupt=cut)
    assert len(stub.calls)==1 and len(list((output/'calls').glob('*.response.json')))==1
    unexpected=[]
    result=run(ref,authorization_reference=auth,backend_factory=lambda:unexpected.append(1),max_cells=1)
    assert result['status']=='paused_after_complete_cell' and not unexpected
    assert len(stub.calls)==1
    record=read_record(next((output/'records').glob('*.json')))
    assert record['documents'][0]['text']==TEXT and record['attempt_records'][0]['attempts'][0]['generated_text']==TEXT


def test_unresolved_intent_blocks_resume(tmp_path):
    ref,auth,output=inputs(tmp_path);stub=Stub()
    def cut(event,key):
        if event=='after_intent':raise PowerLoss()
    with pytest.raises(PowerLoss):run(ref,authorization_reference=auth,backend_factory=lambda:stub,interrupt=cut)
    assert not stub.calls
    with pytest.raises(ResumeBlocked,match='Unresolved'):run(ref,authorization_reference=auth,backend_factory=lambda:stub)
    assert not stub.calls


def test_infrastructure_errors_never_become_construction_failures(tmp_path):
    ref,auth,output=inputs(tmp_path);stub=Stub([RuntimeError('scripted infrastructure error')])
    with pytest.raises(RuntimeError):run(ref,authorization_reference=auth,backend_factory=lambda:stub)
    assert len(stub.calls)==1 and not list((output/'records').glob('*.json'))
    infra=read_record(next((output/'infrastructure').glob('*.json')))
    assert infra['kind']=='infrastructure_error' and infra['attempt_records']
    with pytest.raises(ResumeBlocked):run(ref,authorization_reference=auth,backend_factory=lambda:stub)
    assert len(stub.calls)==1


def test_completion_sealing_duplicates_and_read_only_resume(tmp_path):
    ref,auth,output=inputs(tmp_path);stub=Stub()
    run(ref,authorization_reference=auth,backend_factory=lambda:stub,max_cells=1)
    assert len(stub.calls)==1
    seal=run(ref,authorization_reference=auth,backend_factory=lambda:stub)
    assert seal['backend_calls']==100 and len(seal['record_sha256'])==50 and len(stub.calls)==100
    records=[read_record(p) for p in (output/'records').glob('*.json')]
    assert all(r['document_diversity']['duplicate_slots']==2 for r in records if r['intensity']==3)
    before={str(p):file_sha(p) for p in output.rglob('*.json')}
    assert run(ref,authorization_reference=auth,backend_factory=lambda:pytest.fail('must not load backend'))==seal
    assert before=={str(p):file_sha(p) for p in output.rglob('*.json')}
    with pytest.raises(FileExistsError):atomic_record(output/'complete.seal.json',{})


def test_all_failures_hit_exact_200_call_cap_without_expanding_retry_budget(tmp_path):
    ref,auth,output=inputs(tmp_path);stub=Stub(['born on Avignon']*201)
    seal=run(ref,authorization_reference=auth,backend_factory=lambda:stub)
    assert seal['backend_calls']==len(stub.calls)==200
    assert all(read_record(p)['status']=='semantic_construction_failed' for p in (output/'records').glob('*.json'))
    journal=CallJournal(output,{'model_provenance':PROVENANCE},lambda:stub)
    journal.start_cell('extra');journal.set_seed(42)
    with pytest.raises(ResumeBlocked,match='budget'):journal.generate('unused',150)
    assert len(stub.calls)==200


def test_intensity_three_all_or_none_after_partial_failure(tmp_path):
    ref,auth,output=inputs(tmp_path);stub=Stub([TEXT]*25+[TEXT,'born on Avignon','born on Avignon',TEXT])
    run(ref,authorization_reference=auth,backend_factory=lambda:stub,max_cells=25)
    run(ref,authorization_reference=auth,backend_factory=lambda:stub,max_cells=1)
    records=[read_record(p) for p in (output/'records').glob('*.json')]
    r=next(r for r in records if r['intensity']==3)
    assert r['status']=='semantic_construction_failed' and r['documents']==[] and len(r['partial_documents'])==2
    assert len(stub.calls)==29


def test_target_abstention_never_loads_backend(tmp_path):
    ref,auth,output=inputs(tmp_path,abstain=True)
    seal=run(ref,authorization_reference=auth,backend_factory=lambda:pytest.fail('no candidate, no calls'))
    assert seal['backend_calls']==0
    assert all(read_record(p)['status']=='target_construction_failed' for p in (output/'records').glob('*.json'))


def test_blinding_and_unapproved_forms():
    q,*_=packet_fixture();form=target_review_form(q)
    assert form['decision'] is None and form['reviewer_id'] is None and not form['candidates']
    attempts=[{'query_id':q['query_id'],'question':q['question'],'target':'10 September 1959','text':TEXT,
               'heuristic_acceptance':True,'intensity':3,'attempt':2,'qa_answer':'secret'}]*2
    public,private=blinded_forms(attempts)
    assert public==blinded_forms(attempts)[0] and len({r['blind_id'] for r in public})==2
    assert all(not {'heuristic_acceptance','intensity','attempt','qa_answer'}&r.keys() for r in public)
    assert all(r['decision'] is None for r in public) and len(private)==2


def test_atomic_checkpoint_tampering_and_one_writer(tmp_path):
    atomic_record(tmp_path/'record.json',{'a':1})
    path=tmp_path/'record.json';path.chmod(0o644);value=json.loads(path.read_text());value['payload']['a']=2;path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='checksum'):read_record(path)
    with writer_lock(tmp_path):
        with pytest.raises(ResumeBlocked):
            with writer_lock(tmp_path):pass


def re_pin_manifest(tmp_path, ref, artifact, mutate):
    manifest=json.loads(Path(ref['path']).read_text());path=Path(manifest['artifacts'][artifact]['path'])
    value=json.loads(path.read_text());mutate(value)
    manifest['artifacts'][artifact]=raw(path,value)
    protocol_path=Path(manifest['artifacts']['protocol']['path']);protocol=json.loads(protocol_path.read_text())
    protocol['input_sha256']={k:v['sha256'] for k,v in manifest['artifacts'].items() if k!='protocol'}
    manifest['artifacts']['protocol']=raw(protocol_path,protocol)
    return raw(Path(ref['path']),manifest)


@pytest.mark.parametrize('case', ['pending','same_reviewer','no_uncertainty','missing_abstention'])
def test_target_review_enforcement_in_driver(tmp_path,case):
    ref,_,_=inputs(tmp_path)
    def mutate(rows):
        if case=='pending':rows[0]['review_state']='pending'
        elif case=='same_reviewer':
            p=rows[0]['candidates'][0]['packet'];p['review']['reviewer_id']=p['payload']['nominator_id']
        elif case=='no_uncertainty':del rows[0]['candidates'][0]['packet']['review']['uncertainty']
        else:rows[0]['candidates']=[]
    changed=re_pin_manifest(tmp_path,ref,'targets',mutate)
    with pytest.raises(ValueError):preflight(changed)


def test_protocol_and_source_mismatches(tmp_path):
    ref,_,_=inputs(tmp_path)
    manifest=json.loads(Path(ref['path']).read_text());protocol_path=Path(manifest['artifacts']['protocol']['path'])
    protocol=json.loads(protocol_path.read_text());protocol['max_backend_calls']=201
    manifest['artifacts']['protocol']=raw(protocol_path,protocol);ref=raw(Path(ref['path']),manifest)
    with pytest.raises(ValueError,match='configuration'):preflight(ref)
    protocol['max_backend_calls']=200;manifest['artifacts']['protocol']=raw(protocol_path,protocol)
    manifest['driver_implementation_sha256']={};ref=raw(Path(ref['path']),manifest)
    with pytest.raises(ValueError,match='source'):preflight(ref)


def test_heldout_data_refused_and_exact_cohort_not_replaced(tmp_path):
    ref,_,_=inputs(tmp_path)
    changed=re_pin_manifest(tmp_path,ref,'data',lambda d:d.update(scope='heldout'))
    # Dataset hash changed, so the pre-content cohort binding fails first.
    with pytest.raises(ValueError):preflight(changed)


def test_review_export_includes_rejections_and_blinds_private_fields(tmp_path):
    from src.experiments.semantic_v3_review import construction_summary, export_semantic_review
    ref,auth,output=inputs(tmp_path);stub=Stub(['born on Avignon',TEXT]+[TEXT]*100)
    run(ref,authorization_reference=auth,backend_factory=lambda:stub)
    summary=construction_summary(output,ref)
    assert summary['groups']['3']['valid_constructions']==25 and summary['backend_calls']==101
    assert summary['retrieval_or_QA_outcomes']=='not_evaluated'
    count=export_semantic_review(output,ref,tmp_path/'public',tmp_path/'private')
    assert count==101  # Every failed and passed attempt, not only accepted text.
    public=json.loads((tmp_path/'public/reviewer_A.blank.json').read_text())
    assert any(r['text']=='born on Avignon' for r in public)
    assert all(r['decision'] is None and not {'heuristic_outcome','reason','intensity','slot','attempt'}&r.keys() for r in public)
    mapping=json.loads((tmp_path/'private/unblinding.json').read_text())
    assert len(mapping)==count and any(r['reason'] for r in mapping)


def test_authorization_scope_expiry_and_hash_bindings(tmp_path):
    ref,auth,output=inputs(tmp_path)
    original=json.loads(Path(auth['path']).read_text())
    for change in ({'expires_at':'2020-01-02T00:00:00Z'},{'scope':'heldout'},
                   {'manifest_sha256':'0'*64},{'max_backend_calls':201},{'purpose':'QA'}):
        updated=raw(Path(auth['path']),{**original,**change})
        with pytest.raises(PermissionError):run(ref,authorization_reference=updated,backend_factory=lambda:pytest.fail('unauthorized'))
        assert not output.exists()


def test_sealed_journal_detects_even_rechecksummed_response_changes(tmp_path):
    ref,auth,output=inputs(tmp_path);stub=Stub()
    run(ref,authorization_reference=auth,backend_factory=lambda:stub)
    path=next((output/'calls').glob('*.response.json'));value=json.loads(path.read_text())
    value['payload']['result']['text']='born on Avignon';value['sha256']=digest(value['payload'])
    path.chmod(0o644);path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='journal mutated'):
        run(ref,authorization_reference=auth,backend_factory=lambda:pytest.fail('sealed'))


def test_completed_record_mutation_detected(tmp_path):
    ref,auth,output=inputs(tmp_path,abstain=True)
    run(ref,authorization_reference=auth,backend_factory=lambda:pytest.fail('abstain'))
    path=next((output/'records').glob('*.json'));value=json.loads(path.read_text())
    value['payload']['status']='valid_construction';value['sha256']=digest(value['payload'])
    path.chmod(0o644);path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='mutated'):run(ref,authorization_reference=auth)


def test_draft_and_unrelated_namespace_refused(tmp_path):
    ref,auth,output=inputs(tmp_path)
    output.mkdir();(output/'unrelated.json').write_text('{}')
    with pytest.raises(FileExistsError):run(ref,authorization_reference=auth,backend_factory=lambda:pytest.fail('wrong namespace'))
    manifest=json.loads(Path(ref['path']).read_text());manifest['status']='draft_blocked'
    ref=raw(Path(ref['path']),manifest)
    with pytest.raises(ValueError,match='Draft'):preflight(ref)


def test_committed_blank_forms_grant_no_approvals():
    root=Path('pilot_prep/twowiki_semantic_v3')
    auth=json.loads((root/'forms/authorization.blank.json').read_text())
    assert auth['allow_model_calls'] is False and auth['authorizer_id'] is None
    assert json.loads((root/'manifest.draft.json').read_text())['status']=='draft_blocked'
    assert json.loads((root/'forms/target_review.blank.json').read_text())['review_state']=='pending'


def test_content_handoff_is_blocked_before_data_read_if_history_uncertified(tmp_path):
    from src.experiments.semantic_v3_preparation import prepare_target_forms
    ref,_,_=inputs(tmp_path);manifest=json.loads(Path(ref['path']).read_text());handoff=manifest['artifacts']
    forms=prepare_target_forms(handoff)
    assert len(forms)==25 and all(f['review_state']=='pending' and not f['candidates'] for f in forms)
    registry_path=Path(handoff['registry']['path']);registry=json.loads(registry_path.read_text())
    registry['historical_gaps']=['not certified'];handoff['registry']=raw(registry_path,registry)
    Path(handoff['data']['path']).unlink()  # Must fail on history before opening content.
    with pytest.raises(ValueError,match='Historical'):prepare_target_forms(handoff)


def test_candidate_review_before_cohort_freeze_refused(tmp_path):
    ref,_,_=inputs(tmp_path)
    def mutate(rows):rows[0]['candidates'][0]['packet']['review']['reviewed_at']='2020-01-01T00:00:00Z'
    ref=re_pin_manifest(tmp_path,ref,'targets',mutate)
    with pytest.raises(ValueError,match='predates'):preflight(ref)


def test_unpinned_model_environment_inventory_is_not_ready(tmp_path):
    ref,_,_=inputs(tmp_path)
    def mutate(runtime):runtime.update(execution_kind='authorized_model')
    ref=re_pin_manifest(tmp_path,ref,'runtime',mutate)
    with pytest.raises(ValueError,match='pins missing'):preflight(ref)


def test_retry_after_cached_rejection_makes_only_the_unstarted_call(tmp_path):
    ref,auth,output=inputs(tmp_path);first=Stub(['born on Avignon'])
    def cut(event,key):
        if event=='after_response':raise PowerLoss()
    with pytest.raises(PowerLoss):run(ref,authorization_reference=auth,backend_factory=lambda:first,interrupt=cut)
    second=Stub([TEXT])
    run(ref,authorization_reference=auth,backend_factory=lambda:second,max_cells=1)
    assert len(first.calls)==1 and len(second.calls)==1
    r=read_record(next((output/'records').glob('*.json')))
    attempts=r['attempt_records'][0]['attempts']
    assert len(attempts)==2 and attempts[0]['generated_text']=='born on Avignon' and attempts[1]['generated_text']==TEXT
    assert attempts[0]['prompt_revision']==0 and attempts[1]['prompt_revision']==1


def test_mid_intensity_three_resume_replays_completed_slots(tmp_path):
    ref,auth,output=inputs(tmp_path);stub=Stub()
    run(ref,authorization_reference=auth,backend_factory=lambda:stub,max_cells=25)
    def cut(event,key):
        if event=='after_response' and key.endswith('.001'):raise PowerLoss()
    with pytest.raises(PowerLoss):run(ref,authorization_reference=auth,backend_factory=lambda:stub,interrupt=cut)
    assert len(stub.calls)==27
    run(ref,authorization_reference=auth,backend_factory=lambda:stub,max_cells=1)
    assert len(stub.calls)==28
    r=next(read_record(p) for p in (output/'records').glob('*.json') if read_record(p)['intensity']==3)
    assert r['status']=='valid_construction' and len(r['documents'])==3 and len(r['attempt_records'])==3


def test_preparation_cli_freezes_metadata_and_receipt_only(tmp_path):
    import subprocess,sys
    ref,_,_=inputs(tmp_path);manifest=json.loads(Path(ref['path']).read_text());a=manifest['artifacts']
    output=tmp_path/'cli-cohort.json'
    result=subprocess.run([sys.executable,'-B','scripts/prepare_semantic_v3_pilot.py','select',
        '--registry',a['registry']['path'],'--registry-sha256',a['registry']['sha256'],
        '--pool-ids',a['pool_ids']['path'],'--pool-sha256',a['pool_ids']['sha256'],
        '--dataset-sha256',a['data']['sha256'],'--output',str(output)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(output.read_text())==json.loads(Path(a['cohort']['path']).read_text())
    receipt=json.loads(Path(str(output)+'.freeze-receipt.json').read_text())
    assert receipt['input_sha256']['cohort']==file_sha(output) and receipt['frozen_at']
