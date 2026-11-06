#!/usr/bin/env python3
"""Prepare/freeze the explicitly nonprospective historical-25 V3 diagnostic.

Preparation and freeze are offline. Only the explicit construct subcommand can
invoke the existing guarded driver, after actual externally pinned authorization.
"""
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import hashlib
import os
import tempfile
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.attacks.semantic_quality_profile_v3 import descriptor
from src.attacks.semantic_quality_targets_v3 import digest
from src.experiments.semantic_v3_checkpoint import publish_json
from src.experiments.semantic_v3_diagnostic import (RULE, KIND, PARENT_SHA256, REVIEW_ROLES,
                                                   ACKNOWLEDGMENTS, ACCEPTANCE_CRITERIA, admit_diagnostic)
from src.experiments.semantic_v3_preparation import file_sha, read_pinned, target_review_form
from src.experiments.semantic_v3_pilot import DATASET, implementation_pins, validate_content, preflight, run
from src.experiments.semantic_v3_mlx import validate_snapshot
from src.experiments.semantic_v3_resources import validate_policy

RESULTS = Path.home()/'Documents/rag-research-results'
PARENT = RESULTS/'twowiki-semantic-quality-25-v2-20261104/protocol.json'
DATA = RESULTS/'twowiki-v2-development-recovery-20261103/development_data.json'
REGISTRY = ROOT/'reports/twowiki_v3_exposure_reconciliation/reconciled_registry.json'
REGISTRY_SHA = '799c87aa83f6cb8ded2a16d0cbf110f35d1512b359d725dd27fa342422a68e65'
SNAPSHOT = Path.home()/'.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed'


def reference(path):
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path or path.is_symlink():
        raise ValueError('Canonical absolute nonsymlink packet path required')
    return {'path': str(path), 'sha256': file_sha(path)}


def write(packet, name, value):
    path = packet/name
    publish_json(path, value)
    return reference(path)


def snapshot(packet, name, ref):
    """Publish exact source bytes once; preserve signed digests across freezing."""
    source=Path(ref['path'])
    if source.is_symlink():raise ValueError('Input symlink forbidden')
    raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ref['sha256']:
        raise ValueError('Snapshot source fingerprint mismatch')
    path=packet/name
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.pending-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as sink:
            sink.write(raw);sink.flush();os.fsync(sink.fileno())
        os.chmod(tmp,0o444);os.link(tmp,path)
        directory=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:os.unlink(tmp)
    return reference(path)


