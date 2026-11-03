"""Development-only typed source-control regression suite. Synthetic fixtures."""
import hashlib
import pytest

from src.attacks.semantic_typed_evidence_v4_1 import bind_typed_sources
from src.attacks.semantic_template_control_v4_1 import (
    prepare_template_control, template_forms, validate_template_statement,
    review_metadata_status, PROFILE,
)
from src.attacks.semantic_document_diversity_v3 import audit_documents


CASES = [
    (
        'Do both films: Yes, Giorgio and Jack Reacher: Never Go Back have the directors from the same country?',
        'yes', 'no',
        [
            ('yes,_giorgio', 'Yes, Giorgio is a musical film directed by Franklin J. Schaffner, starring actors.'),
            ('franklin_schaffner', 'Franklin James Schaffner (1900) was an American film director.'),
            ('jack_reacher', 'Jack Reacher: Never Go Back is a thriller film directed by Edward Zwick and written by others.'),
            ('edward_zwick', 'Edward M. Zwick (born 1952) is an American filmmaker.'),
        ],
    ),
    (
        'Do both directors of films The White Adventure and Valley Girl (1983 film) share the same nationality?',
        'no', 'yes',
        [
            ('white_adventure', 'The White Adventure is a crime film directed by Arthur Maria Rabenalt and starring actors.'),
            ('rabenalt', 'Arthur Maria Rabenalt (1900) was an Austrian film director.'),
            ('valley_girl', 'Valley Girl is a romance film directed by Martha Coolidge and starring actors.'),
            ('coolidge', 'Martha Coolidge (born 1946) is an American film director.'),
        ],
    ),
    (
        'Where was the place of death of the director of film General John Regan (1933 Film)?',
        'Chobham, Surrey', 'Avignon',
        [
            ('general_john_regan', 'General John Regan is a 1933 comedy film directed by Henry Edwards and starring Chrissie White.'),
            ('henry_edwards', 'Henry Edwards (1882–1952) was an English actor and director. He co-starred with Chrissie White and died in Chobham, Surrey.'),
        ],
    ),
    (
        'Where was the director of film The Idiot Returns born?',
        'Prague', 'Avignon',
        [
            ('idiot_returns', 'The Idiot Returns is a Czech film directed by Saša Gedeon.'),
            ('sasa_gedeon', 'Saša Gedeon (born 29 August 1970 in Prague) is a Czech director.'),
        ],
    ),
    (
        'Where was the place of death of the director of film The Silk Express?',
        'Hollywood', 'Avignon',
        [
            ('silk_express', 'The Silk Express is a drama film directed by Ray Enright and written by others.'),
            ('ray_enright', 'Ray Enright (1896–1965) was an American director. Enright died in Hollywood, California.'),
        ],
    ),
]


def case(i):
    question, gold, target, sources = CASES[i]
    docs = [{'doc_id': key, 'text': text} for key, text in sources]
    q = {'query_id': f'synthetic-{i}', 'question': question, 'gold_answer': gold,
         'gold_aliases': [], 'gold_doc_ids': [r['doc_id'] for r in docs]}
    pins = {r['doc_id']: hashlib.sha256(r['text'].encode()).hexdigest() for r in docs}
    return q, target, docs, pins


@pytest.mark.parametrize('i', range(5))
def test_five_typed_source_bindings_and_three_templates(i):
    q, target, docs, pins = case(i)
    binding = bind_typed_sources(q, docs, pins)
    assert binding['status'] == 'source_text_compatible_unverified'
    assert binding['construction_eligible'] is False
    assert binding['injection_approved'] is False
    record = prepare_template_control(q, target, binding)
    assert len(record['diagnostic_templates']) == 3
    assert record['surface_diversity']['unique_normalized_texts'] == 3
    assert record['surface_diversity']['semantic_independence_verified'] is False
    assert record['factual_approval'] is False
    assert record['review_metadata_status'] == 'missing_metadata'
    assert record['profile'] == PROFILE
    for slot, doc in enumerate(record['diagnostic_templates']):
        assert validate_template_statement(q, target, slot, doc['text'])


def test_c05_third_form_corrected_to_directors_not_filmmakers():
    q, target, *_ = case(1)
    sentence = template_forms(q, target)[2]
    assert sentence.startswith('Yes, the directors of')
    assert 'filmmakers behind' not in sentence


def test_quoted_yes_giorgio_is_title_not_boolean():
    q, target, *_ = case(0)
    forms = template_forms(q, target)
    assert all('"Yes, Giorgio"' in sentence for sentence in forms)
    assert all(sentence.startswith('No,') for sentence in forms)


