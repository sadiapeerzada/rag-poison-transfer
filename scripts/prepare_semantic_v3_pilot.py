"""Preparation commands only. No command loads models or executes construction."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src.experiments.semantic_v3_preparation import build_registry, file_sha, read_pinned, select_cohort, prepare_target_forms
from src.experiments.semantic_v3_checkpoint import publish_json


def projected_ids(value):
    """Metadata projection from declared, previously exposed sources only."""
    found=set()
    if isinstance(value,dict):
        for key,item in value.items():
            if key in ('query_id','source_query_id','destination_query_id') and isinstance(item,str):found.add(item)
            elif key in ('query_ids','known_historical_ids','selected_query_ids') and isinstance(item,list):
                found.update(q for q in item if isinstance(q,str))
            elif re.fullmatch(r'[0-9a-f]{32}',key):found.add(key)
            if isinstance(item,(dict,list)):found.update(projected_ids(item))
    elif isinstance(value,list):
        for item in value:
            if isinstance(item,(dict,list)):found.update(projected_ids(item))
    return sorted(found)


def inventory(plan_path, output):
    """Only outputs known exclusions. Never creates a custodian certificate."""
    plan=json.loads(Path(plan_path).read_text());output=Path(output)
    output.mkdir(parents=True,exist_ok=False);sources=[]
    for index,entry in enumerate(plan['sources']):
        path=Path(entry['path']);value=json.loads(path.read_text())
        for key in entry.get('pointer',[]):value=value[key]
        ids=sorted(set(value)) if entry.get('ids_only') else projected_ids(value)
        export=output/f'source-{index:03d}.ids.json';publish_json(export,ids)
        sources.append({'category':entry['category'],'provenance':str(path),
                        'original_sha256':file_sha(path),'projection':entry.get('pointer',[]),
                        'ids_export':{'path':str(export.resolve()),'sha256':file_sha(export)}})
    registry=build_registry(sources,plan['historical_gaps'])
    publish_json(output/'registry.json',registry)
    return registry


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('inventory');p.add_argument('--source-plan',required=True);p.add_argument('--output-directory',required=True)
    p=sub.add_parser('select');
    for name in ('registry','registry-sha256','pool-ids','pool-sha256','dataset-sha256','output'):p.add_argument('--'+name,required=True)
    p=sub.add_parser('target-forms');p.add_argument('--handoff',required=True);p.add_argument('--output',required=True)
    args=parser.parse_args()
    if args.command=='inventory':
        registry=inventory(args.source_plan,args.output_directory)
        print(json.dumps({'excluded_ids':len(registry['excluded_query_ids']),'status':registry['status'],'selection_allowed':False}))
    elif args.command=='target-forms':
        forms=prepare_target_forms(json.loads(Path(args.handoff).read_text()))
        publish_json(args.output,forms)
        print('25 blank target forms prepared; no targets or approvals invented.')
    else:
        registry=read_pinned({'path':args.registry,'sha256':args.registry_sha256})
        pool=read_pinned({'path':args.pool_ids,'sha256':args.pool_sha256})
        cohort=select_cohort(pool,registry,dataset_sha256=args.dataset_sha256)
        publish_json(args.output,cohort)
        publish_json(args.output+'.freeze-receipt.json', {
            'schema':'semantic-v3-pre-content-freeze-receipt/v1',
            'frozen_at':datetime.now(timezone.utc).isoformat(),
            'input_sha256':{'cohort':file_sha(args.output),'registry':args.registry_sha256,
                            'pool_ids':args.pool_sha256,'data':args.dataset_sha256},
            'selector_source_sha256':file_sha(ROOT/'src/experiments/semantic_v3_preparation.py')})
        print('Ordered 25-ID cohort frozen. No content inspected or inference executed.')


if __name__=='__main__':main()
