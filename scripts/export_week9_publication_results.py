#!/usr/bin/env python3
"""Read-only frozen-record validation and new-directory publication exports.

No model/dataset construction. Does not amend original aggregate or README.
Matplotlib is optional until --figures; install it outside the frozen runtime.
"""
import argparse
from collections import Counter
import csv
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import random
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from src.evaluation.metrics import exact_match,f1_score
from src.evaluation.qa_records import extract_answer


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def equal(a,b):
    if isinstance(a,(float,int)) and isinstance(b,(float,int)):
        return math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-12)
    return a==b


def verify_inputs(root,aggregate_sha):
    root=Path(root)
    if sha(root/'aggregate.json')!=aggregate_sha:
        raise ValueError('Externally pinned aggregate hash mismatch')
    aggregate=read(root/'aggregate.json')
    for path,key in [('protocol.json','protocol_sha256'),('construction/construction.seal.json','construction_seal_sha256'),('evaluation/evaluation.complete.json','evaluation_completion_sha256')]:
        if sha(root/path)!=aggregate[key]:
            raise ValueError('Aggregate provenance mismatch: '+key)
    protocol=read(root/'protocol.json');ids=protocol['binding']['query_ids']
    if aggregate.get('scope')!='heldout' or len(ids)!=300 or len(set(ids))!=300:
        raise ValueError('Expected unchanged 300-query held-out population')
    matrices={f'{a}.intensity-{i}.seed-{s}' for a,i,s in protocol['binding']['matrix']}
    if len(matrices)!=12 or set(aggregate['cells'])!=matrices:
        raise ValueError('Expected twelve complete matrix cells')
    checked=0
    for directory,filename in [('construction','construction.seal.json'),('evaluation','evaluation.complete.json')]:
        parent=root/directory;manifest=read(parent/filename)
        actual={p.relative_to(parent).as_posix() for p in parent.rglob('*') if p.is_file() and p.name!=filename}
        if actual!=set(manifest['files_sha256']):
            raise ValueError('Artifact inventory mismatch')
        for relative,digest in manifest['files_sha256'].items():
            if sha(parent/relative)!=digest:
                raise ValueError('Artifact file hash mismatch: '+relative)
            checked+=1
    rows={};constructions={}
    for cell in sorted(matrices):
        rows[cell]=read(root/'evaluation'/cell/'rows.json')
        constructions[cell]=read(root/'construction'/cell/'construction.json')
        expected=[(arm,qid) for arm in ('dense','rcd') for qid in ids]
        if [(r['pipeline'],r['query_id']) for r in rows[cell]]!=expected:
            raise ValueError('Query pairing/population mismatch')
        ledger={r['query_id']:r for r in constructions[cell]['records']}
        for row in rows[cell]:
            record=ledger[row['query_id']];m=row['measurement']
            if row['construction_status']!=record['status']:
                raise ValueError('Construction/evaluation mismatch')
            if record['status']!='valid_construction':
                if m is not None or row['evaluation_status']!='not_evaluated_construction_failed':
                    raise ValueError('Fabricated failed-construction observation')
                continue
            if (m['poison_target_answer']!=record['target_answer'] or
                sorted(m['poison_doc_ids'])!=sorted(d['doc_id'] for d in record['documents'])):
                raise ValueError('Matched target/poison identity mismatch')
            for condition in ('clean','poisoned'):
                obs=m[condition+'_condition'];g=obs['generation']
                answer=extract_answer(g['raw_response'])
                if (answer!=obs['answer'] or g['prompt_sha256']!=hashlib.sha256(g['prompt'].encode()).hexdigest() or
                    obs['em']!=exact_match(answer,m['gold_answer']) or not equal(obs['f1'],f1_score(answer,m['gold_answer']))):
                    raise ValueError('Raw-response/metric mismatch')
            poisoned=m['poisoned_condition'];poison=set(m['poison_doc_ids'])
            if poisoned['targeted_asr']!=bool(exact_match(poisoned['answer'],m['poison_target_answer'])):
                raise ValueError('Targeted ASR mismatch')
            if poisoned['poison_retrieved']!=bool(poison&set(poisoned['generation_evidence_doc_ids'])):
                raise ValueError('Generator exposure mismatch')
            for k in (1,3,5,10):
                if poisoned['prr_at_k'][str(k)]!=float(bool(poison&set(poisoned['retrieved_doc_ids'][:k]))):
                    raise ValueError('Poison retrieval mismatch')
            if m['query_untargeted_degradation']!=(m['clean_condition']['answer_correct'] and not poisoned['answer_correct']):
                raise ValueError('Untargeted degradation mismatch')
    return aggregate,protocol,rows,constructions,checked


