"""Disabled-by-default, construction-only prospective driver around frozen V3.

No loader or CLI executes models. An explicitly pinned authorization is checked
before even invoking a supplied lazy backend factory. No Dense/RCD/QA imports.
"""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import platform
import importlib.metadata

from src.attacks.semantic_quality_profile_v3 import construct, validate_profile
from src.attacks.semantic_quality_targets_v3 import digest, select_target
from src.experiments.semantic_v3_preparation import read_pinned, select_cohort, file_sha
from src.experiments.semantic_v3_checkpoint import atomic_record, read_record, writer_lock, CallJournal, verify_journal

ROOT=Path(__file__).resolve().parents[2]
DRIVER_FILES=('src/experiments/semantic_v3_preparation.py','src/experiments/semantic_v3_checkpoint.py',
              'src/experiments/semantic_v3_pilot.py', 'src/experiments/semantic_v3_review.py')


def implementation_pins():return {f:file_sha(ROOT/f) for f in DRIVER_FILES}


def _authorization(reference, manifest_sha, protocol_sha, output, *, now=None):
    if reference is None:raise PermissionError('Separate, externally pinned model-call authorization required')
    auth=read_pinned(reference)
    if (auth.get('schema')!='semantic-v3-model-call-authorization/v1' or auth.get('allow_model_calls') is not True
            or auth.get('manifest_sha256')!=manifest_sha or auth.get('protocol_sha256')!=protocol_sha
            or auth.get('output_namespace')!=str(output) or auth.get('scope')!='development'
            or auth.get('purpose')!='construction-only' or type(auth.get('max_backend_calls')) is not int
            or auth['max_backend_calls']!=200 or auth.get('authorizer_type')!='human'
            or not isinstance(auth.get('authorizer_id'),str) or not auth['authorizer_id'].strip()):
        raise PermissionError('Model-call authorization is incomplete or does not bind this pilot')
    now=now or datetime.now(timezone.utc)
    issued=datetime.fromisoformat(auth['issued_at'].replace('Z','+00:00'))
    expires=datetime.fromisoformat(auth['expires_at'].replace('Z','+00:00'))
    if issued.utcoffset() is None or expires.utcoffset() is None or not issued<=now<expires:
        raise PermissionError('Authorization not current')
    return auth


