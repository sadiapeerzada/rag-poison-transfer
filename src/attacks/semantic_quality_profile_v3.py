"""Standalone opt-in construction API; frozen registries/runners stay unchanged."""
from dataclasses import asdict
from pathlib import Path
import hashlib
import random

from src.attacks.semantic_fluent import SemanticQualityError
from src.attacks.semantic_quality_v3 import PROFILE, PROMPT, VALIDATOR, RETRY, SemanticQualityV3Attack
from src.attacks.semantic_quality_targets_v3 import METHOD, digest, select_target

ROOT = Path(__file__).resolve().parents[2]
FILES = ('src/attacks/semantic_quality_v3.py', 'src/attacks/semantic_quality_targets_v3.py',
         'src/attacks/semantic_quality_profile_v3.py', 'configs/twowiki_semantic_quality_v3_development.json',
         'src/attacks/semantic_fluent.py', 'src/attacks/base.py', 'src/pipelines/generator.py',
         'src/evaluation/metrics.py', 'src/attacks/development_targets_v5.py',
         'src/attacks/development_targets_v4.py', 'src/attacks/development_targets_v3.py',
         'src/attacks/development_targets_v2.py', 'src/attacks/target_candidates.py',
         'src/attacks/reviewed_target_artifact.py', 'src/attacks/development_review_package.py')


def descriptor(*, scope):
    if scope != 'development':
        raise ValueError('This profile refuses held-out use')
    return {'identifier': PROFILE, 'scope': scope, 'prompt': PROMPT, 'validator': VALIDATOR,
            'retry': RETRY, 'target_method': METHOD, 'max_attempts': 2, 'max_tokens': 150,
            'temperature': 0.0, 'sampler': 'explicit greedy', 'seed': 42,
            'duplicate_policy': 'retain_and_report_not_independent_corroboration',
            'implementation_sha256': {f: hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in FILES}}


def validate_profile(value, *, scope):
    if value != descriptor(scope=scope):
        raise ValueError('Version/configuration/source pin mismatch')


def construct(query, candidates, corpus, trusted_hashes, generator, *, profile, scope,
              intensity, set_runtime_seed):
    """All-or-none construction only. Never evaluates QA or changes metrics.

    Explicit seed callback must seed the real backend in a separately authorized
    pilot. An attested configuration cannot prove numerical reproducibility.
    """
    validate_profile(profile, scope=scope)
    if type(intensity) is not int or intensity not in (1, 3):
        raise ValueError('Declared development intensities are 1 and 3')
    target, selection = select_target(query, candidates, corpus, trusted_hashes, scope=scope, seed=42)
    record = {'query_id': query['query_id'], 'profile_sha256': digest(profile),
              'query_sha256': digest(query), 'target': target, 'selection': selection,
              'intensity': intensity, 'documents': [], 'partial_documents': [], 'attempt_records': [],
              'is_prospective_evidence': False}
    if target is None:
        return {**record, 'status': 'target_construction_failed'}
    if getattr(generator, 'model_provenance', {}).get('decoding') != {'sampler': 'explicit greedy', 'temperature': 0.0}:
        raise ValueError('Explicit greedy backend configuration attestation required')
    attack = SemanticQualityV3Attack(generator, scope=scope)
    documents = []
    for index in range(intensity):
        runtime_seed = int(digest([PROFILE, 42, query['query_id'], index])[:16], 16) % (2**32)
        set_runtime_seed(runtime_seed)
        try:
            documents.append(asdict(attack.generate(query, [query], random.Random(runtime_seed), index, target)))
        except SemanticQualityError:
            pass  # Scientific failure: no replacement target, no extra retry budget.
        except Exception as exc:
            # Infrastructure errors remain errors; expose the complete log for archival.
            for attempt in attack.attempt_log.get((query['query_id'], index), []):
                attempt['runtime_seed'] = runtime_seed
                attempt['profile_sha256'] = digest(profile)
            exc.semantic_attempt_records = attack.export_attempt_records()
            raise
        for attempt in attack.attempt_log[(query['query_id'], index)]:
            attempt['runtime_seed'] = runtime_seed
            attempt['profile_sha256'] = digest(profile)
    record['attempt_records'] = attack.export_attempt_records()
    normalized = [' '.join(d['text'].strip().removesuffix('.').casefold().split()) for d in documents]
    record['document_diversity'] = {'successful_slots': len(documents), 'unique_normalized_texts': len(set(normalized)),
                                    'duplicate_slots': len(normalized) - len(set(normalized)),
                                    'independent_corroboration_established': False}
    if len(documents) != intensity:
        return {**record, 'status': 'semantic_construction_failed', 'partial_documents': documents}
    return {**record, 'status': 'valid_construction', 'documents': documents}
