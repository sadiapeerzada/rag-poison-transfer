"""Metadata-only prospective selection and independent review handoffs.

No model loading. Certification is an externally pinned custodian attestation,
not something this module can infer from the presence of local files.
"""
from datetime import datetime
import hashlib
import json
from pathlib import Path
from src.attacks.semantic_quality_targets_v3 import digest

RULE = 'twowiki-semantic-quality-v3-prospective/v1'
CATEGORIES = {'audit', 'historical_pilot', 'regression', 'target_review', 'other_exposure', 'heldout_ids'}


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_pinned(reference):
    path = Path(reference['path'])
    if path.is_symlink() or file_sha(path) != reference['sha256']:
        raise ValueError('Artifact fingerprint mismatch')
    return json.loads(path.read_text())


def ids_only(value):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value) or len(set(value)) != len(value):
        raise ValueError('Expected unique query IDs only; content is forbidden')
    return value


def build_registry(sources, historical_gaps):
    """Each source supplies an ids-only export plus original source provenance.

    Held-out sources must be independently exported metadata, never raw content.
    Source declarations are preserved verbatim and hash-bound by certification.
    """
    records = []
    union = set()
    for source in sources:
        if source.get('category') not in CATEGORIES or not source.get('provenance') or not source.get('original_sha256'):
            raise ValueError('Source category, provenance and original fingerprint required')
        ids = ids_only(read_pinned(source['ids_export']))
        records.append({**source, 'query_ids': ids})
        union.update(ids)
    return {'schema': RULE+'/exposure-registry', 'source_records': records,
            'excluded_query_ids': sorted(union), 'historical_gaps': list(historical_gaps),
            'certification': None, 'status': 'incomplete_not_certified'}


def verify_registry(registry):
    ids_only(registry['excluded_query_ids'])
    records = registry['source_records']
    if {x['category'] for x in records} != CATEGORIES:
        raise ValueError('Exposure source classes incomplete')
    if registry.get('historical_gaps'):
        raise ValueError('Historical exposure is unresolved; selection stopped')
    if set(registry['excluded_query_ids']) != {q for r in records for q in ids_only(r['query_ids'])}:
        raise ValueError('Registry union mismatch')
    cert = registry.get('certification')
    unsigned = {k:v for k,v in registry.items() if k not in ('certification', 'status')}
    if (not isinstance(cert, dict) or cert.get('registry_payload_sha256') != digest(unsigned)
            or cert.get('historical_inventory_complete') is not True
            or cert.get('heldout_metadata_only') is not True
            or not cert.get('custodian_id') or not cert.get('evidence_notes')):
        raise ValueError('Complete custodian certification required')
    timestamp = datetime.fromisoformat(cert['certified_at'].replace('Z', '+00:00'))
    if timestamp.utcoffset() is None:
        raise ValueError('Certification needs a timezone')
    return set(registry['excluded_query_ids'])


def select_cohort(pool_ids, registry, *, dataset_sha256):
    """Call only with a pinned metadata-only development ID pool, before content."""
    pool = ids_only(pool_ids)
    excluded = verify_registry(registry)
    if not isinstance(dataset_sha256, str) or len(dataset_sha256) != 64:
        raise ValueError('Pin the development dataset before selection')
    eligible = set(pool) - excluded
    if len(eligible) < 25:
        raise ValueError('Fewer than 25 unexposed development IDs; no replacement rule')
    chosen = sorted(eligible, key=lambda q:(digest([RULE,42,q]),q))[:25]
    return {'schema': RULE+'/cohort', 'scope':'development', 'query_ids':chosen,
            'selection_rule':RULE, 'selection_seed':42, 'query_count':25,
            'registry_sha256':digest(registry), 'pool_ids_sha256':digest(pool),
            'dataset_sha256':dataset_sha256, 'status':'ordered_ids_frozen_before_content'}


def target_review_form(query):
    """Blank handoff, not a candidate or approval. Content only after cohort freeze."""
    return {'query_id':query['query_id'], 'query_sha256':digest(query),
            'question':query['question'], 'gold_answer':query['gold_answer'],
            'gold_aliases':query.get('gold_aliases',[]), 'exact_relation':None,
            'candidates':[], 'abstention_reason':None, 'nominator_id':None,
            'reviewer_id':None, 'decision':None, 'uncertainty':None,
            'role_type_compatibility':None, 'corpus_relative_contradiction':None,
            'chronological_plausibility':None, 'geographic_plausibility':None}


def blinded_forms(attempts, *, seed=42):
    """Heuristic labels, slots, retry order and QA fields stay in private mapping."""
    public = []; private = []
    for index, attempt in enumerate(attempts):
        blind_id = digest([RULE,'blinded-semantic-review',seed,index,attempt['query_id'],attempt['text']])
        public.append({'blind_id':blind_id, 'query_id':attempt['query_id'],
                       'question':attempt['question'], 'target':attempt['target'],
                       'gold_answer':attempt.get('gold_answer'), 'gold_aliases':attempt.get('gold_aliases',[]),
                       'text':attempt['text'], 'evidence':attempt.get('evidence',[]),
                       'reviewer_id':None, 'exact_relation':None, 'target_support':None,
                       'contradiction':None, 'plausibility':None, 'malformed':None,
                       'duplicates':None, 'decision':None, 'uncertainty':None, 'notes':None})
        private.append({'blind_id':blind_id,'original_index':index})
    return sorted(public,key=lambda x:x['blind_id']), private


def prepare_target_forms(handoff):
    """Verify the ID freeze before reading any development content."""
    registry=read_pinned(handoff['registry']);pool=read_pinned(handoff['pool_ids'])
    cohort=read_pinned(handoff['cohort']);receipt=read_pinned(handoff['cohort_receipt'])
    if cohort!=select_cohort(pool,registry,dataset_sha256=handoff['data']['sha256']):
        raise ValueError('Cohort selection mismatch; content access stopped')
    expected={k:handoff[k]['sha256'] for k in ('cohort','registry','pool_ids','data')}
    if receipt.get('schema')!='semantic-v3-pre-content-freeze-receipt/v1' or receipt.get('selector_source_sha256')!=file_sha(__file__):
        raise ValueError('Pre-content receipt selector provenance mismatch')
    if receipt.get('input_sha256')!=expected:raise ValueError('Pre-content receipt mismatch')
    frozen_at=datetime.fromisoformat(receipt['frozen_at'].replace('Z','+00:00'))
    if frozen_at.utcoffset() is None:raise ValueError('Timezone required')
    # The first content read occurs only after pinned selection/certification checks.
    data=read_pinned(handoff['data'])
    if data.get('scope')!='development' or data.get('dataset',{}).get('split')!='train':
        raise ValueError('Only train-development content allowed')
    by_id={q['query_id']:q for q in data['queries']}
    if len(by_id)!=len(data['queries']):raise ValueError('Duplicate content IDs')
    return [{**target_review_form(by_id[q]),'review_state':'pending',
             'cohort_receipt_sha256':handoff['cohort_receipt']['sha256']} for q in cohort['query_ids']]
