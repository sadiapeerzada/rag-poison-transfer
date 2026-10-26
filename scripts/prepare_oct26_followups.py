#!/usr/bin/env python3
"""Predeclare source-selection budget and 2Wiki cohort hygiene, without inference.

This prepares protocols/preflights; it does not claim full execution adapters exist.
No README update, push, model call, or modification of historical artifacts.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src.experiments.week9_construction import canonical, fingerprint, rules

REVISION='9823f70484dea525100394220b0ea5184d0eeb7b'
SOURCES=('bm25','dense','hybrid','reranker')
TARGETS=(*SOURCES,'rcd')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as out:json.dump(value,out,indent=2,sort_keys=True,ensure_ascii=False);out.write('\n')


def choose_source_candidate(candidates,feedback):
    """Bounded source-only selection. Never accepts other-target feedback."""
    if len(candidates)>3 or len(candidates)!=len(feedback):raise ValueError('Frozen budget is at most three candidates')
    for index,row in enumerate(feedback):
        if set(row)-{'source_pipeline','candidate_index','construction_valid','source_target_match'}:
            raise ValueError('Forbidden target feedback in source-only selector')
        if row.get('source_pipeline') not in SOURCES or row.get('candidate_index')!=index:
            raise ValueError('Source identity/order mismatch')
        if type(row.get('construction_valid')) is not bool or type(row.get('source_target_match')) is not bool:
            raise ValueError('Missing actual source/validity flags')
        if not row['construction_valid'] and row['source_target_match']:
            raise ValueError('Failed construction cannot have source success')
    if len({r['source_pipeline'] for r in feedback})>1:raise ValueError('Mixed source pipelines')
    valid=[i for i,r in enumerate(feedback) if r['construction_valid']]
    success=[i for i in valid if feedback[i]['source_target_match']]
    return candidates[(success or valid)[0]] if valid else None


def transfer_definition(hotpot_root,pin):
    root=Path(hotpot_root)
    if sha(root/'aggregate.json')!=pin:raise ValueError('HotpotQA aggregate pin mismatch')
    prior=json.loads((root/'protocol.json').read_text())
    return {'schema':'rag-poison-transfer.source-selection-proposal/v1','status':'predeclared_budget_not_executed',
        'historical_hotpot_aggregate_sha256':pin,'historical_protocol_sha256':sha(root/'protocol.json'),
        'query_ids':prior['binding']['query_ids'],'dataset':prior['binding']['dataset'],
        'base_construction_rules':rules(),'sources':list(SOURCES),'targets':list(TARGETS),
        'candidate_budget_per_query_condition':3,'source_feedback_calls_per_valid_candidate':1,
        'candidate_order':'same frozen nomination list; rotate by original query/seed hash; take up to three distinct candidates',
        'candidate_library':'source-blind, generated once for all sources, all twelve conditions; no changes to attack definitions',
        'source_feedback_context':'each fixed candidate-band poisoned pooled corpus; source pipeline only',
        'selection':'evaluate every available candidate within fixed budget; first source target match, otherwise first valid construction; no extra retries',
        'freeze_barrier':'all candidate journals and all 48 source-selected construction conditions sealed before final target evaluation',
        'final_source_success':'re-evaluate source in selected union corpus; do not use selection-stage success as ATR denominator',
        'metrics':'full-population end-to-end ASR; conditional valid ASR; ATR intersection of final source/target successes divided by final source successes, null at zero',
        'clean_reuse':'one independently verified all-300 clean baseline per target, reused only with exact query/corpus/model/prompt provenance',
        'uncertainty':'query-cluster bootstrap retaining all seeds, sources and targets; compare source-matched conditions; disclose multiplicity',
        'source_conditions':48,'source_target_conditions':240,
        'maximum_calls':{'semantic_candidate_generation':21600,'source_screening_qa':43200,'final_clean_qa':1500,'final_poisoned_qa':72000},
        'rcd':'one unchanged composite defended target, never four wrapper variants',
        'execution_adapter_status':'not yet implemented or real-model smoke validated; no full execution authorized'}


def normalized_question(text):
    import re
    return ' '.join(re.findall(r'\w+',text.casefold()))


def near_duplicate(a,b,threshold=.85):
    if a==b:return True
    def grams(text):
        words=text.split()
        return {tuple(words[i:i+3]) for i in range(max(1,len(words)-2))}
    left,right=grams(a),grams(b)
    return bool(left|right) and len(left&right)/len(left|right)>=threshold


def select_cohorts(train,dev,history,history_questions,revision=REVISION):
    """Deterministic hygiene-only selection. Never uses answers, outcomes or attack eligibility."""
    train_ids=[r['_id'] for r in train];dev_ids=[r['_id'] for r in dev]
    if len(train_ids)!=len(set(train_ids)) or len(dev_ids)!=len(set(dev_ids)):
        raise ValueError('Duplicate dataset IDs')
    rank=lambda split,r:hashlib.sha256(canonical(['2wiki-cohort-hygiene/v1',revision,42,split,r['_id']])).hexdigest()
    blocked=set(history);comparison=[];selected={};exclusions=Counter()
    for split,records in [('train',train),('dev',dev)]:
        chosen=[]
        for row in sorted(records,key=lambda r:rank(split,r)):
            if row['_id'] in blocked:exclusions[split+'_id_overlap']+=1;continue
            text=normalized_question(row['question'])
            previous=comparison+[normalized_question(q) for q in history_questions]
            if any(near_duplicate(text,p) for p in previous):
                exclusions[split+'_exact_or_near_question_overlap']+=1;continue
            chosen.append({'query_id':row['_id'],'normalized_question_sha256':hashlib.sha256(text.encode()).hexdigest(),
                           'question_sha256':hashlib.sha256(row['question'].encode()).hexdigest()})
            blocked.add(row['_id']);comparison.append(text)
            if len(chosen)==300:break
        if len(chosen)!=300:raise ValueError('Insufficient disjoint cohort under predefined hygiene rules')
        selected[split]=chosen
    return selected,dict(exclusions)


def known_history():
    rows=[];files=[]
    for path in sorted((ROOT/'results').glob('*2wiki*.jsonl')):
        parsed=[json.loads(line) for line in path.read_text().splitlines()]
        rows.extend(parsed);files.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path),'records':len(parsed),
                                        'recorded_revisions':sorted({r.get('dataset_revision','missing') for r in parsed})})
    return {r['query_id'] for r in rows},sorted({r['question'] for r in rows}),files


def prepare_2wiki(output,fetch=False):
    output=Path(output)
    if output.exists():raise FileExistsError('Use a new versioned output directory')
    history,questions,files=known_history()
    policy={'schema':'rag-poison-transfer.2wiki-cohort-policy/v1','status':'predeclared_before_new_question_access',
        'dataset':'Salesforce/ContextualBench','config':'2WikiMultihopQA','revision':REVISION,
        'development_split':'train','heldout_split':'dev','development_count':300,'heldout_count':300,
        'selection_seed':42,'selection_rank':'SHA256(canonical [2wiki-cohort-hygiene/v1,revision,42,split,id])',
        'duplicate_rule':'unique IDs; normalized Unicode word-token questions; exact or 3-token-shingle Jaccard >=0.85 excluded against known history and already selected cohorts',
        'selection_exclusions':'history IDs + question duplicates only; no selection on answers, type, eligibility, model outcome or difficulty',
        'historical_25_query_sweep':'exact IDs unrecovered after bounded search; potential exposure remains unresolved',
        'complete_historical_nonoverlap_certified':False,'known_historical_ids':sorted(history),'historical_sources':files,
        'rcd_and_attack_definitions':'unchanged; separate new dataset protocol; no held-out tuning',
        'producer_script_sha256':sha(__file__),'producer_git_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}
    write(output/'cohort_policy.json',policy)
    if not fetch:return policy
    from huggingface_hub import HfApi,HfFileSystem
    import pyarrow.parquet as pq
    info=HfApi().dataset_info(policy['dataset'],revision=REVISION,files_metadata=True)
    if info.sha!=REVISION:raise ValueError('Dataset revision mismatch')
    filesystem=HfFileSystem();tables={'train':[],'dev':[]};inventory=[]
    for item in info.siblings:
        split='train' if item.rfilename.startswith('2WikiMultihopQA/train-') else 'dev' if item.rfilename.startswith('2WikiMultihopQA/dev-') else None
        if split is None:continue
        path='datasets/'+policy['dataset']+'@'+REVISION+'/'+item.rfilename
        with filesystem.open(path,'rb',block_size=65536) as stream:
            records=pq.read_table(stream,columns=['_id','question']).to_pylist()
        tables[split].extend(records)
        inventory.append({'path':item.rfilename,'repository_file_bytes':item.size,'projected_columns':['_id','question'],'row_count':len(records)})
    cohorts,exclusions=select_cohorts(tables['train'],tables['dev'],history,questions)
    manifest={'schema':'rag-poison-transfer.2wiki-disjoint-cohort-manifest/v1','status':'cohort_frozen_no_evaluation',
        'policy_sha256':sha(output/'cohort_policy.json'),'dataset_revision':REVISION,'seed':42,
        'cohorts':cohorts,'cohort_fingerprints':{s:fingerprint(v) for s,v in cohorts.items()},'exclusions':exclusions,
        'source_inventory':inventory,'complete_historical_nonoverlap_certified':False,
        'known_historical_nonoverlap_verified':not (set(history)&{r['query_id'] for group in cohorts.values() for r in group}),
        'development_heldout_id_overlap':len({r['query_id'] for r in cohorts['train']}&{r['query_id'] for r in cohorts['dev']}),
        'near_duplicate_cross_cohort_check':'passed by selection; no model outcomes or answer text accessed',
        'interpretation':'historically risk-disclosed replication; not an untouched/unexposed test cohort',
        'execution_adapter_status':'pending; full replication not authorized'}
    write(output/'cohort_manifest.json',manifest)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=('transfer','2wiki'))
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--hotpot-root',type=Path)
    parser.add_argument('--aggregate-sha256');parser.add_argument('--fetch-cohort-metadata',action='store_true')
    args=parser.parse_args()
    if args.stage=='transfer':
        if not args.hotpot_root or not args.aggregate_sha256:parser.error('Supply pinned HotpotQA root and aggregate hash')
        result=transfer_definition(args.hotpot_root,args.aggregate_sha256);write(args.output,result)
    else:result=prepare_2wiki(args.output,args.fetch_cohort_metadata)
    print(json.dumps({'status':result['status'],'output':str(args.output),'model_calls':0,'full_experiment_executed':False},indent=2))


if __name__=='__main__':main()
