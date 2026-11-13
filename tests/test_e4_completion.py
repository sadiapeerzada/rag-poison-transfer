from copy import deepcopy

import pytest

from scripts.complete_e4_review import preserve_annotations, require_complete, summarize_failures
from scripts.prepare_e4_case_review import FAMILIES
from scripts.prepare_e4_failure_review import select_failures


def frame():
    return [dict(case_id=f'{f}-{i}-{s}-{q}-{rep}', query_id=f'{f}-{i}-{s}-{q}',
                 family=f, intensity=i, status=s)
            for f in FAMILIES for i in (1, 3)
            for s in ('target_construction_failed', 'semantic_construction_failed')
            if s != 'semantic_construction_failed' or f == FAMILIES[1]
            for q in range(8) for rep in range(3)]


def test_failure_allocation_is_separate_unique_and_order_invariant():
    rows = frame()
    excluded = {rows[0]['query_id']}
    chosen = select_failures(rows, excluded)
    assert len(chosen) == len({r['query_id'] for r in chosen}) == 24
    assert not excluded & {r['query_id'] for r in chosen}
    assert chosen == select_failures(list(reversed(rows)), excluded)
    from collections import Counter
    assert set(Counter((r['family'], r['intensity'], r['status']) for r in chosen).values()) == {4}


def test_failure_shortfall_never_silently_relaxes_uniqueness():
    with pytest.raises(ValueError, match='lacks four'):
        select_failures(frame(), {r['query_id'] for r in frame()})


def test_original_annotation_preserved_including_qualifications():
    old = [{'case_id': 'a', 'rationale': 'Uncertain', 'external_evidence': [{'limit': 'one hop only'}]}]
    new = deepcopy(old)+[{'case_id': 'b'}]
    preserve_annotations(old, new)
    new[0]['external_evidence'][0]['limit'] = 'fully verified'
    with pytest.raises(ValueError, match='changed'):
        preserve_annotations(old, new)


def test_completion_rejects_missing_or_unbound_case():
    with pytest.raises(ValueError, match='Incomplete'):
        require_complete([{'case_id': 'a'}, {'case_id': 'b'}], [{'case_id': 'a'}])
    with pytest.raises(ValueError, match='Incomplete'):
        require_complete([{'case_id': 'a'}], [{'case_id': 'wrong'}])


def failed_inputs():
    band = dict(target_answer=None, status='target_construction_failed', attempt_records=[], documents=[], partial_documents=[])
    cases = [dict(case_id='a', query_id='q', status='target_construction_failed', gold_context=[], candidate_records=[deepcopy(band) for _ in range(3)])]
    reviews = [dict(case_id='a', packet_sha256='packet', independent_adjudication=False,
                    review_method='assistant_source_assisted', tier='native_source_assisted',
                    verdict='unadjudicated', rationale='No target exists.', gold_assessment='question_defect', flags=[],
                    native_evidence=[dict(doc_id='d', excerpt='context')], external_evidence=[],
                    reviewed_candidate_bands=[0, 1, 2], reviewed_attempts=0,
                    target_validity='absent_not_reviewable', failure_mechanism='no_target_no_generated_evidence')]
    cases[0]['gold_context']=[dict(doc_id='d', text='Original context.')]
    return cases, reviews


def test_absent_target_is_never_counted_as_false_or_answered():
    cases, reviews = failed_inputs()
    result = summarize_failures(cases, reviews, 'packet', 'ledger')
    assert result['verdicts'] == {'unadjudicated': 1}
    assert result['retained_generation_attempts'] == result['assigned_target_bands'] == 0
    reviews[0]['verdict'] = 'source_contradicts_target'
    with pytest.raises(ValueError, match='nonexistent target'):
        summarize_failures(cases, reviews, 'packet', 'ledger')


@pytest.mark.parametrize('mutation', ['bands', 'attempts', 'target', 'accepted'])
def test_failure_review_requires_complete_attempt_provenance(mutation):
    cases, reviews = failed_inputs()
    if mutation == 'bands':
        reviews[0]['reviewed_candidate_bands'] = [0]
    elif mutation == 'attempts':
        reviews[0]['reviewed_attempts'] = 99
    elif mutation == 'target':
        reviews[0]['target_validity'] = 'false'
    else:
        cases[0]['candidate_records'][0]['documents'] = [{'text': 'accepted'}]
    with pytest.raises(ValueError):
        summarize_failures(cases, reviews, 'packet', 'ledger')