def summarize(measurements,population):
    n=len(measurements);sumfield=lambda c,k:sum(m[c+'_condition'][k] for m in measurements)
    successes=sumfield('poisoned','targeted_asr');exposed=[m for m in measurements if m['poisoned_condition']['poison_retrieved']]
    mean=lambda values:sum(values)/len(values) if values else None
    result={'population_query_seed':population,'valid_query_seed':n,'failed_query_seed':population-n,
        'targeted_successes':successes,'end_to_end_asr':successes/population,'conditional_asr':successes/n if n else None,
        'exposed':len(exposed),'exposure_rate':len(exposed)/n if n else None,
        'asr_given_exposure':sum(m['poisoned_condition']['targeted_asr'] for m in exposed)/len(exposed) if exposed else None,
        'degradation_count':sum(m['query_untargeted_degradation'] for m in measurements),
        'degradation_rate':sum(m['query_untargeted_degradation'] for m in measurements)/n if n else None}
    for c in ('clean','poisoned'):
        result[c+'_em']=sumfield(c,'em')/n if n else None
        result[c+'_f1']=sumfield(c,'f1')/n if n else None
        result[c+'_qa_wall_seconds_mean']=mean([m[c+'_condition']['generation']['elapsed_seconds'] for m in measurements])
        result[c+'_model_reported_seconds_mean']=mean([m[c+'_condition']['generation']['generator_latency_seconds'] for m in measurements])
        result[c+'_retrieval_seconds_mean']=mean([m[c+'_condition']['retrieval_elapsed_seconds'] for m in measurements])
    result['em_retention']=result['poisoned_em']/result['clean_em'] if result['clean_em'] else None
    result['f1_retention']=result['poisoned_f1']/result['clean_f1'] if result['clean_f1'] else None
    result['diagnostic_retrieval_seconds_mean']=mean([m['poisoned_condition']['diagnostic_retrieval_elapsed_seconds'] for m in measurements])
    for k in (1,3,5,10):result['prr_'+str(k)]=mean([m['poisoned_condition']['prr_at_k'][str(k)] for m in measurements])
    observations=[m[c+'_condition'] for m in measurements for c in ('clean','poisoned')]
    for key in ('normal_retrieval_calls','diagnostic_retrieval_calls','normal_inner_retrieval_operations','diagnostic_inner_retrieval_operations'):
        values=[o['retrieval_call_accounting'].get(key) for o in observations]
        result[key]=sum(values) if all(type(v) is int for v in values) else None
    result['prompt_tokens_total']=sum(o['generation']['prompt_tokens'] for o in observations)
    result['completion_tokens_total']=sum(o['generation']['completion_tokens'] for o in observations)
    return result


def cell_tables(aggregate,rows,constructions):
    exported=[]
    for cell,raw in rows.items():
        construction=constructions[cell];counts=Counter(r['status'] for r in construction['records'])
        for arm in ('dense','rcd'):
            selected=[r['measurement'] for r in raw if r['pipeline']==arm and r['measurement'] is not None]
            result=summarize(selected,300)
            result={**{'cell':cell,'attack':construction['family'],'intensity':construction['intensity'],'seed':construction['seed'],'arm':arm,
                'target_construction_failed':counts['target_construction_failed'],'semantic_construction_failed':counts['semantic_construction_failed']},**result}
            saved=aggregate['cells'][cell][arm]
            comparisons={'end_to_end_asr':'end_to_end_targeted_asr','conditional_asr':'conditional_targeted_asr_valid',
                'exposure_rate':'poison_exposure_valid','clean_em':'clean_em_valid','poisoned_em':'poisoned_em_valid',
                'clean_f1':'clean_f1_valid','poisoned_f1':'poisoned_f1_valid','degradation_rate':'untargeted_degradation_valid'}
            for field,source in comparisons.items():
                if not equal(result[field],saved[source]['value']):raise ValueError('Export/aggregate mismatch: '+field)
            for k in (1,3,5,10):
                if not equal(result['prr_'+str(k)],saved['prr_at_k_valid'][str(k)]['value']):raise ValueError('Export PRR mismatch')
            exported.append(result)
    return exported


