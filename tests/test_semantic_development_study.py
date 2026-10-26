"""Synthetic-only development methodology fixtures; no real reviewer/model claims."""
import copy
import json
from pathlib import Path
import random
import pytest
from scripts import run_week9_protocol_poison_matrix as base
from src.experiments import semantic_development_study as study
from src.experiments import semantic_review as review
from src.experiments import execution_reliability as reliable
from src.attacks import semantic_profiles as profiles
from src.pipelines.generator import GenerationResult


def queries(n=30):
    return [{'query_id':f'dev-{i}','question':f'Who wrote The Example Historical Chronicle {i}?',
        'gold_answer':'Alice Author' if i<29 else 'Bob Writer','gold_doc_ids':['clean']} for i in range(n)]


def test_selection_is_deterministic_order_independent_and_outcome_free():
    pool=queries();other=list(reversed(pool))
    assert study.select(pool,['heldout'])==study.select(other,['heldout'])
    assert len(study.select(pool,['heldout']))==25
    assert {q['query_id'] for q in study.select([{**q,'outcome':'changed'} for q in pool],['heldout'])}=={q['query_id'] for q in study.select(pool,['heldout'])}


@pytest.mark.parametrize('pool,heldout',[(queries(),['dev-0']),(queries()+[queries()[0]],['heldout']),(queries(20),['heldout']),(queries(),['same','same'])])
def test_selection_refuses_overlap_duplicates_or_short_pool(pool,heldout):
    with pytest.raises(ValueError):study.select(pool,heldout)


@pytest.fixture
def setup(tmp_path,monkeypatch):
    full={'queries':queries(),'corpus':[{'doc_id':'clean','text':'Synthetic dataset-provided evidence only.'}]}
    data=tmp_path/'train.json';data.write_text(json.dumps(full));manifest=tmp_path/'cohort.json';manifest.write_text(json.dumps({'cohorts':{'dev':[{'query_id':'heldout'}]}}))
    replica={'schema':'rag-poison-transfer.2wiki-replication-inputs/v2','scope':'development',
        'local_data':str(data),'local_data_sha256':base.sha(data),'cohort_manifest':str(manifest),'cohort_manifest_sha256':base.sha(manifest)}
    binding={'scope':'development','query_ids':['dev-0','dev-1'],'matrix':[list(c) for c in base.protocol.cells('development')],
        'dataset':{'loader':'load_2wikimultihopqa','split':'train','revision':'fixture'},'model_identity':'fixture'}
    cfg={'top_k':3,'max_tokens':64,'retriever':'dense'}
    monkeypatch.setattr(base,'context_metadata',lambda *a:(binding,cfg,cfg,full['queries']))
    monkeypatch.setattr(base,'environment',lambda:{'python':'fixture'})
    monkeypatch.setattr(base,'model_binding',lambda *a:{'revision':'fixture'})
    monkeypatch.setattr(base,'code_binding',lambda:{'git_commit_sha':'fixture','code_fingerprint':'fixture'})
    monkeypatch.setattr(base,'runtime_seed',lambda *a:None)
    class Backend:
        def __init__(self):self.calls=0
        def generate(self,prompt,max_tokens):
            self.calls+=1
            if 'Reference answer:' in prompt:
                target=prompt.split('Reference answer: "')[1].split('"')[0]
                question=prompt.split('Question: ')[1].split('\n')[0];book=question[len('Who wrote '):-1]
                text=(f'A discussion mentions {target} without affirming this relationship.' if 'historical background' in prompt else f'{target} wrote {book}.')
            else:text='Bob Writer'
            return GenerationResult(text,.1,10,20)
    backend=Backend();monkeypatch.setattr(base,'generator',lambda *a:backend)
    path=tmp_path/'study'/'protocol.json'
    pin=base.freeze_protocol(path,'development',Path('snapshot'),replica,semantic_profile=profiles.DEVELOPMENT,development_study=study.IDENTIFIER)['protocol_sha256']
    return path,pin,backend,full,replica


def test_study_protocol_binds_25_train_ids_two_intensities_and_separation(setup):
    path,pin,backend,full,_=setup;value,*_=base.load_protocol(path,pin)
    assert backend.calls==0 and value['schema']==base.DEVELOPMENT_STUDY_PROTOCOL_SCHEMA
    assert value['binding']['query_ids']==[q['query_id'] for q in study.select(full['queries'],['heldout'])]
    assert base.declared_cells(value)==[('semantic_fluent_false_evidence',1,42),('semantic_fluent_false_evidence',3,42)]
    assert value['development_study']['maximum_total_backend_calls']==400
    assert len(base.load_clean(value,{})['queries'])==25


