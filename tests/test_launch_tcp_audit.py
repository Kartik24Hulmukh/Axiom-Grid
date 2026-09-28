"""Audit gates must fail closed; synthetic results must never mask failures."""
import copy
import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location("launch_tcp_audit",Path(__file__).resolve().parents[1]/"scripts/launch_tcp_audit.py")
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

def valid_report():
    counts = {"health_1_client": 200, "health_100_clients": 1000,
              "fuzz_100_clients": 720, "synthetic_120_clients": 3000,
              "extraction_queue_100_clients": 200, "recovery": 120}
    scenarios = {name: {"server_errors": 0, "transport_errors": 0,
                       "max_ms": 10, "n": count, "codes": {"200": count}}
                 for name, count in counts.items()}
    return {"scenarios": scenarios, "personas_completed": 120,
            "probes": {path: 200 for path in ["/healthz", "/livez", "/readyz", "/metrics"]},
            "shutdown_exit": -15, "shutdown_complete": True,
            "shutdown_s": .2, "fd_base": 11, "fd_after": 11, "fd_growth": 0,
            "server_exception_markers": {}, "resources": [{"rss_mb": 100, "fds": 11}]}

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


@pytest.mark.parametrize("change", [
    {"harness_error": "partial execution"},
    {"server_exception_markers": None},
    {"fd_growth": -1, "resources": []},
])
def test_incomplete_observation_cannot_pass(change):
    report = valid_report()
    report.update(change)
    assert audit.gate(report)


def test_empty_report_returns_failure_instead_of_raising():
    assert audit.gate({})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, None])
def test_invalid_latency_cannot_pass(value):
    report = valid_report()
    report["scenarios"]["recovery"]["max_ms"] = value
    assert audit.gate(report)


def test_empty_health_sample_cannot_pass():
    report = valid_report()
    report["scenarios"]["health_100_clients"]["n"] = 0
    assert audit.gate(report)


def test_loaded_error_latency_is_a_release_gate():
    report = valid_report()
    report["scenarios"]["fuzz_100_clients"]["max_ms"] = 201
    assert audit.gate(report)


def test_unexpected_health_status_cannot_pass():
    report = valid_report()
    report["scenarios"]["health_100_clients"]["codes"] = {"404": 1000}
    assert audit.gate(report)


@pytest.mark.parametrize("section", ["scenarios", "probes", "resources",
                                      "server_exception_markers"])
@pytest.mark.parametrize("value", [None, [], "bad", 42, True])
def test_malformed_sections_fail_without_crashing(section, value):
    report = valid_report()
    report[section] = value
    assert audit.gate(report)


@pytest.mark.parametrize("codes", [{"200": "1000"}, {"200": -1000},
                                    {"invalid": 1000}, {"600": 1000},
                                    {"200": True}, {}, None])
def test_malformed_status_accounting(codes):
    report = valid_report()
    report["scenarios"]["health_100_clients"]["codes"] = codes
    assert audit.gate(report)


def test_server_error_counter_cannot_hide_a_503():
    report = valid_report()
    report["scenarios"]["extraction_queue_100_clients"]["codes"] = {"200": 199, "503": 1}
    assert audit.gate(report)


def test_fd_decrease_is_not_a_leak():
    report = valid_report()
    report.update(fd_after=10, fd_growth=-1)
    assert audit.gate(report) == []