def clustered_intervals(rows,ids,aggregate):
    import numpy as np
    result=[];effect=[]
    for group,saved in aggregate['paired_query_cluster_uncertainty'].items():
        x={arm:np.zeros((len(ids),5)) for arm in ('dense','rcd')}
        for seed in (42,43,44):
            raw={(r['pipeline'],r['query_id']):r for r in rows[group+'.seed-'+str(seed)]}
            for arm in x:
                for i,qid in enumerate(ids):
                    m=raw[arm,qid]['measurement']
                    if m:x[arm][i]+=[1,m['poisoned_condition']['targeted_asr'],m['query_untargeted_degradation'],m['poisoned_condition']['poison_retrieved'],m['clean_condition']['answer_correct']]
        rng=random.Random(20261025);indices=np.asarray([rng.choices(range(len(ids)),k=len(ids)) for _ in range(2000)])
        draw={arm:v[indices].sum(axis=1) for arm,v in x.items()}
        for metric,col,denom in [('end_to_end_targeted_asr',1,None),('conditional_targeted_asr_valid',1,0),('untargeted_degradation_valid',2,0),('poison_exposure_valid',3,0)]:
            points={};values={}
            for arm in x:
                total=x[arm].sum(axis=0);d=3*len(ids) if denom is None else total[denom]
                points[arm]=float(total[col]/d) if d else None
                denominator=3*len(ids) if denom is None else draw[arm][:,denom]
                with np.errstate(invalid='ignore',divide='ignore'):values[arm]=draw[arm][:,col]/denominator
                ordered=sorted(float(v) for v in values[arm] if np.isfinite(v))
                interval=[ordered[int((len(ordered)-1)*p)] for p in (.025,.975)] if ordered else [None,None]
                result.append({'group':group,'arm':arm,'metric':metric,'point':points[arm],'ci_low':interval[0],'ci_high':interval[1],
                    'interpretation':'additional descriptive arm-wise query-cluster interval; not a new confirmatory test'})
            diff=values['dense']-values['rcd'];ordered=sorted(float(v) for v in diff if np.isfinite(v))
            interval=[ordered[int((len(ordered)-1)*p)] for p in (.025,.975)] if ordered else [None,None]
            existing=saved['metrics'][metric]
            if not all(equal(v,w) for v,w in zip(interval,existing['ci95_percentile'])) or not equal(points['dense']-points['rcd'],existing['dense_minus_rcd']):
                raise ValueError('Independent bootstrap comparison mismatch')
            effect.append({'group':group,'metric':metric,'dense_minus_rcd':existing['dense_minus_rcd'],'ci_low':interval[0],'ci_high':interval[1],
                'replicates':2000,'unique_queries':300,'multiplicity_adjusted':False})
    return result,effect


def write_tables(output,name,rows,fields=None):
    fields=fields or list(rows[0])
    with (output/(name+'.csv')).open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    fmt=lambda v:'undefined' if v is None else format(v,'.6f') if isinstance(v,float) else str(v)
    lines=['| '+' | '.join(fields)+' |','|'+'|'.join('---' for _ in fields)+'|']
    lines.extend('| '+' | '.join(fmt(r.get(f)).replace('|','/') for f in fields)+' |' for r in rows)
    (output/(name+'.md')).write_text('\n'.join(lines)+'\n')
    escape=lambda x:fmt(x).replace('\\',r'\textbackslash{}').replace('_',r'\_').replace('%',r'\%').replace('&',r'\&')
    tex=['% booktabs; values are proportions unless seconds/count fields indicate otherwise.',r'\begin{tabular}{'+'l'*len(fields)+'}',r'\toprule', ' & '.join(escape(f) for f in fields)+r' \\',r'\midrule']
    tex+=[' & '.join(escape(r.get(f)) for f in fields)+r' \\' for r in rows]
    tex += [r'\bottomrule',r'\end{tabular}']
    (output/(name+'.tex')).write_text('\n'.join(tex)+'\n')


