"""One explicit incident exception; no inference on import or preparation.

Legacy guards remain unchanged. Publication is a labeled resolution receipt, never
an assertion that the interrupted original physical call returned a response.
"""
import contextlib
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
from src.evaluation.qa_records import validate_qa
from src.experiments.week9_construction import fingerprint
from src.experiments.execution_reliability import atomic, read, once

SCHEMA = 'rag-poison-transfer.single-intent-recovery-amendment/v1'
ROOT = Path(__file__).resolve().parents[2]
EXECUTOR_FILES = ('src/experiments/single_intent_recovery.py', 'scripts/recover_hotpotqa_single_intent.py')
INCIDENT = {
    'protocol_sha256': '510155bcb15dab07f63d217b66575d8dfd403a7d05b21d0e7cd65b93badd13c8',
    'request_fingerprint': 'dec08535d5e02ffaa9838f4f35ca3061c3c7b530d550a3c90c4ddda31e22f9ec',
    'intent_sha256': '0515674a780eee590a8b7a28fa4c33a8cb5cb882ebf3e9ca0874697c3294b64e',
    'intent_relative': 'calls/semantic_fluent_false_evidence.intensity-1.seed-44/0/6d040ffb2265adc64d9557897a52b731a39c8031a1fd3cda9fbcd04950fb118f/00.intent.json',
    'runtime_seed': 3215750484,
    'recovery_dir': '/private/tmp/hotpotqa-transfer-single-intent-recovery-v1',
    'parent_inventory_fingerprint': '0ab4403df576b858395c0638f07ad91e8cad123e8e180e33ebd05703e04a863d',
    'source_commit': 'ade475d34c174bdc41b81523754050eab4307c2d',
}


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()


def executor_binding():
    return {'git_commit': git(ROOT, 'rev-parse', 'HEAD'),
        'clean': not bool(git(ROOT, 'status', '--porcelain', '--untracked-files=all')),
        'files_sha256': {p: sha(ROOT / p) for p in EXECUTOR_FILES}}


def verify_source(checkout, protocol):
    checkout = Path(checkout)
    if git(checkout, 'status', '--porcelain', '--untracked-files=all'):
        raise ValueError('Frozen execution checkout is dirty')
    paths = [p for p in git(checkout, 'ls-files').splitlines()
        if (p.startswith(('src/', 'scripts/')) and p.endswith('.py')) or p == 'run.py']
    binding = {'git_commit_sha': git(checkout, 'rev-parse', 'HEAD'),
        'code_fingerprint': fingerprint({p: sha(checkout / p) for p in paths})}
    if binding != protocol['source'] or binding['git_commit_sha'] != INCIDENT['source_commit']:
        raise ValueError('Frozen execution source mismatch')


def inventory(root):
    result = {}
    for p in sorted(Path(root).rglob('*')):
        if p.is_symlink() or p.name.startswith('.atomic-'):
            raise ValueError('Symlink or incomplete atomic publication')
        if p.is_file(): result[p.relative_to(root).as_posix()] = sha(p)
    return result


def response_relative(plan):
    return plan['incident']['intent_relative'].replace('.intent.json', '.response.json')


def external_output(path, protocol, frozen_checkout):
    path = Path(path).resolve()
    for protected in (Path(protocol).resolve().parent.parent, Path(frozen_checkout).resolve(), ROOT):
        if path == protected or protected in path.parents:
            raise ValueError('Recovery/proposal output must be outside experiment and code checkouts')
    return path


def _identity(plan):
    external_output(plan['recovery_dir'], plan['protocol'], plan['frozen_checkout'])
    if str(Path(plan['recovery_dir']).resolve()) != INCIDENT['recovery_dir']:
        raise ValueError('Recovery namespace is fixed; no fresh-namespace retry')
    if fingerprint(plan.get('parent_files_sha256')) != INCIDENT['parent_inventory_fingerprint']:
        raise ValueError('Forensic inventory binding mismatch')
    if plan.get('schema') != SCHEMA or plan.get('incident') != INCIDENT:
        raise ValueError('Amendment is restricted to the single authorized incident')
    if plan.get('physical_call_policy') != {
        'original': 'indeterminate', 'replacement_maximum': 1,
        'extra_physical_call_allowance': 1, 'logical_quality_attempt_limit': 2,
        'replacement_is_original_response': False, 'recovery_interruption': 'halt-no-regeneration'}:
        raise ValueError('Physical-call/retry policy mismatch')
    if plan.get('executor') != executor_binding():
        raise ValueError('Recovery executor provenance changed; prepare a new plan')


