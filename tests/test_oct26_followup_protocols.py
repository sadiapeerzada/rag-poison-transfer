import copy
import json

import pytest

from scripts.prepare_oct26_followups import choose_source_candidate,normalized_question,near_duplicate,select_cohorts


def feedback(source='bm25'):
    return [{'source_pipeline':source,'candidate_index':i,'construction_valid':i!=0,'source_target_match':i==2} for i in range(3)]


def test_source_only_selection_and_budget():
    candidates=['candidate-a','candidate-b','candidate-c']
    assert choose_source_candidate(candidates,feedback())=='candidate-c'
    observations=feedback()
    for r in observations:r['source_target_match']=False
    assert choose_source_candidate(candidates,observations)=='candidate-b'
    for r in observations:r['construction_valid']=False
    assert choose_source_candidate(candidates,observations) is None
    with pytest.raises(ValueError,match='three'):
        choose_source_candidate(candidates+['fourth'],feedback()+[feedback()[0]])


@pytest.mark.parametrize('change',[
    lambda rows:rows[0].update(rcd_target_success=True),
    lambda rows:rows[0].update(source_pipeline='rcd'),
    lambda rows:rows[1].update(source_pipeline='dense'),
    lambda rows:rows[0].update(source_target_match=True),
])
def test_target_feedback_and_false_success_rejected(change):
    rows=feedback();change(rows)
    with pytest.raises(ValueError):choose_source_candidate(['a','b','c'],rows)


def examples(prefix,count):
    return [{'_id':prefix+str(i),'question':' '.join(prefix+str(i)+'word'+str(j) for j in range(8))} for i in range(count)]


def test_deterministic_disjoint_cohorts_never_use_answers():
    train=examples('train',305);dev=examples('dev',305)
    a,excluded=select_cohorts(train,dev,{'dev0'},[])
    b,_=select_cohorts(list(reversed(train)),list(reversed(dev)),{'dev0'},[])
    assert a==b
    trainids={r['query_id'] for r in a['train']};devids={r['query_id'] for r in a['dev']}
    assert len(trainids)==len(devids)==300 and not trainids&devids and 'dev0' not in devids
    assert all('answer' not in r for group in a.values() for r in group)
    with pytest.raises(ValueError,match='Duplicate'):
        select_cohorts(train+[train[0]],dev,set(),[])


def test_exact_and_near_duplicate_rule():
    assert near_duplicate(normalized_question('Who Was Alice?'),normalized_question('who was alice'))
    first=' '.join('token'+str(i) for i in range(30))
    assert near_duplicate(first,first.replace('token29','different'))
    assert not near_duplicate('entirely different words','none of these match')
