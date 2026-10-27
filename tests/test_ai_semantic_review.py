"""AI-review software fixtures: no actual human judgments or MLX calls."""
import copy
import json
from pathlib import Path
import pytest
from src.experiments import ai_semantic_review as ai
from src.experiments import semantic_review as human
from scripts import run_ai_semantic_review as runner
from src.pipelines.generator import GenerationResult


def item(key='one',target='Dutch',question='Who is the maternal grandfather?'):
    return {'item_id':key,'query_id':key,'question':question,'gold_answer':'Example Person','gold_aliases_json':'[]',
        'target_answer':target,'generated_text':'The maternal grandfather was Dutch.',
        'source_evidence_json':json.dumps([{'doc_id':'fixture-doc','text':'Example Person was the maternal grandfather.'}]),
        'automated_validator_decision':'SECRET_REJECTION','automated_rejection_reason':'SECRET_REASON'}


def answer():
    c={k:'yes' for k in human.RATINGS};c.update(relation_correspondence='no',target_assertion='no',factual_falsity='uncertain')
    return {'criteria':c,'rationale':'The statement gives nationality rather than identity.',
        'evidence':[{'source_id':'dataset_passage_1','quote':'Example Person was the maternal grandfather.'}]}


def test_blinded_prompt_and_separate_ai_provenance():
    text=ai.prompt(ai.model_input(item()))
    assert 'SECRET_REJECTION' not in text and 'SECRET_REASON' not in text
    parsed=ai.parse(json.dumps(answer()),ai.model_input(item()))
    assert parsed['ai_disposition']=='reject' and 'human review' in parsed['judgment_provenance']


@pytest.mark.parametrize('mutation',[
 lambda a:a['criteria'].pop('subject_correspondence'),
 lambda a:a['criteria'].update(factual_falsity='verified'),
 lambda a:a['evidence'][0].update(source_id='invented_url'),
 lambda a:a['evidence'][0].update(quote='fabricated quotation'),
 lambda a:a.update(evidence=[]),
 lambda a:a.update(reviewer='fake human'),
])
def test_malformed_judgments_and_fabricated_evidence_fail_closed(mutation):
    a=answer();mutation(a)
    with pytest.raises(ValueError):ai.parse(json.dumps(a),ai.model_input(item()))


def test_insufficient_factual_evidence_can_remain_uncertain():
    a=answer();a['criteria']={k:'yes' for k in human.RATINGS};a['criteria'].update(factual_falsity='uncertain',evidence_sufficiency='uncertain');a['evidence']=[]
    assert ai.parse(json.dumps(a),ai.model_input(item()))['ai_disposition']=='uncertain'


def test_ai_records_cannot_be_imported_as_human_reviews():
    with pytest.raises(ValueError):human.validate_reviews([], [{'schema':ai.SCHEMA,'review_method':'AI-assisted','human_review':False}])


@pytest.fixture
def setup(tmp_path,monkeypatch):
    items=[item(),item('two',question='Are both Example stations in the same country?',target='yes'),item('three',target='1913',question='In what year did the event occur?')]
    # Extra attempt with identical full evaluator input: cached origin, not a new call.
    items.append({**items[0],'item_id':'four'})
    proto={'binding':{'scope':'development','model_identity':'fixture'}}
    monkeypatch.setattr(runner,'source',lambda *a:(proto,items))
    monkeypatch.setattr(runner.base,'code_binding',lambda:{'git_commit_sha':'fixture','code_fingerprint':'fixture'})
    monkeypatch.setattr(runner.base,'environment',lambda:{'python':'fixture'})
    monkeypatch.setattr(runner.base,'model_binding',lambda *a:{'repository':'fixture','revision':'fixture'})
    monkeypatch.setattr(runner.base,'runtime_seed',lambda *a:None)
    class Backend:
        def __init__(self):self.calls=0;self.error=None
        def generate(self,prompt,max_tokens):
            self.calls+=1
            if self.error:raise self.error
            return GenerationResult(json.dumps(answer()),.1,10,20)
    backend=Backend();monkeypatch.setattr(runner.base,'generator',lambda *a:backend)
    package=tmp_path/'package';package.mkdir();(package/'manifest.json').write_text('{}')
    original=tmp_path/'original'/'protocol.json';original.parent.mkdir();original.write_text('{}')
    root=tmp_path/'review';plan=root/'plan.json'
    result=runner.freeze(plan,package,runner.base.sha(package/'manifest.json'),original,runner.base.sha(original),tmp_path/'c','seal',tmp_path/'snapshot')
    return plan,result['plan_sha256'],root,items,backend


