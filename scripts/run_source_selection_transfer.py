#!/usr/bin/env python3
"""Versioned bounded source-only selection; explicit stages, no implicit full run.

Candidate generation precedes source feedback. All source selections are frozen
before any final target QA. RCD is a target only. Historical results are read-only.
"""
import argparse
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from run import build_retriever
from scripts import run_week9_protocol_poison_matrix as base
from scripts.prepare_oct26_followups import SOURCES,TARGETS,choose_source_candidate
from scripts.run_week9_matched_poison_comparison import evaluate_pipeline,validated_top_k
from src.experiments import week9_construction as old
from src.experiments.protocol import corpus_fingerprint,query_set_fingerprint
from src.attacks.development_targets_v3 import nominate
from src.attacks.development_targets_v2 import build_pool
from src.attacks.lexical import LexicalInfluentialTokenAttack
from src.attacks.semantic_fluent import SemanticFluentFalseEvidenceAttack,SemanticQualityError
from src.attacks.asr import build_prompt
from src.evaluation.qa_records import generate_qa
from src.evaluation.metrics import exact_match
from src.evaluation.qa_records import validate_qa,extract_answer

SCHEMA='rag-poison-transfer.bounded-source-selection/v1'
SEAL='rag-poison-transfer.selected-source-poison-seal/v1'


def candidates(query,development,seed):
    choices=sorted(nominate(query,development,build_pool(development))['candidates'],key=old.canonical)
    if not choices:return []
    start=old.derived_seed(seed,query['query_id'],'target-selection')%len(choices)
    return (choices[start:]+choices[:start])[:3]


def configurations(dense,rcd):
    return {name:copy.deepcopy(rcd if name=='rcd' else {**dense,'retriever':name,
        **({'reranker_model':'cross-encoder/ms-marco-MiniLM-L-6-v2'} if name=='reranker' else {})}) for name in TARGETS}


def freeze(output,base_protocol,pin,snapshot,scope,embedder_snapshot,reranker_snapshot):
    prior=base.read_pinned(base_protocol,pin)
    binding,dense,rcd,dev=base.metadata('heldout')
    if prior['binding']!=binding or prior['rules']!=old.rules():raise ValueError('Base protocol/config/rules mismatch')
    ids=binding['query_ids'] if scope=='heldout' else list(base.DEV_IDS)
    spec={'schema':SCHEMA,'scope':scope,'source':base.code_binding(),'environment':base.environment(),
        'base_protocol_sha256':pin,'binding':{**binding,'query_ids':ids,'scope':scope,'matrix':[list(c) for c in old.cells(scope)]},'configs':configurations(dense,rcd),
        'rules':old.rules(),'model':base.model_binding(snapshot,binding['model_identity']),
        'candidate_budget':3,'selection_rule':'all fixed candidates evaluated on source only; first target match else first valid',
        'sources':list(SOURCES),'targets':list(TARGETS),'matrix':[list(c) for c in old.cells(scope)],
        'target_barrier':'all source-selected poison snapshots must be sealed before final source/target evaluation',
        'source_screening':'candidate-band pooled corpus; final ATR uses new final-source measurements in selected union corpus',
        'maximum_model_calls':(208800 if scope=='heldout' else 220),
        'clean_baseline_reuse_implemented':False,
        'retrieval_snapshots':{
            'embedder':{'path':str(Path(embedder_snapshot).resolve()),'binding':base.model_binding(embedder_snapshot,'BAAI/bge-small-en-v1.5')},
            'reranker':{'path':str(Path(reranker_snapshot).resolve()),'binding':base.model_binding(reranker_snapshot,'cross-encoder/ms-marco-MiniLM-L-6-v2')}},
        'construction_failures':'Option2 preserved; null poisoned measurements, zero end-to-end contribution; no source resampling'}
    base.legacy._ensure_output_outside_repository(Path(output).parent)
    base.write(output,spec)
    return {'protocol_sha256':base.sha(output),'scope':scope,'maximum_model_calls':spec['maximum_model_calls']}