def prepare(packet, output):
    if packet.exists() or output.exists():
        raise FileExistsError('Preparation and execution namespaces must both be unused')
    if packet == output or packet in output.parents or output in packet.parents:
        raise ValueError('Separate preparation and execution namespaces required')
    parent = read_pinned({'path': str(PARENT), 'sha256': PARENT_SHA256})
    original_sha = parent['binding']['development_artifact_sha256']
    original = read_pinned({'path': str(DATA), 'sha256': original_sha})
    registry = read_pinned({'path': str(REGISTRY), 'sha256': REGISTRY_SHA})
    ids = parent['binding']['query_ids']
    queries = {q['query_id']: q for q in original['queries']}
    if len(ids) != 25 or len(set(ids)) != 25 or not set(ids) <= queries.keys():
        raise ValueError('Documented historical population missing; no substitutions')
    # No new selection. Retain the entire original development corpus and exact
    # query objects; aliases are not invented or asserted complete.
    data = {'scope': 'development', 'dataset': DATASET,
            'historical_source_sha256': original_sha,
            'queries': [queries[q] for q in ids], 'corpus': original['corpus']}
    packet.mkdir(parents=True, exist_ok=False)
    artifacts = {'historical_protocol': snapshot(packet, 'historical_protocol.json', {'path':str(PARENT),'sha256':PARENT_SHA256}),
                 'data': write(packet, 'development_data.json', data),
                 'registry': snapshot(packet, 'exposure_registry.uncertified.json', {'path':str(REGISTRY),'sha256':REGISTRY_SHA}),
                 'pool_ids': write(packet, 'documented_25.ids.json', ids),
                 'profile': write(packet, 'profile.json', descriptor(scope='development'))}
    cohort = {'schema': RULE+'/cohort', 'scope': 'development', 'query_ids': ids,
              'query_count': 25, 'selection_rule': 'reuse-exact-documented-v2-order-no-replacement',
              'historical_protocol_sha256': PARENT_SHA256, 'historical_data_sha256': original_sha,
              'dataset_sha256': artifacts['data']['sha256'], 'prospective_evidence': False}
    artifacts['cohort'] = write(packet, 'cohort.reused.json', cohort)
    artifacts['cohort_receipt'] = write(packet, 'reuse_receipt.json', {
        'schema': RULE+'/reuse-receipt', 'frozen_at': datetime.now(timezone.utc).isoformat(),
        'pre_content_prospective_freeze': False,
        'input_sha256': {k: artifacts[k]['sha256'] for k in
                        ('cohort', 'registry', 'pool_ids', 'data', 'historical_protocol')}})
    forms = [{**target_review_form(q), 'review_state': 'pending',
              'cohort_receipt_sha256': artifacts['cohort_receipt']['sha256'],
              'gold_doc_ids': q.get('gold_doc_ids', []), 'gold_alias_completeness': 'UNREVIEWED'}
             for q in data['queries']]
    write(packet, 'targets.blank.json', forms)
    model_files = {p.relative_to(SNAPSHOT).as_posix(): file_sha(p)
                   for p in SNAPSHOT.rglob('*') if p.is_file()}
    if model_files != parent['model']['files_sha256']:
        raise ValueError('Actual cached model inventory differs from historical binding')
    runtime = {'execution_kind': 'authorized_model', 'snapshot_path': str(SNAPSHOT),
        'model_files': [{'path': str(SNAPSHOT/k), 'sha256': v} for k,v in sorted(model_files.items())],
        'model_provenance': {'model_identity': parent['model']['repository'],
            'revision': parent['model']['revision'], 'model_files_sha256': model_files,
            'decoding': {'sampler': 'explicit greedy', 'temperature': 0.0}},
        'environment': {'python': platform.python_version(),
            'packages': {d.metadata['Name']: d.version for d in importlib.metadata.distributions()
                         if d.metadata['Name']}},
        'resource_policy': {'min_free_disk_bytes': 12*2**30, 'max_output_bytes': 512*2**20,
            'min_available_memory_bytes': 2*2**30, 'max_process_rss_bytes': 10*2**30,
            'max_memory_pressure': 'normal', 'max_elapsed_seconds': 72*3600,
            'max_backend_calls': 200, 'deadline': None},
        'inventory_certification': None}
    validate_snapshot(runtime)  # File hashing only; no model/tokenizer loading.
    write(packet, 'runtime.proposed.json', runtime)
    write(packet, 'candidate_packet.blank.json', {
        'target':None,'packet':{'payload':{'query_sha256':None,'target':None,'nominator_id':None,
            'evidence':[{'doc_id':None,'start':None,'end':None,'quote':None}],
            'facts':{},'fact_citations':{}},
            'review':{'payload_sha256':None,'reviewer_id':None,'reviewer_type':'human',
                'reviewed_at':None,'decision':None,'uncertainty':None,'notes':None,
                'checks':dict.fromkeys(('referent_identity','entity_type_and_role','aliases_complete',
                    'corpus_relative_contradiction','chronological_plausibility','geographic_granularity'),None)}}})
    write(packet, 'study_review.blank.json', {'schema': RULE+'/human-study-review',
        'review_payload_sha256': None, 'acknowledgments': dict.fromkeys(sorted(ACKNOWLEDGMENTS), False),
        'signatures': [{'role': role, 'signer_id': None, 'signed_at': None, 'signed_evidence': None}
                       for role in sorted(REVIEW_ROLES)]})
    write(packet, 'authorization.blank.json', {'schema': 'semantic-v3-model-call-authorization/v1',
        'allow_model_calls': False, 'manifest_sha256': None, 'protocol_sha256': None,
        'scope': 'development', 'purpose': 'construction-only', 'study_kind': KIND,
        'prospective_evidence': False, 'historical_exposure_risk_acknowledged': False,
        'output_namespace': str(output), 'max_backend_calls': 200, 'authorizer_type': 'human',
        'authorizer_id': None, 'issued_at': None, 'expires_at': None, 'resource_policy_sha256': None})
    write(packet, 'packet.index.json', {'schema': RULE+'/prepared-packet', 'status': 'NO_GO_HUMAN_EVIDENCE_REQUIRED',
        'study_kind': KIND, 'artifacts': artifacts, 'output_namespace': str(output),
        'driver_implementation_sha256': implementation_pins(),
        'preparation_script_sha256': file_sha(__file__),
        'original_development_data': {'path': str(DATA), 'sha256': original_sha},
        'engineering_commit': '7e471dd3b5f6b9187f6e8b810952f891557eb2ba'})
    return {'status': 'NO_GO_HUMAN_EVIDENCE_REQUIRED', 'packet': str(packet), 'query_count': 25}