def _protocol(plan):
    path = Path(plan['protocol'])
    if path.is_symlink() or sha(path) != INCIDENT['protocol_sha256']:
        raise ValueError('Frozen protocol fingerprint mismatch')
    protocol = read(path)
    verify_source(plan['frozen_checkout'], protocol)
    if Path(protocol['planned_outputs']['candidates']).resolve() != Path(plan['candidates']).resolve():
        raise ValueError('Candidate path differs from the frozen output namespace')
    if protocol['execution']['unresolved_intent'] != 'halt-no-regeneration':
        raise ValueError('Unexpected parent execution policy')
    return protocol


def _request(plan):
    path = Path(plan['candidates']) / INCIDENT['intent_relative']
    if sha(path) != INCIDENT['intent_sha256']:
        raise ValueError('Original intent changed')
    request = read(path)
    if fingerprint(request) != INCIDENT['request_fingerprint']:
        raise ValueError('Original request fingerprint mismatch')
    return request


def _parent(plan, receipt=None, allow_continuation=False):
    current = inventory(plan['candidates']); baseline = plan['parent_files_sha256']
    if any(current.get(k) != v for k, v in baseline.items()):
        raise ValueError('Protected parent file changed or disappeared')
    extra = set(current) - set(baseline)
    rel = response_relative(plan)
    if rel in extra:
        if receipt is None or read(Path(plan['candidates']) / rel) != receipt:
            raise ValueError('Conflicting original response/resolution receipt')
        extra.remove(rel)
    if extra and not allow_continuation:
        raise ValueError('Parent advanced or unexpected files appeared before recovery')


def prepare(protocol, candidates, frozen_checkout, model_snapshot, recovery_dir):
    candidates = Path(candidates).resolve(); protocol = Path(protocol).resolve()
    recovery_dir = external_output(recovery_dir, protocol, frozen_checkout)
    if str(recovery_dir) != INCIDENT['recovery_dir']:
        raise ValueError('Recovery namespace is fixed; no fresh-namespace retry')
    if recovery_dir.exists(): raise ValueError('Fresh recovery namespace required')
    plan = {'schema': SCHEMA, 'incident': dict(INCIDENT), 'protocol': str(protocol),
        'candidates': str(candidates), 'frozen_checkout': str(Path(frozen_checkout).resolve()),
        'model_snapshot': str(Path(model_snapshot).resolve()), 'recovery_dir': str(recovery_dir),
        'executor': executor_binding(), 'parent_files_sha256': inventory(candidates),
        'physical_call_policy': {'original': 'indeterminate', 'replacement_maximum': 1,
            'extra_physical_call_allowance': 1, 'logical_quality_attempt_limit': 2,
            'replacement_is_original_response': False, 'recovery_interruption': 'halt-no-regeneration'},
        'scientific_contract_change': 'One explicitly disclosed extra physical-call allowance; scientific targets, prompts, quality retry policy and denominators unchanged',
        'original_backend_execution': 'unknown; intent does not prove execution or completion',
        'execution_authorization': 'NOT GRANTED by preparation; explicit future opt-in required'}
    _identity(plan); p = _protocol(plan); request = _request(plan)
    if fingerprint(plan['parent_files_sha256']) != INCIDENT['parent_inventory_fingerprint']:
        raise ValueError('Parent differs from the previously verified forensic inventory')
    if request['provenance']['model'] != p['model']:
        raise ValueError('Model provenance mismatch')
    unresolved = []
    for f in candidates.rglob('*.intent.json'):
        if not f.with_name(f.name.replace('.intent.json', '.response.json')).exists():
            unresolved.append(f.relative_to(candidates).as_posix())
    if unresolved != [INCIDENT['intent_relative']]:
        raise ValueError('Another or missing unresolved incident')
    # Independently validate every completed checkpoint and journal without ignoring
    # the parent guard globally. The one missing response remains indeterminate.
    for f in candidates.rglob('*.json'):
        obj = read(f)
        if not isinstance(obj, dict): continue
        if 'data_sha256' in obj and obj['data_sha256'] != fingerprint(obj.get('data')):
            raise ValueError('Parent checkpoint integrity mismatch')
        if f.name.endswith('.response.json'):
            intent = f.with_name(f.name.replace('.response.json', '.intent.json'))
            if not intent.exists(): raise ValueError('Orphan parent response')
            req = read(intent)
            if obj.get('request_fingerprint') != fingerprint(req) or 'error' in obj:
                raise ValueError('Invalid completed parent response')
            validate_qa(obj['generation'], obj['generation']['extracted_answer'])
            if obj['generation']['prompt'] != req['prompt'] or obj.get('generation_sha256') != fingerprint(obj['generation']):
                raise ValueError('Parent generation integrity mismatch')
    _parent(plan)
    return plan


