import copy
import hashlib
import json

import pytest

from src.experiments import twowiki_replication as two
from src.experiments.week9_construction import fingerprint
from scripts import run_week9_protocol_poison_matrix as base


@pytest.fixture
def prepared(tmp_path):
    cohorts={s:[{'query_id':s+str(i),'question_sha256':hashlib.sha256(('Who wrote '+s+str(i)+'?').encode()).hexdigest()} for i in range(300)] for s in ('train','dev')}
    policy={'known_historical_ids':['historical-'+str(i) for i in range(300)]}
    policy_path=tmp_path/'cohort_policy.json';policy_path.write_text(json.dumps(policy))
    manifest={'schema':'rag-poison-transfer.2wiki-disjoint-cohort-manifest/v1','dataset_revision':two.REVISION,
        'complete_historical_nonoverlap_certified':False,'known_historical_nonoverlap_verified':True,'development_heldout_id_overlap':0,
        'cohorts':cohorts,'cohort_fingerprints':{s:fingerprint(r) for s,r in cohorts.items()},'policy_sha256':two.sha(policy_path)}
    path=tmp_path/'cohort_manifest.json';path.write_text(json.dumps(manifest))
    development={'corpus':[{'doc_id':'fixture','text':'Synthetic development corpus.'}],
        'queries':[{'query_id':r['query_id'],'question':'Who wrote '+r['query_id']+'?','gold_answer':'Fixture Author '+str(i),'gold_doc_ids':['fixture']} for i,r in enumerate(cohorts['train'])]}
    dep=tmp_path/'development.json';dep.write_text(json.dumps(development))
    spec={'schema':two.SCHEMA,'cohort_manifest':str(path),'cohort_manifest_sha256':two.sha(path),'development_data':str(dep),'development_data_sha256':two.sha(dep)}
    return spec,manifest,development


def test_exact_cohort_binding_and_disclosure(prepared):
    spec,manifest,data=prepared
    got=two.load_cohort(spec['cohort_manifest'],spec['cohort_manifest_sha256'])
    assert got['complete_historical_nonoverlap_certified'] is False
    binding,dense,rcd,pool=two.metadata('heldout',spec,{'retriever':'dense'},{'retriever':'rcd','rcd_consistency_weight':.45,'generator_model':'fixture','generator_backend':'mlx'})
    assert len(binding['query_ids'])==len(pool)==300 and binding['dataset']['split']=='dev'
    assert rcd['rcd_consistency_weight']==.45 and rcd['retriever']=='rcd'
    assert {q['query_id'] for q in pool}.isdisjoint(binding['query_ids'])


def test_development_smoke_never_fetches_heldout_answers(prepared,monkeypatch):
    spec,manifest,data=prepared
    monkeypatch.setattr(two,'fetch_selected',lambda *a:pytest.fail('No held-out fetch in development smoke'))
    result=two.load_clean({'replication':spec,'binding':{'scope':'development'}})
    assert result['queries']==data['queries'][:2] and result['corpus']==data['corpus']


def test_modified_identity_or_false_historical_claim_rejected(prepared):
    spec,manifest,data=prepared
    path=__import__('pathlib').Path(spec['cohort_manifest'])
    manifest['complete_historical_nonoverlap_certified']=True
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='exposure disclosure'):
        two.load_cohort(path,two.sha(path))


def test_explicit_new_protocol_schema(prepared,monkeypatch,tmp_path):
    spec,manifest,data=prepared
    dense={'retriever':'dense'};rcd={'retriever':'rcd','generator_model':'fixture','generator_backend':'mlx'}
    monkeypatch.setattr(base,'metadata',lambda scope:({},dense,rcd,[]))
    monkeypatch.setattr(base,'sha',lambda path:'a'*64)
    monkeypatch.setattr(base,'environment',lambda:{'python':'software fixture'})
    monkeypatch.setattr(base,'code_binding',lambda:{'git_commit_sha':'b'*40})
    monkeypatch.setattr(base,'model_binding',lambda *a:{'repository':'fixture','revision':'c'*40})
    out=tmp_path/'protocol.json'
    base.freeze_protocol(out,'development',tmp_path/'fixture',replication=spec)
    value=json.loads(out.read_text())
    assert value['schema']==base.REPLICATION_PROTOCOL_SCHEMA
    assert value['rules']['dataset_replication']=='risk-disclosed-2wiki/v1'
    assert value['binding']['query_ids']==['train0','train1']
    base.load_protocol(out,two.sha(out))
