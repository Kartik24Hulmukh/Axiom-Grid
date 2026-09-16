"""Audit gates must fail closed; synthetic results must never mask failures."""
import copy
import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location("launch_tcp_audit",Path(__file__).resolve().parents[1]/"scripts/launch_tcp_audit.py")
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

def valid_report():
    scenarios={name:{"server_errors":0,"transport_errors":0,"max_ms":10,"n":3000}
        for name in ["health_1_client","health_100_clients","fuzz_100_clients","synthetic_120_clients","extraction_queue_100_clients","recovery"]}
    return {"scenarios":scenarios,"personas_completed":120,
            "probes":{path:200 for path in ["/healthz","/livez","/readyz","/metrics"]},
            "shutdown_exit":-15,"shutdown_complete":True,
            "shutdown_s":.2,"fd_growth":0,"server_exception_markers":{}}

def test_signal_reraise_requires_lifespan_completion():
    report=valid_report()
    assert audit.gate(report)==[]
    report['shutdown_complete']=False
    assert audit.gate(report)

@pytest.mark.parametrize("change",[{'shutdown_exit':-9},{'fd_growth':1},{'shutdown_s':26},
    {'server_exception_markers':{'Traceback':1}},{'probes':{'/readyz':503}}])
def test_fail_closed(change):
    report=valid_report(); report.update(change)
    assert audit.gate(report)

@pytest.mark.parametrize('metric,value',[('server_errors',1),('transport_errors',1),('max_ms',200)])
def test_request_failures_are_not_hardcoded(metric,value):
    report=copy.deepcopy(valid_report()); report['scenarios']['recovery'][metric]=value
    assert audit.gate(report)

def test_all_720_fuzz_indexes_are_valid():
    vectors=[(audit.ROUTES[i%6],audit.FUZZ[(i//6)%len(audit.FUZZ)]) for i in range(720)]
    assert len(vectors)==720
    assert len(set(vectors))==72

def test_summary_counts_transport_and_server_errors():
    result=audit.summarize([{'status':-1,'ms':1},{'status':500,'ms':3},{'status':422,'ms':2}],1)
    assert result['transport_errors']==result['server_errors']==1
    assert result['n']==3

@pytest.mark.parametrize('section',['scenarios','probes'])
def test_missing_evidence_fails(section):
    report=valid_report(); report[section]={}
    assert audit.gate(report)

def test_partial_persona_results_fail():
    report=valid_report(); report['personas_completed']=119
    assert audit.gate(report)
