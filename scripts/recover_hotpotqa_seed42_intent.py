#!/usr/bin/env python3
"""Seed-42 recovery controller. Every production dispatch requires future approval."""
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
    parser.add_argument('--output', type=Path)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--plan-sha256')
    parser.add_argument('--approve-request-fingerprint')
    parser.add_argument('--extra-physical-call-allowance', type=int)
    parser.add_argument('--approve-execution', action='store_true')
    parser.add_argument('--approve-publication', action='store_true')
    args = parser.parse_args()
    # The worker import root is a literal; no proposal can select executable code.
    frozen = Path('/Users/sadiapeerzada/Documents/rag-research-results/hotpotqa-reliable-execution')
    sys.path.insert(0, str(frozen if args.stage == '_worker' else ROOT))
    spec = importlib.util.spec_from_file_location('seed42_recovery_core', ROOT / 'src/experiments/seed42_intent_recovery.py')
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    if args.stage == 'prepare':
        if not args.output or args.approve_execution or args.approve_publication:
            parser.error('prepare requires --output and grants no execution/publication approval')
        if args.output.absolute() != core.PROPOSAL:
            raise ValueError('Proposal output namespace is fixed outside protected checkouts')
        core._plain_path(args.output)
        output = core.external_output(args.output, core.PROTOCOL, core.FROZEN)
        if output == core.RESEARCH or core.RESEARCH in output.parents or output == core.RECOVERY or core.RECOVERY in output.parents:
            raise ValueError('Proposal must be outside all research and recovery directories')
        plan = core.prepare()
        core.reliable.atomic(output, plan)
        result = {'status': 'proposal_only_no_inference', 'proposal_sha256': core.sha(output),
                  'incident': plan['incident'], 'physical_call_policy': plan['policy'],
                  'required_future_approvals': ['execute', 'publish', 'resume']}
    else:
        if not args.plan or not args.plan_sha256 or core.sha(args.plan) != args.plan_sha256:
            raise ValueError('Exact existing proposal file SHA required')
        plan = core.reliable.read(args.plan)
        if args.stage == 'verify':
            result = core.verify(plan, args.plan_sha256)
        else:
            stage = 'execute' if args.stage in ('execute', '_worker') else 'publish'
            approved = (args.approve_execution and not args.approve_publication if stage == 'execute'
                        else args.approve_publication and not args.approve_execution)
            approval = stage if approved else None
            core.approve(plan, args.plan_sha256, args.approve_request_fingerprint,
                         args.extra_physical_call_allowance, approval, stage)
            if args.stage == 'execute':
                subprocess.run([sys.executable, str(Path(__file__).resolve()), '_worker',
                    '--plan', str(args.plan.resolve()), '--plan-sha256', args.plan_sha256,
                    '--approve-request-fingerprint', args.approve_request_fingerprint,
                    '--extra-physical-call-allowance', str(args.extra_physical_call_allowance),
                    '--approve-execution'], cwd=core.FROZEN, check=True)
                return
            if args.stage == 'publish':
                result = core.publish(plan, args.plan_sha256, args.approve_request_fingerprint,
                                      args.extra_physical_call_allowance, approval)
            else:
                # Frozen generator, formatter, greedy sampler, seed function and
                # capture code; this import happens only after explicit execution approval.
                from scripts import run_week9_protocol_poison_matrix as base
                from src.evaluation.qa_records import capture_generation
                result = core.execute(plan, args.plan_sha256, args.approve_request_fingerprint,
                    args.extra_physical_call_allowance, approval,
                    lambda: base.generator(core.reliable.read(core.PROTOCOL)['configs']['rcd'], core.MODEL),
                    base.runtime_seed, capture_generation)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