def load(path,pin,snapshot=None):
    spec=base.read_pinned(path,pin)
    if spec.get('schema')!=SCHEMA or spec.get('source')!=base.code_binding() or spec.get('environment')!=base.environment() or spec.get('rules')!=old.rules() or spec.get('candidate_budget')!=3:
        raise ValueError('Transfer protocol/source/environment mismatch')
    binding,dense,rcd,dev=base.metadata('heldout')
    wanted={**binding,'query_ids':binding['query_ids'] if spec['scope']=='heldout' else list(base.DEV_IDS),'scope':spec['scope'],'matrix':[list(c) for c in old.cells(spec['scope'])]}
    if spec['binding']!=wanted or spec['configs']!=configurations(dense,rcd) or spec['sources']!=list(SOURCES) or spec['targets']!=list(TARGETS) or spec['matrix']!=[list(c) for c in old.cells(spec['scope'])]:
        raise ValueError('Transfer cohort/configuration/matrix mismatch')
    if snapshot is not None and spec['model']!=base.model_binding(snapshot,binding['model_identity']):raise ValueError('Model mismatch')
    for name,identity in [('embedder','BAAI/bge-small-en-v1.5'),('reranker','cross-encoder/ms-marco-MiniLM-L-6-v2')]:
        entry=spec['retrieval_snapshots'][name]
        if base.model_binding(entry['path'],identity)!=entry['binding']:raise ValueError('Retrieval snapshot mismatch')
    return spec,dense,rcd,dev


def retrieval_config(spec,name):
    cfg=copy.deepcopy(spec['configs'][name])
    if 'retrieval_snapshots' in spec:
        cfg['embedder_model']=spec['retrieval_snapshots']['embedder']['path']
        if name=='reranker':cfg['reranker_model']=spec['retrieval_snapshots']['reranker']['path']
    return cfg


def clean_data(spec,rcd):
    return base.load_clean({'binding':spec['binding']},rcd)


def source_guard(spec):
    if base.code_binding()!=spec['source'] or base.environment()!=spec['environment']:
        raise ValueError('Transfer source/environment changed during execution')


def fixed_construction(q,choice,family,intensity,seed,band,backend):
    row={'query_id':q['query_id'],'query_fingerprint':old.fingerprint(q),'target_answer':choice['answer'] if choice else None,
         'documents':[],'partial_documents':[],'attempt_records':[],'candidate_band':band,'selection':choice}
    if choice is None:return {**row,'status':old.TARGET_FAILED}
    attack=LexicalInfluentialTokenAttack(4) if family==old.ATTACKS[0] else SemanticFluentFalseEvidenceAttack(backend,max_tokens=150,max_attempts=2)
    if family==old.ATTACKS[1]:attack.capture_smoke_diagnostics=True
    docs=[]
    for index in range(intensity):
        runtime=old.derived_seed(seed,q['query_id'],family+'.candidate-'+str(band),index);base.runtime_seed(runtime)
        try:docs.append(asdict(attack.generate(q,[q],random.Random(runtime),index,choice['answer'])))
        except SemanticQualityError:pass
    if family==old.ATTACKS[1]:row['attempt_records']=attack.export_attempt_records()
    return {**row,'status':old.VALID if len(docs)==intensity else old.SEMANTIC_FAILED,
            'documents':docs if len(docs)==intensity else [],'partial_documents':[] if len(docs)==intensity else docs}


def materialize(path,pin,root,snapshot,allow_full=False):
    spec,dense,rcd,development=load(path,pin,snapshot)
    if spec['scope']=='heldout' and not allow_full:raise ValueError('Full candidate construction requires explicit compute approval/--allow-full-compute')
    root=base.legacy._ensure_output_outside_repository(Path(root))
    if root.exists():raise FileExistsError('Fresh transfer output required; interrupted attempts remain preserved')
    clean=clean_data(spec,rcd);root.mkdir(parents=True)
    base.write(root/'plan.json',{'protocol_sha256':pin,'source':spec['source'],'query_fingerprint':query_set_fingerprint(clean['queries']),'corpus_fingerprint':corpus_fingerprint(clean['corpus'])})
    backend=None
    for family,intensity,seed in old.cells(spec['scope']):
        source_guard(spec)
        identity=old.cell_id(family,intensity,seed)
        for band in range(3):
            records=[]
            for q in clean['queries']:
                choices=candidates(q,development,seed);choice=choices[band] if len(choices)>band else None
                if choice and family==old.ATTACKS[1] and backend is None:backend=base.generator(rcd,snapshot)
                journal=base.JournalGenerator(backend,root/'calls'/identity/str(band)/hashlib.sha256(q['query_id'].encode()).hexdigest(),
                    {'protocol_sha256':pin,'model':spec['model'],'candidate_band':band,'family':family,'intensity':intensity,'seed':seed,'query_id':q['query_id']})
                records.append(fixed_construction(q,choice,family,intensity,seed,band,journal))
            base.write(root/'candidates'/identity/(str(band)+'.json'),{'family':family,'intensity':intensity,'seed':seed,'records':records})
    source_guard(spec)
    files=base.construction_files(root)
    base.write(root/'candidates.complete.json',{'protocol_sha256':pin,'files_sha256':files})
    return {'status':'candidate_library_complete_no_source_or_target_evaluation','candidate_completion_sha256':base.sha(root/'candidates.complete.json')}


