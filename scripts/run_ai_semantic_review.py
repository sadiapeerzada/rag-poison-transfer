#!/usr/bin/env python3
"""Frozen, blinded, local AI review of completed development attempts. No human import."""
import sys
sys.dont_write_bytecode=True
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import time
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import run_week9_protocol_poison_matrix as base
from src.experiments import ai_semantic_review as ai
from src.experiments import semantic_review as human
from src.experiments import execution_reliability as reliable

PLAN_SCHEMA='rag-poison-transfer.ai-semantic-review-plan/v2'


def source(package,package_pin,original,original_pin,construction,seal_pin):
    # This is read-only post-experiment analysis, not replay under changed attack code.
    if base.sha(Path(package)/'manifest.json')!=package_pin:raise ValueError('Trusted review manifest mismatch')
    proto=base.read_pinned(original,original_pin)
    if proto['binding']['scope']!='development' or len(proto['binding']['query_ids'])!=25 or proto['binding']['dataset']['split']!='train':raise ValueError('Only completed 25-query train development artifacts supported')
    c=Path(construction);seal=base.read_pinned(c/'construction.seal.json',seal_pin)
    if seal['protocol_sha256']!=original_pin or seal['files_sha256']!=base.construction_files(c):raise ValueError('Original sealed construction mismatch')
    manifest,items=human.load_package(package)
    if manifest['context']['protocol_sha256']!=original_pin or manifest['context']['construction_seal_sha256']!=seal_pin:raise ValueError('Review/source provenance mismatch')
    data=base.read_pinned(proto['replication']['local_data'],proto['replication']['local_data_sha256']);by={q['query_id']:q for q in data['queries']}
    clean={'queries':[by[q] for q in proto['binding']['query_ids']],'corpus':data['corpus']}
    cells={}
    for key,entry in seal['cells'].items():cells[key]=base.read_pinned(c/entry['path'],entry['sha256'])
    if items!=human.items(clean,cells,original_pin):raise ValueError('Review content differs from original sealed attempts')
    return proto,items


def freeze(output,package,package_pin,original,original_pin,construction,seal_pin,snapshot):
    output=base.legacy._ensure_output_outside_repository(Path(output))
    protected=Path(original).resolve().parent
    if output==protected or protected in output.parents:raise ValueError('AI review must use a separate namespace')
    if output.parent.exists():raise FileExistsError('Fresh isolated AI-review namespace required')
    proto,items=source(package,package_pin,original,original_pin,construction,seal_pin)
    value={'schema':PLAN_SCHEMA,'review_method':'AI-assisted','human_review':False,'source':base.code_binding(),
        'environment':base.environment(),'model':base.model_binding(snapshot,proto['binding']['model_identity']),
        'parameters':ai.PARAMETERS,'prompt_version':ai.PROMPT_VERSION,'pilot_selection_version':ai.PILOT_SELECTION_VERSION,
        'package':str(Path(package).resolve()),'package_manifest_sha256':package_pin,
        'original_protocol':str(Path(original).resolve()),'original_protocol_sha256':original_pin,
        'construction':str(Path(construction).resolve()),'construction_seal_sha256':seal_pin,
        'item_ids':[i['item_id'] for i in items],'pilot_item_ids':ai.pilot_ids(items),
        'input_fingerprints':{i['item_id']:base.protocol.fingerprint(ai.model_input(i)) for i in items},
        'maximum_unique_model_calls':len({base.protocol.fingerprint(ai.model_input(i)) for i in items}),
        'maximum_attempt_records':len(items),'cache_rule':'exact full prompt/model/parameters/seed only; no judgment regeneration',
        'separate_from_human_import':True,'limitation':'Evaluator is the same Qwen model snapshot as construction; correlated self-review, not independent adjudication'}
    reliable.atomic(output,value);return {'plan_sha256':base.sha(output),'maximum_unique_calls':value['maximum_unique_model_calls'],'pilot_item_ids':value['pilot_item_ids']}


