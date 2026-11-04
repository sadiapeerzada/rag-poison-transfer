"""Evidence/review-gated development selection. No inferred NER or new nominees.

Callers supply candidates and reviewed, hash-bound evidence packets. A hash binds
bytes, not truth or reviewer identity. Unknown evidence always means abstention.
"""
import hashlib
import json
from datetime import datetime
from src.attacks.development_targets_v5 import calendar_key
from src.attacks.semantic_quality_v3 import relation
from src.evaluation.metrics import normalize_answer

METHOD = 'twowiki-evidence-gated-targets/v3-development'
CHECKS = ('referent_identity', 'entity_type_and_role', 'aliases_complete',
          'corpus_relative_contradiction', 'chronological_plausibility', 'geographic_granularity')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _abstain(reason):
    return {'eligible': False, 'reason': reason, 'method': METHOD,
            'corpus_relative_contradiction': 'unverified', 'plausibility': 'unverified',
            'independent_reviewer_approval': 'not_established'}


def assess_candidate(query, target, packet, corpus, trusted_hashes, *, scope):
    """Require an externally pinned corpus and a human review bound to all facts.

    Typed facts are manual evidence annotations, not automatic semantic findings.
    The reviewer must validate their support in the exact cited spans.
    """
    if scope != 'development':
        raise ValueError('Target method is development-only')
    if not isinstance(packet, dict):
        return _abstain('evidence_packet_missing')
    payload = packet.get('payload', {})
    if not isinstance(payload, dict):
        return _abstain('invalid_evidence_payload')
    if payload.get('query_sha256') != digest(query) or payload.get('target') != target:
        return _abstain('query_target_binding_mismatch')
    plan = relation(query['question'], target)
    if plan is None:
        return _abstain('unsupported_relation_or_target_shape')
    aliases = query.get('gold_aliases', [])
    if not isinstance(aliases, list) or any(not isinstance(x, str) or not x.strip() for x in aliases):
        return _abstain('invalid_aliases')
    golds = [query['gold_answer'], *aliases]
    if any(normalize_answer(target) == normalize_answer(g) or
           (calendar_key(target) is not None and calendar_key(target) == calendar_key(g)) for g in golds):
        return _abstain('gold_or_alias_equivalent_target')
    refs = payload.get('evidence', [])
    if not isinstance(refs, list) or not refs:
        return _abstain('evidence_missing')
    docs = {d['doc_id']: d['text'] for d in corpus}
    if len(docs) != len(corpus):
        return _abstain('duplicate_corpus_ids')
    for ref in refs:
        if not isinstance(ref, dict):
            return _abstain('invalid_evidence_reference')
        doc_id = ref.get('doc_id'); text = docs.get(doc_id)
        if text is None or trusted_hashes.get(doc_id) != hashlib.sha256(text.encode()).hexdigest():
            return _abstain('untrusted_source_bytes')
        start, end = ref.get('start'), ref.get('end')
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text) or text[start:end] != ref.get('quote'):
            return _abstain('evidence_span_mismatch')
    # Relation, aliases and identity need actual pinned gold support, not unrelated sources.
    if not set(query.get('gold_doc_ids', [])) or not set(query['gold_doc_ids']) <= {r['doc_id'] for r in refs}:
        return _abstain('gold_support_not_cited')
    facts = payload.get('facts', {})
    required = {'relation_kind', 'referent', 'referent_type', 'target_type', 'gold_aliases', 'corpus_gold_answer'}
    if plan.answer_type == 'place':
        required |= {'gold_granularity', 'target_granularity'}
    if plan.kind == 'kinship':
        required |= {'compatible_roles', 'target_birth', 'referent_birth', 'target_death'}
    if plan.kind in ('birth_date', 'death_date'):
        required |= {'referent_birth', 'referent_death'}
    if not isinstance(facts, dict) or not required <= facts.keys():
        return _abstain('typed_facts_incomplete')
    citations = payload.get('fact_citations', {})
    if not isinstance(citations, dict) or any(not isinstance(citations.get(k), list) or not citations[k] or
            any(type(n) is not int or not 0 <= n < len(refs) for n in citations[k]) for k in required):
        return _abstain('typed_fact_citations_missing')
    if facts['relation_kind'] != plan.kind or facts['referent'] != plan.subject:
        return _abstain('role_or_subject_mismatch')
    if facts['target_type'] != plan.answer_type:
        return _abstain('incompatible_target_type')
    expected_referent = 'film' if plan.kind == 'comparison_film' else 'pair' if plan.kind.startswith('boolean') else 'person'
    if facts['referent_type'] != expected_referent:
        return _abstain('incompatible_referent_type')
    if facts['gold_aliases'] != golds or facts['corpus_gold_answer'] != query['gold_answer']:
        return _abstain('alias_or_corpus_gold_binding_mismatch')
    if plan.kind.startswith('comparison') and not any(normalize_answer(plan.other) == normalize_answer(g) for g in golds):
        return _abstain('comparison_gold_not_other_operand')
    if plan.answer_type == 'place' and (facts['gold_granularity'] not in ('city', 'county', 'region', 'country') or
            facts['target_granularity'] != facts['gold_granularity']):
        return _abstain('geographic_granularity_mismatch')
    if plan.kind in ('kinship', 'birth_date', 'death_date'):
        fields = ('target_birth', 'referent_birth', 'target_death') if plan.kind == 'kinship' else ('referent_birth', 'referent_death')
        dates = {k: calendar_key(facts[k]) for k in fields}
        if any(x is None for x in dates.values()):
            return _abstain('chronology_evidence_incomplete')
        if plan.kind == 'kinship':
            if not isinstance(facts['compatible_roles'], list) or plan.role not in facts['compatible_roles']:
                return _abstain('incompatible_family_role')
            if not dates['target_birth'] < dates['referent_birth'] or not dates['target_birth'] < dates['target_death']:
                return _abstain('kinship_chronology_incompatible')
            # Bounded plausibility screen, not a genealogy inference.
            age_gap = int(dates['referent_birth'][:4]) - int(dates['target_birth'][:4])
            if not 12 <= age_gap <= (120 if 'grand' in plan.role else 100):
                return _abstain('kinship_age_gap_outside_development_bounds')
        elif dates['referent_birth'] > dates['referent_death']:
            return _abstain('contradictory_life_dates')
        elif plan.kind == 'death_date' and not dates['referent_birth'] <= calendar_key(target):
            return _abstain('death_precedes_documented_birth')
        elif plan.kind == 'birth_date' and not calendar_key(target) <= dates['referent_death']:
            return _abstain('birth_follows_documented_death')
        elif plan.kind != 'kinship':
            birth = calendar_key(target) if plan.kind == 'birth_date' else dates['referent_birth']
            death = calendar_key(target) if plan.kind == 'death_date' else dates['referent_death']
            if not 0 <= int(death[:4]) - int(birth[:4]) <= 120:
                return _abstain('lifespan_outside_development_bounds')
    review = packet.get('review', {})
    if not isinstance(review, dict) or review.get('payload_sha256') != digest(payload):
        return _abstain('review_binding_missing_or_mismatched')
    reviewer, nominator = review.get('reviewer_id'), payload.get('nominator_id')
    if review.get('reviewer_type') != 'human' or not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(nominator, str) or not nominator.strip() or reviewer.strip().casefold() == nominator.strip().casefold():
        return _abstain('independent_human_reviewer_required')
    try:
        timestamp = datetime.fromisoformat(review.get('reviewed_at', '').replace('Z', '+00:00'))
        if timestamp.utcoffset() is None:
            raise ValueError('timezone required')
    except (ValueError, TypeError):
        return _abstain('invalid_review_timestamp')
    if (review.get('decision') != 'approve' or not isinstance(review.get('checks'), dict)
            or set(review['checks']) != set(CHECKS)
            or any(type(review['checks'][k]) is not bool or not review['checks'][k] for k in CHECKS)):
        return _abstain('review_rejected_uncertain_or_incomplete')
    if not isinstance(review.get('notes'), str) or len(review['notes'].strip()) < 30:
        return _abstain('review_justification_missing')
    return {'eligible': True, 'reason': 'bound_human_review_record_approved', 'method': METHOD,
            'corpus_relative_contradiction': 'human_reviewed_corpus_relative',
            'plausibility': 'bounded_checks_and_human_review',
            'independent_reviewer_approval': 'record_approved_identity_not_authenticated',
            'packet_sha256': digest(packet)}


def select_target(query, candidates, corpus, trusted_hashes, *, scope, seed=42):
    """Select once before generation; no replacement after output failure."""
    if scope != 'development':
        raise ValueError('Target selection is development-only')
    decisions = []
    seen = set()
    for candidate in candidates:
        target = candidate.get('target')
        if not isinstance(target, str) or not target.strip() or target in seen:
            return None, {'method': METHOD, 'reason': 'invalid_or_duplicate_candidate', 'decisions': decisions}
        seen.add(target)
        verdict = assess_candidate(query, target, candidate.get('packet'), corpus, trusted_hashes, scope=scope)
        decisions.append({'target': target, **verdict})
    eligible = [d for d in decisions if d['eligible']]
    selected = min(eligible, key=lambda d: (digest([METHOD, seed, query['query_id'], d['target']]), d['target'])) if eligible else None
    return (selected['target'] if selected else None), {'method': METHOD, 'reason': 'selected' if selected else 'no_independently_supported_candidate', 'decisions': decisions}