def authorize(plan, approved_fingerprint, extra_calls):
    _identity(plan); _protocol(plan); _request(plan)
    if approved_fingerprint != INCIDENT['request_fingerprint'] or extra_calls != 1:
        raise ValueError('Explicit one-request/one-extra-call execution opt-in required')
    if not plan['executor']['clean']:
        raise ValueError('Draft executor cannot execute; review/commit and prepare a clean plan')


@contextlib.contextmanager
def parent_lock(plan):
    # Cooperates with the unchanged original runner; no lock is acquired in prepare.
    root = Path(plan['candidates'])
    with root.with_name(root.name + '.writer.lock').open('a') as f:
        try: fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError('Original stage writer is active') from None
        yield


def _recovery_files(plan):
    root = Path(plan['recovery_dir'])
    allowed = {'replacement.intent.json', 'replacement.response.json', 'replacement.error.json'}
    if root.is_symlink(): raise ValueError('Recovery symlink forbidden')
    if root.exists() and any(p.is_symlink() or not p.is_file() or p.name not in allowed for p in root.iterdir()):
        raise ValueError('Ambiguous recovery namespace or unpublished atomic file')


def _replacement(plan, plan_pin):
    _recovery_files(plan)
    root = Path(plan['recovery_dir']); i = root / 'replacement.intent.json'; r = root / 'replacement.response.json'
    if not i.exists(): raise RuntimeError('No recovery physical intent exists')
    expected = {'schema': SCHEMA, 'amendment_sha256': plan_pin, 'physical_attempt': 'replacement-1',
        'original_physical_attempt': 'indeterminate', 'request': _request(plan),
        'runtime_seed': INCIDENT['runtime_seed'], 'executor': plan['executor']}
    if read(i) != expected: raise ValueError('Recovery intent/provenance mismatch')
    if (root / 'replacement.error.json').exists(): raise RuntimeError('Recovery error recorded; no retry permitted')
    if not r.exists(): raise RuntimeError('Recovery intent has no response; do not retry')
    obj = read(r)
    if obj.get('schema') != SCHEMA or set(obj) != {'schema', 'amendment_sha256', 'intent_sha256', 'generation', 'generation_sha256', 'physical_call_accounting'}:
        raise ValueError('Recovery response schema mismatch')
    if obj.get('intent_sha256') != sha(i) or obj.get('amendment_sha256') != plan_pin:
        raise ValueError('Recovery response provenance mismatch')
    if obj.get('physical_call_accounting') != {'original_indeterminate': 1, 'replacement_completed': 1, 'conservative_physical_dispatch_count': 2}:
        raise ValueError('Recovery physical-call accounting mismatch')
    g = obj['generation']; validate_qa(g, g['extracted_answer'])
    if g['prompt'] != expected['request']['prompt'] or obj.get('generation_sha256') != fingerprint(g):
        raise ValueError('Recovery generation mismatch')
    return obj