def load(path,pin,snapshot=None):
    value=base.read_pinned(path,pin)
    if value.get('pilot_selection_version')!=ai.PILOT_SELECTION_VERSION or value.get('schema')!=PLAN_SCHEMA or value.get('parameters')!=ai.PARAMETERS or value.get('prompt_version')!=ai.PROMPT_VERSION or value.get('review_method')!='AI-assisted' or value.get('human_review') is not False:raise ValueError('AI review version/configuration mismatch')
    if value['source']!=base.code_binding() or value['environment']!=base.environment():raise ValueError('AI review requires exact clean code/environment')
    if snapshot is not None and base.model_binding(snapshot,value['model']['repository'])!=value['model']:raise ValueError('Evaluator model snapshot mismatch')
    _,items=source(value['package'],value['package_manifest_sha256'],value['original_protocol'],value['original_protocol_sha256'],value['construction'],value['construction_seal_sha256'])
    if [i['item_id'] for i in items]!=value['item_ids'] or value['input_fingerprints']!={i['item_id']:base.protocol.fingerprint(ai.model_input(i)) for i in items} or value['pilot_item_ids']!=ai.pilot_ids(items):raise ValueError('AI review input census mismatch')
    expected_calls={base.protocol.fingerprint({'review_plan_sha256':pin,'model':value['model'],'parameters':value['parameters'],'prompt':ai.prompt(ai.model_input(i))}) for i in items}
    if value['maximum_unique_model_calls']!=len(expected_calls) or value['maximum_attempt_records']!=len(items):raise ValueError('AI review budget/census mismatch')
    callroot=Path(path).parent/'calls'
    if callroot.exists() and any(p.is_dir() and p.name not in expected_calls for p in callroot.iterdir()):raise ValueError('Unexpected model-call namespace')
    return value,items


def assessment_record(root,item,value,pin):
    root=Path(root);data=ai.model_input(item);p=ai.prompt(data)
    binding={"review_plan_sha256":pin,"model":value["model"],"parameters":value["parameters"],"prompt":p}
    key=base.protocol.fingerprint(binding);directory=root/"calls"/key
    record=reliable.read(root/"assessments"/(item["item_id"]+".json"))
    intent=reliable.read(directory/"00.intent.json");saved=reliable.read(directory/"00.response.json")
    if (intent!={"prompt":p,"max_tokens":value["parameters"]["max_tokens"],"provenance":binding,"context":{}} or
        saved.get("request_fingerprint")!=base.protocol.fingerprint(intent) or "error" in saved or
        record.get("schema")!=ai.SCHEMA or record.get("human_review") is not False or record.get("review_method")!="AI-assisted" or
        record.get("review_plan_sha256")!=pin or record.get("input_sha256")!=base.protocol.fingerprint(data) or
        record.get("call_key")!=key or record.get("prompt")!=p or record.get("evaluator")!=value["model"] or
        record.get("parameters")!=value["parameters"] or record.get("raw_response")!=saved["generation"]["raw_response"] or
        record.get("response_sha256")!=base.sha(directory/"00.response.json")):
        raise ValueError("Assessment/journal provenance mismatch")
    clock=reliable.read(directory/"clock.json")
    if any(record.get(k)!=v for k,v in clock.items()):raise ValueError("Assessment clock mismatch")
    try:parsed=ai.parse(record["raw_response"],data)
    except (ValueError,TypeError,KeyError) as error:
        if record.get("status")!="unevaluated_invalid_response" or record.get("validation_error")!=str(error):raise ValueError("Invalid-assessment classification mismatch")
    else:
        if record.get("status")!="assessed" or record.get("assessment")!=parsed:raise ValueError("Assessment differs from recorded model response")
    return record