def test_wrong_director_rejected_even_when_reshashed():
    q, target, docs, pins = case(1)
    docs[0]['text'] = docs[0]['text'].replace('Arthur Maria Rabenalt', 'Different Director')
    pins[docs[0]['doc_id']] = hashlib.sha256(docs[0]['text'].encode()).hexdigest()
    with pytest.raises(ValueError, match='Director identity'):
        bind_typed_sources(q, docs, pins)


def test_source_hash_substitution_rejected():
    q, target, docs, pins = case(3)
    docs[1]['text'] += ' Added evidence.'
    with pytest.raises(ValueError, match='hash mismatch'):
        bind_typed_sources(q, docs, pins)


def test_unmatched_gold_source_ids_rejected():
    q, target, docs, pins = case(4)
    q['gold_doc_ids'][0] = 'wrong_slug'
    with pytest.raises(ValueError, match='identities mismatch'):
        bind_typed_sources(q, docs, pins)


def test_wrong_title_rejected():
    q, target, docs, pins = case(4)
    q['question'] = q['question'].replace('The Silk Express', 'A Different Film')
    with pytest.raises(ValueError, match='Film title'):
        bind_typed_sources(q, docs, pins)


def test_ambiguous_henry_edwards_requires_corroboration():
    q, target, docs, pins = case(2)
    docs[1]['text'] = docs[1]['text'].replace('Chrissie White', 'a colleague')
    pins[docs[1]['doc_id']] = hashlib.sha256(docs[1]['text'].encode()).hexdigest()
    with pytest.raises(ValueError, match='co-star'):
        bind_typed_sources(q, docs, pins)


def test_negation_or_title_drift_not_accepted():
    q, target, docs, pins = case(3)
    sentence = template_forms(q, target)[0]
    with pytest.raises(ValueError, match='pinned relation'):
        validate_template_statement(q, target, 0, sentence.replace('was born', 'was not born'))
    with pytest.raises(ValueError, match='pinned relation'):
        validate_template_statement(q, target, 0, sentence.replace('The Idiot Returns', 'Another Film'))
    with pytest.raises(ValueError, match='pinned relation'):
        validate_template_statement(q, target, 1, sentence)


def test_duplicate_templates_not_distinct():
    q, target, *_ = case(1)
    sentence = template_forms(q, target)[0]
    docs = [{'doc_id': str(i), 'text': sentence + ('.' if i else '')} for i in range(3)]
    diversity = audit_documents(docs, 3)
    assert diversity['construction_eligible'] is False
    assert diversity['unique_normalized_texts'] == 1


@pytest.mark.parametrize('qtext', [
    'Which film whose director was born first, A or B?',
    'Who is younger, A or B?',
    "When did Jane Smith's father die?",
    'Are Town A, Town B and Town C both located in the same country?',
])
def test_unsupported_forms_abstain(qtext):
    q = {'question': qtext, 'gold_answer': 'no'}
    assert template_forms(q, 'yes') == []


def test_review_metadata_missing_never_approved():
    assert review_metadata_status({'reviewer_model_id': 'Claude', 'run_id': None, 'timestamp': None}) == 'incomplete_provenance'
    assert review_metadata_status({'reviewer_model_id': 'Claude', 'run_id': 'x', 'timestamp': '2026-11-03'}) == 'invalid_timestamp'
    assert review_metadata_status({'reviewer_model_id': 'Claude', 'run_id': 'x', 'timestamp': '2026-11-03T13:00:00+00:00'}) == 'self_reported_metadata_only'
    q, target, docs, pins = case(3)
    result = prepare_template_control(q, target, bind_typed_sources(q, docs, pins),
                                      {'reviewer_model_id': 'Claude', 'run_id': 'x', 'timestamp': '2026-11-03T13:00:00+00:00'})
    assert result['review_identity_authenticated'] is False
    assert result['construction_eligible'] is False
    assert result['injection_approved'] is False


def test_refuses_heldout_everywhere():
    q, target, docs, pins = case(3)
    with pytest.raises(ValueError, match='held-out'):
        bind_typed_sources(q, docs, pins, scope='heldout')
    binding = bind_typed_sources(q, docs, pins)
    with pytest.raises(ValueError, match='held-out'):
        prepare_template_control(q, target, binding, scope='heldout')


def test_gold_alias_cannot_be_target():
    q, target, docs, pins = case(3)
    q['gold_aliases'] = [target]
    binding = bind_typed_sources(q, docs, pins)
    with pytest.raises(ValueError, match='alias'):
        prepare_template_control(q, target, binding)