@pytest.mark.parametrize('change',[
 lambda v:v['development_study'].update(query_count=26),
 lambda v:v['development_study']['matrix'].append(['lexical_influential_token',1,42]),
 lambda v:v['binding']['query_ids'].reverse(),
 lambda v:v['binding'].update(scope='heldout'),
 lambda v:v['replication'].update(scope='heldout'),
 lambda v:v['semantic_profile'].update(identifier=profiles.LEGACY),
])
def test_stale_study_bindings_and_wrong_scope_fail_closed(setup,change):
    path,pin,*_=setup;v=json.loads(path.read_text());change(v);path.write_text(json.dumps(v))
    with pytest.raises(ValueError):base.load_protocol(path,base.sha(path))


def test_study_cli_cannot_change_after_freeze(monkeypatch):
    import sys
    monkeypatch.setattr(sys,'argv',['runner','construct','--development-study',study.IDENTIFIER])
    with pytest.raises(SystemExit):base.main()


def construct(setup):
    path,pin,backend,full,_=setup;v=json.loads(path.read_text());root=Path(v['planned_outputs']['construction'])
    done=base.construct(path,pin,root,Path('fixture'))
    value,dense,rcd,clean,cells=base.load_sealed(path,pin,root,done['construction_seal_sha256'])
    return value,clean,cells,root,done['construction_seal_sha256']


def test_partial_intensity3_counts_and_denominators_are_separate(setup):
    value,clean,cells,root,seal=construct(setup)
    stats=study.construction_summary(cells,root)
    one=stats['semantic_fluent_false_evidence.intensity-1.seed-42'];three=stats['semantic_fluent_false_evidence.intensity-3.seed-42']
    assert one['fully_constructed_queries']==25 and one['documents_automatically_accepted_including_partials']==25
    assert three['fully_constructed_queries']==0 and three['partially_constructed_queries']==25
    assert three['documents_attempted']==75 and three['documents_automatically_accepted_including_partials']==50
    assert three['valid_documents_retained_for_injection']==0 and three['documents_retried']==25
    assert three['generation_attempts']==100 and three['rates']['full_query_coverage']['denominator']==25
    assert base.protocol.replay(clean,cells['semantic_fluent_false_evidence.intensity-3.seed-42'])['queries']==[]


def test_study_pause_and_completed_journal_resume_do_not_regenerate(setup,monkeypatch):
    path,pin,backend,*_=setup;v=json.loads(path.read_text());root=Path(v['planned_outputs']['construction'])
    with pytest.raises(reliable.PauseExecution):base.construct(path,pin,root,Path('fixture'),max_batches=1)
    assert backend.calls==25 and not (root/'construction.seal.json').exists()
    with pytest.raises(FileNotFoundError):base.load_sealed(path,pin,root,'0'*64)
    base.construct(path,pin,root,Path('fixture'));assert backend.calls==125


@pytest.fixture
def package(setup,tmp_path):
    value,clean,cells,root,seal=construct(setup)
    records=review.items(clean,cells,setup[1]);directory=tmp_path/'review'
    review.write_package(directory,records,{'protocol_sha256':setup[1],'construction_seal_sha256':seal},reliable.atomic)
    return directory,records


def test_blinding_lossless_master_and_pending_reviews(package):
    directory,records=package;manifest,loaded=review.load_package(directory)
    assert records==loaded and manifest['review_item_count']==125
    rows=review.read_reviews(directory/'blinded_review.csv')
    assert len(rows)==125 and 'automated_validator_decision' not in rows[0]
    assert all(r['final_reviewer_decision']=='pending' and r['reviewer']==r['review_timestamp']=='' for r in rows)
    result=review.validate_reviews(records,rows)
    assert result['completed_reviews']==0 and len(result['pending_review_ids'])==125
    assert result['status']=='awaiting_independent_review'
    missing=review.validate_reviews(records,[]);assert len(missing['missing_review_ids'])==125


@pytest.mark.parametrize('change',[
 lambda r:r.update(final_reviewer_decision='approved'),
 lambda r:r.update(subject_correspondence='true'),
 lambda r:r.update(generated_text='tampered'),
 lambda r:r.update(final_reviewer_decision='accept'),
 lambda r:r.update(evidence_references_json='not JSON'),
 lambda r:r.update(independent_of_generation='automatically verified'),
 lambda r:r.update(unexpected='value'),
])
def test_malformed_or_unsubstantiated_reviews_rejected(package,change):
    _,records=package;row=review.blind(records[0]);change(row)
    with pytest.raises(ValueError):review.validate_reviews(records,[row])


def test_duplicate_unknown_and_altered_package_rejected(package):
    directory,records=package;row=review.blind(records[0])
    with pytest.raises(ValueError):review.validate_reviews(records,[row,row])
    with pytest.raises(ValueError):review.validate_reviews(records,[{**row,'item_id':'unknown'}])
    (directory/'master.jsonl').write_text('tampered')
    with pytest.raises(ValueError,match='integrity'):review.load_package(directory)


