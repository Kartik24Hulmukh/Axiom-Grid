"""Bounded, diagnostic-only checkpoint tests; never execute the burst or a server."""
import ast
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/summarize_service_junit.py"
MODULE = "overlay.tests.test_surrogate_encode_zero_day"
FUNCTION = "test_surrogate_burst_100_workers_zero_5xx_and_recovery_slo"
IDENTITY = MODULE + "::" + FUNCTION
PROPERTY = "axiom_surrogate_burst_phase"
PHASES = ("workload", "no_5xx", "health", "quantiles", "p50", "complete")
PRIVATE = "SYNTHETIC_PRIVATE_PHASE_PAYLOAD_9173"
HEADING = "Last recorded burst phase:"
NOTICE = "::notice title=Service diagnostic checkpoint::surrogate_burst_phase="


def load_summary_module():
    spec = importlib.util.spec_from_file_location("service_failure_phase_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case(*, classname=MODULE, name=FUNCTION, outcome="failure", phase="p50"):
    node = ET.Element("testcase", {"classname": classname, "name": name})
    if outcome:
        ET.SubElement(node, outcome, {"message": PRIVATE}).text = PRIVATE
    if phase is not None:
        properties = ET.SubElement(node, "properties")
        ET.SubElement(properties, "property", {"name": PROPERTY, "value": phase})
    return node


def valid_result(phase="p50"):
    return {"scope": "diagnostic-only", "production_qualified": False, "status": "available",
            "counts": {"tests": 1, "failures": 1, "errors": 0, "skipped": 0},
            "failed_tests": [IDENTITY], "omitted_failures": 0,
            "failure_phases": [{"test": IDENTITY, "phase": phase}]}


class ServiceFailurePhaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = load_summary_module()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="service-failure-phase-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.report = self.root / "report.xml"

    def summarize(self, *cases):
        root = ET.Element("testsuite", {"name": PRIVATE})
        for node in cases:
            root.append(node)
        self.report.write_bytes(ET.tostring(root, encoding="utf-8"))
        return self.summary.summarize(self.report)

    def assert_available(self, result):
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["scope"], "diagnostic-only")
        self.assertIs(result["production_qualified"], False)
        self.assertIsInstance(result["failure_phases"], list)
        self.assertLessEqual(len(result["failure_phases"]), 1)
        self.assertNotIn(PRIVATE, json.dumps(result) + self.summary.render(result))

    def assert_no_phase(self, result):
        self.assert_available(result)
        self.assertEqual(result["failure_phases"], [])
        rendered = self.summary.render(result)
        self.assertNotIn(HEADING, rendered)
        self.assertNotIn("surrogate_burst_phase=", rendered)

    def invoke_main(self, *, forged=None, summary_path=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        env = {"GITHUB_STEP_SUMMARY": str(summary_path)} if summary_path is not None else {}
        with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            if forged is None:
                code = self.summary.main([str(self.report)])
            else:
                with mock.patch.object(self.summary, "summarize", return_value=forged):
                    code = self.summary.main([str(self.report)])
        self.assertEqual(code, 0, "diagnostics must not become a test/release gate")
        return stdout.getvalue(), stderr.getvalue()

    def test_each_approved_phase_is_recorded_for_failure_and_error_only(self):
        for outcome in ("failure", "error"):
            for phase in PHASES:
                with self.subTest(outcome=outcome, phase=phase):
                    result = self.summarize(case(outcome=outcome, phase=phase))
                    self.assert_available(result)
                    self.assertEqual(result["failed_tests"], [IDENTITY])
                    self.assertEqual(result["failure_phases"], [{"test": IDENTITY, "phase": phase}])
                    rendered = self.summary.render(result)
                    self.assertIn(HEADING, rendered)
                    self.assertIn(phase, rendered)
                    self.assertIn("diagnostic", rendered.lower())
                    self.assertIn("checkpoint", rendered.lower())
                    self.assertRegex(rendered.lower(), r"not [^\n.]*root[- ]cause verdict")
                    self.assertIn("not qualification", rendered.lower())

    def test_passing_skipped_and_property_free_failures_have_no_phase(self):
        for node in (case(outcome=None), case(outcome="skipped"), case(phase=None)):
            self.assert_no_phase(self.summarize(node))
        self.assert_no_phase(self.summarize())

    def test_raw_classname_and_name_must_match_exactly_without_parameters(self):
        for classname, name in ((MODULE, FUNCTION + "[p50]"), (MODULE, FUNCTION + f"[{PRIVATE}]"),
                                (MODULE + ".extra", FUNCTION), ("other." + MODULE, FUNCTION),
                                (MODULE, FUNCTION + "_extra"), (MODULE, FUNCTION.upper()),
                                (MODULE + " ", FUNCTION), (MODULE, FUNCTION + " "),
                                ("other.api", "test_unrelated")):
            with self.subTest(classname=classname, name=name):
                self.assert_no_phase(self.summarize(case(classname=classname, name=name)))

    def test_unknown_values_and_property_names_never_become_phase_diagnostics(self):
        for value in ("", "P50", "p50 ", " p50", "50", PRIVATE,
                      f"p50\n::error::{PRIVATE}", "health%0A::warning::injected", "quantiles,complete"):
            with self.subTest(value=value):
                self.assert_no_phase(self.summarize(case(phase=value)))
        for name in (PROPERTY + "_extra", PROPERTY.upper(), "other", PRIVATE):
            node = case()
            node.find("properties/property").set("name", name)
            self.assert_no_phase(self.summarize(node))

    def test_wellformed_unrelated_properties_are_ignored_not_emitted(self):
        node = case()
        properties = node.find("properties")
        ET.SubElement(properties, "property", {"name": "private-other", "value": PRIVATE})
        result = self.summarize(node)
        self.assert_available(result)
        self.assertEqual(result["failure_phases"], [{"test": IDENTITY, "phase": "p50"}])
        self.assertNotIn("private-other", json.dumps(result) + self.summary.render(result))

    def test_duplicate_matching_properties_omit_optional_phase_even_when_identical(self):
        for phase in ("p50", "health", PRIVATE):
            node = case()
            ET.SubElement(node.find("properties"), "property", {"name": PROPERTY, "value": phase})
            self.assert_no_phase(self.summarize(node))

    def test_duplicate_or_attributed_properties_containers_omit_optional_phase(self):
        node = case()
        ET.SubElement(node, "properties")
        self.assert_no_phase(self.summarize(node))
        node = case()
        node.find("properties").set("private", PRIVATE)
        self.assert_no_phase(self.summarize(node))
        node = case()
        ET.SubElement(node.find("properties"), "unexpected", {"private": PRIVATE})
        self.assert_no_phase(self.summarize(node))

    def test_malformed_matching_property_omits_optional_phase(self):
        for mutation in ("missing-value", "extra-attribute", "text", "child"):
            node = case()
            prop = node.find("properties/property")
            if mutation == "missing-value":
                del prop.attrib["value"]
            elif mutation == "extra-attribute":
                prop.set("private", PRIVATE)
            elif mutation == "text":
                prop.text = PRIVATE
            else:
                ET.SubElement(prop, "payload").text = PRIVATE
            with self.subTest(mutation=mutation):
                self.assert_no_phase(self.summarize(node))

    def test_malformed_unknown_properties_and_nonwhitespace_tails_omit_phase(self):
        for mutation in ("missing-value", "extra-attribute", "child", "text", "tail"):
            node = case()
            prop = ET.SubElement(node.find("properties"), "property", {"name": "other", "value": PRIVATE})
            if mutation == "missing-value":
                del prop.attrib["value"]
            elif mutation == "extra-attribute":
                prop.set("extra", PRIVATE)
            elif mutation == "child":
                ET.SubElement(prop, "nested").text = PRIVATE
            elif mutation == "text":
                prop.text = PRIVATE
            else:
                prop.tail = PRIVATE
            with self.subTest(mutation=mutation):
                self.assert_no_phase(self.summarize(node))
        node = case()
        node.find("properties/property").tail = PRIVATE
        self.assert_no_phase(self.summarize(node))
        node = case()
        node.find("properties").text = PRIVATE
        self.assert_no_phase(self.summarize(node))

    def test_multiple_raw_exact_target_cases_anywhere_omit_all_optional_phase(self):
        for outcome in ("failure", "error", "skipped", None):
            for phase in ("health", None):
                with self.subTest(outcome=outcome, phase=phase):
                    self.assert_no_phase(self.summarize(case(), case(outcome=outcome, phase=phase)))
        root = ET.Element("testsuite")
        root.append(case())
        nested = ET.SubElement(root, "testsuite")
        nested.append(case(outcome=None))
        self.report.write_bytes(ET.tostring(root))
        self.assert_no_phase(self.summary.summarize(self.report))

    def test_nested_fake_target_in_failure_output_or_properties_cannot_source_phase(self):
        for wrapper in ("failure", "system-out", "properties"):
            with self.subTest(wrapper=wrapper):
                parent = case(classname="svc.api", name="test_parent", outcome=None, phase=None)
                ET.SubElement(parent, wrapper).append(case())
                result = self.summarize(parent)
                self.assert_no_phase(result)
                # Counts intentionally retain the old root.iter diagnostic behavior.
                self.assertEqual(result["counts"]["tests"], 2)
                self.assertIn(IDENTITY, result["failed_tests"])

    def test_exact_target_under_suite_only_nested_ancestry_can_source_phase(self):
        for root_name in ("testsuite", "testsuites"):
            with self.subTest(root=root_name):
                root = ET.Element(root_name)
                outer = ET.SubElement(root, "testsuite")
                inner = ET.SubElement(outer, "testsuite")
                inner.append(case())
                self.report.write_bytes(ET.tostring(root, encoding="utf-8"))
                result = self.summary.summarize(self.report)
                self.assert_available(result)
                self.assertEqual(result["failure_phases"], [{"test": IDENTITY, "phase": "p50"}])

    def test_direct_testcase_under_testsuites_cannot_source_phase(self):
        root = ET.Element("testsuites")
        root.append(case())
        self.report.write_bytes(ET.tostring(root, encoding="utf-8"))
        result = self.summary.summarize(self.report)
        self.assert_no_phase(result)
        self.assertEqual(result["counts"], {"tests": 1, "failures": 1, "errors": 0, "skipped": 0})
        self.assertEqual(result["failed_tests"], [IDENTITY])

    def test_forged_duplicate_target_labels_cannot_source_rendered_phase_or_notice(self):
        result = valid_result()
        result["counts"].update(tests=2, failures=2)
        result["failed_tests"] = [IDENTITY, IDENTITY]
        rendered = self.summary.render(result)
        self.assertIn("failures=2", rendered)
        self.assertNotIn(HEADING, rendered)
        stdout, stderr = self.invoke_main(forged=result)
        self.assertEqual(stderr, "")
        self.assertNotIn(NOTICE, stdout)
        self.assertNotIn(HEADING, stdout)

    def test_parameterized_case_is_not_a_second_raw_exact_target(self):
        result = self.summarize(case(), case(name=FUNCTION + "[other]", outcome=None))
        self.assert_available(result)
        self.assertEqual(result["failure_phases"], [{"test": IDENTITY, "phase": "p50"}])

    def test_phase_requires_target_to_be_retained_in_bounded_failed_labels(self):
        others = [case(classname="svc.api", name=f"test_other_{index}", phase=None) for index in range(20)]
        result = self.summarize(*others, case())
        self.assert_no_phase(result)
        self.assertEqual(len(result["failed_tests"]), 20)
        self.assertEqual(result["omitted_failures"], 1)
        retained = self.summarize(case(), *others)
        self.assert_available(retained)
        self.assertEqual(retained["failure_phases"], [], "twenty labels exhaust the combined output-label budget")
        self.assertEqual(len(retained["failed_tests"]), 20)
        self.assertEqual(retained["omitted_failures"], 1)
        boundary = self.summarize(case(), *others[:18])
        self.assert_available(boundary)
        self.assertEqual(len(boundary["failed_tests"]), 19)
        self.assertEqual(boundary["failure_phases"], [{"test": IDENTITY, "phase": "p50"}])
        self.assertEqual(boundary["omitted_failures"], 0)

    def test_duplicate_target_beyond_label_cap_still_invalidates_first_phase(self):
        others = [case(classname="svc.api", name=f"test_other_{index}", phase=None) for index in range(20)]
        result = self.summarize(case(), *others, case(outcome=None))
        self.assert_no_phase(result)
        self.assertEqual(len(result["failed_tests"]), 20)

    def test_case_limit_still_fail_closed_with_phase_present(self):
        with mock.patch.object(self.summary, "MAX_CASES", 1):
            result = self.summarize(case(), case(classname="svc.api", name="test_other", phase=None))
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn(PRIVATE, json.dumps(result) + self.summary.render(result))
        self.assertNotIn(HEADING, self.summary.render(result))

    def test_render_accepts_all_approved_values_with_a_retained_failed_identity(self):
        for phase in PHASES:
            rendered = self.summary.render(valid_result(phase))
            self.assertIn(HEADING, rendered)
            self.assertIn(phase, rendered)
            self.assertIn("failures=1", rendered)
            self.assertNotIn(PRIVATE, rendered)

    def test_render_invalid_optional_data_is_omitted_while_valid_counts_are_preserved(self):
        invalid = [None, {}, "p50", 1, True,
                   [{"test": IDENTITY, "phase": "p50"}] * 2,
                   [None], [[]], [PRIVATE],
                   [{"test": IDENTITY}], [{"phase": "p50"}],
                   [{"test": IDENTITY, "phase": "p50", "private": PRIVATE}],
                   [{"test": "svc.api::test_other", "phase": "p50"}],
                   [{"test": None, "phase": "p50"}], [{"test": IDENTITY, "phase": None}],
                   [{"test": IDENTITY, "phase": ["p50"]}],
                   [{"test": IDENTITY, "phase": PRIVATE}],
                   [{"test": IDENTITY, "phase": f"p50\n::error::{PRIVATE}"}],
                   [{"test": IDENTITY + "[private]", "phase": "p50"}],
                   [{"test": IDENTITY, "phase": "p50 "}]]
        for phases in invalid:
            with self.subTest(phases=phases):
                result = valid_result()
                result["failure_phases"] = phases
                before = copy.deepcopy(result)
                rendered = self.summary.render(result)
                self.assertEqual(result, before, "defensive rendering must not mutate its input")
                self.assertIn("failures=1", rendered)
                self.assertIn(IDENTITY, rendered)
                self.assertNotIn(HEADING, rendered)
                self.assertNotIn(PRIVATE, rendered)
                self.assertNotIn("::error::", rendered)

    def test_render_requires_phase_identity_membership_in_failed_labels(self):
        result = valid_result()
        result["failed_tests"] = ["svc.api::test_other"]
        rendered = self.summary.render(result)
        self.assertIn("failures=1", rendered)
        self.assertNotIn(HEADING, rendered)
        self.assertNotIn(IDENTITY, rendered)

    def test_missing_optional_field_remains_backward_compatible(self):
        result = valid_result()
        del result["failure_phases"]
        rendered = self.summary.render(result)
        self.assertIn("failures=1", rendered)
        self.assertNotIn(HEADING, rendered)

    def test_output_cap_is_16kib_and_exact_utf8_byte_boundary_is_inclusive(self):
        self.assertEqual(self.summary.MAX_OUTPUT_BYTES, 16 * 1024)
        self.assertEqual(self.summary.MAX_PHASES, 1)
        rendered = self.summary.render(valid_result())
        size = len(rendered.encode("utf-8"))
        self.assertLessEqual(size, 16 * 1024)
        with mock.patch.object(self.summary, "MAX_OUTPUT_BYTES", size):
            self.assertEqual(self.summary.render(valid_result()), rendered)
        with mock.patch.object(self.summary, "MAX_OUTPUT_BYTES", size - 1):
            bounded = self.summary.render(valid_result())
            self.assertLessEqual(len(bounded.encode("utf-8")), size - 1)
            self.assertNotIn(HEADING, bounded)
            self.assertNotIn(PRIVATE, bounded)

    def test_render_and_notices_share_twenty_label_combined_budget(self):
        result = valid_result()
        result["counts"].update(tests=20, failures=20)
        result["failed_tests"] = [IDENTITY] + [f"svc.api::test_other_{index}" for index in range(19)]
        rendered = self.summary.render(result)
        self.assertIn("failures=20", rendered)
        self.assertNotIn(HEADING, rendered)
        self.assertLessEqual(len(rendered.encode("utf-8")), 16 * 1024)
        stdout, stderr = self.invoke_main(forged=result)
        self.assertEqual(stderr, "")
        self.assertNotIn(NOTICE, stdout)
        self.assertNotIn(HEADING, stdout)
        self.assertEqual(sum(line.startswith("::notice title=Service test case::")
                             for line in stdout.splitlines()), 20)
        result["counts"].update(tests=19, failures=19)
        result["failed_tests"].pop()
        self.assertIn(HEADING, self.summary.render(result))
        stdout, _ = self.invoke_main(forged=result)
        self.assertEqual(sum(line.startswith(NOTICE) for line in stdout.splitlines()), 1)

    def test_maximum_length_safe_labels_stay_bounded_without_raw_payload(self):
        result = valid_result()
        result["counts"].update(tests=20, failures=20)
        label = "a" * 200 + "::test_" + "b" * 123
        result["failed_tests"] = [label] * 20
        result["failure_phases"] = []
        rendered = self.summary.render(result)
        self.assertEqual(rendered.count(label), 20)
        self.assertLessEqual(len(rendered.encode("utf-8")), 16 * 1024)
        self.assertNotIn(PRIVATE, rendered)

    def test_main_outputs_exact_fixed_notice_for_each_approved_phase(self):
        for phase in PHASES:
            self.summarize(case(phase=phase))
            destination = self.root / "step-summary.md"
            destination.unlink(missing_ok=True)
            stdout, stderr = self.invoke_main(summary_path=destination)
            self.assertEqual(stderr, "")
            self.assertIn(NOTICE + phase, stdout.splitlines())
            self.assertEqual(sum(line.startswith(NOTICE) for line in stdout.splitlines()), 1)
            self.assertNotIn(PRIVATE, stdout + destination.read_text())
            self.assertIn(HEADING, destination.read_text())
            self.assertNotIn("::notice", destination.read_text())

    def test_main_never_emits_unapproved_property_payload_or_injected_command(self):
        self.summarize(case(phase=f"p50\n::error::{PRIVATE}"))
        stdout, stderr = self.invoke_main()
        self.assertEqual(stderr, "")
        self.assertNotIn(NOTICE, stdout)
        self.assertNotIn(PRIVATE, stdout)
        self.assertNotIn("::error::", stdout)
        self.assertNotIn(HEADING, stdout)

    def test_main_revalidates_forged_optional_phase_before_annotation(self):
        for phases in ([{"test": IDENTITY, "phase": f"p50\n::error::{PRIVATE}"}],
                       [{"test": f"{IDENTITY}\n::warning::{PRIVATE}", "phase": "p50"}],
                       [{"test": IDENTITY, "phase": "p50"}] * 2,
                       [{"test": IDENTITY, "phase": "p50", "private": PRIVATE}],
                       "p50", None):
            result = valid_result()
            result["failure_phases"] = phases
            with self.subTest(phases=phases):
                stdout, stderr = self.invoke_main(forged=result)
                self.assertEqual(stderr, "")
                self.assertIn("failures=1", stdout)
                self.assertNotIn(NOTICE, stdout)
                self.assertNotIn(PRIVATE, stdout)
                self.assertNotIn("::error::", stdout)
                self.assertNotIn("::warning::", stdout)
                self.assertNotIn(HEADING, stdout)


class SyntheticProducerPhaseTests(unittest.TestCase):
    """Compile only the real test function; supply fake synchronous dependencies."""

    @classmethod
    def setUpClass(cls):
        source = ROOT / "overlay/tests/test_surrogate_encode_zero_day.py"
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == FUNCTION]
        if len(matches) != 1:
            raise AssertionError("expected exactly one checkpoint producer function")
        # No surrounding imports, fixture definitions, module globals, or server code.
        selected = copy.deepcopy(matches[0])
        if selected.decorator_list:
            raise AssertionError("unexpected executable producer decorators")
        cls.code = compile(ast.fix_missing_locations(ast.Module(body=[selected], type_ignores=[])),
                           "synthetic-checkpoint-producer-only", "exec")

    def prepare(self, *, post_status=422, health_status=200, p50=1,
                workload_error=None, quantiles_error=None):
        phases = []
        calls = {"workers": [], "indices": [], "posts": [], "health": [], "quantiles": []}

        class RecordedProperties(list):
            def append(self, item):
                if item[0] == PROPERTY:
                    phases.append(item[1])
                super().append(item)

        properties = RecordedProperties([("unrelated", PRIVATE), (PROPERTY, "stale"),
                                         (PROPERTY, "p50"), ("other", 42)])
        request = SimpleNamespace(node=SimpleNamespace(user_properties=properties))

        class SynchronousPool:
            def __init__(pool, *, max_workers):
                calls["workers"].append(max_workers)
            def __enter__(pool):
                return pool
            def __exit__(pool, *_):
                return False
            def map(pool, function, indices):
                indices = list(indices)
                calls["indices"].append(indices)
                return map(function, indices)

        def post(route, *, content, headers):
            calls["posts"].append((route, content, headers))
            if workload_error is not None:
                raise workload_error
            return SimpleNamespace(status_code=post_status)

        def get(route):
            calls["health"].append(route)
            return SimpleNamespace(status_code=health_status)

        def fake_quantiles(latencies, *, n):
            calls["quantiles"].append((list(latencies), n))
            if quantiles_error is not None:
                raise quantiles_error
            return [p50] * 99

        ticks = iter(index / 100000 for index in range(1200))
        client = SimpleNamespace(post=post, get=get)
        namespace = {"__name__": "synthetic_checkpoint_producer", "ThreadPoolExecutor": SynchronousPool,
                     "time": SimpleNamespace(perf_counter=lambda: next(ticks)), "quantiles": fake_quantiles,
                     "VECTORS": {"first": "synthetic-body-a", "second": "synthetic-body-b"},
                     "ROUTES": ["/synthetic-a", "/synthetic-b"], "JSON": {"Content-Type": "application/json"}}
        exec(self.code, namespace)
        return lambda: namespace[FUNCTION](client, request), properties, phases, calls

    def assert_properties(self, properties, phase):
        self.assertEqual(list(properties), [("unrelated", PRIVATE), ("other", 42), (PROPERTY, phase)])
        self.assertEqual(sum(name == PROPERTY for name, _ in properties), 1)

    def test_synthetic_success_preserves_unrelated_properties_and_finishes_complete(self):
        run, properties, phases, calls = self.prepare(p50=199.999)
        run()
        self.assert_properties(properties, "complete")
        self.assertEqual(phases, list(PHASES))
        self.assertEqual(calls["workers"], [100])
        self.assertEqual(calls["indices"], [list(range(600))])
        self.assertEqual(len(calls["posts"]), 600)
        self.assertEqual(calls["health"], ["/healthz"])
        self.assertEqual(len(calls["quantiles"]), 1)
        latencies, n = calls["quantiles"][0]
        self.assertEqual(n, 100)
        self.assertEqual(len(latencies), 600)
        self.assertTrue(all(value >= 0 for value in latencies))

    def test_synthetic_500_propagates_assertion_at_no_5xx_checkpoint(self):
        run, properties, phases, calls = self.prepare(post_status=500)
        with self.assertRaises(AssertionError):
            run()
        self.assert_properties(properties, "no_5xx")
        self.assertEqual(phases, ["workload", "no_5xx"])
        self.assertEqual(len(calls["posts"]), 600)
        self.assertEqual(calls["health"], [])
        self.assertEqual(calls["quantiles"], [])

    def test_synthetic_health_503_propagates_assertion_at_health_checkpoint(self):
        run, properties, phases, calls = self.prepare(health_status=503)
        with self.assertRaises(AssertionError):
            run()
        self.assert_properties(properties, "health")
        self.assertEqual(phases, ["workload", "no_5xx", "health"])
        self.assertEqual(calls["health"], ["/healthz"])
        self.assertEqual(calls["quantiles"], [])

    def test_synthetic_p50_equal_200_propagates_assertion_without_complete(self):
        run, properties, phases, calls = self.prepare(p50=200)
        with self.assertRaises(AssertionError):
            run()
        self.assert_properties(properties, "p50")
        self.assertEqual(phases, list(PHASES[:-1]))
        self.assertEqual(len(calls["quantiles"]), 1)

    def test_synthetic_workload_exception_is_not_swallowed_or_relabelled(self):
        original = RuntimeError(PRIVATE)
        run, properties, phases, calls = self.prepare(workload_error=original)
        with self.assertRaises(RuntimeError) as caught:
            run()
        self.assertIs(caught.exception, original)
        self.assert_properties(properties, "workload")
        self.assertEqual(phases, ["workload"])
        self.assertEqual(len(calls["posts"]), 1)
        self.assertEqual(calls["health"], [])
        self.assertEqual(calls["quantiles"], [])

    def test_synthetic_quantiles_exception_is_not_swallowed_or_relabelled(self):
        original = RuntimeError(PRIVATE)
        run, properties, phases, calls = self.prepare(quantiles_error=original)
        with self.assertRaises(RuntimeError) as caught:
            run()
        self.assertIs(caught.exception, original)
        self.assert_properties(properties, "quantiles")
        self.assertEqual(phases, ["workload", "no_5xx", "health", "quantiles"])
        self.assertEqual(len(calls["posts"]), 600)
        self.assertEqual(len(calls["quantiles"]), 1)


if __name__ == "__main__":
    unittest.main()
