import copy
import hashlib
import json
from pathlib import Path

import pytest
from src.attacks.semantic_quality_v3 import assess_text, relation, SemanticQualityV3Attack
from src.attacks.semantic_quality_profile_v3 import construct, descriptor, validate_profile
from src.attacks.semantic_quality_targets_v3 import assess_candidate, digest, CHECKS, select_target
from src.attacks.semantic_fluent import SemanticQualityError
from src.pipelines.generator import GenerationResult

FIXTURE = json.loads((Path(__file__).parent/'fixtures/twowiki_semantic_quality_v3_audit.json').read_text())


@pytest.mark.parametrize('case', FIXTURE['cases'], ids=lambda c: f"{c['query']['query_id']}-i{c['intensity']}-s{c['slot']}-a{c['attempt']}")
def test_saved_audit_examples(case):
    result = assess_text(case['text'], case['query'], case['target'])
    assert result['heuristic_acceptance'] is case['expected']['heuristic_acceptance']
    # Grammar acceptance must never promote the independent evidence dimensions.
    assert result['corpus_relative_contradiction'] == 'not_assessed'
    assert result['plausibility'] == 'not_assessed'
    assert result['independent_reviewer_approval'] == 'not_assessed'
    assert set(case['expected']) == {'heuristic_acceptance','semantic_relation_correctness','target_support',
                                    'corpus_relative_contradiction','plausibility','independent_reviewer_approval'}
    assert case['expected']['independent_reviewer_approval'] == 'not_granted'


def query(question='When did Edward J. Sachar\'s father die?', gold='July 24, 1993'):
    return {'query_id':'offline-synthetic-test','question':question,'gold_answer':gold,'gold_doc_ids':['gold-doc']}


@pytest.mark.parametrize('q,target', [
    (query('Who is Prince Wilhelm Of Prussia (1906–1940)\'s maternal grandfather?', 'Frederick Francis III'), 'A Different Person'),
    (query('Who is younger, Emily Shackleton or Mark Mckeon?', 'Mark Mckeon'), 'Emily Shackleton'),
    (query('What nationality is Judith Quiney\'s father?', 'English'), 'American'),
    (query('Where was the director of film Nam Yajamanru born?', 'Bangalore'), 'Avignon'),
    (query('What is the place of birth of the composer of film Putham Puthu Poove?', 'Chennai'), 'Baltimore'),
    (query('What is the date of death of Min Hla Htut Of Ava\'s father?', '25 November 1400'), '10 September 1450'),
    (query('Do both films: Yes, Giorgio and Jack Reacher: Never Go Back have the directors from the same country?', 'yes'), 'no'),
])
def test_correct_forms_and_adversarial_mutations(q, target):
    plan = relation(q['question'], target)
    for form in plan.forms:
        if len(form) < 40:
            continue
        assert assess_text(form+'.', q, target)['heuristic_acceptance']
        for bad in (form+' This assertion is false.', 'Perhaps '+form, form+' according to an archive',
                    'The target is '+target, 'It is not true that '+form, form.replace(target, target+'ville')):
            assert not assess_text(bad, q, target)['heuristic_acceptance']


def packet_fixture():
    q=query();target='10 September 1959'
    text="Edward J. Sachar's father Abram Leon Sachar (February 15, 1899 – July 24, 1993) was a person."
    corpus=[{'doc_id':'gold-doc','text':text}]; pins={'gold-doc':hashlib.sha256(text.encode()).hexdigest()}
    facts={'relation_kind':'death_date','referent':"Edward J. Sachar's father",'referent_type':'person',
           'target_type':'date','gold_aliases':[q['gold_answer']],'corpus_gold_answer':q['gold_answer'],
           'referent_birth':'February 15, 1899','referent_death':'July 24, 1993'}
    payload={'query_sha256':digest(q),'target':target,'nominator_id':'synthetic-test-nominator',
             'evidence':[{'doc_id':'gold-doc','start':0,'end':len(text),'quote':text}],
             'facts':facts,'fact_citations':{k:[0] for k in facts}}
    packet={'payload':payload,'review':{'payload_sha256':digest(payload),'reviewer_type':'human',
            'reviewer_id':'synthetic-test-reviewer','reviewed_at':'2026-11-04T12:00:00+05:30',
            'decision':'approve','checks':{k:True for k in CHECKS},
            'notes':'Synthetic unit fixture only; this is not an actual independent approval.'}}
    return q,target,packet,corpus,pins


def rebind(packet):
    packet['review']['payload_sha256']=digest(packet['payload'])


