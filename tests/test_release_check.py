"""Strict synthetic regression contracts; all benchmark/subprocess calls stubbed.

These tests exercise the evaluator, not live model behavior or qualification.
"""
import hashlib
from copy import deepcopy
import importlib.util
import json
import math
import pathlib
import re
import shutil
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
        return covered_report(check._load_profile_manifest())
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
    expected = covered_report(check._load_profile_manifest())
    expected["profile_coverage"] = check._validate_report_coverage(expected, check._load_profile_manifest())
    assert report == expected
    command, kwargs = calls[0]
    assert command[:2] == [sys.executable, "-c"]
    assert configurations == [[{"name": name, "class": invoice_pack,
                                 "dir": str(check.REPO_ROOT / relative)}
                                for name, relative in check.PROFILE_PACKS]]
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


# Full-shape synthetic reports for the new independent coverage contract.
def covered_report(manifest):
    columns = ("answerable_fields", "unanswerable_fields", "grounded_answers",
               "correct_refusals", "false_refusals", "ungrounded_renders")
    docs = []
    packs = {p["name"]: dict.fromkeys(columns, 0) | {"total_documents": 0}
             for p in manifest["packs"]}
    for expected in manifest["documents"]:
        a = len(expected["answerable"]); u = len(check.INVOICE_FIELDS)-a
        doc = {k: expected[k] for k in ("pack", "fixture_id", "file")}
        doc.update(answerable_fields=a, unanswerable_fields=u, grounded_answers=a,
                   correct_refusals=u, false_refusals=0, ungrounded_renders=0)
        doc["field_details"] = [{"field": f,
            "status": "grounded" if f in expected["answerable"] else "correct_refusal",
            "grounded": f in expected["answerable"], "rendered": f in expected["answerable"]}
            for f in check.INVOICE_FIELDS]
        docs.append(doc)
        packs[expected["pack"]]["total_documents"] += 1
        for c in columns: packs[expected["pack"]][c] += doc[c]
    for row in packs.values(): row["ungrounded_render_count"] = row.pop("ungrounded_renders")
    a = sum(d["answerable_fields"] for d in docs)
    u = sum(d["unanswerable_fields"] for d in docs)
    gates = {"grounded_answer_rate": {"measured": 100, "numerator": a, "denominator": a},
             "refusal_on_unanswerable": {"measured": 100, "numerator": u, "denominator": u},
             "false_refusal_rate": {"measured": 0, "numerator": 0, "denominator": a},
             "ungrounded_render_count": {"measured": 0}}
    return {"gates": gates, "per_document": docs, "packs": packs,
            "corpus_hash": manifest["corpus_hash"]}


@pytest.fixture
def profile_copy(monkeypatch, tmp_path):
    for _, relative in check.PROFILE_PACKS:
        shutil.copytree(check.REPO_ROOT / relative, tmp_path / relative)
    monkeypatch.setattr(check, "REPO_ROOT", tmp_path)
    return tmp_path


def rewrite_index(root, edit, relative="fixtures/held_out_negative"):
    index = root / relative / "ground_truth.json"
    data = json.loads(index.read_text())
    edit(data)
    index.write_text(json.dumps(data))


def test_fixed_profile_covers_both_datasets_and_independent_negatives():
    manifest = check._load_profile_manifest()
    assert len(manifest["packs"]) == 2
    assert len(manifest["documents"]) == 7
    assert len({d["fixture_id"] for d in manifest["documents"]}) == 7
    result = check._validate_report_coverage(covered_report(manifest),manifest)
    assert result["answerable_fields"] == 39
    assert result["unanswerable_fields"] == 24
    assert result["document_count"] == 7
    assert all(check._evaluate(check._compute_gate_metrics(covered_report(manifest)),
                              dict.fromkeys(check.CHECK_NAMES,True)).values())