def figures(output,pooled,intervals,effects,cellrows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10,'svg.fonttype':'none','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
    colors={'dense':'#2266a8','rcd':'#c56a1a'}
    def save(fig,name):
        fig.savefig(output/(name+'.svg'),bbox_inches='tight');fig.savefig(output/(name+'.pdf'),bbox_inches='tight');fig.savefig(output/(name+'.png'),dpi=300,bbox_inches='tight');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4),sharey=True)
    for axis,(family,title) in zip(axes,[('lexical_influential_token','Lexical'),('semantic_fluent_false_evidence','Semantic')]):
        for arm in ('dense','rcd'):
            entries=[next(r for r in pooled if r['attack']==family and r['intensity']==i and r['arm']==arm) for i in (1,3)]
            ci=[next(r for r in intervals if r['group']==family+'.intensity-'+str(i) and r['arm']==arm and r['metric']=='end_to_end_targeted_asr') for i in (1,3)]
            y=[100*r['end_to_end_asr'] for r in entries]
            axis.errorbar([1,3],y,yerr=[[y[j]-100*ci[j]['ci_low'] for j in (0,1)],[100*ci[j]['ci_high']-y[j] for j in (0,1)]],label=arm.upper(),color=colors[arm],marker='o',capsize=4)
        axis.set(title=title,xlabel='Required poison documents',xticks=[1,3],ylim=(0,55));axis.legend()
    axes[0].set_ylabel('End-to-end targeted ASR (%)')
    fig.suptitle('HotpotQA: all 300 queries retained');fig.text(.5,-.04,'Descriptive arm-wise 95% query-cluster intervals; failures contribute zero successes.',ha='center',fontsize=8)
    save(fig,'intensity_asr')
    entries=[r for r in cellrows if r['arm']=='dense'];fig,ax=plt.subplots(figsize=(11,4))
    labels=[('L' if r['attack'].startswith('lexical') else 'S')+f" {r['intensity']}/{r['seed']}" for r in entries]
    valid=[r['valid_query_seed']/3 for r in entries];target=[r['target_construction_failed']/3 for r in entries];semantic=[r['semantic_construction_failed']/3 for r in entries]
    ax.bar(labels,valid,label='Mechanically valid',color='#3a8a75');ax.bar(labels,target,bottom=valid,label='Target construction failed',color='#b4bcc6');ax.bar(labels,semantic,bottom=[a+b for a,b in zip(valid,target)],label='Semantic construction failed',color='#b96255')
    ax.set(ylabel='Declared population (%)',ylim=(0,100),xlabel='Family (L/S), intensity / poison seed',title='Construction coverage: failures are not successful defenses');ax.tick_params(axis='x',rotation=45);ax.legend(fontsize=8)
    save(fig,'construction_coverage')
    entries=[r for r in effects if r['metric']=='end_to_end_targeted_asr'];fig,ax=plt.subplots(figsize=(7,3.7))
    for i,r in enumerate(entries):
        ax.errorbar(100*r['dense_minus_rcd'],i,xerr=[[100*(r['dense_minus_rcd']-r['ci_low'])],[100*(r['ci_high']-r['dense_minus_rcd'])]],fmt='o',capsize=4,color='#4b5675')
    ax.axvline(0,color='black',linestyle='--',linewidth=1)
    ax.set(yticks=range(len(entries)),yticklabels=[('Lexical' if r['group'].startswith('lexical') else 'Semantic')+' I'+r['group'][-1] for r in entries],xlabel='Dense − RCD end-to-end ASR (percentage points)',title='Paired 95% query-cluster intervals; no primary interval excludes zero')
    save(fig,'paired_asr_effects')