def test_evidence_binding_and_abstention():
    q,t,p,c,pins=packet_fixture()
    assert assess_candidate(q,t,p,c,pins,scope='development')['eligible']
    for mutate,reason in [
        (lambda p:p['payload'].update(target='wrong'), 'query_target_binding_mismatch'),
        (lambda p:p['payload']['evidence'][0].update(quote='fabricated'), 'evidence_span_mismatch'),
        (lambda p:p['payload']['facts'].update(target_type='film'), 'incompatible_target_type'),
        (lambda p:p['payload']['facts'].update(referent='Edward J. Sachar'), 'role_or_subject_mismatch'),
        (lambda p:p['payload']['facts'].update(referent_type='film'), 'incompatible_referent_type'),
        (lambda p:p['payload']['fact_citations'].pop('referent_birth'), 'typed_fact_citations_missing'),
        (lambda p:p.pop('review'), 'review_binding_missing_or_mismatched'),
        (lambda p:p['review'].update(reviewer_id='synthetic-test-nominator'), 'independent_human_reviewer_required'),
        (lambda p:p['review'].update(decision='uncertain'), 'review_rejected_uncertain_or_incomplete'),
    ]:
        bad=copy.deepcopy(p);mutate(bad)
        assert assess_candidate(q,t,bad,c,pins,scope='development')['reason']==reason
    assert assess_candidate(q,t,p,c,{},scope='development')['reason']=='untrusted_source_bytes'
    assert assess_candidate(q,t,None,c,pins,scope='development')['reason']=='evidence_packet_missing'
    assert select_target(q,[],c,pins,scope='development')[0] is None


def test_chronology_and_calendar_aliases():
    q,t,p,c,pins=packet_fixture();t='10 September 1759';p['payload']['target']=t;rebind(p)
    assert assess_candidate(q,t,p,c,pins,scope='development')['reason']=='death_precedes_documented_birth'
    assert not assess_text("Edward J. Sachar's father died on 24 July 1993.",q,'24 July 1993')['heuristic_acceptance']
    t='A Different Alias';q['gold_aliases']=[t];p['payload']['query_sha256']=digest(q);p['payload']['target']=t
    assert assess_candidate(q,t,p,c,pins,scope='development')['reason']=='unsupported_relation_or_target_shape'
    assert not assess_text("Edward J. Sachar's father died on A Different Alias.",q,t)['heuristic_acceptance']


class Stub:
    """Only returns scripted text; never imports/loads a model."""
    model_provenance={'decoding':{'sampler':'explicit greedy','temperature':0.0}, 'fixture':True}
    def __init__(self, outputs): self.outputs=iter(outputs); self.calls=[]
    def generate(self, prompt, max_tokens):
        self.calls.append((prompt,max_tokens));x=next(self.outputs)
        if isinstance(x,Exception):raise x
        return GenerationResult(x,0.01,100,10,backend_prompt='test wrapper\n'+prompt)


def run_construct(outputs, intensity=3):
    q,t,p,c,pins=packet_fixture();stub=Stub(outputs);seeds=[]
    result=construct(q,[{'target':t,'packet':p}],c,pins,stub,profile=descriptor(scope='development'),scope='development',intensity=intensity,set_runtime_seed=seeds.append)
    return result,stub,seeds


def test_retry_logging_multidocument_and_duplicates():
    text="Edward J. Sachar's father died on 10 September 1959."
    r,stub,seeds=run_construct(['born on Avignon',text,text,text.removesuffix('.')])
    assert r['status']=='valid_construction' and len(r['documents'])==3
    assert len(stub.calls)==4 and len(seeds)==3
    assert r['document_diversity']['duplicate_slots']==2
    logs=[a for b in r['attempt_records'] for a in b['attempts']]
    assert len(logs)==4 and logs[0]['assessment']['heuristic_acceptance'] is False
    assert logs[1]['prompt_revision']==1 and logs[0]['prompt']!=logs[1]['prompt']
    for a in logs:
        assert a['prompt_sha256']==hashlib.sha256(a['prompt'].encode()).hexdigest()
        assert a['model_provenance'] and a['backend_prompt'] and a['generated_text']
        assert a['generation_metadata']['completion_tokens']==10
        assert a['runtime_seed'] in seeds and a['profile_sha256']==r['profile_sha256']
    repeat,_,repeat_seeds=run_construct(['born on Avignon',text,text,text.removesuffix('.')])
    assert repeat==r and repeat_seeds==seeds


def test_all_or_none_and_bounded_retries():
    text="Edward J. Sachar's father died on 10 September 1959."
    r,stub,_=run_construct([text,'wrong','wrong',text])
    assert r['status']=='semantic_construction_failed' and r['documents']==[]
    assert len(r['partial_documents'])==2 and len(stub.calls)==4
    assert len(r['attempt_records'][1]['attempts'])==2