def execute(plan, plan_pin, approved_fingerprint, extra_calls, backend_factory, seed, capture):
    """Future opt-in only. One physical dispatch; response replay never calls a backend."""
    authorize(plan, approved_fingerprint, extra_calls)
    if fingerprint_bytes(plan) != plan_pin: raise ValueError('Amendment content pin mismatch')
    root = Path(plan['recovery_dir'])
    with parent_lock(plan):
        _recovery_files(plan)
        if (root / 'replacement.intent.json').exists():
            obj = _replacement(plan, plan_pin)
            _parent(plan, resolution(plan, plan_pin, obj))
            return {'status': 'replacement_already_saved', 'new_backend_calls': 0}
        _parent(plan)
        if root.exists() and any(root.iterdir()): raise ValueError('Unrecognized recovery namespace')
        request = _request(plan)
        atomic(root / 'replacement.intent.json', {'schema': SCHEMA, 'amendment_sha256': plan_pin,
            'physical_attempt': 'replacement-1', 'original_physical_attempt': 'indeterminate',
            'request': request, 'runtime_seed': INCIDENT['runtime_seed'], 'executor': plan['executor']})
        try:
            backend = backend_factory()
            seed(INCIDENT['runtime_seed'])
            _, generation = capture(backend, request['prompt'], request['max_tokens'])
            validate_qa(generation, generation['extracted_answer'])
            if generation['prompt'] != request['prompt']: raise ValueError('Recovery prompt mismatch')
            atomic(root / 'replacement.response.json', {'schema': SCHEMA,
                'amendment_sha256': plan_pin, 'intent_sha256': sha(root / 'replacement.intent.json'),
                'generation': generation, 'generation_sha256': fingerprint(generation),
                'physical_call_accounting': {'original_indeterminate': 1, 'replacement_completed': 1,
                    'conservative_physical_dispatch_count': 2}})
        except Exception as error:
            if not (root / 'replacement.response.json').exists():
                atomic(root / 'replacement.error.json', {'schema': SCHEMA, 'error_type': type(error).__name__,
                    'error': str(error), 'backend_execution': 'not inferred from exception', 'automatic_retry': False})
            raise
        return {'status': 'replacement_saved_separately_not_published', 'new_backend_calls': 1}


def fingerprint_bytes(plan):
    # Plan pins use actual immutable JSON bytes written by atomic(), not canonical JSON.
    payload = json.dumps(plan, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + '\n'
    return hashlib.sha256(payload.encode()).hexdigest()


def resolution(plan, plan_pin, replacement):
    """Explicitly labeled logical resolution compatible with the unchanged reader."""
    root = Path(plan['recovery_dir'])
    return {'request_fingerprint': INCIDENT['request_fingerprint'], 'generation': replacement['generation'],
        'generation_sha256': replacement['generation_sha256'],
        'execution': {'kind': 'explicit_replacement_resolution', 'backend_call_executed': False},
        'recovery': {'schema': SCHEMA, 'original_attempt_status': 'indeterminate',
            'is_original_response': False, 'amendment_sha256': plan_pin,
            'replacement_response': str(root / 'replacement.response.json'),
            'replacement_response_sha256': sha(root / 'replacement.response.json'),
            'original_intent_sha256': INCIDENT['intent_sha256'],
            'physical_call_accounting': replacement['physical_call_accounting'],
            'requires_incident_disclosure_in_final_results': True}}


def publish(plan, plan_pin, approved_fingerprint, extra_calls):
    """Future separately requested publication; never overwrite an original response."""
    authorize(plan, approved_fingerprint, extra_calls)
    if fingerprint_bytes(plan) != plan_pin: raise ValueError('Amendment content pin mismatch')
    with parent_lock(plan):
        obj = _replacement(plan, plan_pin); receipt = resolution(plan, plan_pin, obj)
        _parent(plan, receipt)
        once(Path(plan['candidates']) / response_relative(plan), receipt)
    return {'status': 'explicit_resolution_published', 'new_backend_calls': 0}


def verify_resolution(plan, plan_pin):
    _identity(plan); _protocol(plan); _request(plan)
    if fingerprint_bytes(plan) != plan_pin: raise ValueError('Amendment content pin mismatch')
    obj = _replacement(plan, plan_pin); receipt = resolution(plan, plan_pin, obj)
    _parent(plan, receipt, allow_continuation=True)
    if read(Path(plan['candidates']) / response_relative(plan)) != receipt:
        raise ValueError('Missing or conflicting resolution receipt')
    from src.experiments.execution_reliability import accounting, validate_store
    validate_store(plan['candidates'])  # No blanket exemption for later incidents.
    base_counts = accounting(plan['candidates'])
    replacement_counts = accounting(plan['recovery_dir'])
    completed = base_counts['actual_backend_calls'] + replacement_counts['actual_backend_calls']
    return {'status': 'verified_explicit_replacement_not_original',
        'extra_recorded_completed_recovery_calls': 1, 'original_indeterminate_calls': 1,
        'base_stage_accounting_requires_external_recovery_addition': True,
        'physical_call_accounting': {
            'base_completed_calls_excluding_resolution_receipt': base_counts['actual_backend_calls'],
            'separately_completed_replacement_calls': replacement_counts['actual_backend_calls'],
            'total_recorded_completed_calls': completed, 'indeterminate_original_calls': 1,
            'conservative_consumed_call_count': completed + 1,
            'additional_physical_budget_allowance': 1,
            'logical_quality_attempt_limit_unchanged': 2}}