def verify_files(root,manifest,excluded):
    if any(p.is_symlink() for p in root.rglob('*')):raise ValueError('Frozen transfer artifacts cannot contain symlinks')
    actual={p.relative_to(root).as_posix():base.sha(p) for p in root.rglob('*') if p.is_file() and p.name not in excluded}
    if actual!=manifest['files_sha256']:raise ValueError('Transfer frozen file integrity mismatch')


def source_select(path,pin,library,library_pin,output,snapshot,allow_full=False):
    spec,dense,rcd,dev=load(path,pin,snapshot)
    if spec['scope']=='heldout' and not allow_full:raise ValueError('Full source screening requires compute approval')
    library=Path(library);manifest=base.read_pinned(library/'candidates.complete.json',library_pin)
    verify_files(library,manifest,{'candidates.complete.json'})
    if manifest['protocol_sha256']!=pin:raise ValueError('Candidate protocol mismatch')
    output=base.legacy._ensure_output_outside_repository(Path(output))
    if output.exists():raise FileExistsError('Fresh source-selection output required')
    clean=clean_data(spec,rcd);output.mkdir(parents=True);backend=None
    previous_plan=json.loads((library/'plan.json').read_text())
    if previous_plan!={'protocol_sha256':pin,'source':spec['source'],'query_fingerprint':query_set_fingerprint(clean['queries']),'corpus_fingerprint':corpus_fingerprint(clean['corpus'])}:
        raise ValueError('Candidate library dataset/source provenance mismatch')
    for family,intensity,seed in old.cells(spec['scope']):
        source_guard(spec)
        identity=old.cell_id(family,intensity,seed)
        bands=[json.loads((library/'candidates'/identity/(str(band)+'.json')).read_text()) for band in range(3)]
        for band,cell in enumerate(bands):
            if (cell['family'],cell['intensity'],cell['seed'])!=(family,intensity,seed) or [r['query_id'] for r in cell['records']]!=[q['query_id'] for q in clean['queries']]:raise ValueError('Candidate matrix/population mismatch')
            for q,record in zip(clean['queries'],cell['records']):
                choices=candidates(q,dev,seed);choice=choices[band] if len(choices)>band else None
                if record['target_answer']!=(choice['answer'] if choice else None) or record['query_fingerprint']!=old.fingerprint(q):raise ValueError('Frozen candidate selection mismatch')
                if record['status']==old.VALID and len(record['documents'])!=intensity:raise ValueError('Partial intensity substitution')
                if record['status']!=old.VALID and record['documents']:raise ValueError('Failed candidate has injected documents')
        for source in SOURCES:
            feedback={q['query_id']:[] for q in clean['queries']}
            for band,cell in enumerate(bands):
                poisoned=old.replay(clean,cell);retriever=None
                if poisoned['queries']:
                    if backend is None:backend=base.generator(rcd,snapshot)
                    retriever=build_retriever(retrieval_config(spec,source));retriever.build(copy.deepcopy(poisoned['corpus']))
                journal=base.JournalGenerator(backend,output/'calls'/identity/source/str(band),{'protocol_sha256':pin,'candidate_library_completion_sha256':library_pin,'source':source,'band':band,'model':spec['model']})
                for q,record in zip(clean['queries'],cell['records']):
                    measured=None;match=False
                    if record['status']==old.VALID:
                        base.runtime_seed(42);evidence=retriever.retrieve(q['question'],top_k=3)
                        measured=generate_qa(journal,build_prompt(q['question'],[d.text for d in evidence]),64,
                            context={'stage':'source-screen','source':source,'query_id':q['query_id'],'candidate_band':band})
                        match=bool(exact_match(measured['extracted_answer'],record['target_answer']))
                    feedback[q['query_id']].append({'source_pipeline':source,'candidate_index':band,'construction_valid':record['status']==old.VALID,'source_target_match':match,'observation':measured})
            selected=[]
            for index,q in enumerate(clean['queries']):
                options=[band['records'][index] for band in bands]
                flags=[{k:v for k,v in f.items() if k!='observation'} for f in feedback[q['query_id']]]
                choice=choose_source_candidate(options,flags)
                if choice is None:
                    anytarget=next((r for r in options if r['target_answer'] is not None),None)
                    choice={**(anytarget or options[0]),'status':old.SEMANTIC_FAILED if anytarget else old.TARGET_FAILED,'documents':[]}
                selected.append({**choice,'source_pipeline':source,'source_feedback':feedback[q['query_id']]})
            base.write(output/'selected'/identity/(source+'.json'),{'family':family,'intensity':intensity,'seed':seed,'source':source,'records':selected})
    source_guard(spec)
    base.write(output/'selection.seal.json',{'schema':SEAL,'protocol_sha256':pin,'candidate_library_completion_sha256':library_pin,
        'files_sha256':base.construction_files(output)})
    return {'status':'all_source_selections_frozen_no_final_target_evaluation','selection_seal_sha256':base.sha(output/'selection.seal.json')}