def export(root,aggregate_sha,output,make_figures=False):
    output=Path(output).resolve();root=Path(root).resolve()
    if output.exists() or root==output or root in output.parents or ROOT==output or ROOT in output.parents:
        raise ValueError('Use a fresh output directory outside frozen inputs and repository')
    aggregate,protocol,rows,constructions,checked=verify_inputs(root,aggregate_sha)
    cellrows=cell_tables(aggregate,rows,constructions);pooled=[]
    for attack in protocol['rules']['attacks']:
        for intensity in (1,3):
            for arm in ('dense','rcd'):
                selected=[r['measurement'] for cell,raw in rows.items() if constructions[cell]['family']==attack and constructions[cell]['intensity']==intensity for r in raw if r['pipeline']==arm and r['measurement'] is not None]
                pooled.append({'attack':attack,'intensity':intensity,'arm':arm,**summarize(selected,900)})
    intervals,effects=clustered_intervals(rows,protocol['binding']['query_ids'],aggregate)
    output.mkdir(parents=True)
    write_tables(output,'per_cell_metrics',cellrows)
    write_tables(output,'pooled_metrics',pooled)
    write_tables(output,'paired_effects',effects)
    write_tables(output,'descriptive_arm_intervals',intervals)
    base=['attack','intensity','seed','arm']
    write_tables(output,'targeted_asr',cellrows,base+['population_query_seed','valid_query_seed','target_construction_failed','semantic_construction_failed','targeted_successes','end_to_end_asr','conditional_asr'])
    write_tables(output,'retrieval_and_exposure',cellrows,base+['valid_query_seed','prr_1','prr_3','prr_5','prr_10','exposure_rate','asr_given_exposure'])
    write_tables(output,'utility_retention',cellrows,base+['valid_query_seed','clean_em','poisoned_em','em_retention','clean_f1','poisoned_f1','f1_retention','degradation_rate'])
    write_tables(output,'latency_and_calls',cellrows,base+['clean_qa_wall_seconds_mean','poisoned_qa_wall_seconds_mean','clean_model_reported_seconds_mean','poisoned_model_reported_seconds_mean','clean_retrieval_seconds_mean','poisoned_retrieval_seconds_mean','diagnostic_retrieval_seconds_mean','normal_retrieval_calls','diagnostic_retrieval_calls','normal_inner_retrieval_operations','diagnostic_inner_retrieval_operations'])
    overhead=[]
    for cell in rows:
        dense=next(r for r in cellrows if r['cell']==cell and r['arm']=='dense')
        rcd=next(r for r in cellrows if r['cell']==cell and r['arm']=='rcd')
        ratios={}
        for key in ('clean_retrieval_seconds_mean','poisoned_retrieval_seconds_mean','normal_inner_retrieval_operations','diagnostic_inner_retrieval_operations'):
            ratios['rcd_over_dense_'+key]=rcd[key]/dense[key] if dense[key] else None
        overhead.append({'cell':cell,'valid_query_seed':dense['valid_query_seed'],**ratios})
    write_tables(output,'retrieval_overhead',overhead)
    if make_figures:figures(output,pooled,intervals,effects,cellrows)
    notes='''# Validated HotpotQA publication exports

All rates are proportions in CSV/LaTeX; figure axes explicitly show percent or percentage points. All 300 unique questions remain in the primary population. Pooled population 900 denotes query/seed observations, not independent queries. Failure records have no invented QA values. Non-gold targets are label-conditioned, not independently verified falsehoods. Mechanically valid is not a factual/linguistic adjudication.

The paired-effect table reproduces the frozen 2,000-query-cluster bootstrap, seed 20261025. Positive Dense-minus-RCD ASR/degradation/exposure means lower adverse rates for RCD. Intervals are unadjusted for multiplicity. Arm-wise intervals were added solely for descriptive plotting, not new confirmatory tests. Every primary paired ASR interval includes zero; do not claim overall RCD superiority.

Utility, retention, latency and retrieval summaries are conditional on valid constructions and represent the actually measured workload. They are not full-population utility estimates. Outer QA timing includes instrumentation; reported backend timing and retrieval timing are separate. Measurements come from sequential local execution, not a controlled hardware benchmark. RCD changes the number of internal retrieval operations; compare it on matched query/cell cohorts.

Construction coverage and failed semantic attempts must accompany ASR figures. Lower semantic end-to-end ASR does not show stronger defense: most attacks were never constructed. Intensity changes also change the surviving semantic subset. Existing artifacts and the scientific audit are unchanged. No new model experiment was executed by this exporter.
'''
    (output/'INTERPRETATION.md').write_text(notes)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip())
    versions={}
    for package in ('numpy','matplotlib'):
        try:versions[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:versions[package]=None
    manifest={'schema':'rag-poison-transfer.publication-export/v1','aggregate_sha256':aggregate_sha,
        'protocol_sha256':aggregate['protocol_sha256'],'construction_seal_sha256':aggregate['construction_seal_sha256'],
        'evaluation_completion_sha256':aggregate['evaluation_completion_sha256'],'frozen_experiment_source':protocol['source'],
        'producer_git_sha':commit,'producer_git_dirty':dirty,'producer_script_sha256':sha(__file__),'postprocess_versions':versions,
        'sealed_input_files_verified':checked,'row_count':len(cellrows),'figures_generated':make_figures,
        'files_sha256':{p.name:sha(p) for p in output.iterdir() if p.is_file()}}
    (output/'EXPORT_MANIFEST.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root',type=Path,required=True);parser.add_argument('--aggregate-sha256',required=True)
    parser.add_argument('--output-dir',type=Path,required=True);parser.add_argument('--figures',action='store_true')
    args=parser.parse_args();print(json.dumps(export(args.input_root,args.aggregate_sha256,args.output_dir,args.figures),indent=2))


if __name__=='__main__':main()
