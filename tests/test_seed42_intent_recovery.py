"""Synthetic-only recovery evidence; never import MLX or dispatch a real model."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from src.experiments import seed42_intent_recovery as recovery
from src.experiments import single_intent_recovery as legacy
from src.experiments import execution_reliability as reliable
from src.evaluation.qa_records import capture_generation
from src.pipelines.generator import GenerationResult


@pytest.fixture
def incident(tmp_path, monkeypatch):
    candidates = tmp_path / 'experiment/transfer/execution/candidates'
    protocol_path = candidates.parent.parent / 'protocol.json'
    frozen = tmp_path / 'frozen'
    frozen.mkdir()
    (frozen / 'run.py').write_text('# frozen synthetic scientific code\n')
    model = tmp_path / 'models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots' / recovery.INCIDENT['model_revision']
    model.mkdir(parents=True)
    (model / 'config.json').write_text('{}')
    (model / 'model.safetensors').write_bytes(b'synthetic fixture, not model weights')
    source = {'git_commit_sha': 'fixture-source', 'code_fingerprint': recovery.fingerprint({'run.py': recovery.sha(frozen / 'run.py')})}
    protocol = {'source': source, 'model': recovery._model_binding(model, recovery.INCIDENT['model_repository']),
                'environment': {'fixture': True}, 'execution': {'unresolved_intent': 'halt-no-regeneration'},
                'planned_outputs': {'candidates': str(candidates)},
                'binding': {'matrix': [['semantic_fluent_false_evidence', 1, 42],
                                       ['semantic_fluent_false_evidence', 3, 42]],
                            'query_ids': [recovery.INCIDENT['query_id'], 'later-query']}}
    reliable.atomic(protocol_path, protocol)
    identity = copy.deepcopy(recovery.INCIDENT)
    identity.update(source=source, protocol_sha256=recovery.sha(protocol_path))
    request = {'prompt': 'Exact synthetic revision prompt.', 'max_tokens': 150, 'context': {},
               'provenance': {k: identity[k] for k in ('query_id', 'family', 'intensity', 'seed', 'candidate_band')}}
    request['provenance'].update(model=protocol['model'], protocol_sha256=identity['protocol_sha256'])
    intent = candidates / identity['intent_relative']
    reliable.atomic(intent, request)
    identity.update(intent_sha256=recovery.sha(intent), request_fingerprint=recovery.fingerprint(request))
    class Backend:
        calls = 0
        failure = None
        def generate(self, prompt, max_tokens):
            self.calls += 1
            assert prompt == request['prompt'] and max_tokens == 150
            if self.failure:
                raise self.failure
            return GenerationResult('Synthetic replacement evidence.', .1, 5, 3)
    # One completed predecessor, in the same immutable incident journal.
    prior = {**request, 'prompt': 'Earlier synthetic prompt.'}
    class PriorBackend:
        def generate(self, prompt, max_tokens):
            return GenerationResult('Earlier response.', .1, 4, 2)
    _, generation = capture_generation(PriorBackend(), prior['prompt'], 150)
    reliable.atomic(intent.with_name('00.intent.json'), prior)
    reliable.atomic(intent.with_name('00.response.json'), {
        'request_fingerprint': recovery.fingerprint(prior), 'generation': generation,
        'generation_sha256': recovery.fingerprint(generation)})
    reliable.atomic(candidates / 'query-checkpoints/completed.json', {
        'schema': reliable.VERSION, 'binding': {}, 'data': {'fixture': True},
        'data_sha256': recovery.fingerprint({'fixture': True})})
    identity['inventory_fingerprint'] = recovery.fingerprint(recovery.inventory(candidates))
    for key, value in {'CANDIDATES': candidates, 'PROTOCOL': protocol_path, 'FROZEN': frozen,
                       'MODEL': model, 'RECOVERY': tmp_path / 'replacement', 'INCIDENT': identity,
                       'RESEARCH': tmp_path / 'experiment', 'MODEL_LOCK': tmp_path / 'model.lock',
                       'SUPERVISOR_LOCKS': (tmp_path / 'supervisor.lock',)}.items():
        monkeypatch.setattr(recovery, key, value)
    monkeypatch.setattr(recovery, 'environment', lambda: protocol['environment'])
    monkeypatch.setattr(recovery, 'git', lambda root, *args:
        '' if args[0] == 'status' else 'run.py' if args[0] == 'ls-files' else 'fixture-source')
    binding = {'commit': 'fixture-executor', 'clean': True, 'files_sha256': {'fixture': 'hash'}}
    monkeypatch.setattr(recovery, 'executor_binding', lambda: copy.deepcopy(binding))
    monkeypatch.setattr(recovery, 'check_workers', lambda: None)
    monkeypatch.setattr(reliable, '_MODEL_LEASE', None)
    backend = Backend()
    factory_calls = []
    seeds = []
    def factory():
        factory_calls.append(True)
        return backend
    plan = recovery.prepare()
    pin = recovery.fingerprint_bytes(plan)
    def execute():
        return recovery.execute(plan, pin, identity['request_fingerprint'], 1, 'execute', factory, seeds.append, capture_generation)
    def publish():
        return recovery.publish(plan, pin, identity['request_fingerprint'], 1, 'publish')
    fixture = SimpleNamespace(plan=plan, pin=pin, backend=backend, execute=execute, publish=publish,
                              intent=intent, factory_calls=factory_calls, seeds=seeds, binding=binding,
                              protocol=protocol, request=request)
    yield fixture
    if reliable._MODEL_LEASE is not None:
        reliable._MODEL_LEASE.close()
        reliable._MODEL_LEASE = None


def test_production_identity_and_legacy_authorization_are_separate():
    assert recovery.INCIDENT['protocol_sha256'] == '94e4b6d8fb49a7e662074fb766c92498ad0667abf9cf38233e0f49aa401183aa'
    assert recovery.INCIDENT['intent_sha256'] == '8765ff8b160155529aa75d89385e96357adae7b5663b85768dbb7fcdd8e7769f'
    assert recovery.INCIDENT['request_fingerprint'] == '6fca4964d2548ff495909c4e47a1233836cd6099d148c9b034099d86735e6c76'
    assert recovery.INCIDENT['inventory_fingerprint'] == '747657ff5d89a088ce7dcff92910bd3b8230f3343e49e4f6b97acf1fc3b08561'
    assert recovery.INCIDENT['source']['git_commit_sha'] == '9a937afbd94b5a46394b5724a6be2d571d2e0c19'
    assert recovery.INCIDENT['runtime_seed'] == 94494956
    assert recovery.INCIDENT['intent_relative'].endswith('/01.intent.json')
    assert legacy.INCIDENT['request_fingerprint'] == 'dec08535d5e02ffaa9838f4f35ca3061c3c7b530d550a3c90c4ddda31e22f9ec'
    assert legacy.INCIDENT['runtime_seed'] == 3215750484


def test_lifecycle_preserves_original_journal_and_distinguishes_physical_calls(incident):
    f = incident
    before = recovery.inventory(recovery.CANDIDATES)
    assert f.execute()['new_backend_calls'] == 1
    assert f.backend.calls == 1 and f.seeds == [94494956]
    assert recovery.inventory(recovery.CANDIDATES) == before
    assert not recovery.response_path().exists()
    with pytest.raises(RuntimeError, match='Unresolved'):
        reliable.validate_store(recovery.CANDIDATES)
    f.publish()
    resolution = reliable.read(recovery.response_path())
    assert resolution['recovery']['is_original_response'] is False
    assert resolution['recovery']['original_physical_call'] == 'indeterminate'
    assert resolution['execution']['backend_call_executed'] is False
    assert all(recovery.sha(recovery.CANDIDATES / k) == v for k, v in before.items())
    # This demonstrates the frozen validator's structural compatibility, not
    # recovery provenance validation: only the external verifier supplies that.
    reliable.validate_store(recovery.CANDIDATES)
    result = recovery.verify(f.plan, f.pin)
    assert result['base_recorded_completed_calls'] == 1
    assert result['separate_replacement_completed_calls'] == 1
    assert result['conservative_physical_count'] == 3
    f.publish()  # Idempotent publication never dispatches.
    assert f.backend.calls == 1


@pytest.mark.parametrize('field', ['protocol_sha256', 'intent_sha256', 'request_fingerprint',
    'query_id', 'candidate_band', 'model_revision', 'source', 'inventory_fingerprint', 'runtime_seed'])
def test_proposal_identity_substitution_is_rejected(incident, field):
    f = incident
    f.plan['incident'][field] = 'substitution'
    with pytest.raises(ValueError, match='authorization'):
        f.execute()
    assert f.backend.calls == 0 and not recovery.RECOVERY.exists()


@pytest.mark.parametrize('where', ['protocol', 'intent', 'checkpoint', 'addition'])
def test_actual_store_or_protocol_mutation_blocks_dispatch(incident, where):
    f = incident
    path = {'protocol': recovery.PROTOCOL, 'intent': f.intent,
            'checkpoint': recovery.CANDIDATES / 'query-checkpoints/completed.json',
            'addition': recovery.CANDIDATES / 'unexpected.json'}[where]
    path.write_text('{}')
    with pytest.raises(ValueError):
        f.execute()
    assert f.backend.calls == 0


@pytest.mark.parametrize('field', ['query_id', 'candidate_band', 'seed', 'model'])
def test_request_identity_checked_even_if_hash_constants_are_rebound_in_fixture(incident, field, monkeypatch):
    f = incident
    request = copy.deepcopy(f.request)
    request['provenance'][field] = 'wrong'
    f.intent.write_text(json.dumps(request))
    monkeypatch.setitem(recovery.INCIDENT, 'intent_sha256', recovery.sha(f.intent))
    monkeypatch.setitem(recovery.INCIDENT, 'request_fingerprint', recovery.fingerprint(request))
    with pytest.raises(ValueError, match='identity'):
        recovery.bindings()
    assert f.backend.calls == 0


@pytest.mark.parametrize('field', ['revision', 'source', 'model_bytes', 'source_bytes', 'source_commit', 'dirty_source', 'environment', 'namespace'])
def test_frozen_bindings_fail_closed(incident, field, monkeypatch):
    f = incident
    if field == 'revision':
        f.protocol['model']['revision'] = 'wrong'
    elif field == 'source':
        f.protocol['source'] = {'git_commit_sha': 'wrong'}
    elif field == 'namespace':
        f.protocol['planned_outputs']['candidates'] = '/wrong'
    elif field == 'model_bytes':
        (recovery.MODEL / 'model.safetensors').write_bytes(b'changed')
    elif field == 'source_bytes':
        (recovery.FROZEN / 'run.py').write_text('# changed')
    elif field in ('source_commit', 'dirty_source'):
        old = recovery.git
        monkeypatch.setattr(recovery, 'git', lambda root, *args:
            'wrong' if args[0] == ('rev-parse' if field == 'source_commit' else 'status') else old(root, *args))
    elif field == 'environment':
        monkeypatch.setattr(recovery, 'environment', lambda: {'wrong': True})
    if field in ('revision', 'source', 'namespace'):
        recovery.PROTOCOL.write_text(json.dumps(f.protocol))
        monkeypatch.setitem(recovery.INCIDENT, 'protocol_sha256', recovery.sha(recovery.PROTOCOL))
    with pytest.raises(ValueError):
        recovery.bindings()
    assert f.backend.calls == 0


@pytest.mark.parametrize('stage,approval', [('execute', None), ('execute', 'publish'), ('publish', None), ('publish', 'execute')])
def test_execution_and_publication_require_independent_approvals(incident, stage, approval):
    f = incident
    with pytest.raises(ValueError, match='approval'):
        recovery.approve(f.plan, f.pin, recovery.INCIDENT['request_fingerprint'], 1, approval, stage)
    assert f.backend.calls == 0


@pytest.mark.parametrize('pin,request_pin,allowance', [('wrong', 'correct', 1), ('correct', 'wrong', 1),
    ('correct', 'correct', 0), ('correct', 'correct', 2), ('correct', 'correct', True)])
def test_pins_and_physical_allowance_required(incident, pin, request_pin, allowance):
    f = incident
    with pytest.raises(ValueError):
        recovery.approve(f.plan, f.pin if pin == 'correct' else pin,
            recovery.INCIDENT['request_fingerprint'] if request_pin == 'correct' else request_pin,
            allowance, 'execute', 'execute')
    assert f.backend.calls == 0


@pytest.mark.parametrize('failure', [KeyboardInterrupt(), RuntimeError('backend failed')])
def test_interrupted_replacement_is_terminal(incident, failure):
    f = incident
    f.backend.failure = failure
    with pytest.raises(type(failure)):
        f.execute()
    assert (recovery.RECOVERY / 'replacement.intent.json').exists()
    f.backend.failure = None
    with pytest.raises(RuntimeError, match='already claimed'):
        f.execute()
    with pytest.raises(RuntimeError, match='no retry'):
        f.publish()
    assert f.backend.calls == len(f.factory_calls) == 1
    assert not recovery.response_path().exists()


def test_successful_replacement_cannot_be_dispatched_twice(incident):
    f = incident
    f.execute()
    with pytest.raises(RuntimeError, match='already claimed'):
        f.execute()
    assert f.backend.calls == 1


def test_killed_process_claim_and_partial_atomic_debris_block_retry(incident):
    f = incident
    reliable.atomic(recovery.RECOVERY / 'replacement.intent.json', recovery.replacement_intent(f.plan, f.pin))
    with pytest.raises(RuntimeError, match='already claimed'):
        f.execute()
    with pytest.raises(RuntimeError, match='no retry'):
        f.publish()
    assert f.backend.calls == 0
    (recovery.RECOVERY / '.atomic-partial').write_text('incomplete')
    with pytest.raises(ValueError, match='namespace'):
        f.execute()


@pytest.mark.parametrize('target', ['stage', 'model', 'supervisor'])
def test_concurrent_lock_blocks_prepare_and_dispatch(incident, target):
    import fcntl
    path = {'stage': recovery.CANDIDATES.with_name('candidates.writer.lock'),
            'model': recovery.MODEL_LOCK, 'supervisor': recovery.SUPERVISOR_LOCKS[0]}[target]
    with path.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match='lock'):
            recovery.prepare()
        with pytest.raises(RuntimeError, match='lock'):
            incident.execute()
    assert incident.backend.calls == 0


def test_process_check_blocks_unlocked_worker(incident, monkeypatch):
    # Restore the actual detector, while only mocking the OS process listing.
    spec = importlib.util.spec_from_file_location('detector', Path(recovery.__file__))
    detector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(detector)
    monkeypatch.setattr(detector.subprocess, 'check_output', lambda *a, **k:
        '123456 python run_source_selection_transfer.py candidates\n')
    with pytest.raises(RuntimeError, match='worker'):
        detector.check_workers()


@pytest.mark.parametrize('field', ['original_physical_call', 'is_original_response', 'replacement_response_sha256', 'proposal_sha256'])
def test_structurally_compatible_receipt_is_not_sufficient_for_verification(incident, field):
    f = incident
    f.execute(); f.publish()
    obj = reliable.read(recovery.response_path())
    obj['recovery'][field] = 'tampered'
    recovery.response_path().write_text(json.dumps(obj))
    reliable.validate_store(recovery.CANDIDATES)  # Legacy reader does not check recovery provenance.
    with pytest.raises(ValueError):
        recovery.verify(f.plan, f.pin)
    assert f.backend.calls == 1


@pytest.mark.parametrize('where', ['replacement_intent', 'replacement_response', 'original', 'checkpoint',
                                   'unrelated_intent', 'unrelated_receipt', 'unknown_artifact'])
def test_verification_preserves_unrelated_fail_closed_guards(incident, where):
    f = incident
    f.execute(); f.publish()
    if where == 'replacement_intent':
        path = recovery.RECOVERY / 'replacement.intent.json'
    elif where == 'replacement_response':
        path = recovery.RECOVERY / 'replacement.response.json'
    elif where == 'original':
        path = f.intent
    elif where == 'checkpoint':
        path = recovery.CANDIDATES / 'query-checkpoints/completed.json'
    elif where == 'unrelated_intent':
        path = recovery.CANDIDATES / 'calls/later.intent.json'
    elif where == 'unrelated_receipt':
        path = recovery.CANDIDATES / 'calls/later.response.json'
    else:
        path = recovery.CANDIDATES / 'arbitrary.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'recovery': {}}) if where == 'unrelated_receipt' else '{}')
    with pytest.raises((ValueError, RuntimeError, KeyError)):
        recovery.verify(f.plan, f.pin)
    assert f.backend.calls == 1


def test_preparation_and_verification_are_read_only_and_do_not_generate(incident):
    f = incident
    before = recovery.inventory(recovery.CANDIDATES)
    recovery.prepare()
    assert recovery.inventory(recovery.CANDIDATES) == before and f.backend.calls == 0
    assert not recovery.RECOVERY.exists()
    f.execute(); f.publish()
    before = recovery.inventory(recovery.CANDIDATES)
    recovery.verify(f.plan, f.pin)
    assert f.backend.calls == 1 and recovery.inventory(recovery.CANDIDATES) == before


def test_existing_original_response_is_never_overwritten(incident):
    f = incident
    f.execute()
    recovery.response_path().write_text('{"original": "conflict"}')
    before = recovery.response_path().read_bytes()
    with pytest.raises(ValueError):
        f.publish()
    assert recovery.response_path().read_bytes() == before


def test_uncommitted_executor_and_new_namespace_refused(incident, monkeypatch):
    f = incident
    f.binding['clean'] = False
    f.plan['executor']['clean'] = False
    with pytest.raises(ValueError, match='Executor'):
        f.execute()
    f.binding['clean'] = f.plan['executor']['clean'] = True
    monkeypatch.setattr(recovery, 'RECOVERY', recovery.RECOVERY.with_name('another'))
    with pytest.raises(ValueError, match='namespace'):
        f.execute()
    assert f.backend.calls == 0


def test_import_does_not_import_mlx_or_initialize_backend():
    code = """
