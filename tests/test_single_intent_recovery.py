"""Synthetic backend fixtures only; no real recovery authorization or inference."""
import copy
import hashlib
from pathlib import Path
import pytest
from src.experiments import single_intent_recovery as recovery
from src.experiments import execution_reliability as reliable
from src.evaluation.qa_records import capture_generation
from src.pipelines.generator import GenerationResult


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    candidates = tmp_path / 'experiment/heldout/execution/candidates'
    protocol = tmp_path / 'experiment/heldout/protocol.json'
    rel = 'calls/synthetic-cell/0/synthetic-query/00.intent.json'
    doc = {'source': {'git_commit_sha': 'fixture-only'}, 'model': {'repository': 'fixture-only'},
        'execution': {'unresolved_intent': 'halt-no-regeneration'},
        'planned_outputs': {'candidates': str(candidates)}}
    reliable.atomic(protocol, doc)
    request = {'prompt': 'Synthetic prompt with an exact frozen input.', 'max_tokens': 150,
        'provenance': {'model': doc['model'], 'protocol_sha256': recovery.sha(protocol)}, 'context': {}}
    reliable.atomic(candidates / rel, request)
    data = {'query_id': 'completed-fixture', 'status': 'valid_construction'}
    reliable.atomic(candidates / 'query-checkpoints/completed.json', {
        'schema': reliable.VERSION, 'binding': {'fixture': True},
        'data': data, 'data_sha256': recovery.fingerprint(data)})
    # An independently completed earlier call must remain byte-identical too.
    prior = {'prompt': 'Earlier synthetic request.', 'max_tokens': 150, 'provenance': {}, 'context': {}}
    class PriorBackend:
        def generate(self, prompt, max_tokens):
            return GenerationResult('Earlier synthetic response.', .1, 4, 4)
    _, prior_generation = capture_generation(PriorBackend(), prior['prompt'], 150)
    reliable.atomic(candidates / 'completed/00.intent.json', prior)
    reliable.atomic(candidates / 'completed/00.response.json', {
        'request_fingerprint': recovery.fingerprint(prior), 'generation': prior_generation,
        'generation_sha256': recovery.fingerprint(prior_generation)})
    binding = {'git_commit': 'synthetic-executor', 'clean': True, 'files_sha256': {'fixture': 'hash'}}
    monkeypatch.setattr(recovery, 'executor_binding', lambda: copy.deepcopy(binding))
    monkeypatch.setattr(recovery, 'verify_source', lambda *a: None)
    incident = {'protocol_sha256': recovery.sha(protocol), 'request_fingerprint': recovery.fingerprint(request),
        'intent_sha256': recovery.sha(candidates / rel), 'intent_relative': rel,
        'source_commit': 'fixture-only', 'runtime_seed': 123, 'recovery_dir': str(tmp_path / 'recovery'),
        'parent_inventory_fingerprint': recovery.fingerprint(recovery.inventory(candidates))}
    monkeypatch.setattr(recovery, 'INCIDENT', incident)
    plan = recovery.prepare(protocol, candidates, tmp_path / 'frozen-checkout', tmp_path / 'snapshot', tmp_path / 'recovery')
    pin = recovery.fingerprint_bytes(plan)
    class Backend:
        calls = 0
        crash = False
        def generate(self, prompt, max_tokens):
            self.calls += 1
            assert prompt == request['prompt'] and max_tokens == 150
            if self.crash: raise KeyboardInterrupt('fixture interruption')
            return GenerationResult('Synthetic replacement, not an original response.', .1, 10, 8)
    backend = Backend(); seeds = []; factory_calls = []
    def factory(): factory_calls.append(True); return backend
    def execute():
        return recovery.execute(plan, pin, incident['request_fingerprint'], 1, factory, seeds.append, capture_generation)
    return plan, pin, backend, seeds, execute, factory_calls


def test_production_identity_is_the_one_approved_incident():
    assert recovery.INCIDENT['request_fingerprint'] == 'dec08535d5e02ffaa9838f4f35ca3061c3c7b530d550a3c90c4ddda31e22f9ec'
    assert recovery.INCIDENT['runtime_seed'] == 3215750484