def final_evaluate(path,pin,selected,seal_pin,output,snapshot,allow_full=False):
    spec,dense,rcd,dev=load(path,pin,snapshot)
    if spec['scope']=='heldout' and not allow_full:raise ValueError('Full target evaluation requires compute approval')
    selected=Path(selected);seal=base.read_pinned(selected/'selection.seal.json',seal_pin)
    verify_files(selected,seal,{'selection.seal.json'})
    if seal['schema']!=SEAL or seal['protocol_sha256']!=pin:raise ValueError('Source-selection seal mismatch')
    expected={str(Path('selected')/old.cell_id(*c)/(source+'.json')) for c in old.cells(spec['scope']) for source in SOURCES}
    if not expected.issubset(seal['files_sha256']):raise ValueError('Global source-selection barrier incomplete')
    output=base.legacy._ensure_output_outside_repository(Path(output))
    if output.exists():raise FileExistsError('Fresh final transfer output required')
    clean=clean_data(spec,rcd);output.mkdir(parents=True);backend=None;summary=[]
    for family,intensity,seed in old.cells(spec['scope']):
        source_guard(spec)
        identity=old.cell_id(family,intensity,seed)
        for source in SOURCES:
            cell=json.loads((selected/'selected'/identity/(source+'.json')).read_text());poisoned=old.replay(clean,cell)
            valid={q['query_id'] for q in poisoned['queries']};clean_valid={'corpus':clean['corpus'],'queries':[q for q in clean['queries'] if q['query_id'] in valid]}
            observed={}
            if valid and backend is None:backend=base.generator(rcd,snapshot)
            for target in TARGETS:
                pairs=[]
                if valid:
                    cfg=retrieval_config(spec,target);clean_r=build_retriever(cfg);poison_r=build_retriever(cfg)
                    clean_r.build(copy.deepcopy(clean['corpus']));poison_r.build(copy.deepcopy(poisoned['corpus']))
                    base.runtime_seed(42)
                    journal=base.JournalGenerator(backend,output/'calls'/identity/source/target,{'protocol_sha256':pin,'selection_seal_sha256':seal_pin,'source':source,'target':target,'model':spec['model']})
                    pairs=evaluate_pipeline(pipeline=target,clean_retriever=clean_r,poisoned_retriever=poison_r,clean_data=clean_valid,poisoned_data=poisoned,generator=journal,top_k=3,max_tokens=64)
                byid={p['query_id']:p for p in pairs}
                observed[target]=[{'query_id':q['query_id'],'construction_status':cell['records'][i]['status'],'measurement':byid.get(q['query_id'])} for i,q in enumerate(clean['queries'])]
                base.write(output/'rows'/identity/source/(target+'.json'),observed[target])
            for target in TARGETS:
                source_success={r['query_id'] for r in observed[source] if r['measurement'] and r['measurement']['poisoned_condition']['targeted_asr']}
                target_success={r['query_id'] for r in observed[target] if r['measurement'] and r['measurement']['poisoned_condition']['targeted_asr']}
                summary.append({'family':family,'intensity':intensity,'seed':seed,'source':source,'target':target,'population':len(clean['queries']),
                    'valid':len(valid),'source_successes':len(source_success),'target_successes':len(target_success),
                    'transferred':len(source_success&target_success),'atr':len(source_success&target_success)/len(source_success) if source_success else None,
                    'target_end_to_end_asr':len(target_success)/len(clean['queries']),'target_conditional_asr':len(target_success)/len(valid) if valid else None})
    source_guard(spec)
    base.write(output/'transfer_summary.json',summary)
    base.write(output/'transfer.complete.json',{'schema':SCHEMA,'protocol_sha256':pin,'selection_seal_sha256':seal_pin,'scope':spec['scope'],'files_sha256':base.construction_files(output),
        'limitations':'point estimates only; final independent aggregate validation and query-cluster ATR uncertainty still required'})
    return {'status':'executed_requires_independent_validation_and_ATR_intervals','source_target_cells':len(summary),'completion_sha256':base.sha(output/'transfer.complete.json')}