def test_synthetic_review_import_preserves_supplied_fields_and_missing_reviews(package):
    # Explicitly fabricated unit-test fixture; not a real review or experimental artifact.
    _,records=package;row=review.blind(records[0]);row.update({k:'yes' for k in review.RATINGS})
    row.update(reviewer='synthetic-test-only',review_timestamp='2000-01-01T00:00:00+00:00',independent_of_generation='yes',
        final_reviewer_decision='accept',reviewer_confidence='high',
        evidence_references_json=json.dumps([{'source_reference':'synthetic-fixture','claim_supported':'Unit-test assertion only','limitations':'Not factual evidence'}]))
    result=review.validate_reviews(records,[row]);assert result['completed_review_records']==[row]
    assert result['completed_reviews']==1 and len(result['missing_review_ids'])==124
    assert result['status']=='awaiting_independent_review' and result['does_not_approve_a_heldout_protocol']


def test_study_paired_evaluation_and_aggregate_failure_accounting(setup,monkeypatch):
    from types import SimpleNamespace
    import run
    value,clean,cells,root,seal=construct(setup);path,pin,backend,*_=setup
    class Retriever:
        def build(self,corpus):self.docs=[SimpleNamespace(**d) for d in corpus]
        def retrieve(self,q,top_k):return self.docs[:top_k]
    monkeypatch.setattr(run,'build_retriever',lambda *a:Retriever());monkeypatch.setattr(reliable,'release_idle_memory',lambda:None)
    out=Path(value['planned_outputs']['evaluation']);before=backend.calls
    done=base.evaluate(path,pin,root,seal,out,Path('fixture'));assert backend.calls-before==100
    count=backend.calls;base.evaluate(path,pin,root,seal,out,Path('fixture'));assert backend.calls==count
    destination=Path(value['planned_outputs']['aggregate'])
    base.aggregate(path,pin,root,seal,out,done['evaluation_completion_sha256'],destination)
    result=json.loads(destination.read_text());assert result['diagnostic_only'] and result['development_study']==study.descriptor()
    three=result['cells']['semantic_fluent_false_evidence.intensity-3.seed-42']
    for arm in ('dense','rcd'):
        assert three[arm]['attempted']==25 and three[arm]['evaluated']==0
        assert three[arm]['end_to_end_targeted_asr']==base.protocol.rate(0,25)
        assert three[arm]['conditional_targeted_asr_valid']==base.protocol.rate(0,0)


def test_study_indeterminate_generation_is_not_retried(setup,monkeypatch):
    path,pin,backend,*_=setup;value=json.loads(path.read_text());root=Path(value['planned_outputs']['construction'])
    original=backend.generate
    def interrupt(*a,**kw):backend.calls+=1;raise KeyboardInterrupt('synthetic interruption after intent')
    monkeypatch.setattr(backend,'generate',interrupt)
    with pytest.raises(KeyboardInterrupt):base.construct(path,pin,root,Path('fixture'))
    assert backend.calls==1
    monkeypatch.setattr(backend,'generate',original)
    with pytest.raises(RuntimeError,match='Unresolved'):base.construct(path,pin,root,Path('fixture'))
    assert backend.calls==1


def test_review_cli_import_is_bound_to_actual_sealed_records(setup,tmp_path,monkeypatch):
    import sys
    from scripts import review_semantic_development as cli
    value,clean,cells,root,seal=construct(setup);path,pin,*_=setup;directory=tmp_path/'package'
    records=review.items(clean,cells,pin)
    review.write_package(directory,records,cli.package_context(value,cells,pin,seal),reliable.atomic)
    out=tmp_path/'import.json'
    argv=['review','import','--protocol',str(path),'--protocol-sha256',pin,'--construction-dir',str(root),
        '--construction-seal-sha256',seal,'--package',str(directory),'--reviews',str(directory/'blinded_review.csv'),'--output',str(out)]
    monkeypatch.setattr(sys,'argv',argv);cli.main();assert json.loads(out.read_text())['completed_reviews']==0
    # Rehashing altered master data cannot bypass trusted construction binding.
    master=directory/'master.jsonl';changed=[{**records[0],'question':'Altered question'},*records[1:]]
    master.write_text(''.join(json.dumps(r)+'\n' for r in changed));manifest=json.loads((directory/'manifest.json').read_text())
    manifest['files_sha256']['master.jsonl']=base.sha(master);(directory/'manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(sys,'argv',[*argv[:-1],str(tmp_path/'second-import.json')])
    with pytest.raises(ValueError,match='trusted frozen'):cli.main()


def test_review_outputs_cannot_invalidate_frozen_namespaces(tmp_path):
    from scripts.review_semantic_development import safe_output
    construction=tmp_path/'construction';evaluation=tmp_path/'evaluation';value={'planned_outputs':{'evaluation':str(evaluation)}}
    for path in (construction,construction/'new.json',evaluation/'review.json'):
        with pytest.raises(ValueError,match='sealed'):safe_output(path,value,construction)
    assert safe_output(tmp_path/'reviews',value,construction)==tmp_path/'reviews'
