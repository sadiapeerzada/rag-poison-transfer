"""Opt-in development date-equivalence exclusion; no inferred entity aliases."""
from datetime import date
import hashlib
import re
import sys
from src.attacks import development_targets_v2 as v2, development_targets_v4 as v4

IDENTIFIER = 'development-source-focus-guard/v2'
METHOD_VERSION = 'answer-compatible-targets/development-method-v5-calendar-equivalence'


def calendar_key(value):
    """Only the two complete English date formats already admitted by v2."""
    if not isinstance(value, str) or not v2.calendar_date(value):
        return None
    value = value.strip().casefold()
    match = re.fullmatch(r'([a-z]+) (\d{1,2}), (\d{4})', value)
    if match:
        month, day, year = match.groups()
    else:
        day, month, year = value.split()
    return date(int(year), v2.MONTHS[month], int(day)).isoformat()


def date_equivalent_to_gold(query, target):
    key = calendar_key(target)
    return key is not None and key in {calendar_key(x) for x in
        [query['gold_answer'], *query.get('gold_aliases', [])]}


def descriptor(identifier=IDENTIFIER):
    if identifier != IDENTIFIER:
        raise ValueError('Unknown target method identifier')
    parent = v4.descriptor()
    hashes = dict(parent['implementation_sha256'])
    path = v4.ROOT / 'src/attacks/development_targets_v5.py'
    hashes['src/attacks/development_targets_v5.py'] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {**parent, 'identifier': IDENTIFIER, 'method_version': METHOD_VERSION,
        'parent_method': v4.METHOD_VERSION,
        'rule': parent['rule'] + '; exclude equivalent complete English calendar dates from gold and supplied aliases',
        'implementation_sha256': hashes}


def validate(value, scope):
    if scope != 'development' or value != descriptor():
        raise ValueError('Development-only target method version/source mismatch')


def nominate(query, development):
    result = v4.nominate(query, development)
    candidates = [r for r in result['candidates'] if not date_equivalent_to_gold(query, r['answer'])]
    return {**result, 'candidates': candidates, 'eligible': bool(candidates),
        'target_method_version': METHOD_VERSION,
        'reason': result['reason'] if candidates or not result['candidates'] else 'calendar_equivalent_gold_or_alias'}


def method_module(identifier):
    """Keep the frozen v1 implementation untouched; reject unknown identifiers."""
    if identifier == v4.IDENTIFIER:
        return v4
    if identifier == IDENTIFIER:
        return sys.modules[__name__]
    raise ValueError('Unknown target method identifier')
