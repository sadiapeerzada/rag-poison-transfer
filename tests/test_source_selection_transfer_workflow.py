import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_source_selection_transfer as transfer
from scripts import run_week9_protocol_poison_matrix as base
from src.experiments import week9_construction as old
from src.pipelines.generator import GenerationResult


def fixture(monkeypatch,zero=False):
    q=lambda i,question,gold:{'query_id':i,'question':question,'gold_answer':gold,'gold_doc_ids':['clean']}
    data={'queries':[q('q1','Who wrote the book?','Alice Author'),q('q2','Describe this category.','Unknown')],
          'corpus':[{'doc_id':'clean','text':'Synthetic corpus only.'}]}
    development=[q('dev1','Who wrote a book?','Bob Writer'),q('dev2','Who wrote another book?','Dana Author')]
    config={'top_k':3,'max_tokens':64,'retriever':'dense'}
    spec={'scope':'development','source':{'git_commit_sha':'a'*40},'model':{'revision':'b'*40},
          'binding':{'scope':'development','query_ids':['q1','q2']},'configs':{p:config for p in transfer.TARGETS}}
    monkeypatch.setattr(transfer,'load',lambda *a:(spec,config,config,development))
    monkeypatch.setattr(transfer,'source_guard',lambda spec:None)
    monkeypatch.setattr(transfer,'clean_data',lambda *a:copy.deepcopy(data))
    monkeypatch.setattr(base,'runtime_seed',lambda s:None)
    class Backend:
        def generate(self,prompt,max_tokens):
            if 'Reference answer: "' in prompt:
                target=prompt.split('Reference answer: "')[1].split('"')[0]
                text=f'{target} is the documented answer to this question. The entry gives a direct identifying relation.'
            else:text='No target' if zero else 'Bob Writer'
            return GenerationResult(text,.1,10,20)
    monkeypatch.setattr(base,'generator',lambda *a:Backend())
    class Retriever:
        def build(self,corpus):self.docs=[SimpleNamespace(**d) for d in corpus]
        def retrieve(self,question,top_k):return self.docs[:top_k]
    monkeypatch.setattr(transfer,'build_retriever',lambda config:Retriever())
    return data


@pytest.mark.parametrize('zero',[False,True])
def test_complete_synthetic_source_only_workflow(monkeypatch,tmp_path,zero):
    fixture(monkeypatch,zero)
    lib=tmp_path/'library';sel=tmp_path/'selected';out=tmp_path/'evaluation'
    library_pin=transfer.materialize(Path('unused'),'a'*64,lib,Path('fixture'))['candidate_completion_sha256']
    seal=transfer.source_select(Path('unused'),'a'*64,lib,library_pin,sel,Path('fixture'))['selection_seal_sha256']
    result=transfer.final_evaluate(Path('unused'),'a'*64,sel,seal,out,Path('fixture'))
    assert result['source_target_cells']==40
    import json
    rows=json.loads((out/'transfer_summary.json').read_text())
    assert all(r['population']==2 and r['valid']==1 for r in rows)
    if zero:assert all(r['atr'] is None and r['source_successes']==0 for r in rows)
    else:assert all(r['atr']==1 for r in rows)
    assert all(r['target'] in transfer.TARGETS and r['source']!='rcd' for r in rows)
    result=transfer.aggregate(Path('unused'),'a'*64,out,base.sha(out/'transfer.complete.json'),sel,seal,tmp_path/'aggregate.json',replicates=4)
    assert result['cells']==40
    intervals=json.loads((tmp_path/'aggregate.json').read_text())['atr_query_cluster_intervals']
    if zero:assert all(r['atr'] is None and r['defined_replicates']==0 for r in intervals.values())
    # Corrupt source selection after sealing: target evaluation must not start.
    (sel/'extra.json').write_text('{}')
    with pytest.raises(ValueError,match='integrity'):
        transfer.final_evaluate(Path('unused'),'a'*64,sel,base.sha(sel/'selection.seal.json'),tmp_path/'bad',Path('fixture'))
    assert not (tmp_path/'bad').exists()
