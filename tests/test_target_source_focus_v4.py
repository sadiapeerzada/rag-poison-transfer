"""Narrow source-type regression; all questions/labels are synthetic software fixtures."""
import pytest
from src.attacks import development_targets_v2 as v2, development_targets_v3 as v3, development_targets_v4 as v4
from src.experiments import week9_construction as p
from scripts import run_week9_protocol_poison_matrix as runner
from src.attacks import semantic_profiles


def q(qid,question,gold):return {'query_id':qid,'question':question,'gold_answer':gold}


def test_country_request_demonym_can_no_longer_contaminate_person_pool():
    source=q('bad','Which country the director of film Example Film is from?','Dutch')
    dest=q('dest','Who is Example Person\'s maternal grandfather?','Example Grandfather')
    good=q('good','Who wrote The Example Book?','Example Writer')
    assert v2.classify(source)[0]=='person'  # The frozen bug remains reproducible.
    assert any(r['answer']=='Dutch' for r in v3.nominate(dest,[source,good],v2.build_pool([source,good]))['candidates'])
    fixed=v4.nominate(dest,[source,good]);assert fixed['excluded_source_ids']==['bad']
    assert [r['answer'] for r in fixed['candidates']]==['Example Writer']
    target,selection=p.select_target(dest,[source,good],42,target_method=v4.descriptor(),scope='development')
    assert target=='Example Writer'


def test_source_scarcity_abstains_without_forcing_replacement():
    src=q('bad','Which country the director of film Example Film is from?','Dutch')
    dest=q('dest','Who is the example grandfather?','Example Person')
    assert p.select_target(dest,[src],42,target_method=v4.descriptor(),scope='development')[0] is None
    assert not v4.nominate(src,[src])['eligible']


def test_country_music_roles_and_genuine_person_nicknames_are_not_blacklisted():
    person=q('p','Which country singer wrote The Example Song?','Example Singer')
    nickname=q('n','Who was nicknamed Dutch?','Dutch')
    assert not v4.focus_conflict(person) and not v4.focus_conflict(nickname)
    assert v4.nominate(q('d','Who wrote the book?','Another Person'),[nickname])['candidates'][0]['answer']=='Dutch'


def test_corrected_target_method_requires_explicit_development_configuration():
    with pytest.raises(ValueError):v4.validate(v4.descriptor(),'heldout')
    with pytest.raises(ValueError):runner.validate_target_method(v4.descriptor(),'development',None,None)
    with pytest.raises(ValueError):v4.descriptor('unknown')
    assert p.rules()['target_method']=='frozen-development-v3-mechanics-promoted-label-conditioned/v1'


def test_new_target_method_freeze_is_versioned_and_replay_bound(monkeypatch,tmp_path):
    from test_semantic_development_study import setup as study_setup
    # Reuse that test's synthetic dataset/config bindings without real model calls.
    configured=study_setup.__wrapped__(tmp_path,monkeypatch)
    old_path,old_pin,backend,*_=configured
    import json
    from pathlib import Path
    from src.experiments import semantic_development_study as study
    old=json.loads(old_path.read_text());future=tmp_path/'corrected'/'protocol.json'
    pin=runner.freeze_protocol(future,'development',Path('fixture'),old['replication'],
        semantic_profile=semantic_profiles.DEVELOPMENT,development_study=study.IDENTIFIER,target_method=v4.IDENTIFIER)['protocol_sha256']
    value,*_=runner.load_protocol(future,pin)
    assert value['schema']==runner.CORRECTED_DEVELOPMENT_PROTOCOL_SCHEMA
    assert value['rules']['target_method']==v4.IDENTIFIER and 'target_method' not in old
    root=Path(value['planned_outputs']['construction'])
    result=runner.construct(future,pin,root,Path('fixture'))
    _,_,_,_,cells=runner.load_sealed(future,pin,root,result['construction_seal_sha256'])
    assert all(c['target_method']==v4.descriptor() for c in cells.values())
    assert all(r['target_method_sha256']==p.fingerprint(v4.descriptor()) for c in cells.values() for r in c['records'])
    value['target_method']['method_version']='stale';future.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='mismatch'):runner.load_protocol(future,runner.sha(future))
