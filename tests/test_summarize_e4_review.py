import copy

import pytest

from scripts.summarize_e4_review import summarize


def inputs():
    cases = [{'case_id': 'c', 'query_id': 'q', 'gold_context': [{'doc_id': 'd', 'text': 'A source statement.'}]}]
    reviews = [{'case_id': 'c', 'packet_sha256': 'packet', 'independent_adjudication': False,
                'review_method': 'assistant_source_assisted', 'tier': 'native_source_assisted',
                'verdict': 'ambiguous', 'rationale': 'Unresolved relation.',
                'native_evidence': [{'doc_id': 'd', 'excerpt': 'source statement'}],
                'external_evidence': [], 'gold_assessment': 'insufficient_evidence', 'flags': []}]
    return cases, reviews


def test_unreviewed_is_never_counted_as_verified():
    cases, reviews = inputs()
    cases.append({'case_id': 'c2', 'query_id': 'q2', 'gold_context': []})
    result = summarize(cases, reviews, 'packet', 'ledger')
    assert result['reviewed'] == result['unreviewed'] == 1
    assert result['independently_adjudicated'] == 0
    assert result['verdicts'] == {'ambiguous': 1}


@pytest.mark.parametrize('mutation', ['wrong_packet', 'invented_excerpt', 'duplicate', 'unknown', 'independent', 'external_without_citation'])
def test_rejects_invalid_provenance(mutation):
    cases, reviews = inputs()
    r = reviews[0]
    if mutation == 'wrong_packet':
        r['packet_sha256'] = 'different'
    elif mutation == 'invented_excerpt':
        r['native_evidence'][0]['excerpt'] = 'not in source'
    elif mutation == 'duplicate':
        reviews.append(copy.deepcopy(r))
    elif mutation == 'unknown':
        r['case_id'] = 'absent'
    elif mutation == 'independent':
        r['independent_adjudication'] = True
    elif mutation == 'external_without_citation':
        r['tier'] = 'external_primary_source_assisted'
    with pytest.raises(ValueError):
        summarize(cases, reviews, 'packet', 'ledger')
