#!/usr/bin/env python3
"""Plan/freeze a fresh two-query development diagnostic; never invokes inference."""
import sys
sys.dont_write_bytecode=True
import argparse
import copy
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import run_week9_protocol_poison_matrix as base
from scripts.audit_2wiki_smoke_incident import audit
from src.experiments import execution_reliability as reliable
from src.experiments import twowiki_replication as two


def validate_development_parent(parent):
    binding=parent.get('binding',{});ids=binding.get('query_ids',[])
    if (parent.get('schema')!=base.RELIABLE_REPLICATION_SCHEMA or binding.get('scope')!='development' or
        len(ids)!=2 or len(set(ids))!=2 or binding.get('matrix')!=[list(c) for c in base.protocol.cells('development')] or
        binding.get('dataset',{}).get('loader')!='load_2wikimultihopqa' or binding.get('dataset',{}).get('split')!='train' or
        binding.get('dataset',{}).get('revision')!=two.REVISION or
        parent.get('replication',{}).get('schema')!=two.LOCAL_SCHEMA or parent['replication'].get('scope')!='development' or
        parent.get('execution')!=reliable.DEFAULTS or
        parent.get('rules')!={**base.protocol.rules(),'dataset_replication':'risk-disclosed-2wiki/v1'}):
        raise ValueError('Recovery preparation permits only the exact two-query train/development smoke, intensity 1, seed 42')


def prepare(parent_path,parent_pin,failed_root,namespace,snapshot,freeze=False):
    parent=base.read_pinned(parent_path,parent_pin);validate_development_parent(parent)
    failed_root=Path(failed_root).resolve();namespace=base.legacy._ensure_output_outside_repository(Path(namespace))
    if failed_root!=Path(parent['planned_outputs']['construction']).resolve():raise ValueError('Failed construction path differs from parent protocol')
    parent_root=Path(parent_path).resolve().parent
    if namespace.exists() or namespace==parent_root or parent_root in namespace.parents or namespace==failed_root or failed_root in namespace.parents:
        raise ValueError('Use a new isolated namespace outside the failed protocol/run')
    incident=audit(parent_path,parent_pin,failed_root)
    if incident['plan_status']!='matches':raise ValueError('Incident plan does not match frozen parent')
    binding,*_=base.context_metadata('development',parent['replication'])
    if binding!=parent['binding']:raise ValueError('Development IDs, pool, configs or input provenance changed')
    if base.model_binding(snapshot,parent['binding']['model_identity'])!=parent['model']:raise ValueError('Model snapshot changed')
    reference={'parent_protocol_sha256':parent_pin,'failed_namespace':str(failed_root),
        'incident_inventory_sha256':incident['inventory_sha256'],
        'meaning':'new separately approved development diagnostic; not completion or retry of an indeterminate call'}
    result={'status':'plan_only_no_files_written','scope':'development','query_ids':parent['binding']['query_ids'],
        'matrix':parent['binding']['matrix'],'new_namespace':str(namespace),'incident_reference':reference,
        'maximum_model_calls_without_cache_savings':20,'maximum_with_planned_identical_clean_hits':16,
        'new_model_calls_executed':0,'requires':['review implementation and tests before committing',
            'separate explicit approval for a new diagnostic namespace and additional model-call budget',
            'clean reviewed commit before freeze; do not bypass provenance guards'],
        'unresolved_calls_in_failed_run':incident['journal_counts'].get('unresolved_intent',0)}
    if freeze:
        # This is metadata-only, and must still fail from an unreviewed dirty checkout.
        base.code_binding()
        replication=copy.deepcopy(parent['replication']);replication['development_incident_reference']=reference
        frozen=base.freeze_protocol(namespace/'protocol.json','development',snapshot,replication)
        value=base.read_pinned(namespace/'protocol.json',frozen['protocol_sha256'])
        for field in ('binding','rules','model','execution'):
            if value[field]!=parent[field]:raise ValueError('New diagnostic changed frozen scientific field: '+field)
        reliable.atomic(namespace/'incident_reference.json',{'reference':reference,'diagnostics':incident})
        result.update(status='fresh_development_protocol_frozen_no_inference',protocol_sha256=frozen['protocol_sha256'])
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('parent-protocol','failed-construction-dir','new-namespace','model-snapshot'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--parent-protocol-sha256',required=True)
    p.add_argument('--freeze',action='store_true',help='Metadata-only; requires reviewed clean code. No model execution.')
    a=p.parse_args();print(json.dumps(prepare(a.parent_protocol,a.parent_protocol_sha256,a.failed_construction_dir,a.new_namespace,a.model_snapshot,a.freeze),indent=2))

if __name__=='__main__':main()