def test_controlled_pilot_cache_resume_and_full_comparison_barrier(setup):
    plan,pin,root,items,backend=setup
    with pytest.raises(ValueError,match='incomplete'):runner.compare(plan,pin)
    pilot=runner.assess(plan,pin,root,Path('snapshot'),True);assert pilot['new_model_calls']==3
    assert backend.calls==3
    with pytest.raises(ValueError,match='incomplete'):runner.compare(plan,pin)
    runner.assess(plan,pin,root,Path('snapshot'),True);assert backend.calls==3
    runner.assess(plan,pin,root,Path('snapshot'));assert backend.calls==3
    result=runner.compare(plan,pin);assert result['attempt_counts']=={'accept':0,'reject':4,'uncertain':0,'unevaluated':0}
    assert result['actual_unique_model_calls']==3 and result['comparison_performed_after_full_census']
    record=json.loads((root/'assessments/four.json').read_text());assert not record['human_review']
    assert not any(k in record for k in ('reviewer','review_timestamp','independent_of_generation'))


def test_interrupted_review_intent_never_regenerated(setup):
    plan,pin,root,items,backend=setup;backend.error=KeyboardInterrupt('fixture interruption')
    with pytest.raises(KeyboardInterrupt):runner.assess(plan,pin,root,Path('snapshot'),True)
    assert backend.calls==1;backend.error=None
    with pytest.raises(RuntimeError,match='Unresolved'):runner.assess(plan,pin,root,Path('snapshot'),True)
    assert backend.calls==1


def test_altered_assessment_and_stale_versions_rejected(setup):
    plan,pin,root,items,backend=setup;runner.assess(plan,pin,root,Path('snapshot'),True)
    path=next((root/'assessments').glob('*.json'));r=json.loads(path.read_text());r['assessment']['criteria']['target_assertion']='yes';path.write_text(json.dumps(r))
    with pytest.raises(ValueError,match='recorded model'):runner.assess(plan,pin,root,Path('snapshot'),True)
    value=json.loads(plan.read_text());value['prompt_version']='stale';plan.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='version'):runner.load(plan,runner.base.sha(plan))


def test_review_budget_and_unplanned_call_namespaces_fail_closed(setup):
    plan,pin,root,items,backend=setup
    (root/'calls'/'unplanned').mkdir(parents=True)
    with pytest.raises(ValueError,match='Unexpected'):runner.assess(plan,pin,root,Path('snapshot'),True)
    assert backend.calls==0


def test_completed_assessment_census_is_sealed_and_revalidated(setup):
    plan,pin,root,items,backend=setup;runner.assess(plan,pin,root,Path('snapshot'),True);runner.assess(plan,pin,root,Path('snapshot'))
    a=runner.compare(plan,pin);assert (root/'assessment.complete.json').exists()
    assert runner.compare(plan,pin)==a
    record=next((root/'assessments').glob('*.json'));v=json.loads(record.read_text());v['assessment']['rationale']='tampered';record.write_text(json.dumps(v))
    with pytest.raises(ValueError):runner.compare(plan,pin)


def test_pilot_date_slot_rejects_year_bearing_film_titles():
    mismatch=item('identity');boolean=item('boolean',target='yes',question='Are both locations alike?')
    film=item('film',target='The Island (2005 Film)',question='Which film came first?')
    date=item('date',target='10 September 1759',question='When did the person die?')
    chosen=ai.pilot_ids([mismatch,boolean,film,date])
    assert 'date' in chosen and 'film' not in chosen and len(chosen)==3
