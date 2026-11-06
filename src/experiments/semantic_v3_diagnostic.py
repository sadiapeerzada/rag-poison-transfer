"""Admission for a separately reviewed, exposed-material construction diagnostic.

No prospective selector/certificate is reused or relaxed. Hashes bind bytes;
external human identity, factual review and signature authenticity need custody.
"""
from datetime import datetime
from pathlib import Path
import re
from src.attacks.semantic_quality_targets_v3 import digest
from src.experiments.semantic_v3_preparation import ids_only, read_pinned

RULE = 'twowiki-semantic-quality-v3-nonprospective-diagnostic/v1'
KIND = 'nonprospective-development-diagnostic'
# Exact original V2 development protocol, not a caller-selected population.
PARENT_SHA256 = '6ea932386b8ba4e3e544bed55ccb22ea991f589d1311fb138b6baa689557abf8'
REVIEW_ROLES = {'responsible_researcher', 'supervisor', 'inventory_reviewer',
                'target_review_custodian', 'semantic_review_custodian', 'resource_operator'}
ACKNOWLEDGMENTS = {'nonprospective_only', 'historical_exposure_unresolved',
                   'no_qa_or_heldout_evaluation', 'unchanged_semantic_method',
                   'all_25_no_replacement', 'independent_target_reviews_complete',
                   'all_attempt_blinded_review_planned', 'backup_restore_verified',
                   'resources_and_boundary_monitoring_limits_accepted'}

ACCEPTANCE_CRITERIA = {
    'operational_completion': 'sealed-50-records-with-intact-journal-and-no-unresolved-events',
    'reporting_scope': 'nonprospective-development-construction-only',
    'denominator_queries_per_intensity': 25,
    'semantic_review': 'two-independent-blinded-passes-all-saved-attempts-then-adjudication',
    'retain_abstentions_failures_partials_and_duplicates': True,
    'minimum_acceptance_rate': None,
    'extra_retries_or_replacement': False,
    'independent_confirmation': False,
    'automatic_300_query_authorization': False,
}


def _time(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.utcoffset() is None:
        raise ValueError('Dated human evidence requires timezone')
    return result


def admit_diagnostic(manifest, values):
    """All metadata is checked before the shared driver opens data/targets."""
    artifacts = manifest['artifacts']
    if (manifest.get('study_kind') != KIND or manifest.get('prospective_evidence') is not False
            or manifest.get('historical_exposure_risk_acknowledged') is not True):
        raise ValueError('Explicit nonprospective diagnostic disclosure required')
    if 'protocol' in values and values['protocol'].get('acceptance_criteria')!=ACCEPTANCE_CRITERIA:
        raise ValueError('Frozen diagnostic acceptance/reporting criteria mismatch')
    parent = values['historical_protocol']
    if (artifacts['historical_protocol']['sha256'] != PARENT_SHA256
            or parent.get('schema') != 'rag-poison-transfer.semantic-development-protocol/v2'
            or parent.get('development_study', {}).get('identifier') != 'semantic-quality-25/v1'
            or parent.get('binding', {}).get('scope') != 'development'
            or parent['binding'].get('complete_historical_nonoverlap_certified') is not False):
        raise ValueError('Exact historical development protocol required')
    ids = ids_only(parent['binding']['query_ids'])
    if len(ids) != 25:
        raise ValueError('Exactly 25 documented historical development queries required')
    cohort = values['cohort']
    expected = {'schema': RULE+'/cohort', 'scope': 'development', 'query_ids': ids,
                'query_count': 25, 'selection_rule': 'reuse-exact-documented-v2-order-no-replacement',
                'historical_protocol_sha256': PARENT_SHA256,
                'historical_data_sha256': parent['binding']['development_artifact_sha256'],
                'dataset_sha256': artifacts['data']['sha256'], 'prospective_evidence': False}
    if cohort != expected or values['pool_ids'] != ids:
        raise ValueError('Diagnostic population must equal the documented historical 25 in order')
    registry = values['registry']
    # Preserve the evidence of uncertainty; this design does not issue a certificate.
    if (not registry.get('historical_gaps') or registry.get('certification') is not None
            or not set(ids) <= set(registry.get('excluded_query_ids', []))):
        raise ValueError('Historical exposure uncertainty and known exposure must be retained')
    receipt = values['cohort_receipt']
    if (receipt.get('schema') != RULE+'/reuse-receipt'
            or receipt.get('pre_content_prospective_freeze') is not False
            or receipt.get('input_sha256') != {k: artifacts[k]['sha256'] for k in
                ('cohort', 'registry', 'pool_ids', 'data', 'historical_protocol')}):
        raise ValueError('Diagnostic reuse receipt mismatch')
    _time(receipt['frozen_at'])
    review = values['study_review']
    payload = {'input_sha256': {k: v['sha256'] for k, v in artifacts.items()
                               if k not in ('protocol', 'study_review')},
               'driver_implementation_sha256': manifest['driver_implementation_sha256'],
               'output_namespace': manifest['output_namespace'], 'study_kind': KIND}
    if (review.get('schema') != RULE+'/human-study-review'
            or review.get('review_payload_sha256') != digest(payload)
            or review.get('acknowledgments') != dict.fromkeys(ACKNOWLEDGMENTS, True)):
        raise PermissionError('Complete source/input/namespace-bound diagnostic human review required')
    signatures = review.get('signatures', [])
    if {r.get('role') for r in signatures} != REVIEW_ROLES or len(signatures) != len(REVIEW_ROLES):
        raise PermissionError('All accountable diagnostic review roles required')
    evidence_paths=set()
    artifact_paths={Path(r['path']) for r in artifacts.values()}
    for record in signatures:
        if not isinstance(record.get('signer_id'), str) or not record['signer_id'].strip():
            raise PermissionError('Actual human identity required')
        _time(record['signed_at'])
        evidence = record.get('signed_evidence')
        if (not isinstance(evidence,dict) or set(evidence)!={'path','sha256'}
                or not isinstance(evidence['sha256'],str)
                or not re.fullmatch('[0-9a-f]{64}',evidence['sha256'])):
            raise PermissionError('Externally retained signed evidence reference required')
        path=Path(evidence['path'])
        if (not path.is_absolute() or path.resolve()!=path or path.is_symlink()
                or path in artifact_paths or path in evidence_paths):
            raise PermissionError('Signed evidence must use separate canonical metadata paths')
        evidence_paths.add(path)
        signed = read_pinned(evidence)
        if (signed.get('signer_id') != record['signer_id'] or signed.get('role') != record['role']
                or signed.get('review_payload_sha256') != digest(payload)
                or signed.get('decision') != 'approve'):
            raise PermissionError('Signed human evidence does not bind the reviewed study')
    people = {r['role']: r['signer_id'].strip().casefold() for r in signatures}
    if people['supervisor'] == people['responsible_researcher']:
        raise PermissionError('Supervisor must be distinct from responsible researcher')
    if people['inventory_reviewer'] == people['responsible_researcher']:
        raise PermissionError('Independent inventory reviewer required')
    return cohort, receipt