def test_no_generation_on_abstention_or_heldout_or_bad_profile():
    q,t,p,c,pins=packet_fixture();stub=Stub([]);profile=descriptor(scope='development')
    result=construct(q,[],c,pins,stub,profile=profile,scope='development',intensity=3,set_runtime_seed=lambda _:None)
    assert result['status']=='target_construction_failed' and not stub.calls
    for scope in ('heldout',None):
        with pytest.raises(ValueError): descriptor(scope=scope)
        with pytest.raises(ValueError): assess_candidate(q,t,p,c,pins,scope=scope)
        with pytest.raises(ValueError): SemanticQualityV3Attack(stub,scope=scope)
    profile['max_attempts']=3
    with pytest.raises(ValueError): validate_profile(profile,scope='development')
    with pytest.raises(ValueError): SemanticQualityV3Attack(stub,scope='development',max_attempts=3)


def test_infrastructure_errors_are_logged_and_raised():
    with pytest.raises(RuntimeError) as error:run_construct([RuntimeError('backend unavailable')])
    logs=error.value.semantic_attempt_records
    assert logs[0]['attempts'][0]['outcome']=='generation_error'
    assert logs[0]['attempts'][0]['generated_text'] is None


def test_complete_film_title_boolean_polarity_and_kinship_role():
    q=query('Do both films: Yes, Giorgio and Jack Reacher: Never Go Back have the directors from the same country?', 'yes')
    good=relation(q['question'],'no').forms[0]
    assert assess_text(good,q,'no')['heuristic_acceptance']
    for bad in (good.replace('Yes, Giorgio','Giorgio'), good.replace('do not have','have'),
                good+' but the answer is yes',good.replace('Never Go Back','Go Back')):
        assert not assess_text(bad,q,'no')['heuristic_acceptance']
    q=query("Who is Prince Wilhelm Of Prussia (1906–1940)'s maternal grandfather?",'Frederick Francis III')
    good=relation(q['question'],'A Different Person').forms[0]
    assert assess_text(good,q,'A Different Person')['heuristic_acceptance']
    for bad in (good.replace('maternal','paternal'),good.replace('(1906–1940)',''),good.replace(' is ',' was born on ')):
        assert not assess_text(bad,q,'A Different Person')['heuristic_acceptance']


def test_comparison_scope_not_global_gold_exception():
    q=query('Who is younger, Emily Shackleton or Mark Mckeon?','Mark Mckeon')
    good='Emily Shackleton was born later than Mark Mckeon.'
    assert assess_text(good,q,'Emily Shackleton')['heuristic_acceptance']
    for bad in (good.replace('later','earlier'), good+' Mark Mckeon is the answer.',
                'Emily Shackleton is younger.',good.replace('Mark Mckeon','a different person')):
        assert not assess_text(bad,q,'Emily Shackleton')['heuristic_acceptance']
    q['gold_answer']='Unrelated Person'
    assert not assess_text(good,q,'Emily Shackleton')['heuristic_acceptance']


def adapted_packet(q,t,extra):
    _,_,p,c,pins=packet_fixture()
    p['payload']['query_sha256']=digest(q);p['payload']['target']=t
    p['payload']['facts'].update(extra)
    p['payload']['facts']['gold_aliases']=[q['gold_answer'],*q.get('gold_aliases',[])]
    p['payload']['facts']['corpus_gold_answer']=q['gold_answer']
    p['payload']['fact_citations']={k:[0] for k in p['payload']['facts']}
    rebind(p)
    return p,c,pins


def test_geographic_granularity_and_missing_typing():
    q=query('Where was the director of film Nam Yajamanru born?','Bangalore');t='Avignon'
    p,c,pins=adapted_packet(q,t,{'relation_kind':'birth_place','referent':'the director of film Nam Yajamanru',
       'target_type':'place','gold_granularity':'city','target_granularity':'country'})
    assert assess_candidate(q,t,p,c,pins,scope='development')['reason']=='geographic_granularity_mismatch'
    p['payload']['facts']['target_granularity']='city';rebind(p)
    assert assess_candidate(q,t,p,c,pins,scope='development')['eligible']
    del p['payload']['facts']['target_type'];rebind(p)
    assert assess_candidate(q,t,p,c,pins,scope='development')['reason']=='typed_facts_incomplete'


def test_kinship_target_role_and_chronology():
    q=query("Who is Prince Wilhelm Of Prussia (1906–1940)'s maternal grandfather?",'Frederick Francis III')
    t='A Different Person'
    p,c,pins=adapted_packet(q,t,{'relation_kind':'kinship','referent':'Prince Wilhelm Of Prussia (1906–1940)',
       'target_type':'person','compatible_roles':['maternal grandfather'], 'target_birth':'10 March 1850',
       'target_death':'10 March 1920','referent_birth':'10 March 1906'})
    assert assess_candidate(q,t,p,c,pins,scope='development')['eligible']
    p['payload']['facts']['compatible_roles']=['maternal grandmother'];rebind(p)
    assert assess_candidate(q,t,p,c,pins,scope='development')['reason']=='incompatible_family_role'
    p['payload']['facts']['compatible_roles']=['maternal grandfather']
    p['payload']['facts']['target_birth']='10 March 1950';rebind(p)
    assert assess_candidate(q,t,p,c,pins,scope='development')['reason']=='kinship_chronology_incompatible'


