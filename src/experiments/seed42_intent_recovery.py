"""Incident-specific seed-42 amendment. No backend imports or inference at import.

The unchanged seed-44 authorization is never rebound. Only its I/O primitives are
shared. All production identities and namespaces below are fixed, not CLI inputs.
"""
import contextlib
import fcntl
import importlib.metadata
import hashlib
import os
from pathlib import Path
import subprocess
import sys

from src.evaluation.qa_records import validate_qa
from src.experiments import execution_reliability as reliable
from src.experiments.single_intent_recovery import (
    external_output, fingerprint_bytes, git, inventory, sha,
)
from src.experiments.week9_construction import fingerprint

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = Path('/Users/sadiapeerzada/Documents/rag-research-results')
CANDIDATES = RESEARCH / 'hotpotqa-transfer-20261028/transfer/execution/candidates'
PROTOCOL = CANDIDATES.parent.parent / 'protocol.json'
FROZEN = RESEARCH / 'hotpotqa-reliable-execution'
MODEL = Path('/Users/sadiapeerzada/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed')
AMENDMENT_ROOT = Path('/Users/sadiapeerzada/Documents/rag-recovery-amendments/hotpotqa-seed42-v1')
RECOVERY = AMENDMENT_ROOT / 'replacement'
PROPOSAL = AMENDMENT_ROOT / 'amendment.json'
MODEL_LOCK = Path('/private/tmp/rag-poison-transfer-local-model.writer.lock')
SUPERVISOR_LOCKS = (
    CANDIDATES.with_name('candidates.supervisor.lock'),
    Path('/private/tmp/rag-transfer-supervisor/logs/transfer-supervisor/candidates.supervisor.lock'),
    ROOT / 'logs/transfer-supervisor/candidates.supervisor.lock',
)
SCHEMA = 'rag-poison-transfer.seed42-single-intent-recovery/v1'
INCIDENT = {
    'protocol_sha256': '94e4b6d8fb49a7e662074fb766c92498ad0667abf9cf38233e0f49aa401183aa',
    'intent_sha256': '8765ff8b160155529aa75d89385e96357adae7b5663b85768dbb7fcdd8e7769f',
    'request_fingerprint': '6fca4964d2548ff495909c4e47a1233836cd6099d148c9b034099d86735e6c76',
    'inventory_fingerprint': '747657ff5d89a088ce7dcff92910bd3b8230f3343e49e4f6b97acf1fc3b08561',
    'source': {'git_commit_sha': '9a937afbd94b5a46394b5724a6be2d571d2e0c19',
               'code_fingerprint': '80844d1935d3524bd20c1929ed2f7627a8ef212730c5c657ea8c7d572f72f704'},
    'intent_relative': 'calls/semantic_fluent_false_evidence.intensity-1.seed-42/1/236491dc1eb4b16c9723a7fc93ff1394577a5455e3e155415bb0c1594539a55a/01.intent.json',
    'query_id': '5add74b75542992200553b24', 'family': 'semantic_fluent_false_evidence',
    'intensity': 1, 'seed': 42, 'candidate_band': 1, 'runtime_seed': 94494956,
    'model_repository': 'mlx-community/Qwen2.5-7B-Instruct-4bit',
    'model_revision': 'c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed', 'max_tokens': 150,
}
POLICY = {'original_physical_call': 'indeterminate', 'replacement_maximum': 1,
          'extra_physical_call_allowance': 1, 'replacement_is_original': False,
          'interruption': 'halt-no-regeneration', 'logical_quality_attempt_limit': 2,
          'additional_quality_repair_calls': 0}
EXECUTOR_FILES = (
    'src/experiments/seed42_intent_recovery.py',
    'src/experiments/single_intent_recovery.py',
    'src/experiments/execution_reliability.py',
    'src/experiments/week9_construction.py', 'src/evaluation/qa_records.py',
    'scripts/recover_hotpotqa_seed42_intent.py',
    'tools/supervise_source_selection_candidates.py',
)


def executor_binding():
    return {'commit': git(ROOT, 'rev-parse', 'HEAD'),
            'clean': not bool(git(ROOT, 'status', '--porcelain', '--untracked-files=all')),
            'files_sha256': {p: sha(ROOT / p) for p in EXECUTOR_FILES}}


def environment():
    return {'python': sys.version, **{p: importlib.metadata.version(p) for p in
            ('numpy', 'torch', 'transformers', 'sentence-transformers', 'datasets', 'mlx', 'mlx-lm')}}


