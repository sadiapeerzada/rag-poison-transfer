"""Development-only source-focus guard; legacy v2/v3 remain unchanged.

Abstain on demonstrated country-request/person-role conflicts. This does not
perform general NER, verify aliases, or establish factual falsehood.
"""
import hashlib
from pathlib import Path
import re
from src.attacks import development_targets_v2 as v2
from src.attacks import development_targets_v3 as v3

IDENTIFIER='development-source-focus-guard/v1'
METHOD_VERSION='answer-compatible-targets/development-method-v4-source-focus'
SCHEMA='rag-poison-transfer.development-target-method/v1'
ROOT=Path(__file__).resolve().parents[2]


def focus_conflict(query):
    # Country music singer/actor is a human request, so do not blacklist the
    # word 'country' or the label 'Dutch'. Detect the demonstrated request head.
    country_request=re.match(r'^\s*(?:what|which)\s+country\s+(?:the\b|is\b|was\b|does\b|did\b|has\b|had\b)',query['question'],re.I)
    return bool(country_request and v2.classify(query)[0]=='person')


def descriptor(identifier=IDENTIFIER):
    if identifier!=IDENTIFIER:raise ValueError('Unknown target method identifier')
    names=['src/attacks/development_targets_v4.py','src/attacks/development_targets_v3.py',
        'src/attacks/development_targets_v2.py','src/attacks/target_candidates.py']
    hashes={}
    for name in names:
        with (ROOT/name).open('rb') as stream:hashes[name]=hashlib.file_digest(stream,'sha256').hexdigest()
    return {'schema':SCHEMA,'identifier':IDENTIFIER,'method_version':METHOD_VERSION,
        'parent_method':v3.METHOD_VERSION,'scope':'development',
        'rule':'exclude country-request sources/destinations misclassified as person; do not infer country/demonym typing',
        'implementation_sha256':hashes}


def validate(value,scope):
    if scope!='development' or value!=descriptor():raise ValueError('Development-only target method version/source mismatch')


def nominate(query,development):
    excluded=[q['query_id'] for q in development if focus_conflict(q)]
    if focus_conflict(query):
        return {'eligible':False,'candidates':[],'method_family':METHOD_VERSION,
            'reason':'requested_country_conflicts_with_embedded_person_role','excluded_source_ids':sorted(excluded)}
    safe=[q for q in development if q['query_id'] not in set(excluded)]
    result=v3.nominate(query,safe,v2.build_pool(safe))
    return {**result,'target_method_version':METHOD_VERSION,'excluded_source_ids':sorted(excluded)}
