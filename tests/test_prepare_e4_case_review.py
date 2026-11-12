from collections import Counter
import random

import pytest

from scripts.prepare_e4_case_review import BINS, FAMILIES, TARGETS, outcome_bin, read, select_cases


def measurements(matches, exposed=False):
    return {t: {'poison_doc_ids': ['poison'], 'poisoned_condition': {
        'targeted_asr': m, 'generation_evidence_doc_ids': ['poison' if exposed else 'clean']}}
        for t, m in zip(TARGETS, matches)}


@pytest.mark.parametrize('matches,exposed,bucket', [
    ((1, 1, 1), True, BINS[0]), ((0, 1, 1), True, BINS[1]),
    ((0, 0, 1), False, BINS[1]), ((1, 0, 0), True, BINS[2]),
    ((0, 0, 0), True, BINS[3]), ((0, 0, 0), False, BINS[4]),
])
def test_partition(matches, exposed, bucket):
    assert outcome_bin(measurements(matches, exposed)) == bucket


def frame():
    return [dict(case_id=f'{f}-{i}-{q}-{s}', query_id=f'{f}-{i}-{q}', family=f,
                 intensity=i, outcome_bin=BINS[q % 5])
            for f in FAMILIES for i in (1, 3) for q in range(40) for s in range(3)]


def test_sampling_is_order_invariant_and_deduplicates_questions():
    rows = frame()
    selected = select_cases(rows)
    random.Random(7).shuffle(rows)
    assert select_cases(rows) == selected
    assert len(selected) == len({r['query_id'] for r in selected}) == 100
    assert list(Counter((r['family'], r['intensity']) for r in selected).values()) == [25] * 4
    for f in FAMILIES:
        for i in (1, 3):
            assert Counter(r['outcome_bin'] for r in selected if (r['family'], r['intensity']) == (f, i)) == dict.fromkeys(BINS, 5)


def test_sparse_outcomes_are_redistributed_without_fabricating_cases():
    rows = frame()
    for r in rows:
        r['outcome_bin'] = BINS[0]
    selected = select_cases(rows)
    assert len(selected) == 100
    assert {r['outcome_bin'] for r in selected} == {BINS[0]}


def test_insufficient_unique_questions_fails():
    rows = frame()
    for r in rows:
        r['query_id'] = 'one-question'
    with pytest.raises(ValueError, match='Insufficient unique'):
        select_cases(rows)


def test_rejects_modified_artifact(tmp_path):
    path = tmp_path / 'sealed.json'
    path.write_text('{}')
    with pytest.raises(ValueError, match='hash mismatch'):
        read(path, '0' * 64)