def _plain_path(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlink in protected path')
    return path


def _model_binding(path, repository):
    # Hash bytes only; never initialize a tokenizer, model or MLX runtime.
    path = Path(path)
    if path.parent.name != 'snapshots' or path.parent.parent.name != 'models--' + repository.replace('/', '--'):
        raise ValueError('Model snapshot repository path mismatch')
    return {'repository': repository, 'revision': path.name,
            'files_sha256': {p.relative_to(path).as_posix(): sha(p)
                             for p in sorted(path.rglob('*')) if p.is_file()}}


def bindings():
    for path in (PROTOCOL, CANDIDATES, FROZEN, RECOVERY):
        _plain_path(path)
    if sha(PROTOCOL) != INCIDENT['protocol_sha256']:
        raise ValueError('Protocol SHA mismatch')
    protocol = reliable.read(PROTOCOL)
    if protocol['source'] != INCIDENT['source']:
        raise ValueError('Frozen source identity mismatch')
    if git(FROZEN, 'status', '--porcelain', '--untracked-files=all'):
        raise ValueError('Frozen source is dirty')
    paths = git(FROZEN, 'ls-files').splitlines()
    code = {p: sha(FROZEN / p) for p in paths
            if (p.startswith(('src/', 'scripts/')) and p.endswith('.py')) or p == 'run.py'}
    if {'git_commit_sha': git(FROZEN, 'rev-parse', 'HEAD'), 'code_fingerprint': fingerprint(code)} != INCIDENT['source']:
        raise ValueError('Frozen source commit/code mismatch')
    model = protocol['model']
    if model['repository'] != INCIDENT['model_repository'] or model['revision'] != INCIDENT['model_revision']:
        raise ValueError('Model revision/repository mismatch')
    if _model_binding(MODEL, model['repository']) != model:
        raise ValueError('Model file hashes mismatch')
    if environment() != protocol['environment']:
        raise ValueError('Frozen environment mismatch')
    if protocol['execution']['unresolved_intent'] != 'halt-no-regeneration':
        raise ValueError('Frozen execution policy mismatch')
    if protocol['planned_outputs']['candidates'] != str(CANDIDATES):
        raise ValueError('Frozen candidate namespace mismatch')
    return protocol, _request(protocol)


def _request(protocol=None):
    protocol = protocol or reliable.read(PROTOCOL)
    model = protocol['model']
    request = reliable.read(CANDIDATES / INCIDENT['intent_relative'])
    if sha(CANDIDATES / INCIDENT['intent_relative']) != INCIDENT['intent_sha256']:
        raise ValueError('Intent SHA mismatch')
    if fingerprint(request) != INCIDENT['request_fingerprint']:
        raise ValueError('Request fingerprint mismatch')
    expected = {k: INCIDENT[k] for k in ('query_id', 'family', 'intensity', 'seed', 'candidate_band')}
    expected.update(protocol_sha256=INCIDENT['protocol_sha256'], model=model)
    if request['provenance'] != expected or request['max_tokens'] != INCIDENT['max_tokens'] or request['context'] != {}:
        raise ValueError('Request incident identity mismatch')
    return request


def _owned_model_lease(path):
    handle = reliable._MODEL_LEASE
    return handle is not None and not handle.closed and os.fstat(handle.fileno()).st_ino == path.stat().st_ino


def probe_lock(path):
    path = _plain_path(path)
    if not path.exists():
        return
    if path == MODEL_LOCK and _owned_model_lease(path):
        return
    with path.open('rb') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Active writer lock: ' + str(path)) from None
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def check_workers():
    output = subprocess.check_output(['ps', '-axo', 'pid=,command='], text=True)
    for line in output.splitlines():
        pid, _, command = line.strip().partition(' ')
        if pid == str(os.getpid()):
            continue
        if ('run_source_selection_transfer.py' in command and 'candidates' in command
                or 'supervise_source_selection_candidates.py' in command):
            raise RuntimeError('Active candidate worker/supervisor: ' + pid)


def quiescent(include_supervisors=True):
    probe_lock(CANDIDATES.with_name(CANDIDATES.name + '.writer.lock'))
    probe_lock(MODEL_LOCK)
    if include_supervisors:
        for path in SUPERVISOR_LOCKS:
            probe_lock(path)
        check_workers()


@contextlib.contextmanager
def writer():
    quiescent()
    path = CANDIDATES.with_name(CANDIDATES.name + '.writer.lock')
    with path.open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Active candidate writer') from None
        yield


def _namespace():
    _plain_path(RECOVERY)
    external_output(RECOVERY, PROTOCOL, FROZEN)
    if RECOVERY.exists():
        allowed = {'replacement.intent.json', 'replacement.response.json', 'replacement.error.json'}
        if any(p.is_symlink() or not p.is_file() or p.name not in allowed for p in RECOVERY.iterdir()):
            raise ValueError('Unexpected recovery namespace contents')


def _plan(plan, pin=None, committed=False):
    expected = {'schema', 'incident', 'policy', 'paths', 'executor', 'parent_files_sha256'}
    if set(plan) != expected or plan['schema'] != SCHEMA or plan['incident'] != INCIDENT or plan['policy'] != POLICY:
        raise ValueError('Single incident authorization mismatch')
    if plan['paths'] != {k: str(v) for k, v in
                         [('protocol', PROTOCOL), ('candidates', CANDIDATES), ('frozen', FROZEN),
                          ('model', MODEL), ('recovery', RECOVERY)]}:
        raise ValueError('Fixed namespace mismatch')
    if fingerprint(plan['parent_files_sha256']) != INCIDENT['inventory_fingerprint']:
        raise ValueError('Inventory authorization mismatch')
    if plan['executor'] != executor_binding() or committed and not plan['executor']['clean']:
        raise ValueError('Executor provenance/cleanliness mismatch')
    if pin is not None and fingerprint_bytes(plan) != pin:
        raise ValueError('Proposal SHA mismatch')
    _namespace()
    return bindings()


def response_path():
    return CANDIDATES / INCIDENT['intent_relative'].replace('.intent.json', '.response.json')


def _parent(plan, receipt=None, continuation=False):
    current = inventory(CANDIDATES)
    baseline = plan['parent_files_sha256']
    if any(current.get(k) != v for k, v in baseline.items()):
        raise ValueError('Protected execution-store mutation')
    extras = set(current) - set(baseline)
    rel = response_path().relative_to(CANDIDATES).as_posix()
    if rel in extras:
        if receipt is None or reliable.read(response_path()) != receipt:
            raise ValueError('Conflicting original response/resolution')
        extras.remove(rel)
    if extras and not continuation:
        raise ValueError('Unexpected execution-store addition')
    # Continued frozen outputs may be added, but no unrelated receipts are allowed.
    for relpath in extras:
        if not (relpath.startswith(('calls/', 'query-checkpoints/', 'candidates/')) and relpath.endswith('.json')
                or relpath == 'candidates.complete.json'):
            raise ValueError('Unexpected continuation artifact')
        path = CANDIDATES / relpath
        if path.suffix == '.json':
            obj = reliable.read(path)
            if not isinstance(obj, dict):
                raise ValueError('Unexpected continuation record')
            if 'recovery' in obj or obj.get('execution', {}).get('kind') == 'explicit_replacement_resolution':
                raise ValueError('Unrelated recovery receipt forbidden')
            _continuation_record(relpath, obj)
    return current


def _continuation_record(relpath, obj):
    """Only frozen candidate-stage artifact shapes may extend the pinned baseline."""
    parts = Path(relpath).parts
    if parts[0] == 'calls':
        if len(parts) != 5 or not parts[-1].endswith(('.intent.json', '.response.json')):
            raise ValueError('Unexpected continuation journal path')
        if parts[-1].endswith('.intent.json'):
            provenance = obj.get('provenance', {})
            expected_cell = '{}.intensity-{}.seed-{}'.format(
                provenance.get('family'), provenance.get('intensity'), provenance.get('seed'))
            query = provenance.get('query_id', '')
            if (provenance.get('protocol_sha256') != INCIDENT['protocol_sha256']
                    or provenance.get('model') != reliable.read(PROTOCOL)['model']
                    or parts[1] != expected_cell or parts[2] != str(provenance.get('candidate_band'))
                    or parts[3] != hashlib.sha256(query.encode()).hexdigest()
                    or parts[-1] not in ('00.intent.json', '01.intent.json')
                    or obj.get('max_tokens') != INCIDENT['max_tokens']):
                raise ValueError('Continuation journal identity mismatch')
    elif parts[0] == 'query-checkpoints':
        binding = obj.get('binding', {})
        data = obj.get('data', {})
        query = data.get('query_id', '')
        cell = '{}.intensity-{}.seed-{}'.format(binding.get('family'), binding.get('intensity'), binding.get('seed'))
        expected = ('query-checkpoints', cell, str(binding.get('band')),
                    hashlib.sha256(query.encode()).hexdigest() + '.json')
        if (parts != expected or obj.get('schema') != reliable.VERSION
                or binding.get('protocol_sha256') != INCIDENT['protocol_sha256']
                or data.get('candidate_band') != binding.get('band')
                or data.get('selection') != binding.get('choice')
                or obj.get('data_sha256') != fingerprint(data)):
            raise ValueError('Continuation checkpoint integrity/identity mismatch')
    elif parts[0] == 'candidates':
        if len(parts) != 3 or parts[-1] not in ('0.json', '1.json', '2.json') or not isinstance(obj.get('records'), list):
            raise ValueError('Unexpected continuation ledger')
    elif relpath == 'candidates.complete.json':
        if obj.get('protocol_sha256') != INCIDENT['protocol_sha256'] or not isinstance(obj.get('files_sha256'), dict):
            raise ValueError('Unexpected continuation completion marker')


def prepare():
    """Return proposal only. No output, lock creation or generator initialization."""
    quiescent()
    bindings()
    _namespace()
    if RECOVERY.exists():
        raise ValueError('Recovery namespace already exists; no fresh-namespace retry')
    parent = inventory(CANDIDATES)
    if fingerprint(parent) != INCIDENT['inventory_fingerprint']:
        raise ValueError('Execution inventory changed since forensic audit')
    plan = {'schema': SCHEMA, 'incident': dict(INCIDENT), 'policy': dict(POLICY),
            'paths': {k: str(v) for k, v in [('protocol', PROTOCOL), ('candidates', CANDIDATES),
                      ('frozen', FROZEN), ('model', MODEL), ('recovery', RECOVERY)]},
            'executor': executor_binding(), 'parent_files_sha256': parent}
    unresolved = []
    for path in CANDIDATES.rglob('*.intent.json'):
        if not path.with_name(path.name.replace('.intent.json', '.response.json')).exists():
            unresolved.append(path.relative_to(CANDIDATES).as_posix())
    if unresolved != [INCIDENT['intent_relative']]:
        raise ValueError('Unexpected unresolved incident set')
    # Validate all complete journal/checkpoint records without disguising the one
    # indeterminate call. No validator exemption is used for execution/resume.
    for path in CANDIDATES.rglob('*.json'):
        obj = reliable.read(path)
        if not isinstance(obj, dict):
            continue
        if 'data_sha256' in obj and obj['data_sha256'] != fingerprint(obj.get('data')):
            raise ValueError('Checkpoint corruption')
        if path.name.endswith('.response.json'):
            request = reliable.read(path.with_name(path.name.replace('.response.json', '.intent.json')))
            _generation(obj, request)
            if obj['request_fingerprint'] != fingerprint(request) or 'error' in obj:
                raise ValueError('Completed journal corruption')
    _plan(plan)
    _parent(plan)
    quiescent()
    return plan


def _generation(obj, request):
    g = obj['generation']
    validate_qa(g, g['extracted_answer'])
    if g['prompt'] != request['prompt'] or obj['generation_sha256'] != fingerprint(g):
        raise ValueError('Generation content/prompt mismatch')


def approve(plan, pin, request_pin, allowance, approval, stage):
    if stage not in ('execute', 'publish') or approval != stage or request_pin != INCIDENT['request_fingerprint'] or type(allowance) is not int or allowance != 1:
        raise ValueError('Separate explicit stage/request/one-call approval required')
    return _plan(plan, pin, committed=True)


def replacement_intent(plan, pin):
    return {'schema': SCHEMA, 'proposal_sha256': pin, 'request': _request(),
            'runtime_seed': INCIDENT['runtime_seed'], 'physical_attempt': 'replacement-1',
            'original_physical_call': 'indeterminate', 'executor': plan['executor'],
            'execution_approval': {'stage': 'execute', 'request_fingerprint': INCIDENT['request_fingerprint'],
                                   'extra_physical_call_allowance': 1}}


ACCOUNTING = {'original_indeterminate': 1, 'replacement_completed': 1,
              'conservative_physical_dispatch_count': 2}


def replacement(plan, pin):
    _namespace()
    intent = RECOVERY / 'replacement.intent.json'
    response = RECOVERY / 'replacement.response.json'
    if not intent.exists() or reliable.read(intent) != replacement_intent(plan, pin):
        raise ValueError('Replacement intent/provenance mismatch')
    if (RECOVERY / 'replacement.error.json').exists() or not response.exists():
        raise RuntimeError('Interrupted/failed replacement; no retry permitted')
    obj = reliable.read(response)
    if set(obj) != {'schema', 'proposal_sha256', 'intent_sha256', 'generation', 'generation_sha256', 'physical_call_accounting'}:
        raise ValueError('Replacement response schema mismatch')
    if obj['schema'] != SCHEMA or obj['proposal_sha256'] != pin or obj['intent_sha256'] != sha(intent) or obj['physical_call_accounting'] != ACCOUNTING:
        raise ValueError('Replacement provenance/accounting mismatch')
    _generation(obj, _request())
    return obj


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def execute(plan, pin, request_pin, allowance, approval, backend_factory, seed, capture):
    approve(plan, pin, request_pin, allowance, approval, 'execute')
    with writer():
        _plan(plan, pin, committed=True)
        _parent(plan)
        _namespace()
        # Existence is terminal even after successful capture. Execution never replays
        # or creates another physical call; publication/verification are distinct.
        if RECOVERY.exists():
            raise RuntimeError('Replacement already claimed; no second execution')
        reliable.acquire_model_lease(MODEL_LOCK)
        # Claim the single fixed namespace exclusively and fsync every newly
        # created directory entry. Even an empty/partial claim is terminal.
        missing = []
        parent = RECOVERY.parent
        while not parent.exists():
            missing.append(parent)
            parent = parent.parent
        for directory in reversed(missing):
            directory.mkdir()
            _sync_directory(directory.parent)
        RECOVERY.mkdir()  # EEXIST refuses concurrent or interrupted claims.
        _sync_directory(RECOVERY.parent)
        reliable.atomic(RECOVERY / 'replacement.intent.json', replacement_intent(plan, pin))
        try:
            backend = backend_factory()
            seed(INCIDENT['runtime_seed'])
            _, generation = capture(backend, _request()['prompt'], INCIDENT['max_tokens'])
            obj = {'schema': SCHEMA, 'proposal_sha256': pin,
                   'intent_sha256': sha(RECOVERY / 'replacement.intent.json'), 'generation': generation,
                   'generation_sha256': fingerprint(generation), 'physical_call_accounting': ACCOUNTING}
            _generation(obj, _request())
            reliable.atomic(RECOVERY / 'replacement.response.json', obj)
        except BaseException as error:
            # SIGKILL/power loss may skip this; the durable intent still forbids retry.
            if not (RECOVERY / 'replacement.response.json').exists():
                reliable.atomic(RECOVERY / 'replacement.error.json', {
                    'schema': SCHEMA, 'error_type': type(error).__name__,
                    'physical_completion': 'indeterminate', 'retry_allowed': False})
            raise
    return {'status': 'replacement_saved_separately', 'new_backend_calls': 1}


def receipt(plan, pin):
    obj = replacement(plan, pin)
    return {'request_fingerprint': INCIDENT['request_fingerprint'], 'generation': obj['generation'],
            'generation_sha256': obj['generation_sha256'],
            'execution': {'kind': 'explicit_replacement_resolution', 'backend_call_executed': False},
            'recovery': {'schema': SCHEMA, 'is_original_response': False,
                         'original_physical_call': 'indeterminate', 'original_intent_sha256': INCIDENT['intent_sha256'],
                         'proposal_sha256': pin, 'replacement_response': str(RECOVERY / 'replacement.response.json'),
                         'replacement_response_sha256': sha(RECOVERY / 'replacement.response.json'),
                         'physical_call_accounting': ACCOUNTING,
                         'publication_approval': {'stage': 'publish',
                             'request_fingerprint': INCIDENT['request_fingerprint'],
                             'extra_physical_call_allowance': 1},
                         'scientific_disclosure_required': True}}


def publish(plan, pin, request_pin, allowance, approval):
    approve(plan, pin, request_pin, allowance, approval, 'publish')
    with writer():
        _plan(plan, pin, committed=True)
        resolution = receipt(plan, pin)
        _parent(plan, resolution)
        reliable.once(response_path(), resolution)
    return {'status': 'labeled_resolution_published', 'new_backend_calls': 0}


def verify(plan, pin):
    """Read-only full evidence validation; never creates a verification token."""
    quiescent(include_supervisors=False)
    _plan(plan, pin, committed=True)
    resolution = receipt(plan, pin)
    before = _parent(plan, resolution, continuation=True)
    if reliable.read(response_path()) != resolution:
        raise ValueError('Missing or conflicting labeled resolution')
    reliable.validate_store(CANDIDATES)  # Unrelated unresolved intents/corruption still fail.
    if inventory(CANDIDATES) != before:
        raise ValueError('Execution store changed during verification')
    quiescent(include_supervisors=False)
    counts = reliable.accounting(CANDIDATES)
    return {'status': 'verified_seed42_replacement_not_original', 'proposal_sha256': pin,
            'base_recorded_completed_calls': counts['actual_backend_calls'],
            'separate_replacement_completed_calls': 1, 'original_indeterminate_calls': 1,
            'conservative_physical_count': counts['actual_backend_calls'] + 2,
            'logical_quality_attempt_limit': 2, 'additional_quality_repair_calls': 0}