def preflight(manifest_reference):
    manifest=read_pinned(manifest_reference)
    if (manifest.get('schema')!='semantic-v3-pilot-manifest/v1'
            or manifest.get('base_implementation_commit')!='fba2583ae4569d6e5114052ac1854ad545dc3c16'
            or manifest.get('status')!='frozen_ready_for_authorization') or manifest.get('scope')!='development' or manifest.get('stage')!='construction-only':
        raise ValueError('Draft or non-development manifest cannot execute')
    if manifest.get('driver_implementation_sha256')!=implementation_pins():raise ValueError('Driver source fingerprint mismatch')
    artifacts=manifest['artifacts']
    if set(artifacts)!={'protocol','profile','registry','pool_ids','cohort','cohort_receipt','data','targets','runtime'}:
        raise ValueError('All pinned preparation inputs required')
    values={k:read_pinned(v) for k,v in artifacts.items()}
    protocol=values['protocol']
    if (protocol.get('schema')!='twowiki-semantic-quality-v3-prospective/v1/protocol'
            or protocol.get('status')!='frozen_for_independent_authorization'
            or protocol.get('scope')!='development' or protocol.get('stage')!='construction-only'
            or protocol.get('intensities')!=[1,3] or protocol.get('seed')!=42
            or type(protocol.get('max_backend_calls')) is not int or protocol['max_backend_calls']!=200
            or type(protocol.get('max_attempts_per_document')) is not int or protocol['max_attempts_per_document']!=2
            or type(protocol.get('max_tokens')) is not int or protocol['max_tokens']!=150
            or protocol.get('selection_rule')!='twowiki-semantic-quality-v3-prospective/v1'):
        raise ValueError('Frozen protocol configuration mismatch')
    # Bind the protocol to the other exact artifact bytes, avoiding circular pins.
    if protocol.get('input_sha256')!={k:v['sha256'] for k,v in artifacts.items() if k!='protocol'}:
        raise ValueError('Protocol/input fingerprints differ')
    validate_profile(values['profile'],scope='development')
    cohort=select_cohort(values['pool_ids'],values['registry'],dataset_sha256=artifacts['data']['sha256'])
    if cohort!=values['cohort']:raise ValueError('Cohort differs from pre-content deterministic selection')
    receipt=values['cohort_receipt']
    if receipt.get('schema')!='semantic-v3-pre-content-freeze-receipt/v1' or receipt.get('selector_source_sha256')!=file_sha(ROOT/'src/experiments/semantic_v3_preparation.py'):
        raise ValueError('Cohort receipt selector provenance mismatch')
    if receipt.get('input_sha256')!={k:artifacts[k]['sha256'] for k in ('cohort','registry','pool_ids','data')}:
        raise ValueError('Pre-content cohort-freeze receipt missing or mismatched')
    frozen_at=datetime.fromisoformat(receipt['frozen_at'].replace('Z','+00:00'))
    if frozen_at.utcoffset() is None:raise ValueError('Freeze receipt needs timezone')
    data=values['data'];ids=cohort['query_ids']
    if data.get('scope')!='development' or data.get('dataset',{}).get('split')!='train':
        raise ValueError('Pinned train-development data required; held-out data refused')
    if len({q['query_id'] for q in data['queries']})!=len(data['queries']):raise ValueError('Duplicate dataset query IDs')
    by_id={q['query_id']:q for q in data['queries']}
    if not set(values['pool_ids'])<=by_id.keys():raise ValueError('Metadata pool IDs absent from pinned dataset')
    if not set(ids)<=by_id.keys():raise ValueError('Missing selected query; no replacements')
    targets=values['targets']
    if [t['query_id'] for t in targets]!=ids:raise ValueError('Target ledger must retain exact cohort order')
    pins={d['doc_id']:hashlib.sha256(d['text'].encode()).hexdigest() for d in data['corpus']}
    # These document hashes inherit trust from the independently pinned entire data file.
    selections={}
    for entry in targets:
        q=by_id[entry['query_id']]
        if entry.get('query_sha256')!=digest(q):raise ValueError('Target review query binding mismatch')
        if entry.get('cohort_receipt_sha256')!=artifacts['cohort_receipt']['sha256']:
            raise ValueError('Target ledger lacks frozen-cohort receipt binding')
        if entry.get('review_state') not in ('reviewed','abstain'):raise ValueError('Pending target review cannot execute')
        for c in entry['candidates']:
            review=(c.get('packet') or {}).get('review',{})
            if not isinstance(review.get('uncertainty'),str) or not review['uncertainty'].strip():
                raise ValueError('Explicit independent-review uncertainty required')
            reviewed_at=datetime.fromisoformat(review['reviewed_at'].replace('Z','+00:00'))
            if reviewed_at.utcoffset() is None or reviewed_at<frozen_at:
                raise ValueError('Candidate review predates frozen cohort')
        target,selection=select_target(q,entry['candidates'],data['corpus'],pins,scope='development')
        if target is None and not entry.get('abstention_reason'):raise ValueError('Explicit target abstention reason required')
        if target is not None and entry['review_state']!='reviewed':raise ValueError('Abstention cannot conceal a selected target')
        selections[q['query_id']]={'target':target,'selection':selection}
    runtime=values['runtime']
    if runtime.get('execution_kind') not in ('offline_stub','authorized_model'):raise ValueError('Unknown runtime kind')
    provenance=runtime['model_provenance']
    if provenance.get('decoding')!={'sampler':'explicit greedy','temperature':0.0}:raise ValueError('Decoding mismatch')
    if runtime['environment']['python']!=platform.python_version():raise ValueError('Python environment mismatch')
    for package,version in runtime['environment']['packages'].items():
        if importlib.metadata.version(package)!=version:raise ValueError('Package environment mismatch')
    if runtime['execution_kind']=='authorized_model':
        if not runtime.get('model_files') or not runtime['environment']['packages']:
            raise ValueError('Model and environment pins missing')
        certificate=runtime.get('inventory_certification',{})
        inventory={k:v for k,v in runtime.items() if k!='inventory_certification'}
        if (certificate.get('inventory_sha256')!=digest(inventory)
                or certificate.get('complete_model_and_tokenizer_inventory') is not True
                or certificate.get('complete_environment_inventory') is not True
                or not certificate.get('reviewer_id')):
            raise ValueError('Complete environment/model inventory review required')
        for ref in runtime['model_files']:
            if file_sha(ref['path'])!=ref['sha256']:raise ValueError('Model file fingerprint mismatch')
    return manifest,values,selections,pins