def test_separate_generation_publish_and_accounting(fixture):
    plan, pin, backend, seeds, execute, _ = fixture
    parent = Path(plan['candidates']); before = recovery.inventory(parent)
    result = execute(); assert result['new_backend_calls'] == backend.calls == 1 and seeds == [123]
    assert recovery.inventory(parent) == before
    assert not (parent / recovery.response_relative(plan)).exists()
    # Default legacy behavior remains fail-closed until explicit publication.
    with pytest.raises(RuntimeError, match='Unresolved'): reliable.validate_store(parent)
    replacement = recovery.read(Path(plan['recovery_dir']) / 'replacement.response.json')
    assert replacement['physical_call_accounting'] == {'original_indeterminate': 1,
        'replacement_completed': 1, 'conservative_physical_dispatch_count': 2}
    recovery.publish(plan, pin, recovery.INCIDENT['request_fingerprint'], 1)
    receipt = recovery.read(parent / recovery.response_relative(plan))
    assert receipt['recovery']['is_original_response'] is False
    assert receipt['recovery']['original_attempt_status'] == 'indeterminate'
    assert receipt['execution']['backend_call_executed'] is False
    assert all(recovery.sha(parent / p) == digest for p, digest in before.items())
    reliable.validate_store(parent)
    assert recovery.verify_resolution(plan, pin)['extra_recorded_completed_recovery_calls'] == 1
    assert execute()['new_backend_calls'] == 0 and backend.calls == 1
    recovery.publish(plan, pin, recovery.INCIDENT['request_fingerprint'], 1)
    assert backend.calls == 1


@pytest.mark.parametrize('approved,extra', [('unrelated', 1), (None, 1), ('correct', 0), ('correct', 2)])
def test_authorization_rejects_unrelated_or_missing_budget(fixture, approved, extra):
    plan, pin, backend, _, _, _ = fixture
    approved = recovery.INCIDENT['request_fingerprint'] if approved == 'correct' else approved
    with pytest.raises(ValueError):
        recovery.execute(plan, pin, approved, extra, lambda: backend, lambda s: None, capture_generation)
    assert backend.calls == 0 and not Path(plan['recovery_dir']).exists()


def test_indeterminate_recovery_is_never_retried(fixture):
    plan, pin, backend, _, execute, factory_calls = fixture
    backend.crash = True
    with pytest.raises(KeyboardInterrupt): execute()
    root = Path(plan['recovery_dir'])
    assert (root / 'replacement.intent.json').exists() and not (root / 'replacement.response.json').exists()
    backend.crash = False
    with pytest.raises(RuntimeError, match='do not retry'): execute()
    assert backend.calls == 1 and len(factory_calls) == 1
    assert not (Path(plan['candidates']) / recovery.response_relative(plan)).exists()


def test_saved_response_can_be_published_after_controller_interruption(fixture):
    plan, pin, backend, _, execute, _ = fixture
    execute()  # Simulate the controller stopping before publication.
    assert execute()['new_backend_calls'] == 0
    recovery.publish(plan, pin, recovery.INCIDENT['request_fingerprint'], 1)
    assert backend.calls == 1


@pytest.mark.parametrize('where', ['intent', 'checkpoint', 'protocol', 'new-unrelated-intent'])
def test_parent_conflicts_refuse_generation(fixture, where):
    plan, _, backend, _, execute, _ = fixture
    root = Path(plan['candidates'])
    if where == 'intent': (root / recovery.INCIDENT['intent_relative']).write_text('{}')
    elif where == 'checkpoint': (root / 'query-checkpoints/completed.json').write_text('{}')
    elif where == 'protocol': Path(plan['protocol']).write_text('{}')
    else: reliable.atomic(root / 'unrelated.intent.json', {'prompt': 'unrelated'})
    with pytest.raises(ValueError): execute()
    assert backend.calls == 0


def test_existing_original_response_is_never_overwritten(fixture):
    plan, pin, backend, _, execute, _ = fixture
    execute(); path = Path(plan['candidates']) / recovery.response_relative(plan)
    reliable.atomic(path, {'generation': 'conflict'})
    before = path.read_bytes()
    with pytest.raises(ValueError, match='Conflicting'):
        recovery.publish(plan, pin, recovery.INCIDENT['request_fingerprint'], 1)
    assert path.read_bytes() == before and backend.calls == 1