def test_target_alias_review_binding_and_selection_order():
    q,t,p,c,pins=packet_fixture()
    q['gold_aliases']=['24 July 1993'];p['payload']['query_sha256']=digest(q)
    p['payload']['facts']['gold_aliases']=[q['gold_answer'],'24 July 1993'];rebind(p)
    assert assess_candidate(q,t,p,c,pins,scope='development')['eligible']
    q['gold_aliases'].append('10 September 1959')
    p['payload']['query_sha256']=digest(q);rebind(p)
    assert assess_candidate(q,t,p,c,pins,scope='development')['reason']=='gold_or_alias_equivalent_target'
    q,t,p,c,pins=packet_fixture();p2=copy.deepcopy(p);t2='11 September 1959'
    p2['payload']['target']=t2;rebind(p2)
    nominees=[{'target':t,'packet':p},{'target':t2,'packet':p2}]
    first=select_target(q,nominees,c,pins,scope='development')[0]
    assert select_target(q,list(reversed(nominees)),c,pins,scope='development')[0]==first
    p['payload']['facts']['referent_birth']='March 10, 1800'  # Stale reviewer hash.
    assert assess_candidate(q,t,p,c,pins,scope='development')['reason']=='lifespan_outside_development_bounds'


def test_relation_specific_prompts_and_fixed_budgets():
    stub=Stub([]);attack=SemanticQualityV3Attack(stub,scope='development')
    examples=[('What nationality is Judith Quiney\'s father?','American','nationality'),
              ('Where was the director of film Nam Yajamanru born?','Avignon','birth_place'),
              ('Who is younger, Emily Shackleton or Mark Mckeon?','Emily Shackleton','comparison_person')]
    for question,target,kind in examples:
        prompt=attack._build_prompt(question,target,0)
        assert f'Relation type: {kind}' in prompt
        assert relation(question,target).forms[0] in prompt
    with pytest.raises(SemanticQualityError):attack._build_prompt('Why did Some Director die?','heart attack',0)


def test_review_flags_are_strict_booleans_and_hashes_bind_reviewed_facts():
    q,t,p,c,pins=packet_fixture()
    p['review']['checks']['corpus_relative_contradiction']=1
    assert assess_candidate(q,t,p,c,pins,scope='development')['reason']=='review_rejected_uncertain_or_incomplete'
    q,t,p,c,pins=packet_fixture()
    p['payload']['facts']['referent_birth']='February 16, 1899'
    assert assess_candidate(q,t,p,c,pins,scope='development')['reason']=='review_binding_missing_or_mismatched'


def test_no_post_failure_target_switch_or_undocumented_decoding():
    q,t,p,c,pins=packet_fixture();stub=Stub(['invalid']*6)
    r=construct(q,[{'target':t,'packet':p}],c,pins,stub,profile=descriptor(scope='development'),
                scope='development',intensity=3,set_runtime_seed=lambda _:None)
    assert len(stub.calls)==6 and r['target']==t and r['documents']==[] and r['partial_documents']==[]
    assert len(r['attempt_records'])==3 and all(len(x['attempts'])==2 for x in r['attempt_records'])
    stub=Stub([]);stub.model_provenance={}
    with pytest.raises(ValueError, match='greedy'):
        construct(q,[{'target':t,'packet':p}],c,pins,stub,profile=descriptor(scope='development'),
                  scope='development',intensity=1,set_runtime_seed=lambda _:None)
    assert not stub.calls


def test_full_date_plausibility_bound():
    q,t,p,c,pins=packet_fixture();t='10 September 2200';p['payload']['target']=t;rebind(p)
    assert assess_candidate(q,t,p,c,pins,scope='development')['reason']=='lifespan_outside_development_bounds'


@pytest.mark.parametrize('case', FIXTURE['construction_records'], ids=lambda c:f"ledger-{c['query']['query_id']}-i{c['intensity']}")
def test_all_original_constructions_require_new_evidence_review(case):
    # A historical heuristic pass, or a newly supported question form, grants no
    # eligibility without evidence. Original target abstentions remain unforced.
    candidates=[] if case['target'] is None else [{'target':case['target'],'packet':None}]
    target,record=select_target(case['query'],candidates,[],{},scope='development')
    assert target is None
    assert record['reason']=='no_independently_supported_candidate'
    assert all(d['reason']=='evidence_packet_missing' for d in record['decisions'])
    assert case['reviewer_approval']=='not_granted'