def run(manifest_reference, *, authorization_reference=None, backend_factory=None, max_cells=None, interrupt=None):
    """Only explicit callers can execute; this task uses scripted stubs only.

    Completed calls replay from exact raw response records. Unknown calls block.
    Every actual-call intent, including failed ones, consumes the global budget.
    """
    if authorization_reference is None:
        raise PermissionError('Inference disabled without separately recorded authorization')
    manifest,values,selections,pins=preflight(manifest_reference)
    output=Path(manifest['output_namespace'])
    if not output.is_absolute() or output.resolve()!=output:raise ValueError('Use a canonical absolute fresh namespace')
    auth=_authorization(authorization_reference,manifest_reference['sha256'],manifest['artifacts']['protocol']['sha256'],output)
    context={'manifest_sha256':manifest_reference['sha256'],'authorization_sha256':authorization_reference['sha256'],
             'model_provenance':values['runtime']['model_provenance']}
    if not output.exists():
        output.mkdir(parents=True,exist_ok=False)
        atomic_record(output/'manifest.record.json',{'manifest':manifest,'context':context})
    elif not (output/'manifest.record.json').exists():raise FileExistsError('Existing unrelated namespace refused')
    with writer_lock(output):
        if read_record(output/'manifest.record.json')!={'manifest':manifest,'context':context}:raise ValueError('Namespace binding mismatch')
        call_count=verify_journal(output)
        if call_count>200:raise ValueError('Persisted budget exceeds 200')
        if any(read_record(p)['context']!=context for p in (output/'calls').glob('*.intent.json')):
            raise ValueError('Journal context differs from authorized manifest')
        seal_path=output/'complete.seal.json'
        if seal_path.exists():
            seal=read_record(seal_path)
            if seal['context']!=context or seal['backend_calls']!=call_count:raise ValueError('Seal/context mismatch')
            current_journal={str(p.relative_to(output)):file_sha(p) for p in (output/'calls').glob('*.json')}
            if current_journal!=seal['journal_sha256']:raise ValueError('Sealed call journal mutated')
            expected={f'records/i{i}-{digest(q)}.json' for i in (1,3) for q in values['cohort']['query_ids']}
            if set(seal['record_sha256'])!=expected:raise ValueError('Incomplete seal population')
            for name,sha in seal['record_sha256'].items():
                if file_sha(output/name)!=sha:raise ValueError('Sealed result mutated')
            return seal
        journal=CallJournal(output,context,backend_factory,interrupt=interrupt)
        by_id={q['query_id']:q for q in values['data']['queries']};ledger={r['query_id']:r for r in values['targets']}
        names=[];processed=0
        for intensity in (1,3):
            for qid in values['cohort']['query_ids']:
                key=f'i{intensity}-{digest(qid)}';name=f'records/{key}.json';path=output/name;names.append(name)
                if path.exists():
                    result=read_record(path)
                    if result['query_id']!=qid or result['intensity']!=intensity:raise ValueError('Checkpoint identity mismatch')
                    continue
                journal.start_cell(key)
                try:
                    result=construct(by_id[qid],ledger[qid]['candidates'],values['data']['corpus'],pins,journal,
                                     profile=values['profile'],scope='development',intensity=intensity,set_runtime_seed=journal.set_seed)
                except Exception as exc:
                    failure=output/f'infrastructure/{key}.json'
                    if not failure.exists():atomic_record(failure,{'kind':'infrastructure_error','error_type':type(exc).__name__,
                         'message':str(exc),'attempt_records':getattr(exc,'semantic_attempt_records',[])})
                    raise
                atomic_record(path,result)
                processed+=1
                if max_cells is not None and processed>=max_cells:return {'status':'paused_after_complete_cell','new_cells':processed}
        seal={'status':'complete_construction_only','context':context,'backend_calls':verify_journal(output),
              'record_sha256':{name:file_sha(output/name) for name in names},
              'journal_sha256':{str(p.relative_to(output)):file_sha(p) for p in (output/'calls').glob('*.json')},
              'execution_kind':values['runtime']['execution_kind'],'qa_or_retrieval_evaluated':False}
        atomic_record(seal_path,seal)
        return seal