@pytest.mark.parametrize('field', ['generation', 'physical_call_accounting', 'intent_sha256', 'schema'])
def test_recovery_response_corruption_is_refused(fixture, field):
    plan, pin, backend, _, execute, _ = fixture; execute()
    path = Path(plan['recovery_dir']) / 'replacement.response.json'; record = recovery.read(path)
    if field == 'generation': record[field]['raw_response'] = 'tampered'
    else: record[field] = 'tampered'
    path.write_text(__import__('json').dumps(record))
    with pytest.raises((ValueError, TypeError)):
        recovery.publish(plan, pin, recovery.INCIDENT['request_fingerprint'], 1)
    assert backend.calls == 1


def test_error_response_prevents_retry(fixture):
    plan, pin, backend, _, _, factory_calls = fixture
    def broken(): factory_calls.append(True); raise RuntimeError('fixture model-load error')
    with pytest.raises(RuntimeError, match='fixture model-load error'):
        recovery.execute(plan, pin, recovery.INCIDENT['request_fingerprint'], 1, broken, lambda s: None, capture_generation)
    assert (Path(plan['recovery_dir']) / 'replacement.error.json').exists()
    with pytest.raises(RuntimeError, match='Recovery error'):
        recovery.execute(plan, pin, recovery.INCIDENT['request_fingerprint'], 1, broken, lambda s: None, capture_generation)
    assert len(factory_calls) == 1 and backend.calls == 0


def test_extra_recovery_files_and_orphan_response_refused(fixture):
    plan, _, backend, _, execute, _ = fixture
    root = Path(plan['recovery_dir']); root.mkdir()
    (root / '.atomic-lost').write_text('partial')
    with pytest.raises(ValueError, match='Ambiguous'): execute()
    assert backend.calls == 0


def test_draft_executor_cannot_run(fixture, monkeypatch):
    plan, pin, backend, _, _, _ = fixture
    plan['executor']['clean'] = False
    monkeypatch.setattr(recovery, 'executor_binding', lambda: plan['executor'])
    pin = recovery.fingerprint_bytes(plan)
    with pytest.raises(ValueError, match='Draft executor'):
        recovery.execute(plan, pin, recovery.INCIDENT['request_fingerprint'], 1,
            lambda: backend, lambda s: None, capture_generation)
    assert backend.calls == 0


def test_helper_version_and_plan_pin_mismatch_refuse_dispatch(fixture, monkeypatch):
    plan, pin, backend, _, execute, _ = fixture
    with pytest.raises(ValueError, match='pin mismatch'):
        recovery.execute(plan, '0' * 64, recovery.INCIDENT['request_fingerprint'], 1,
            lambda: backend, lambda s: None, capture_generation)
    monkeypatch.setattr(recovery, 'executor_binding', lambda: {**plan['executor'], 'git_commit': 'changed'})
    with pytest.raises(ValueError, match='executor provenance'): execute()
    assert backend.calls == 0


def test_new_continuation_records_do_not_erase_protected_provenance(fixture):
    plan, pin, _, _, execute, _ = fixture
    execute(); recovery.publish(plan, pin, recovery.INCIDENT['request_fingerprint'], 1)
    reliable.atomic(Path(plan['candidates']) / 'later-valid-checkpoint.json', {'later': True})
    assert recovery.verify_resolution(plan, pin)['status'] == 'verified_explicit_replacement_not_original'


def test_original_journal_replays_explicit_resolution_without_new_backend_call(fixture):
    from scripts.run_week9_protocol_poison_matrix import JournalGenerator
    plan, pin, backend, _, execute, _ = fixture
    execute(); recovery.publish(plan, pin, recovery.INCIDENT['request_fingerprint'], 1)
    intent = Path(plan['candidates']) / recovery.INCIDENT['intent_relative']
    request = recovery.read(intent)
    reader = JournalGenerator(None, intent.parent, request['provenance'])
    result = reader.generate(request['prompt'], request['max_tokens'])
    assert result.text == 'Synthetic replacement, not an original response.' and backend.calls == 1
    base = reliable.accounting(plan['candidates'])
    replacement = reliable.accounting(plan['recovery_dir'])
    assert base['actual_backend_calls'] == 1  # Earlier completed call only.
    assert replacement['actual_backend_calls'] == 1
    assert base['logical_generation_observations'] == 2
    assert recovery.verify_resolution(plan, pin)['original_indeterminate_calls'] == 1