import importlib.abc, sys
class NoMLX(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname == 'mlx' or fullname.startswith(('mlx.', 'mlx_lm')):
            raise AssertionError('MLX import forbidden')
sys.meta_path.insert(0, NoMLX())
from src.experiments import seed42_intent_recovery
assert not any(k == 'mlx' or k.startswith(('mlx.', 'mlx_lm')) for k in sys.modules)
"""
    subprocess.run([sys.executable, '-B', '-c', code], check=True)


def load_supervisor():
    file = Path(__file__).resolve().parents[1] / 'tools/supervise_source_selection_candidates.py'
    spec = importlib.util.spec_from_file_location('seed42_supervisor', file)
    sup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sup)
    return sup


def test_supervisor_missing_plan_stops_before_preflight_or_launch(monkeypatch):
    sup = load_supervisor()
    monkeypatch.setattr(sup, 'preflight', lambda: pytest.fail('preflight before recovery gate'))
    monkeypatch.setattr(sup, 'launch_captured', lambda cmd: pytest.fail('worker launched'))
    with pytest.raises(RuntimeError, match='recovery verification'):
        sup.run(SimpleNamespace(dry_run=True))


def test_supervisor_propagates_failed_verification_before_launch(monkeypatch):
    sup = load_supervisor()
    monkeypatch.setattr(sup, 'preflight', lambda: pytest.fail('gate was bypassed'))
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])
    monkeypatch.setattr(sup.subprocess, 'run', fail)
    with pytest.raises(subprocess.CalledProcessError):
        sup.run(SimpleNamespace(recovery_plan=Path('/synthetic/plan'), recovery_plan_sha256='bad', dry_run=True))


def test_supervisor_gate_invokes_full_verifier_with_exact_plan_pin(monkeypatch):
    sup = load_supervisor()
    commands = []
    monkeypatch.setattr(sup.subprocess, 'run', lambda cmd, **kw: commands.append((cmd, kw)))
    sup.recovery_gate(SimpleNamespace(recovery_plan=Path('/synthetic/plan'), recovery_plan_sha256='pin'))
    cmd, kw = commands[0]
    assert cmd[0] == str(sup.PYTHON) and cmd[2].endswith('recover_hotpotqa_seed42_intent.py')
    assert cmd[3:] == ['verify', '--plan', '/synthetic/plan', '--plan-sha256', 'pin']
    assert kw['check'] is True


def test_supervisor_rechecks_real_evidence_before_every_batch(incident, monkeypatch, tmp_path):
    f = incident
    sup = load_supervisor()
    args = SimpleNamespace(recovery_plan=tmp_path / 'proposal.json', recovery_plan_sha256=f.pin,
                           dry_run=False, approve_full_compute=True, max_batches=2, stall_seconds=10)
    events = []
    # Exercise the supervisor's actual gate, forwarding its metadata-only verifier
    # subprocess to the synthetic verifier. No candidate subprocess is launched.
    def verification_command(cmd, **kwargs):
        assert cmd[3] == 'verify' and cmd[-1] == f.pin
        recovery.verify(f.plan, f.pin)
        events.append('verified')
    monkeypatch.setattr(sup.subprocess, 'run', verification_command)
    monkeypatch.setattr(sup, 'preflight', lambda: {})
    counts = iter([0, 0, 1, 1, 2])
    monkeypatch.setattr(sup, 'checkpoint_audit', lambda **kw: {'count': next(counts), 'expected': 3})
    monkeypatch.setattr(sup, 'LOG', tmp_path / 'supervisor/progress.jsonl')
    monkeypatch.setattr(sup, 'SUPERVISOR_LOCK', tmp_path / 'supervisor/writer.lock')
    monkeypatch.setattr(sup, 'assert_local_runtime_path', lambda p: None)
    monkeypatch.setattr(sup, 'append_event', lambda event: None)
    class Child:
        def poll(self): return 75
        def wait(self): return 75
    monkeypatch.setattr(sup, 'launch_captured', lambda cmd: events.append('launch') or Child())
    # A normal-looking original response alone is not enough to start the supervisor.
    with pytest.raises((ValueError, FileNotFoundError)):
        sup.run(args)
    assert events == []
    f.execute(); f.publish()
    sup.run(args)
    assert events == ['verified', 'verified', 'launch', 'verified', 'verified', 'launch', 'verified']
    assert f.backend.calls == 1


def test_resume_verification_rejects_new_unrelated_checkpoint_corruption(incident):
    f = incident
    f.execute(); f.publish()
    path = recovery.CANDIDATES / 'query-checkpoints/later.json'
    reliable.atomic(path, {'schema': reliable.VERSION, 'binding': {}, 'data': {'later': True},
                           'data_sha256': 'incorrect'})
    with pytest.raises(ValueError, match='integrity'):
        recovery.verify(f.plan, f.pin)


def test_valid_continuation_retains_all_original_evidence(incident):
    f = incident
    f.execute(); f.publish()
    data = {'query_id': 'later-query', 'candidate_band': 0, 'selection': None}
    binding = {'family': 'semantic_fluent_false_evidence', 'intensity': 1, 'seed': 42,
               'band': 0, 'choice': None, 'protocol_sha256': recovery.INCIDENT['protocol_sha256']}
    path = recovery.CANDIDATES / 'query-checkpoints/semantic_fluent_false_evidence.intensity-1.seed-42/0' / (hashlib.sha256(b'later-query').hexdigest() + '.json')
    reliable.atomic(path, {'schema': reliable.VERSION, 'binding': binding, 'data': data,
                           'data_sha256': recovery.fingerprint(data)})
    assert recovery.verify(f.plan, f.pin)['status'] == 'verified_seed42_replacement_not_original'


def test_partial_empty_namespace_is_terminal(incident):
    recovery.RECOVERY.mkdir()
    with pytest.raises(RuntimeError, match='already claimed'):
        incident.execute()
    with pytest.raises(ValueError, match='already exists'):
        recovery.prepare()
    assert incident.backend.calls == 0


def test_source_files_of_legacy_authorization_are_byte_identical_to_parent():
    root = Path(__file__).resolve().parents[1]
    expected = {
        'src/experiments/single_intent_recovery.py': '559659b11b96cb814d88822bb3bdf3999e7a1d27b2ab9ca0a4dc18cc46489a5a',
        'scripts/recover_hotpotqa_single_intent.py': 'a4b3fc5e550205fa0531db2fb7a6bd9ba03abdbafa7a86e9379ddc9ac1220866',
        'tests/test_single_intent_recovery.py': '621060de0dfc2ab64c5d73cd5fe12d837da5e2ff15c74a4a6255f2127bdb9186',
    }
    for rel, digest in expected.items():
        assert hashlib.sha256((root / rel).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize('intensity,index,valid', [(1, 1, True), (1, 2, False),
                                                  (3, 5, True), (3, 6, False)])
def test_continuation_call_limit_spans_all_documents_without_new_quality_attempts(incident, intensity, index, valid):
    f = incident
    f.execute(); f.publish()
    req = copy.deepcopy(f.request)
    req['provenance'].update(intensity=intensity, candidate_band=0, query_id='later-query')
    cell = f'semantic_fluent_false_evidence.intensity-{intensity}.seed-42'
    directory = recovery.CANDIDATES / 'calls' / cell / '0' / hashlib.sha256(b'later-query').hexdigest()
    reliable.atomic(directory / f'{index:02d}.intent.json', req)
    _, g = capture_generation(f.backend, req['prompt'], 150)
    reliable.atomic(directory / f'{index:02d}.response.json', {
        'request_fingerprint': recovery.fingerprint(req), 'generation': g,
        'generation_sha256': recovery.fingerprint(g)})
    if valid:
        assert recovery.verify(f.plan, f.pin)['status'] == 'verified_seed42_replacement_not_original'
    else:
        with pytest.raises(ValueError, match='identity'):
            recovery.verify(f.plan, f.pin)