def aggregate(path,pin,evaluation,completion_pin,selected,seal_pin,output,replicates=2000):
    import numpy as np
    spec,dense,rcd,dev=load(path,pin)
    evaluation,selected=Path(evaluation),Path(selected)
    completion=base.read_pinned(evaluation/'transfer.complete.json',completion_pin)
    seal=base.read_pinned(selected/'selection.seal.json',seal_pin)
    verify_files(evaluation,completion,{'transfer.complete.json'});verify_files(selected,seal,{'selection.seal.json'})
    if completion['selection_seal_sha256']!=seal_pin or completion['protocol_sha256']!=pin or seal['protocol_sha256']!=pin:raise ValueError('Transfer aggregate provenance mismatch')
    ids=spec['binding']['query_ids'];rng=random.Random(20261026)
    indices=np.asarray([rng.choices(range(len(ids)),k=len(ids)) for _ in range(replicates)])
    per_cell=[];clustered={}
    for family,intensity,seed in old.cells(spec['scope']):
        identity=old.cell_id(family,intensity,seed)
        for source in SOURCES:
            source_rows=json.loads((evaluation/'rows'/identity/source/(source+'.json')).read_text())
            ledger=json.loads((selected/'selected'/identity/(source+'.json')).read_text())['records']
            if [r['query_id'] for r in ledger]!=ids:raise ValueError('Source ledger population mismatch')
            for target in TARGETS:
                target_rows=json.loads((evaluation/'rows'/identity/source/(target+'.json')).read_text())
                if [r['query_id'] for r in source_rows]!=ids or [r['query_id'] for r in target_rows]!=ids:raise ValueError('Transfer ID alignment mismatch')
                values=np.zeros((len(ids),4),dtype=int)
                for i,(s,t,l) in enumerate(zip(source_rows,target_rows,ledger)):
                    if s['construction_status']!=l['status'] or t['construction_status']!=l['status']:raise ValueError('Transfer construction status mismatch')
                    if l['status']!=old.VALID:
                        if s['measurement'] is not None or t['measurement'] is not None:raise ValueError('Fabricated failure observations')
                        continue
                    sm,tm=s['measurement'],t['measurement']
                    for m in (sm,tm):
                        if set(m['poison_doc_ids'])!={d['doc_id'] for d in l['documents']} or m['poison_target_answer']!=l['target_answer']:raise ValueError('Poison replay mismatch')
                        for c in ('clean','poisoned'):
                            obs=m[c+'_condition'];validate_qa(obs['generation'],obs['answer'])
                            if obs['em']!=exact_match(obs['answer'],m['gold_answer']):raise ValueError('Transfer EM mismatch')
                        if m['poisoned_condition']['targeted_asr']!=bool(exact_match(m['poisoned_condition']['answer'],l['target_answer'])):raise ValueError('Transfer target metric mismatch')
                    if sm['gold_answer']!=tm['gold_answer']:raise ValueError('Transfer gold pairing mismatch')
                    ss=int(sm['poisoned_condition']['targeted_asr']);ts=int(tm['poisoned_condition']['targeted_asr'])
                    values[i]=[ss*ts,ss,ts,1]
                totals=values.sum(axis=0)
                row={'family':family,'intensity':intensity,'seed':seed,'source':source,'target':target,'population':len(ids),
                    'valid':int(totals[3]),'source_successes':int(totals[1]),'target_successes':int(totals[2]),'transferred':int(totals[0]),
                    'atr':float(totals[0]/totals[1]) if totals[1] else None,
                    'target_end_to_end_asr':float(totals[2]/len(ids)),'target_conditional_asr':float(totals[2]/totals[3]) if totals[3] else None}
                per_cell.append(row)
                key=f'{family}.intensity-{intensity}.{source}->{target}'
                clustered.setdefault(key,np.zeros_like(values));clustered[key]+=values
    if json.loads((evaluation/'transfer_summary.json').read_text())!=per_cell:raise ValueError('Transfer summary differs from aligned raw observations')
    intervals={}
    for key,values in clustered.items():
        totals=values.sum(axis=0);draws=values[indices].sum(axis=1)
        with np.errstate(invalid='ignore',divide='ignore'):ratios=draws[:,0]/draws[:,1]
        ordered=sorted(float(v) for v in ratios if np.isfinite(v))
        intervals[key]={'atr':float(totals[0]/totals[1]) if totals[1] else None,
            'ci95_percentile':[ordered[int((len(ordered)-1)*p)] for p in (.025,.975)] if ordered else None,
            'source_success_denominator':int(totals[1]),'defined_replicates':len(ordered),'undefined_replicates':replicates-len(ordered),
            'unique_queries':len(ids),'resampling_unit':'query cluster retaining all poison seeds','bootstrap_seed':20261026}
    base.write(output,{'schema':'rag-poison-transfer.bounded-source-transfer-aggregate/v1','scope':spec['scope'],'protocol_sha256':pin,
        'selection_seal_sha256':seal_pin,'completion_sha256':completion_pin,'per_cell':per_cell,'atr_query_cluster_intervals':intervals,
        'replicates':replicates,'multiplicity_adjusted':False})
    return {'status':'validated','cells':len(per_cell),'scope':spec['scope']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=('freeze','candidates','source-select','evaluate','aggregate'))
    parser.add_argument('--protocol',type=Path);parser.add_argument('--protocol-sha256');parser.add_argument('--base-protocol',type=Path);parser.add_argument('--base-protocol-sha256')
    parser.add_argument('--model-snapshot',type=Path,required=True);parser.add_argument('--scope',choices=('heldout','development'),default='development')
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--input-dir',type=Path);parser.add_argument('--input-sha256');parser.add_argument('--allow-full-compute',action='store_true')
    parser.add_argument('--embedder-snapshot',type=Path);parser.add_argument('--reranker-snapshot',type=Path)
    parser.add_argument('--selected-dir',type=Path);parser.add_argument('--selection-seal-sha256')
    args=parser.parse_args()
    if args.stage=='freeze':
        if not args.base_protocol or not args.base_protocol_sha256 or not args.embedder_snapshot or not args.reranker_snapshot:parser.error('Supply base protocol/pin and both retrieval snapshots')
        result=freeze(args.output,args.base_protocol,args.base_protocol_sha256,args.model_snapshot,args.scope,args.embedder_snapshot,args.reranker_snapshot)
    else:
        if not args.protocol or not args.protocol_sha256:parser.error('Supply frozen source-selection protocol and pin')
        if args.stage=='candidates':result=materialize(args.protocol,args.protocol_sha256,args.output,args.model_snapshot,args.allow_full_compute)
        else:
            if not args.input_dir or not args.input_sha256:parser.error('Supply exact previous-stage artifact and pin')
            if args.stage=='aggregate':
                if not args.selected_dir or not args.selection_seal_sha256:parser.error('Supply selected source directory and seal pin')
                result=aggregate(args.protocol,args.protocol_sha256,args.input_dir,args.input_sha256,args.selected_dir,args.selection_seal_sha256,args.output)
            else:
                fn=source_select if args.stage=='source-select' else final_evaluate
                result=fn(args.protocol,args.protocol_sha256,args.input_dir,args.input_sha256,args.output,args.model_snapshot,args.allow_full_compute)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
