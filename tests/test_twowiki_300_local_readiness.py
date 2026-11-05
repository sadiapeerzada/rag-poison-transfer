import json

from scripts.audit_twowiki_300_local_readiness import census


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


def test_census_separates_population_and_detects_unsafe_resume(tmp_path):
    protocol = {'binding': {'scope': 'heldout', 'query_ids': [str(i) for i in range(300)],
                           'dataset': {'loader': 'load_2wikimultihopqa'}, 'matrix': []}}
    save(tmp_path / 'historical/protocol.json', protocol)
    first = census(tmp_path)
    pin = first['heldout_300_protocol_pins'][0]
    save(tmp_path / 'run/execution.plan.json', {'binding': {'protocol_sha256': pin}})
    save(tmp_path / 'run/journal/000.intent.json', {'prompt': 'Fixture only'})
    save(tmp_path / 'pilot/protocol.json', {'binding': {'scope': 'development',
         'query_ids': ['pilot'] * 25, 'dataset': {'loader': 'load_2wikimultihopqa'}}})
    save(tmp_path / 'run/construction.seal.json', {'protocol_sha256': pin, 'files_sha256': {}})
    (tmp_path / 'broken.json').write_text('{')
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    result = census(tmp_path)
    assert len(result['heldout_300_protocol_pins']) == 1
    assert len(result['heldout_300_execution_plans']) == 1
    assert 'Unresolved generation intent' in result['checkpoint_stores'][0]['checkpoint_validation']
    assert result['sealed_stages'][0]['file_manifest_matches'] is False
    assert result['problems'] == [{'path': 'broken.json', 'error': 'JSONDecodeError'}]
    assert result['automatic_retry_permitted'] is False and result['model_calls'] == 0
    assert before == {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


def test_journals_without_execution_plans_are_still_checked(tmp_path):
    save(tmp_path / 'old-smoke/calls/0.intent.json', {'prompt': 'Fixture only', 'max_tokens': 1, 'provenance': {}})
    result = census(tmp_path)
    assert len(result['checkpoint_stores']) == 1
    store = result['checkpoint_stores'][0]
    assert store['execution_plan_present'] is False
    assert 'Unresolved generation intent' in store['checkpoint_validation']


def test_other_intent_formats_do_not_imply_missing_native_responses(tmp_path):
    save(tmp_path / 'review/case.intent.json', {'schema': 'external-review/v1', 'prompt_sha256': 'fixture'})
    (tmp_path / 'review/case.response.txt').write_text('Archived fixture response')
    result = census(tmp_path)
    assert result['checkpoint_stores'] == []
    assert result['other_format_intents'][0]['schema'] == 'external-review/v1'
