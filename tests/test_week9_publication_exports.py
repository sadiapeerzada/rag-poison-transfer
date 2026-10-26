"""Postprocessing tests use existing synthetic experiment harnesses only."""
import copy
import hashlib
import json

import pytest

from scripts import export_week9_publication_results as exporter


def test_undefined_retention_and_failure_population():
    result=exporter.summarize([],300)
    assert result['end_to_end_asr']==0
    assert result['conditional_asr'] is result['em_retention'] is result['f1_retention'] is None
    assert result['valid_query_seed']==0 and result['failed_query_seed']==300


def test_export_rejects_wrong_pin_before_output(tmp_path):
    source=tmp_path/'source';source.mkdir();(source/'aggregate.json').write_text('{}')
    destination=tmp_path/'not-created'
    with pytest.raises(ValueError,match='aggregate hash'):
        exporter.export(source,'a'*64,destination)
    assert not destination.exists()


def test_csv_markdown_latex_preserve_values_and_escape(tmp_path):
    exporter.write_tables(tmp_path,'example',[{'key_name':'Dense & RCD','rate':0.123456789,'undefined':None}])
    assert '0.123456789' in (tmp_path/'example.csv').read_text()
    tex=(tmp_path/'example.tex').read_text()
    assert r'key\_name' in tex and r'Dense \& RCD' in tex
    assert 'undefined' in tex


def test_cell_metric_recomputation_matches_aggregate(tmp_path,monkeypatch):
    from test_week9_frozen_construction_protocol import harness,q
    from scripts import run_week9_protocol_poison_matrix as runner
    data={'queries':[q('one','Who wrote the book?','Alice Author'),q('two','Describe this category.','Unresolved')],
          'corpus':[{'doc_id':'clean','text':'Synthetic evidence.'}]}
    development=[q('dev','Who wrote a development book?','Bob Writer')]
    harness(monkeypatch,data,development)
    source=tmp_path/'construct';output=tmp_path/'evaluation'
    seal=runner.construct(tmp_path/'unused','a'*64,source,tmp_path/'fixture')['construction_seal_sha256']
    runner.evaluate(tmp_path/'unused','a'*64,source,seal,output,tmp_path/'fixture')
    cells={p.parent.name:json.loads(p.read_text()) for p in source.glob('*/construction.json')}
    rows={p.parent.name:json.loads(p.read_text()) for p in output.glob('*/rows.json')}
    from src.experiments.week9_construction import summarize
    aggregate={'cells':{key:{arm:summarize([r for r in raw if r['pipeline']==arm]) for arm in ('dense','rcd')} for key,raw in rows.items()}}
    # This is a two-case synthetic scope; exporter cell tables deliberately has final N=300.
    for cell in aggregate['cells'].values():
        for arm in cell.values():arm['end_to_end_targeted_asr']['value']=arm['end_to_end_targeted_asr']['numerator']/300
    result=exporter.cell_tables(aggregate,rows,cells)
    assert len(result)==4 and all(r['valid_query_seed']==1 for r in result)
    bad=copy.deepcopy(aggregate)
    bad['cells'][next(iter(bad['cells']))]['dense']['conditional_targeted_asr_valid']['value']=.123
    with pytest.raises(ValueError,match='aggregate mismatch'):
        exporter.cell_tables(bad,rows,cells)
