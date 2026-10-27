#!/usr/bin/env python3
"""Prepare only by default; execution/publication require future explicit opt-in.

The worker loads the original clean frozen checkout for all actual generation.
No import or prepare/verify operation initializes a generator.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'execute', '_worker', 'publish', 'verify'))
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--plan-sha256')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--recovery-dir', type=Path)
    parser.add_argument('--protocol', type=Path, default=Path('/private/tmp/oct27-hotpotqa-source-transfer-v1/heldout/protocol.json'))
    parser.add_argument('--candidates', type=Path, default=Path('/private/tmp/oct27-hotpotqa-source-transfer-v1/heldout/execution/candidates'))
    parser.add_argument('--frozen-checkout', type=Path, default=Path('/private/tmp/rag-semantic-construction-v2'))
    parser.add_argument('--model-snapshot', type=Path, default=Path('/Users/sadiapeerzada/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed'))
    parser.add_argument('--approve-request-fingerprint')
    parser.add_argument('--extra-physical-call-allowance', type=int)
    a = parser.parse_args()
    if a.stage != 'prepare' and (not a.plan or not a.plan_sha256):
        parser.error('Require an externally pinned amendment plan')
    # Pin before allowing a plan to choose the worker's frozen import root.
    if a.stage != 'prepare':
        import hashlib
        with a.plan.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != a.plan_sha256:
                raise ValueError('Amendment file fingerprint mismatch')
        plan = json.loads(a.plan.read_text())
    import_root = Path(plan['frozen_checkout']) if a.stage == '_worker' else ROOT
    sys.path.insert(0, str(import_root))
    # The recovery helper is versioned separately; scientific generator code comes
    # from the original checkout in the worker, never from this modified worktree.
    spec = importlib.util.spec_from_file_location('single_intent_recovery_helper', ROOT / 'src/experiments/single_intent_recovery.py')
    core = importlib.util.module_from_spec(spec); spec.loader.exec_module(core)
    if a.stage == 'prepare':
        if not a.output or not a.recovery_dir: parser.error('Require fresh --output and --recovery-dir')
        core.external_output(a.output, a.protocol, a.frozen_checkout)
        plan = core.prepare(a.protocol, a.candidates, a.frozen_checkout, a.model_snapshot, a.recovery_dir)
        core.atomic(a.output, plan)
        result = {'status': 'proposal_only_no_recovery_executed', 'plan_sha256': core.sha(a.output),
            'executor_clean': plan['executor']['clean'], 'requires_future_explicit_execution_approval': True}
    elif a.stage == 'verify':
        result = core.verify_resolution(plan, a.plan_sha256)
    else:
        core.authorize(plan, a.approve_request_fingerprint, a.extra_physical_call_allowance)
        if a.stage == 'execute':
            # Do not initialize MLX in the controller. Its child checks the exact
            # frozen environment/model before writing any physical recovery intent.
            argv = [sys.executable, str(Path(__file__).resolve()), '_worker', '--plan', str(a.plan.resolve()),
                '--plan-sha256', a.plan_sha256, '--approve-request-fingerprint', a.approve_request_fingerprint,
                '--extra-physical-call-allowance', str(a.extra_physical_call_allowance)]
            subprocess.run(argv, cwd=plan['frozen_checkout'], check=True)
            return
        if a.stage == 'publish':
            result = core.publish(plan, a.plan_sha256, a.approve_request_fingerprint, a.extra_physical_call_allowance)
        else:
            from scripts import run_week9_protocol_poison_matrix as base
            protocol = core._protocol(plan)
            if base.environment() != protocol['environment']:
                raise ValueError('Frozen runtime dependencies differ')
            snapshot = Path(plan['model_snapshot'])
            if base.model_binding(snapshot, protocol['model']['repository']) != protocol['model']:
                raise ValueError('Frozen local model bytes differ')
            from src.evaluation.qa_records import capture_generation
            cfg = base.metadata('heldout')[2]
            result = core.execute(plan, a.plan_sha256, a.approve_request_fingerprint,
                a.extra_physical_call_allowance, lambda: base.generator(cfg, snapshot),
                base.runtime_seed, capture_generation)
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