def test_changed_recovery_intent_and_orphan_response_refused(fixture):
    plan, pin, backend, _, execute, _ = fixture
    execute(); path = Path(plan['recovery_dir']) / 'replacement.intent.json'
    obj = recovery.read(path); obj['runtime_seed'] += 1
    path.write_text(__import__('json').dumps(obj))
    with pytest.raises(ValueError, match='intent/provenance'):
        recovery.publish(plan, pin, recovery.INCIDENT['request_fingerprint'], 1)
    assert backend.calls == 1


def test_unrelated_incident_plan_is_rejected(fixture):
    plan, pin, backend, _, _, _ = fixture
    plan['incident']['request_fingerprint'] = 'unrelated'
    with pytest.raises(ValueError, match='single authorized incident'):
        recovery.execute(plan, recovery.fingerprint_bytes(plan), 'unrelated', 1,
            lambda: backend, lambda s: None, capture_generation)
    assert backend.calls == 0


def test_active_parent_writer_blocks_recovery_before_any_attempt(fixture):
    import fcntl
    plan, _, backend, _, execute, _ = fixture
    root = Path(plan['candidates'])
    with root.with_name(root.name + '.writer.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match='writer is active'): execute()
    assert backend.calls == 0 and not Path(plan['recovery_dir']).exists()


def test_resolution_does_not_exempt_a_later_unrelated_interruption(fixture):
    plan, pin, _, _, execute, _ = fixture
    execute(); recovery.publish(plan, pin, recovery.INCIDENT['request_fingerprint'], 1)
    reliable.atomic(Path(plan['candidates']) / 'unrelated.intent.json', {'prompt': 'later'})
    with pytest.raises(RuntimeError, match='Unresolved'):
        recovery.verify_resolution(plan, pin)


def test_amended_accounting_does_not_double_count_resolution_receipt(fixture):
    plan, pin, _, _, execute, _ = fixture
    execute(); recovery.publish(plan, pin, recovery.INCIDENT['request_fingerprint'], 1)
    counts = recovery.verify_resolution(plan, pin)['physical_call_accounting']
    assert counts['base_completed_calls_excluding_resolution_receipt'] == 1
    assert counts['separately_completed_replacement_calls'] == 1
    assert counts['total_recorded_completed_calls'] == 2
    assert counts['indeterminate_original_calls'] == 1
    assert counts['conservative_consumed_call_count'] == 3


@pytest.mark.parametrize('where', ['experiment', 'frozen-checkout', 'executor-checkout'])
def test_recovery_cannot_dirty_protected_experiment_or_code(fixture, where):
    plan, _, backend, _, _, _ = fixture
    protected = {'experiment': Path(plan['protocol']).parent.parent,
        'frozen-checkout': Path(plan['frozen_checkout']), 'executor-checkout': recovery.ROOT}[where]
    plan['recovery_dir'] = str(protected / 'forbidden-recovery')
    with pytest.raises(ValueError, match='outside experiment and code'):
        recovery.execute(plan, recovery.fingerprint_bytes(plan), recovery.INCIDENT['request_fingerprint'], 1,
            lambda: backend, lambda s: None, capture_generation)
    assert backend.calls == 0 and not Path(plan['recovery_dir']).exists()


def test_cannot_retry_same_request_in_a_fresh_namespace(fixture):
    plan, _, backend, _, execute, _ = fixture
    backend.crash = True
    with pytest.raises(KeyboardInterrupt): execute()
    plan['recovery_dir'] = str(Path(plan['recovery_dir']).with_name('unauthorized-second-recovery'))
    with pytest.raises(ValueError, match='namespace is fixed'):
        recovery.execute(plan, recovery.fingerprint_bytes(plan), recovery.INCIDENT['request_fingerprint'], 1,
            lambda: backend, lambda s: None, capture_generation)
    assert backend.calls == 1 and not Path(plan['recovery_dir']).exists()