def reviewed_inputs(packet):
    index = read_pinned(reference(packet/'packet.index.json'))
    if (index['driver_implementation_sha256'] != implementation_pins()
            or index['preparation_script_sha256'] != file_sha(__file__)):
        raise ValueError('Preparation source changed; independently review a new version')
    artifacts = dict(index['artifacts'])
    for ref in artifacts.values():read_pinned(ref)
    artifacts['targets'] = reference(packet/'targets.reviewed.json')
    artifacts['runtime'] = reference(packet/'runtime.reviewed.json')
    runtime = read_pinned(artifacts['runtime'])
    if runtime.get('execution_kind') != 'authorized_model':
        raise ValueError('This real-study freeze requires the reviewed pinned model runtime')
    validate_policy(runtime['resource_policy']);validate_snapshot(runtime)
    inventory = {k:v for k,v in runtime.items() if k != 'inventory_certification'}
    cert = runtime.get('inventory_certification') or {}
    if (cert.get('inventory_sha256') != digest(inventory)
            or cert.get('complete_model_and_tokenizer_inventory') is not True
            or cert.get('complete_environment_inventory') is not True or not cert.get('reviewer_id')):
        raise PermissionError('Actual independent runtime inventory review required')
    targets = read_pinned(artifacts['targets'])
    if ([t['query_id'] for t in targets] != read_pinned(artifacts['pool_ids'])
            or any(t.get('review_state') not in ('reviewed','abstain') for t in targets)):
        raise ValueError('All exact 25 require actual reviewed target packets or documented abstentions')
    values={k:read_pinned(v) for k,v in artifacts.items()}
    validate_content({'dataset':DATASET,'study_kind':KIND,'artifacts':artifacts},
                     values,values['cohort'],values['cohort_receipt'])
    return index, artifacts


def review_payload(packet):
    index, artifacts = reviewed_inputs(packet)
    return {'input_sha256': {k:v['sha256'] for k,v in artifacts.items()},
        'driver_implementation_sha256': implementation_pins(),
        'output_namespace': index['output_namespace'], 'study_kind': KIND}


def freeze(packet):
    index, artifacts = reviewed_inputs(packet)
    artifacts['study_review'] = reference(packet/'study_review.signed.json')
    manifest = {'schema': 'semantic-v3-diagnostic-manifest/v1', 'study_kind': KIND,
        'prospective_evidence': False, 'historical_exposure_risk_acknowledged': True,
        'base_implementation_commit': 'fba2583ae4569d6e5114052ac1854ad545dc3c16',
        'status': 'frozen_ready_for_authorization', 'scope': 'development', 'stage': 'construction-only',
        'dataset': DATASET, 'driver_implementation_sha256': implementation_pins(),
        'output_namespace': index['output_namespace'], 'artifacts': artifacts}
    values = {k:read_pinned(v) for k,v in artifacts.items() if k not in ('data','targets')}
    admit_diagnostic(manifest, values)  # All real signatures required, no invented approval.
    # Snapshot only after metadata approval. Byte-identical copies retain the
    # hashes signed by humans and cannot be edited as intake forms on resume.
    for key in ('targets','runtime','study_review'):
        artifacts[key]=snapshot(packet,'frozen-inputs/'+key+'.json',artifacts[key])
    protocol = {'schema': RULE+'/protocol', 'selection_rule': RULE,
        'acceptance_criteria': ACCEPTANCE_CRITERIA,
        'status': 'frozen_for_independent_authorization', 'scope': 'development',
        'stage': 'construction-only', 'query_count': 25, 'intensities': [1,3], 'seed': 42,
        'max_backend_calls': 200, 'max_attempts_per_document': 2, 'max_tokens': 150,
        'input_sha256': {k:v['sha256'] for k,v in artifacts.items()},
        'prospective_evidence': False, 'historical_exposure_risk_acknowledged': True}
    artifacts['protocol'] = write(packet, 'protocol.frozen.json', protocol)
    return write(packet, 'manifest.frozen.json', manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare','review-payload','freeze','preflight','construct','summary','export'))
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--authorization-sha256')
    parser.add_argument('--manifest-sha256')
    args = parser.parse_args()
    packet = args.packet
    if not packet.is_absolute() or packet.resolve() != packet:
        parser.error('--packet must be canonical and absolute')
    if args.command == 'prepare':
        if args.output is None or not args.output.is_absolute() or args.output.resolve() != args.output:
            parser.error('prepare needs canonical absolute --output')
        result = prepare(packet, args.output)
    elif args.command == 'review-payload':
        payload = review_payload(packet)
        result = {'payload': payload, 'review_payload_sha256': digest(payload)}
    elif args.command == 'freeze':result = freeze(packet)
    else:
        if not args.authorization or not args.authorization_sha256 or not args.manifest_sha256:
            parser.error('actual externally pinned manifest and authorization required')
        mref = {'path':str(packet/'manifest.frozen.json'), 'sha256':args.manifest_sha256}
        aref = {'path':str(args.authorization), 'sha256':args.authorization_sha256}
        if args.command == 'preflight':
            preflight(mref, authorization_reference=aref)
            result = {'status':'admitted_construction_only_no_model_loaded'}
        elif args.command == 'construct':
            result = run(mref, authorization_reference=aref, max_cells=1)
        else:
            from src.experiments.semantic_v3_review import construction_summary, export_semantic_review
            manifest = read_pinned(mref)
            output = manifest['output_namespace']
            if args.command == 'summary':
                result = construction_summary(output,mref,authorization_reference=aref)
            else:
                result = {'exported_attempts': export_semantic_review(output,mref,
                    packet/'postrun-review-public', packet/'postrun-review-private',authorization_reference=aref)}
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':main()
