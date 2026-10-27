"""Versioned semantic profiles. Legacy protocols remain valid without this field."""
import hashlib
from pathlib import Path
from src.attacks.semantic_fluent import (
    SemanticFluentFalseEvidenceAttack, SEMANTIC_PROMPT_VERSION,
    SEMANTIC_VALIDATION_VERSION, SEMANTIC_RETRY_POLICY,
)
from src.attacks.semantic_fluent_development import (
    DevelopmentSemanticFluentAttack, DEVELOPMENT_PROMPT_VERSION,
    DEVELOPMENT_VALIDATION_VERSION, DEVELOPMENT_RETRY_POLICY,
)

LEGACY = 'legacy-v3-v4/v1'
DEVELOPMENT = 'question-anchored-development/v1'
DEVELOPMENT_V2 = 'question-anchored-development/v2'
DEVELOPMENT_IDENTIFIERS = (DEVELOPMENT, DEVELOPMENT_V2)
IDENTIFIERS = (LEGACY, *DEVELOPMENT_IDENTIFIERS)
SCHEMA = 'rag-poison-transfer.semantic-profile/v1'
ROOT = Path(__file__).resolve().parents[2]


def descriptor(identifier, scope):
    if identifier not in IDENTIFIERS:raise ValueError('Unknown semantic profile identifier')
    if scope not in ('development','heldout'):raise ValueError('Unknown profile scope')
    if identifier in DEVELOPMENT_IDENTIFIERS and scope!='development':raise ValueError('Semantic profile is development-only; held-out use requires a separate preregistration')
    development=identifier in DEVELOPMENT_IDENTIFIERS
    prompt, validation, retry = DEVELOPMENT_PROMPT_VERSION, DEVELOPMENT_VALIDATION_VERSION, DEVELOPMENT_RETRY_POLICY
    if identifier==DEVELOPMENT_V2:
        from src.attacks.semantic_fluent_development_v2 import PROMPT_VERSION, VALIDATION_VERSION, RETRY_POLICY
        prompt, validation, retry = PROMPT_VERSION, VALIDATION_VERSION, RETRY_POLICY
    files=['src/attacks/semantic_fluent.py','src/attacks/semantic_profiles.py']
    if development:files.append('src/attacks/semantic_fluent_development.py')
    if identifier==DEVELOPMENT_V2:
        files.extend(['src/attacks/semantic_fluent_development_v2.py','src/attacks/development_targets_v5.py',
            'src/attacks/development_targets_v4.py','src/attacks/development_targets_v3.py',
            'src/attacks/development_targets_v2.py','src/attacks/target_candidates.py'])
    hashes={}
    for name in files:
        with (ROOT/name).open('rb') as stream:hashes[name]=hashlib.file_digest(stream,'sha256').hexdigest()
    return {'schema':SCHEMA,'identifier':identifier,
        'prompt_version':prompt if development else SEMANTIC_PROMPT_VERSION,
        'validation_version':validation if development else SEMANTIC_VALIDATION_VERSION,
        'retry_policy':retry if development else SEMANTIC_RETRY_POLICY,
        'max_attempts':2,'max_tokens':150,
        'format':'single-question-anchored-sentence' if development else 'legacy-encyclopedic-paragraph',
        'permitted_scopes':['development'] if development else ['development','heldout'],
        'implementation_sha256':hashes}


def validate(value,scope):
    if not isinstance(value,dict) or value!=descriptor(value.get('identifier'),scope):
        raise ValueError('Semantic profile version/configuration/implementation mismatch')
    return value


def attack(generator,value=None,scope=None):
    if value is None:return SemanticFluentFalseEvidenceAttack(generator,max_tokens=150,max_attempts=2)
    validate(value,scope)
    if value['identifier']==DEVELOPMENT_V2:
        from src.attacks.semantic_fluent_development_v2 import DevelopmentSemanticFluentAttackV2
        return DevelopmentSemanticFluentAttackV2(generator,scope=scope,max_tokens=value['max_tokens'],max_attempts=value['max_attempts'])
    if value['identifier']==DEVELOPMENT:
        return DevelopmentSemanticFluentAttack(generator,scope=scope,max_tokens=value['max_tokens'],max_attempts=value['max_attempts'])
    return SemanticFluentFalseEvidenceAttack(generator,max_tokens=value['max_tokens'],max_attempts=value['max_attempts'])
