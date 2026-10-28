"""Strict synthetic regression contracts; all benchmark/subprocess calls stubbed.

These tests exercise the evaluator, not live model behavior or qualification.
"""
import hashlib
import importlib.util
import json
import math
import pathlib
import re
import subprocess
import sys
import types
from unittest.mock import Mock

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts/release_check.py"
SPEC = importlib.util.spec_from_file_location("release_check_under_test", SCRIPT)
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)
METRICS = {
    "grounded_answer_rate": 96.0,
    "refusal_on_unanswerable": 100.0,
    "false_refusal_rate": 3.0,
    "ungrounded_render_count": 0,
}


def evidence(**updates):
    gates = {k: {"measured": v} for k, v in (METRICS | updates).items()}
    for name in list(METRICS)[:3]:
        value = gates[name]["measured"]
        # Counts are synthetic fixture evidence, not patched production metrics.
        valid = type(value) in (int, float) and 0 <= value <= 100 and math.isfinite(value)
        gates[name].update(numerator=round(value * 10000) if valid else 0, denominator=1000000)
    return {"gates": gates}


def payload(text):
    return json.loads(re.search(r"```json\n(.*?)\n```", text, re.S)[1])


@pytest.fixture(autouse=True)
def no_real_execution(monkeypatch):
    monkeypatch.delenv("KAIRO_PLANTED_PASS", raising=False)
    monkeypatch.delenv("KAIRO_PLANTED_REGRESSION", raising=False)
    monkeypatch.setattr(check.subprocess, "run", Mock(side_effect=AssertionError("real subprocess forbidden")))


@pytest.fixture
def happy(monkeypatch):
    bench = Mock(return_value=evidence())
    monkeypatch.setattr(check, "_run_bench", bench)
    for name in ("_check_cloud_tier_policy_rejection", "_check_verifier_adversarial", "_check_trust_collapse_list"):
        monkeypatch.setattr(check, name, Mock(return_value=True))
    return bench