def test_negative_ground_truth_is_source_justified_not_positive_copies():
    root = check.REPO_ROOT / "fixtures/held_out_negative"
    records = json.loads((root/"ground_truth.json").read_text())["fixtures"]
    by_id = {r["fixture_id"]:r for r in records}
    assert len(by_id) >= 3
    positive = {p.read_bytes() for p in (check.REPO_ROOT/"fixtures/held_out").glob("*.txt")}
    for row in records:
        text = (root/row["file"]).read_text()
        assert (root/row["file"]).read_bytes() not in positive
        assert row["rationale"].strip()
        assert set(row["ground_truth"]) == set(check.INVOICE_FIELDS)
        assert row["ground_truth"]["tax_amount"] is None
        assert row["ground_truth"]["payment_terms"] is None
        assert "Tax:" not in text and "Payment Terms:" not in text
    sparse = by_id["negative_sparse_invoice"]
    assert sparse["ground_truth"] == dict.fromkeys(check.INVOICE_FIELDS) | {
        "vendor_name":"Northstar Binding Studio", "currency":"EUR", "total_amount":84.0}
    text = (root/sparse["file"]).read_text()
    assert "Northstar Binding Studio" in text and "€84.00" in text and "Currency: EUR" in text
    assert "Date:" not in text and "Number:" not in text
    due = by_id["negative_due_only_invoice"]
    assert due["ground_truth"]["invoice_date"] is None
    assert due["ground_truth"]["due_date"] == "2026-11-12"
    assert "Due Date: 2026-11-12" in (root/due["file"]).read_text()
    assert "Invoice Date:" not in (root/due["file"]).read_text()
    note = by_id["negative_noninvoice_note"]
    assert all(value is None for value in note["ground_truth"].values())
    text = (root/note["file"]).read_text()
    assert "nature note" in text and "no payment is requested" in text
    ambiguous = by_id["negative_ambiguous_totals"]
    assert ambiguous["ground_truth"]["total_amount"] is None
    text = (root/ambiguous["file"]).read_text()
    assert "$120.00" in text and "$145.00" in text
    assert "provisional" in text and "Neither is approved" in text


@pytest.mark.parametrize("relative", ["fixtures/held_out", "fixtures/held_out_negative"])
def test_missing_index_document_or_empty_dataset_fails_before_subprocess(profile_copy, relative, tmp_path):
    directory = profile_copy/relative
    index = directory/"ground_truth.json"
    original = index.read_bytes()
    index.unlink()
    with pytest.raises(ValueError): check._run_bench("fixtures/held_out",str(tmp_path/"out.json"))
    index.write_bytes(original)
    records = json.loads(original)["fixtures"]
    (directory/records[0]["file"]).unlink()
    with pytest.raises(ValueError): check._load_profile_manifest()
    index.write_text('{"fixtures": []}')
    with pytest.raises(ValueError): check._load_profile_manifest()


@pytest.mark.parametrize("edit", [
    lambda d: d["fixtures"].append(deepcopy(d["fixtures"][0])),
    lambda d: d["fixtures"][1].update(file=d["fixtures"][0]["file"]),
    lambda d: d["fixtures"][0].update(file="../outside.txt"),
    lambda d: d["fixtures"][0].update(file="/tmp/outside.txt"),
    lambda d: d["fixtures"][0].update(file="nested/file.txt"),
    lambda d: d["fixtures"][0].update(fixture_id=""),
    lambda d: d["fixtures"][0].update(ground_truth={}),
    lambda d: d["fixtures"][0].update(ground_truth={"vendor_name": "fabricated"}),
    lambda d: d["fixtures"][0].update(file=True),
    lambda d: d["fixtures"].append(None),
])
def test_invalid_index_configuration_rejected(profile_copy, edit):
    rewrite_index(profile_copy,edit)
    with pytest.raises(ValueError): check._load_profile_manifest()


def test_global_id_uniqueness_and_unindexed_files(profile_copy):
    positive = json.loads((profile_copy/"fixtures/held_out/ground_truth.json").read_text())["fixtures"][0]["fixture_id"]
    rewrite_index(profile_copy,lambda d:d["fixtures"][0].update(fixture_id=positive))
    with pytest.raises(ValueError): check._load_profile_manifest()


def test_unindexed_empty_and_symlink_documents_rejected(profile_copy):
    extra = profile_copy/"fixtures/held_out_negative/unindexed.txt"
    extra.write_text("not indexed")
    with pytest.raises(ValueError): check._load_profile_manifest()
    extra.unlink()
    source = profile_copy/"fixtures/held_out_negative/sparse_invoice.txt"
    original = source.read_text(); source.write_text(" ")
    with pytest.raises(ValueError): check._load_profile_manifest()
    source.unlink(); target = profile_copy/"outside.txt"; target.write_text(original)
    source.symlink_to(target)
    with pytest.raises(ValueError): check._load_profile_manifest()


def test_malformed_duplicate_index_and_unsupported_profile_rejected(profile_copy):
    index = profile_copy/"fixtures/held_out_negative/ground_truth.json"
    for raw in ('[]', '{', '{"fixtures":[],"fixtures":[]}', '{"fixtures":NaN}'):
        index.write_text(raw)
        with pytest.raises(ValueError): check._load_profile_manifest()
    with pytest.raises(ValueError): check._load_profile_manifest("fixtures/invoice")


