"""Call ledger and resource-stop tests; no model imports or real generation."""
import json
import pytest
from scripts.run_bounded_e1_e2_qwen import count_attempts,validate_journals
from scripts import bounded_pilot_resources as resources


def test_failed_and_indeterminate_intents_consume_call_cap(tmp_path):
    p=tmp_path/'qwen/calls';p.mkdir(parents=True)
    for name in ('completed','failed','indeterminate'):(p/(name+'.intent.json')).write_text('{}')
    assert count_attempts(tmp_path)==3
    with pytest.raises(RuntimeError):validate_journals(tmp_path)


@pytest.mark.parametrize('pressure,thermal',[(2,'No thermal warning'),(1,'CPU_Speed_Limit = 90')])
def test_pressure_or_thermal_warning_stops_before_model_load(monkeypatch,pressure,thermal):
    def output(cmd,**kwargs):
        if cmd[0]=='sysctl':return str(pressure)
        if cmd[0]=='vm_stat':return 'Swapins: 0.\nSwapouts: 0.\nPageouts: 0.\n'
        return thermal
    monkeypatch.setattr(resources.subprocess,'check_output',output)
    with pytest.raises(RuntimeError,match='pressure or thermal'):resources.mac_health()


def test_normal_health_records_swap_baseline(monkeypatch):
    def output(cmd,**kwargs):
        if cmd[0]=='sysctl':return '1'
        if cmd[0]=='vm_stat':return 'Swapins: 3.\nSwapouts: 12.\nPageouts: 1000.\n'
        return 'No thermal warning level has been recorded'
    monkeypatch.setattr(resources.subprocess,'check_output',output)
    assert resources.mac_health()==15


def test_incomplete_outcomes_never_become_defense_successes_or_numeric_rates():
    from scripts.aggregate_e1_bounded_pilot import summarize,paired_contrasts
    from src.experiments.week9_construction import VALID,TARGET_FAILED
    base={'family':'synthetic','intensity':1,'source':'dense','pipeline':'rcd','method':'M1','query_id':'q'}
    rows=[{**base,'status':VALID,'complete':False},
          {**base,'status':TARGET_FAILED,'complete':False,'query_id':'failed'}]
    result=summarize(rows,['q','failed'])[0]
    assert result['metrics']['coverage']['estimate']==.5
    assert result['metrics']['end_to_end_target_match']['estimate'] is None
    assert result['pending']==1
    assert all(r['status']=='INCOMPLETE' for r in paired_contrasts(rows,['q','failed']))


def test_paired_policy_comparison_retains_failures_in_population():
    from scripts.aggregate_e1_bounded_pilot import paired_contrasts
    from src.experiments.week9_construction import VALID,TARGET_FAILED
    base={'family':'synthetic','intensity':1,'source':'dense','pipeline':'rcd'}
    rows=[]
    for method in ('M1','M2','M3'):
        rows.extend([{**base,'method':method,'query_id':'valid','status':VALID,'complete':True,'target_match':method=='M3'},
                     {**base,'method':method,'query_id':'failed','status':TARGET_FAILED,'complete':False}])
    result=paired_contrasts(rows,['valid','failed'])
    assert len(result)==2
    assert all(r['estimate']==.5 for r in result)


def test_shared_session_cap_survives_new_pilot_versions(tmp_path):
    from scripts.run_bounded_e1_e2_qwen import available_calls
    attempts=tmp_path/'e1-e2-20261112-authorized-session/attempts';attempts.mkdir(parents=True)
    for i in range(200):(attempts/f'{i}.json').write_text(json.dumps({'experiment':'E1' if i<160 else 'E2','pilot_root':f'version-{i%3}'}))
    assert available_calls(attempts,{'new_physical_calls':200},160,'E1')==0
    assert available_calls(attempts,{'new_physical_calls':200},160,'E2')==0


def test_general_pageouts_are_not_misclassified_as_swap(monkeypatch):
    state={'pageouts':1,'swapins':3}
    def output(cmd,**kwargs):
        if cmd[0]=='sysctl':return '1'
        if cmd[0]=='vm_stat':return f"Swapins: {state['swapins']}.\nSwapouts: 12.\nPageouts: {state['pageouts']}.\n"
        return 'No thermal warning level has been recorded'
    monkeypatch.setattr(resources.subprocess,'check_output',output)
    assert resources.mac_health()==15
    state['pageouts']=1000
    assert resources.mac_health()==15
    state['swapins']=4
    assert resources.mac_health()==16