def test_import_is_safe(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    original_path = sys.path[:]
    monkeypatch.setattr(check.tempfile, "TemporaryDirectory", Mock(side_effect=AssertionError("import created temp files")))
    module = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(module)
    assert sys.path == original_path
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("report", [None, [], {}, {"gates": None}, {"gates": []}, {"gates": {}}])
def test_malformed_reports_rejected(report):
    with pytest.raises(ValueError):
        check._compute_gate_metrics(report)


@pytest.mark.parametrize("name", list(METRICS))
@pytest.mark.parametrize("replacement", [None, [], {}, {"passes": True}])
def test_required_measurements_never_default(name, replacement):
    report = evidence()
    report["gates"][name] = replacement
    with pytest.raises(ValueError):
        check._compute_gate_metrics(report)
    del report["gates"][name]
    with pytest.raises(ValueError):
        check._compute_gate_metrics(report)


@pytest.mark.parametrize("name", list(METRICS)[:3])
@pytest.mark.parametrize("value", [True, False, "96", None, [], {}, -0.01, 100.01,
                                      float("nan"), float("inf"), -float("inf"), 10**400])
def test_percentages_require_finite_numbers_in_range(name, value):
    with pytest.raises(ValueError):
        check._compute_gate_metrics(evidence(**{name: value}))


@pytest.mark.parametrize("value", [True, False, "0", None, -1, 0.0, 1.5, float("nan"), float("inf")])
def test_ungrounded_count_is_strict_nonnegative_integer(value):
    with pytest.raises(ValueError):
        check._compute_gate_metrics(evidence(ungrounded_render_count=value))


@pytest.mark.parametrize("name", list(METRICS)[:3])
@pytest.mark.parametrize("value", [0, 0.0, 100, 100.0])
def test_valid_percentage_endpoints(name, value):
    assert check._compute_gate_metrics(evidence(**{name: value}))[name] == value


def test_valid_count_need_not_be_zero_to_be_well_formed():
    assert check._compute_gate_metrics(evidence(ungrounded_render_count=2))["ungrounded_renders"] == 2


@pytest.mark.parametrize("updates,passed", [({}, True), ({"grounded_answer_rate": 95}, True),
    ({"grounded_answer_rate": 94.99}, False), ({"refusal_on_unanswerable": 99.99}, False),
    ({"false_refusal_rate": 5}, False), ({"false_refusal_rate": 4.99}, True),
    ({"ungrounded_render_count": 1}, False)])
def test_actual_measurements_determine_regression_status(updates, passed):
    metrics = check._compute_gate_metrics(evidence(**updates))
    assert all(check._evaluate(metrics, dict.fromkeys(check.CHECK_NAMES, True)).values()) is passed


@pytest.mark.parametrize("checks", [{}, dict.fromkeys(check.CHECK_NAMES, 1),
                                   dict.fromkeys(check.CHECK_NAMES, "true")])
def test_additional_checks_must_be_complete_booleans(checks):
    with pytest.raises(ValueError):
        check._evaluate(check._compute_gate_metrics(evidence()), checks)


def test_synthetic_pass_is_explicitly_not_qualification(happy, capsys):
    assert check.main(["--profile", check.PROFILE]) == 0
    text = capsys.readouterr().out
    data = payload(text)
    assert data["regression_passed"] is True
    assert data["production_qualified"] is False
    assert data["release_cleared"] is False
    assert data["profile"] == "synthetic-regression-only"
    assert "production_qualified=false" in text
    assert "NEVER clears release or production" in text
    assert "not network or air-gap proof" in text
    assert "deterministic synthetic test responses" in text
    assert "cleared for release" not in text
    assert "air_gap" not in data["checks"]
    assert happy.call_args.args[0] == "fixtures/held_out"


def test_checksum_is_full_reproducible_checksum_not_signature(happy, capsys):
    assert check.main([]) == 0
    text = capsys.readouterr().out
    canonical = re.search(r"```json\n(.*?)\n```", text, re.S)[1]
    checksum = re.search(r"SHA-256 checksum:\*\* `([a-f0-9]{64})`", text)[1]
    assert checksum == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert "not a cryptographic signature" in text
    assert "Signed by" not in text


@pytest.mark.parametrize("value", ["true", "TRUE", " true "])
def test_planted_pass_rejected_before_any_work(monkeypatch, tmp_path, value, capsys):
    monkeypatch.setenv("KAIRO_PLANTED_PASS", value)
    bench = Mock(side_effect=AssertionError("benchmark must not run"))
    monkeypatch.setattr(check, "_run_bench", bench)
    monkeypatch.setattr(check.tempfile, "TemporaryDirectory", Mock(side_effect=AssertionError("no writes")))
    output = tmp_path / "report.md"
    assert check.main(["--output", str(output)]) != 0
    assert not output.exists()
    bench.assert_not_called()
    assert "rejected" in capsys.readouterr().err


@pytest.mark.parametrize("planted", ["grounded_answer=0", "grounded_answer=100", "not-a-number"])
def test_planted_regression_cannot_rewrite_evidence(monkeypatch, happy, planted, capsys):
    monkeypatch.setenv("KAIRO_PLANTED_REGRESSION", planted)
    assert check.main([]) == 0
    assert payload(capsys.readouterr().out)["metrics"]["grounded_answer_rate"] == 96


def test_no_implicit_report_or_benchmark_artifacts(happy, monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(check, "REPO_ROOT", tmp_path)
    original = tmp_path / "RELEASE_REPORT.md"
    original.write_text("untouched legacy report")
    assert check.main([]) == 0
    assert original.read_text() == "untouched legacy report"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["RELEASE_REPORT.md"]
    assert not pathlib.Path(happy.call_args.args[1]).exists()


def test_explicit_output_and_no_overwrite(happy, tmp_path, capsys):
    output = tmp_path / "report.md"
    assert check.main(["--output", str(output)]) == 0
    text = output.read_text()
    assert text == capsys.readouterr().out
    happy.reset_mock()
    assert check.main(["--output", str(output)]) != 0
    assert output.read_text() == text
    happy.assert_not_called()


@pytest.mark.parametrize("bad", [None, {}, evidence(false_refusal_rate=float("nan")),
                                 evidence(ungrounded_render_count=-1)])
def test_invalid_evidence_fails_and_records_no_qualification(happy, bad, tmp_path, capsys):
    happy.return_value = bad
    output = tmp_path / "invalid.md"
    assert check.main(["--output", str(output)]) == 1
    data = payload(output.read_text())
    assert data["regression_passed"] is False
    assert data["production_qualified"] is False
    assert data["error"] is not None
    assert data["metrics"] is None


def test_benchmark_exception_fails_closed(happy, capsys):
    happy.side_effect = subprocess.TimeoutExpired("fixture", 120)
    assert check.main([]) == 1
    assert payload(capsys.readouterr().out)["regression_passed"] is False


@pytest.mark.parametrize("name", ["_check_cloud_tier_policy_rejection", "_check_verifier_adversarial", "_check_trust_collapse_list"])
def test_failed_additional_check_is_a_regression_failure(monkeypatch, happy, name, capsys):
    monkeypatch.setattr(check, name, lambda: False)
    assert check.main([]) == 1
    assert payload(capsys.readouterr().out)["production_qualified"] is False


def test_benchmark_invocation_uses_explicit_invoice_pack_and_isolated(monkeypatch, tmp_path):
    calls, configurations = [], []
    invoice_pack = type("InvoicePackStub", (), {})
    harness = types.ModuleType("bench.harness")
    def benchmark(config):
        configurations.append(config)
        return evidence()
    harness.run_benchmark = benchmark
    invoice = types.ModuleType("packs.invoice.pack")
    invoice.InvoicePack = invoice_pack
    monkeypatch.setenv("KAIRO_PLANTED_REGRESSION", "grounded_answer=100")
    def run(command, **kwargs):
        calls.append((command, kwargs))
        # Execute the actual generated wrapper, but replace its benchmark and pack
        # imports. No benchmark/dependency or expensive subprocess is invoked.
        with monkeypatch.context() as inner:
            inner.setitem(sys.modules, "bench.harness", harness)
            inner.setitem(sys.modules, "packs.invoice.pack", invoice)
            inner.setattr(sys, "argv", ["-c", *command[3:]])
            exec(compile(command[2], "<benchmark-wrapper>", "exec"), {"__name__": "__main__"})
        (pathlib.Path(kwargs["cwd"]) / "history-marker").write_text("scratch")
        return subprocess.CompletedProcess(command, 0, "", "")
    monkeypatch.setattr(check.subprocess, "run", run)
    report = check._run_bench("fixtures/held_out", str(tmp_path / "bench.json"))
    assert report == evidence()
    command, kwargs = calls[0]
    assert command[:2] == [sys.executable, "-c"]
    assert configurations == [[{"name": "held_out-invoice", "class": invoice_pack,
                                "dir": str(check.REPO_ROOT / "fixtures/held_out")}]]
    assert kwargs["cwd"] != str(check.REPO_ROOT)
    assert not pathlib.Path(kwargs["cwd"]).exists()
    assert kwargs["env"]["KAIRO_GATEWAY_TEST_MODE"] == "true"
    assert kwargs["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert pathlib.Path(kwargs["env"]["AXIOM_STATE_DIR"]).parent == pathlib.Path(kwargs["cwd"])
    assert "KAIRO_PLANTED_PASS" not in kwargs["env"]
    assert "KAIRO_PLANTED_REGRESSION" not in kwargs["env"]
    assert kwargs["timeout"] == 120


def test_benchmark_process_failure_cannot_be_a_pass(monkeypatch, tmp_path):
    monkeypatch.setattr(check.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 1, "", "failed"))
    with pytest.raises(ValueError, match="benchmark failed"):
        check._run_bench("fixtures/held_out", str(tmp_path / "bench.json"))
    assert not (tmp_path / "bench.json").exists()


@pytest.mark.parametrize("function", [check._check_cloud_tier_policy_rejection,
                                     check._check_verifier_adversarial,
                                     check._check_trust_collapse_list])
@pytest.mark.parametrize("returncode", [0, 1])
def test_auxiliary_checks_use_isolated_subprocess_stubs(monkeypatch, function, returncode):
    run = Mock(return_value=subprocess.CompletedProcess([], returncode, "", ""))
    monkeypatch.setattr(check.subprocess, "run", run)
    assert function() is (returncode == 0)
    kwargs = run.call_args.kwargs
    assert not pathlib.Path(kwargs["cwd"]).exists()
    assert kwargs["env"]["KAIRO_GATEWAY_TEST_MODE"] == "true"


def test_planted_regression_cannot_rescue_failed_measurements(monkeypatch, happy, capsys):
    happy.return_value = evidence(grounded_answer_rate=50)
    monkeypatch.setenv("KAIRO_PLANTED_REGRESSION", "grounded_answer=100")
    assert check.main([]) == 1
    data = payload(capsys.readouterr().out)
    assert data["metrics"]["grounded_answer_rate"] == 50
    assert data["regression_passed"] is False


def test_output_write_failure_returns_nonzero(happy, tmp_path, capsys):
    assert check.main(["--output", str(tmp_path / "missing-parent" / "report.md")]) == 2
    assert not (tmp_path / "missing-parent").exists()
    assert "report write failed" in capsys.readouterr().err


def test_evaluation_does_not_rewrite_input_metrics():
    report = evidence()
    before = json.dumps(report, sort_keys=True)
    metrics = check._compute_gate_metrics(report)
    check._evaluate(metrics, dict.fromkeys(check.CHECK_NAMES, True))
    assert json.dumps(report, sort_keys=True) == before
    assert metrics["grounded_answer_rate"] == 96.0
    assert metrics["refusal_on_unanswerable"] == 100.0
    assert metrics["false_refusal_rate"] == 3.0
    assert metrics["ungrounded_renders"] == 0
    assert metrics["rate_counts"]["grounded_answer_rate"] == {"numerator": 960000, "denominator": 1000000}


@pytest.mark.parametrize("name", list(METRICS)[:3])
@pytest.mark.parametrize("field", ["numerator", "denominator"])
@pytest.mark.parametrize("bad", [None, True, False, "1", 1.0, -1, float("nan"), float("inf")])
def test_rate_counts_must_be_strict_valid_integers(name, field, bad):
    report = evidence()
    report["gates"][name][field] = bad
    with pytest.raises(ValueError):
        check._compute_gate_metrics(report)


@pytest.mark.parametrize("name", list(METRICS)[:3])
@pytest.mark.parametrize("field", ["numerator", "denominator"])
def test_missing_rate_counts_rejected(name, field):
    report = evidence()
    del report["gates"][name][field]
    with pytest.raises(ValueError):
        check._compute_gate_metrics(report)


@pytest.mark.parametrize("name", list(METRICS)[:3])
def test_rate_numerator_cannot_exceed_denominator(name):
    report = evidence()
    report["gates"][name].update(numerator=2, denominator=1)
    with pytest.raises(ValueError):
        check._compute_gate_metrics(report)


@pytest.mark.parametrize("name", list(METRICS)[:3])
def test_zero_denominator_is_insufficient_coverage(name):
    report = evidence()
    report["gates"][name].update(numerator=0, denominator=0)
    with pytest.raises(check.InsufficientCoverageError) as caught:
        check._compute_gate_metrics(report)
    assert caught.value.metrics["rate_counts"][name] == {"numerator": 0, "denominator": 0}


@pytest.mark.parametrize("name", list(METRICS)[:3])
def test_measured_rates_must_match_counts_to_four_places(name):
    report = evidence()
    report["gates"][name]["measured"] = 12.3456
    with pytest.raises(ValueError, match="disagrees with counts"):
        check._compute_gate_metrics(report)


@pytest.mark.parametrize("name,numerator,denominator,rounded,expected", [
    ("grounded_answer_rate", 94999999, 100000000, 95.0, False),
    ("grounded_answer_rate", 95, 100, 95.0, True),
    ("refusal_on_unanswerable", 99999999, 100000000, 100.0, False),
    ("refusal_on_unanswerable", 1, 1, 100.0, True),
    ("false_refusal_rate", 4999999, 100000000, 5.0, True),
    ("false_refusal_rate", 5, 100, 5.0, False),
])
def test_exact_count_thresholds_not_rounded_percentages(name, numerator, denominator, rounded, expected):
    report = evidence()
    report["gates"][name].update(measured=rounded, numerator=numerator, denominator=denominator)
    # Both answerable rates describe the same cohort, including at boundaries.
    if name == "grounded_answer_rate":
        report["gates"]["false_refusal_rate"].update(measured=0, numerator=0, denominator=denominator)
    elif name == "false_refusal_rate":
        report["gates"]["grounded_answer_rate"].update(measured=100, numerator=denominator, denominator=denominator)
    metrics = check._compute_gate_metrics(report)
    result_key = {"grounded_answer_rate": "grounded_answer", "refusal_on_unanswerable": "refusal_on_unanswerable",
                  "false_refusal_rate": "false_refusal"}[name]
    assert check._evaluate(metrics, dict.fromkeys(check.CHECK_NAMES, True))[result_key] is expected


def test_empty_benchmark_default_rates_cannot_pass(happy, capsys):
    report = evidence(grounded_answer_rate=100, refusal_on_unanswerable=100, false_refusal_rate=0)
    for name in list(METRICS)[:3]:
        report["gates"][name].update(numerator=0, denominator=0)
    happy.return_value = report
    assert check.main([]) == 1
    result = payload(capsys.readouterr().out)
    assert "Insufficient coverage" in result["error"]
    assert result["regression_passed"] is False
    assert result["production_qualified"] is False
    assert all(c["denominator"] == 0 for c in result["metrics"]["rate_counts"].values())


def test_invoice_like_positive_fields_without_negatives_rejected_with_counts(happy, capsys):
    report = evidence(grounded_answer_rate=100, refusal_on_unanswerable=100, false_refusal_rate=0)
    report["gates"]["grounded_answer_rate"].update(numerator=27, denominator=27)
    report["gates"]["false_refusal_rate"].update(numerator=0, denominator=27)
    report["gates"]["refusal_on_unanswerable"].update(numerator=0, denominator=0)
    happy.return_value = report
    assert check.main([]) == 1
    result = payload(capsys.readouterr().out)
    assert "InvoicePack" in result["benchmark"]
    assert result["metrics"]["rate_counts"]["refusal_on_unanswerable"]["denominator"] == 0
    assert result["metrics"]["rate_counts"]["grounded_answer_rate"]["denominator"] == 27
    check._check_cloud_tier_policy_rejection.assert_not_called()


def test_positive_answerable_and_unanswerable_coverage_retained_on_pass(happy, capsys):
    assert check.main([]) == 0
    result = payload(capsys.readouterr().out)
    assert len(result["metrics"]["rate_counts"]) == 3
    assert all(c["denominator"] > 0 for c in result["metrics"]["rate_counts"].values())
    assert result["production_qualified"] is False


@pytest.mark.parametrize("name", ["grounded_answer_rate", "false_refusal_rate"])
def test_answerable_cohort_denominator_mismatch_rejected(name):
    report = evidence()
    # Preserve each individual rate and its internally consistent counts.
    report["gates"][name]["numerator"] *= 2
    report["gates"][name]["denominator"] *= 2
    with pytest.raises(ValueError, match="same answerable denominator"):
        check._compute_gate_metrics(report)


def test_cohort_mismatch_fails_main_without_qualification(happy, capsys):
    report = evidence()
    report["gates"]["false_refusal_rate"].update(numerator=3, denominator=100)
    happy.return_value = report
    assert check.main([]) == 1
    result = payload(capsys.readouterr().out)
    assert result["regression_passed"] is False
    assert result["production_qualified"] is False
    check._check_cloud_tier_policy_rejection.assert_not_called()
