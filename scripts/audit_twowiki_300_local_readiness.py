#!/usr/bin/env python3
"""Read-only local evidence census. Never infer authorization or replay calls."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_2wiki_smoke_incident import audit, sha
from src.experiments import execution_reliability as reliable
from src.experiments.week9_construction import fingerprint


def census(root):
    root = Path(root).expanduser().resolve(strict=True)
    inventory, problems, protocols, plans, stages = {}, [], {}, [], []
    native_journal_directories, other_intents = set(), []
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            problems.append({'path': rel, 'error': 'symlink_not_followed'})
            continue
        if not path.is_file():
            continue
        inventory[rel] = sha(path)
        if path.suffix != '.json':
            continue
        try:
            obj = json.loads(path.read_text())
        except (ValueError, OSError) as error:
            problems.append({'path': rel, 'error': type(error).__name__})
            continue
        if not isinstance(obj, dict):
            continue
        if path.name.endswith('.intent.json'):
            if {'prompt', 'max_tokens', 'provenance'} <= obj.keys():
                native_journal_directories.add(path.parent)
            else:
                other_intents.append({'path': rel, 'schema': obj.get('schema'),
                    'status': 'separate_format_not_validated_by_execution_reliability'})
        if path.name.endswith('.response.json') and 'request_fingerprint' in obj:
            native_journal_directories.add(path.parent)
        if path.name == 'protocol.json':
            binding = obj.get('binding', {})
            protocols[inventory[rel]] = {'path': rel, 'schema': obj.get('schema'),
                'scope': binding.get('scope'), 'queries': len(binding.get('query_ids', [])),
                'dataset': binding.get('dataset'), 'source': obj.get('source'),
                'matrix': binding.get('matrix'), 'model_revision': obj.get('model', {}).get('revision')}
        if path.name in ('execution.plan.json', 'construction.plan.json', 'evaluation.plan.json'):
            binding = obj.get('binding', {})
            plans.append({'path': rel, 'protocol_sha256': obj.get('protocol_sha256', binding.get('protocol_sha256'))})
        if path.name in ('construction.seal.json', 'evaluation.complete.json'):
            expected = obj.get('files_sha256')
            actual = {p.relative_to(path.parent).as_posix(): sha(p)
                      for p in path.parent.rglob('*') if p.is_file() and p != path}
            stages.append({'path': rel, 'protocol_sha256': obj.get('protocol_sha256'),
                'file_manifest_matches': isinstance(expected, dict) and expected == actual,
                'missing_files': sorted(set(expected or {}) - set(actual)),
                'additional_files': sorted(set(actual) - set(expected or {})),
                'changed_files': sorted(k for k in (expected or {}) if k in actual and expected[k] != actual[k])})
    stores = []
    planned_roots = {(root / p['path']).parent for p in plans}
    unplanned = {p for p in native_journal_directories if not any(s == p or s in p.parents for s in planned_roots)}
    for directory in sorted(planned_roots | unplanned):
        try:
            reliable.validate_store(directory)
            status = 'PASS'
        except (ValueError, RuntimeError, KeyError, TypeError, OSError, AttributeError) as error:
            status = type(error).__name__ + ': ' + str(error)
        stores.append({'path': directory.relative_to(root).as_posix(), 'checkpoint_validation': status,
                       'execution_plan_present': directory in planned_roots})
    incidents = []
    for pin, entry in protocols.items():
        if (entry.get('dataset') or {}).get('loader') != 'load_2wikimultihopqa':
            continue
        construction = (root / entry['path']).parent / 'execution/construction'
        if construction.is_dir():
            details = audit(root / entry['path'], pin, construction)
            incidents.append({k: details[k] for k in ('protocol_sha256', 'scope', 'journal_counts',
                'issues', 'expected_query_checkpoint_count', 'validated_query_checkpoint_count',
                'present_cell_records', 'construction_seal_present', 'automatic_retry_permitted')})
    heldout = {pin for pin, entry in protocols.items()
               if entry.get('scope') == 'heldout' and entry.get('queries') == 300
               and (entry.get('dataset') or {}).get('loader') == 'load_2wikimultihopqa'}
    return {'schema': 'rag-poison-transfer.2wiki-local-readiness-census/v1',
        'root': str(root), 'files_sha256': inventory, 'inventory_sha256': fingerprint(inventory),
        'file_count': len(inventory), 'top_level_file_counts': dict(Counter(p.split('/')[0] for p in inventory)),
        'problems': problems, 'protocols': protocols, 'execution_plans': plans,
        'checkpoint_stores': stores, 'sealed_stages': stages, 'twowiki_construction_incidents': incidents,
        'other_format_intents': other_intents,
        'heldout_300_protocol_pins': sorted(heldout),
        'heldout_300_execution_plans': [p for p in plans if p['protocol_sha256'] in heldout],
        'model_calls': 0, 'automatic_retry_permitted': False, 'scientific_authorization': 'NOT_VERIFIED',
        'limitations': ['Local files only; missing external evidence is not proof of nonexecution.',
            'Hashes establish current bytes, not independent authenticity or model-call approval.',
            'Checkpoint validation does not establish scientific validity or full seal semantics.',
            'Question, answer and prompt text are not emitted.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    evidence = args.results_root.expanduser().resolve(strict=True)
    if output == evidence or evidence in output.parents or output == ROOT or ROOT in output.parents:
        raise ValueError('Census output must be outside source and evidence trees')
    result = census(evidence)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({k: result[k] for k in ('file_count', 'inventory_sha256', 'heldout_300_protocol_pins',
                                          'heldout_300_execution_plans', 'model_calls')}, indent=2))


if __name__ == '__main__':
    main()
