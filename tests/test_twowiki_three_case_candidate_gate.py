"""Mock-only tests for separately frozen 2Wiki candidate-specific review gate."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import twowiki_three_case_candidate_gate as gate


def make_cases():
    cases=[]
    for i, qid, gold, target in gate.CASES:
        text=f"Synthetic source evidence for {qid}: the gold answer is {gold} while the candidate target is {target}."
        d={'doc_id':f'source-{i}', 'text':text, 'text_sha256':gate.sha(text.encode())}
        cases.append({'query_id':qid, 'question':f'Test question {i}?',
                      'gold_answer':gold, 'gold_aliases':[],
                      'gold_doc_ids':[d['doc_id']], 'source_documents':[d],
                      'dossier_sha256':gate.sha(qid.encode())})
    return cases


@pytest.fixture
def bundle(tmp_path,monkeypatch):
    cases=make_cases()
    paths=[tmp_path/name for name in ('dossiers.json','development.json','original-audit.json')]
    for path in paths:path.write_text('{}')
    monkeypatch.setattr(gate,'evidence',lambda d,dev,old: cases)
    monkeypatch.setattr(gate,'git_state',lambda:'verified-test-commit')
    batch=tmp_path/'new-batch'
    args=SimpleNamespace(batch=batch,dossiers=paths[0],development=paths[1],previous_audit=paths[2])
    gate.freeze(args)
    return args,cases,tmp_path


def test_freezes_three_targets_and_six_prompts(bundle):
    args,cases,_=bundle
    manifest=gate.frozen(args.batch,args.dossiers,args.development,args.previous_audit)
    assert len(manifest['records'])==3
    assert manifest['records'][0]['candidate_target']=='The Island (2005 Film)'
    assert manifest['records'][1]['candidate_target']=='no'
    assert manifest['records'][2]['candidate_target']=='1 June 1947'
    assert manifest['factual_approvals']==0
    for i in range(1,4):
        a=(args.batch/f'prompts/reviewer_A/case_{i:02}.txt').read_text()
        b=(args.batch/f'prompts/reviewer_B/case_{i:02}.txt').read_text()
        assert a!=b and 'UNTRUSTED TRAIN SOURCE PACKET' in a
    with pytest.raises(FileExistsError):gate.freeze(args)


def test_frozen_input_and_prompt_tamper_fail(bundle):
    args,cases,_=bundle
    path=args.batch/'prompts/reviewer_A/case_01.txt'
    path.write_text(path.read_text()+'ATTACK')
    with pytest.raises(ValueError,match='Frozen prompt'):gate.frozen(args.batch,args.dossiers,args.development,args.previous_audit)


def captured_result(args,rec,case,slot,decision='approve',model_id='A'):
    i=rec['index'];base=args.batch/f'responses/reviewer_{slot}/case_{i:02}'
    base.parent.mkdir(parents=True,exist_ok=True)
    raw={'query_id':rec['query_id'],'dossier_sha256':rec['dossier_sha256'],
         'candidate_target':rec['candidate_target'],'decision':decision,
         'checks':{k:True for k in gate.CHECKS},
         'evidence_quotes':[{'doc_id':d['doc_id'],'exact_quote':d['text']} for d in case['source_documents']],
         'reason':'The synthetic dossier directly contradicts this candidate answer.',
         'caveats':[]}
    rb=json.dumps(raw).encode()
    base.with_suffix('.json').write_bytes(rb)
    base.with_suffix('.intent.json').write_text(json.dumps({
        'schema':gate.RESPONSE_SCHEMA,'slot':slot,'index':i,'run_id':f'test-{slot}-{i}',
        'prompt_sha256':rec['prompts'][slot]['sha256'],'model':{'model_id':model_id}}))
    base.with_suffix('.provenance.json').write_text(json.dumps({
        'schema':gate.RESPONSE_SCHEMA,'slot':slot,'index':i,'query_id':rec['query_id'],
        'model_id':model_id,'model_snapshot':f'/test/{model_id}',
        'run_id':f'test-{slot}-{i}', 'completed_utc':'2026-11-04T00:00:00Z',
        'prompt_sha256':rec['prompts'][slot]['sha256'], 'response_sha256':gate.sha(rb)}))
    return base,raw


def test_review_is_provisional_even_with_both_approvals(bundle):
    args,cases,root=bundle
    rec=gate.frozen(args.batch,args.dossiers,args.development,args.previous_audit)['records'][0]
    captured_result(args,rec,cases[0],'A','approve','Qwen')
    captured_result(args,rec,cases[0],'B','approve','Phi')
    result=gate.audit(SimpleNamespace(**vars(args),output=root/'audit.json'))
    assert result['status_counts']['concordant_provisional_ai_only']==1
    audit=json.loads((root/'audit.json').read_text())
    assert audit['factual_approvals']==0
    assert audit['poison_injections']==0
    assert audit['rows'][0]['independent_factual_approval'] is False


def test_rejects_markdown_fences_string_booleans_and_wrong_provenance(bundle):
    args,cases,_=bundle
    rec=gate.frozen(args.batch,args.dossiers,args.development,args.previous_audit)['records'][0]
    base,obj=captured_result(args,rec,cases[0],'A')
    assert gate.parse_response(args.batch,rec,cases[0],'A')['status']=='valid_review'
    obj['checks']['gold_supported']='true'
    rb=json.dumps(obj).encode()
    base.with_suffix('.json').write_bytes(rb)
    meta=json.loads(base.with_suffix('.provenance.json').read_text())
    meta['response_sha256']=gate.sha(rb)
    base.with_suffix('.provenance.json').write_text(json.dumps(meta))
    assert gate.parse_response(args.batch,rec,cases[0],'A')['status']=='invalid'
    base.with_suffix('.json').write_text('```json\n'+json.dumps(obj)+'\n```')
    assert gate.parse_response(args.batch,rec,cases[0],'A')['status']=='invalid'


def test_semantic_preflight_zero_calls(bundle):
    args,cases,root=bundle
    snap=root/'model';snap.mkdir()
    (snap/'config.json').write_text('{}')
    (snap/'tokenizer_config.json').write_text('{}')
    request=SimpleNamespace(**vars(args),output=root/'semantic',model_snapshot=snap,
                            model_id='Qwen-pinned',preflight=True)
    result=gate.semantic(request)
    assert result['status']=='semantic_preflight_no_calls'
    assert result['factual_approval'] is False
    assert not request.output.exists()