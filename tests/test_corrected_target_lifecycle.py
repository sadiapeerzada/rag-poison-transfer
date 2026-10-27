"""Offline synthetic lifecycle audit; no experimental generation or review claims."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import run_week9_protocol_poison_matrix as base
from src.attacks import development_targets_v4 as v4, semantic_profiles
from src.experiments import execution_reliability as reliable
from src.experiments import semantic_development_study as study
from test_semantic_development_study import setup as study_setup


@pytest.fixture
def corrected(tmp_path, monkeypatch):
    old_path, _, backend, full, _ = study_setup.__wrapped__(tmp_path, monkeypatch)
    old = json.loads(old_path.read_text())
    path = tmp_path / 'corrected' / 'protocol.json'
    pin = base.freeze_protocol(path, 'development', Path('fixture'), old['replication'],
        semantic_profile=semantic_profiles.DEVELOPMENT, development_study=study.IDENTIFIER,
        target_method=v4.IDENTIFIER)['protocol_sha256']
    value, _, _, development = base.load_protocol(path, pin)
    return path, pin, backend, value, development


def finish(fixture):
    path, pin, _, value, _ = fixture
    root = Path(value['planned_outputs']['construction'])
    result = base.construct(path, pin, root, Path('fixture'))
    loaded = base.load_sealed(path, pin, root, result['construction_seal_sha256'])
    return root, result['construction_seal_sha256'], loaded


def test_corrected_end_to_end_replay_evaluation_aggregation(corrected, monkeypatch):
    import run
    path, pin, backend, value, _ = corrected
    root = Path(value['planned_outputs']['construction'])
    original = base.write
    interrupted = False

    def interrupt_checkpoint(path, record):
        nonlocal interrupted
        if not interrupted and Path(path).parent.name == 'queries':
            interrupted = True
            raise OSError('synthetic interruption after completed response')
        return original(path, record)

    monkeypatch.setattr(base, 'write', interrupt_checkpoint)
    with pytest.raises(OSError, match='synthetic interruption'):
        base.construct(path, pin, root, Path('fixture'))
    assert backend.calls == 1
    monkeypatch.setattr(base, 'write', original)
    root, seal, (_, _, _, clean, cells) = finish(corrected)
    assert backend.calls == 125  # Interrupted response replayed, never regenerated.
    method = v4.descriptor()
    assert json.loads((root / 'construction.plan.json').read_text())['target_method'] == method
    for intent in root.glob('*/generation/*/*.intent.json'):
        assert json.loads(intent.read_text())['provenance']['target_method_sha256'] == base.protocol.fingerprint(method)
    for cell in cells.values():
        assert cell['target_method'] == method
        assert all(row['target_method_sha256'] == base.protocol.fingerprint(method) for row in cell['records'])
    assert len(clean['queries']) == 25

    class Retriever:
        def build(self, corpus): self.docs = [SimpleNamespace(**d) for d in corpus]
        def retrieve(self, query, top_k): return self.docs[:top_k]

    monkeypatch.setattr(run, 'build_retriever', lambda *a: Retriever())
    monkeypatch.setattr(reliable, 'release_idle_memory', lambda: None)
    out = Path(value['planned_outputs']['evaluation'])
    done = base.evaluate(path, pin, root, seal, out, Path('fixture'))
    assert backend.calls == 225
    base.evaluate(path, pin, root, seal, out, Path('fixture'))
    assert backend.calls == 225
    destination = Path(value['planned_outputs']['aggregate'])
    base.aggregate(path, pin, root, seal, out, done['evaluation_completion_sha256'], destination)
    result = json.loads(destination.read_text())
    assert result['target_method'] == method and result['diagnostic_only']
    assert result['protocol_sha256'] == pin and result['construction_seal_sha256'] == seal
    for identity, cell in cells.items():
        rows = json.loads((out / identity / 'rows.json').read_text())
        base.protocol.validate_evaluation_rows(rows, cell, clean, seal)
        assert len(rows) == 50
        for arm in ('dense', 'rcd'):
            summary = result['cells'][identity][arm]
            assert summary['attempted'] == 25
            assert summary['evaluated'] == (25 if cell['intensity'] == 1 else 0)
    frozen = destination.read_bytes()
    base.aggregate(path, pin, root, seal, out, done['evaluation_completion_sha256'], destination)
    assert destination.read_bytes() == frozen and backend.calls == 225


@pytest.mark.parametrize('location', ['descriptor', 'record'])
def test_corrected_cell_target_binding_rejects_tampering(corrected, location):
    _, pin, _, value, development = corrected
    _, _, (_, _, _, clean, cells) = finish(corrected)
    cell = copy.deepcopy(next(iter(cells.values())))
    if location == 'descriptor': cell['target_method']['method_version'] = 'tampered'
    else: cell['records'][0]['target_method_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='target method'):
        base.protocol.validate_cell(cell, clean, development, pin, **base.validation_kwargs(value))


def test_corrected_query_checkpoint_fingerprint_refused_before_replay(corrected, monkeypatch):
    path, pin, backend, value, _ = corrected
    root = Path(value['planned_outputs']['construction'])
    with pytest.raises(reliable.PauseExecution):
        base.construct(path, pin, root, Path('fixture'), max_batches=1)
    checkpoint = next(root.glob('*/queries/*.json'))
    row = json.loads(checkpoint.read_text()); row['target_method_sha256'] = '0' * 64
    checkpoint.write_text(json.dumps(row))
    # Remove only the synthetic assembled cell to exercise query-checkpoint recovery.
    next(root.glob('*/construction.json')).unlink()
    before = backend.calls
    with pytest.raises(ValueError, match='Query target method mismatch'):
        base.construct(path, pin, root, Path('fixture'))
    assert backend.calls == before


def test_corrected_journal_fingerprint_refuses_cross_method_replay(tmp_path):
    class Backend:
        calls = 0
        def generate(self, prompt, max_tokens):
            from src.pipelines.generator import GenerationResult
            self.calls += 1
            return GenerationResult('Synthetic answer', .1, 1, 1)
    backend = Backend()
    provenance = {'target_method_sha256': base.protocol.fingerprint(v4.descriptor())}
    base.JournalGenerator(backend, tmp_path, provenance).generate('Synthetic prompt', 32)
    with pytest.raises(ValueError, match='provenance'):
        base.JournalGenerator(backend, tmp_path, {'target_method_sha256': '0' * 64}).generate('Synthetic prompt', 32)
    assert backend.calls == 1


@pytest.mark.parametrize('scope', ['heldout', 'unknown'])
def test_corrected_protocol_loading_refuses_non_development(corrected, scope):
    path, _, backend, value, _ = corrected
    value['binding']['scope'] = scope
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError): base.load_protocol(path, base.sha(path))
    assert backend.calls == 0