@reliable.exclusive('root')
def assess(path,pin,root,snapshot,pilot=False):
    value,items=load(path,pin,snapshot);root=Path(root)
    if root.resolve()!=Path(path).resolve().parent:raise ValueError('Review execution namespace mismatch')
    reliable.validate_store(root);by={i['item_id']:i for i in items}
    if not pilot:
        pilot_records=[assessment_record(root,by[i],value,pin) for i in value['pilot_item_ids']]
        ai.pilot_sanity(pilot_records,items)
    keys=value['pilot_item_ids'] if pilot else value['item_ids'];backend=None;new_calls=0
    for key in keys:
        item=by[key];out=root/'assessments'/(key+'.json');data=ai.model_input(item);prompt=ai.prompt(data)
        binding={'review_plan_sha256':pin,'model':value['model'],'parameters':value['parameters'],'prompt':prompt}
        call_key=base.protocol.fingerprint(binding);directory=root/'calls'/call_key
        if out.exists():
            assessment_record(root,item,value,pin)
            continue
        class Observed:
            def generate(self,prompt,max_tokens):
                nonlocal backend,new_calls
                if new_calls>=value['maximum_unique_model_calls']:raise RuntimeError('Declared review model budget exceeded')
                started=datetime.now(timezone.utc).isoformat()
                if backend is None:backend=base.generator({"generator_backend":"mlx"},snapshot)
                base.runtime_seed(value['parameters']['seed']);new_calls+=1
                result=backend.generate(prompt,max_tokens=max_tokens)
                reliable.atomic(directory/'clock.json',{'started_utc':started,'completed_utc':datetime.now(timezone.utc).isoformat()})
                return result
        journal=base.JournalGenerator(Observed(),directory,binding)
        replayed=(directory/'00.response.json').exists()
        generated=journal.generate(prompt,value['parameters']['max_tokens'])
        clock=reliable.read(directory/'clock.json')
        record={'schema':ai.SCHEMA,'review_method':'AI-assisted','human_review':False,'item_id':key,
            'review_plan_sha256':pin,'input_sha256':base.protocol.fingerprint(data),'call_key':call_key,
            'evaluator':value['model'],'parameters':value['parameters'],'prompt_version':ai.PROMPT_VERSION,
            'prompt':prompt,'raw_response':generated.text,**clock,'automatic_validator_blinded':True,
            'response_sha256':base.sha(directory/'00.response.json'),
            'backend_call_executed_for_this_item':not replayed,'timestamps_describe_origin_model_call':True}
        try:record.update(status='assessed',assessment=ai.parse(generated.text,data))
        except (ValueError,TypeError,KeyError) as error:record.update(status='unevaluated_invalid_response',validation_error=str(error))
        reliable.atomic(out,record)
    records=[assessment_record(root,by[key],value,pin) for key in keys]
    if pilot:return {'status':'pilot_recorded_not_compared','new_model_calls':new_calls,'pilot_checks':ai.pilot_sanity(records,items)}
    return {'status':'assessment_census_complete_not_compared','new_model_calls':new_calls,'attempt_records':len(records)}


def compare(path,pin):
    value,items=load(path,pin);root=Path(path).parent;reliable.validate_store(root);records=[]
    for item in items:
        p=root/'assessments'/(item['item_id']+'.json')
        if not p.exists():raise ValueError('Assessment census incomplete; automatic-label comparison forbidden')
        record=assessment_record(root,item,value,pin)
        records.append(record)
    counts={k:0 for k in ('accept','reject','uncertain','unevaluated')};disagreements=[]
    for item,record in zip(items,records):
        decision=record.get('assessment',{}).get('ai_disposition','unevaluated');counts[decision]+=1
        if decision=='accept' and item['automated_validator_decision']!='heuristically_supported_unverified':disagreements.append(item['item_id'])
    files={str(p.relative_to(root)):base.sha(p) for folder in ('calls','assessments') for p in (root/folder).rglob('*') if p.is_file()}
    reliable.once(root/'assessment.complete.json',{'schema':'rag-poison-transfer.ai-assessment-completion/v1','review_plan_sha256':pin,'files_sha256':files})
    result={'assessment_completion_sha256':base.sha(root/'assessment.complete.json'),'schema':'rag-poison-transfer.ai-semantic-review-comparison/v1','review_method':'AI-assisted','human_review':False,
        'review_plan_sha256':pin,'attempt_counts':counts,'comparison_performed_after_full_census':True,
        'ai_accept_automatic_nonaccept_item_ids':disagreements,
        'actual_unique_model_calls':len(list((root/'calls').glob('*/00.response.json'))),
        'not_independent_factual_verification':True,'heldout_protocol_approved':False}
    reliable.once(root/'comparison.json',result);return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['freeze','pilot','assess','compare'])
    for name in ('plan','package','original-protocol','construction-dir','model-snapshot'):p.add_argument('--'+name,type=Path)
    for name in ('plan-sha256','package-manifest-sha256','original-protocol-sha256','construction-seal-sha256'):p.add_argument('--'+name)
    p.add_argument('--allow-local-model-calls',action='store_true');a=p.parse_args()
    if not a.plan:p.error('Require --plan')
    if a.stage=='freeze':
        if not all((a.package,a.package_manifest_sha256,a.original_protocol,a.original_protocol_sha256,a.construction_dir,a.construction_seal_sha256,a.model_snapshot)):p.error('Freeze requires pinned original artifacts, package and model')
        result=freeze(a.plan,a.package,a.package_manifest_sha256,a.original_protocol,a.original_protocol_sha256,a.construction_dir,a.construction_seal_sha256,a.model_snapshot)
    elif not a.plan_sha256:p.error('Require trusted --plan-sha256')
    elif a.stage in ('pilot','assess'):
        if not a.allow_local_model_calls or not a.model_snapshot:p.error('Require explicit --allow-local-model-calls and pinned snapshot')
        result=assess(a.plan,a.plan_sha256,a.plan.parent,a.model_snapshot,a.stage=='pilot')
    else:result=compare(a.plan,a.plan_sha256)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