@pytest.mark.parametrize("mutate", [
    lambda r:r["per_document"].pop(),
    lambda r:r["per_document"].append(deepcopy(r["per_document"][0])),
    lambda r:r["per_document"][0].update(fixture_id="unknown"),
    lambda r:r["per_document"][0].update(file="other.txt"),
    lambda r:r["per_document"][0].update(pack="generic"),
    lambda r:r["per_document"][0].update(answerable_fields=True),
    lambda r:r["per_document"][0].update(answerable_fields=0),
    lambda r:r["per_document"][0].update(grounded_answers=0),
    lambda r:r["per_document"][0]["field_details"].pop(),
    lambda r:r["per_document"][0]["field_details"].append({}),
    lambda r:r["per_document"][0]["field_details"][0].update(status="correct_refusal"),
    lambda r:r["per_document"][0]["field_details"][0].update(grounded=False),
    lambda r:r["per_document"][0]["field_details"][1].update(field="vendor_name"),
    lambda r:r["packs"]["held_out-invoice"].update(total_documents=2),
    lambda r:r["packs"]["held_out-invoice"].update(grounded_answers=0),
    lambda r:r["packs"].pop("held_out-negative-invoice"),
    lambda r:r.update(corpus_hash="stale"),
    lambda r:r["gates"]["grounded_answer_rate"].update(denominator=1),
    lambda r:r["gates"]["refusal_on_unanswerable"].update(numerator=0),
    lambda r:r["gates"]["ungrounded_render_count"].update(measured=1),
])
def test_missing_duplicate_stale_or_inconsistent_report_coverage_rejected(mutate):
    manifest = check._load_profile_manifest(); report = covered_report(manifest)
    mutate(report)
    with pytest.raises(ValueError): check._validate_report_coverage(report,manifest)


def test_changed_source_bytes_reject_stale_report(profile_copy):
    old = check._load_profile_manifest(); report = covered_report(old)
    source = profile_copy/"fixtures/held_out_negative/sparse_invoice.txt"
    source.write_text(source.read_text()+"\nAdditional source text.\n")
    with pytest.raises(ValueError): check._validate_report_coverage(report,check._load_profile_manifest())


def test_profile_change_during_subprocess_rejected(monkeypatch,profile_copy,tmp_path):
    def run(command,**kwargs):
        report = covered_report(check._load_profile_manifest())
        pathlib.Path(command[-1]).write_text(json.dumps(report))
        source = profile_copy/"fixtures/held_out_negative/sparse_invoice.txt"
        source.write_text(source.read_text()+"\nChanged during run.\n")
        return subprocess.CompletedProcess(command,0,"","")
    monkeypatch.setattr(check.subprocess,"run",run)
    with pytest.raises(ValueError,match="changed during"):
        check._run_bench("fixtures/held_out",str(tmp_path/"report.json"))


def test_truthful_incorrect_refusal_remains_valid_coverage_but_fails_threshold():
    manifest = check._load_profile_manifest(); report = covered_report(manifest)
    doc = next(d for d in report["per_document"] if d["fixture_id"] == "negative_noninvoice_note")
    field = next(f for f in doc["field_details"] if f["field"] == "vendor_name")
    field.update(status="incorrect_answer", grounded=True, rendered=True)
    doc["correct_refusals"] -= 1
    report["packs"][doc["pack"]]["correct_refusals"] -= 1
    gate = report["gates"]["refusal_on_unanswerable"]
    gate["numerator"] -= 1
    gate["measured"] = round(gate["numerator"] / gate["denominator"] * 100, 4)
    coverage = check._validate_report_coverage(report,manifest)
    assert coverage["document_count"] == 7
    metrics = check._compute_gate_metrics(report)
    assert check._evaluate(metrics,dict.fromkeys(check.CHECK_NAMES,True))["refusal_on_unanswerable"] is False


def test_truthful_false_refusal_preserves_positive_cohort_coverage():
    manifest = check._load_profile_manifest(); report = covered_report(manifest)
    doc = report["per_document"][0]
    doc["field_details"][0].update(status="false_refusal",grounded=False,rendered=False)
    doc["grounded_answers"] -= 1; doc["false_refusals"] += 1
    report["packs"][doc["pack"]]["grounded_answers"] -= 1
    report["packs"][doc["pack"]]["false_refusals"] += 1
    for name, delta in (("grounded_answer_rate",-1),("false_refusal_rate",1)):
        gate = report["gates"][name]; gate["numerator"] += delta
        gate["measured"] = round(gate["numerator"] / gate["denominator"] * 100,4)
    check._validate_report_coverage(report,manifest)
    assert check._compute_gate_metrics(report)["rate_counts"]["false_refusal_rate"]["numerator"] == 1
