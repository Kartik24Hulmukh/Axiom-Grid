"""Contract tests for a sanitized, diagnostic-only service JUnit summary."""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/summarize_service_junit.py"
PUBLIC_TOKEN = "SYNTHETIC_PUBLIC_FIXTURE_TOKEN"


def load_summary_module():
    spec = importlib.util.spec_from_file_location("service_junit_summary_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ServiceJunitSummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = load_summary_module()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.report = self.root / "report.xml"

    def write_xml(self, xml):
        self.report.write_bytes(xml.encode("utf-8") if isinstance(xml, str) else xml)
        return self.report

    def summarize_xml(self, xml):
        return self.summary.summarize(self.write_xml(xml))

    def assert_available(self, result, tests=0, failures=0, errors=0, skipped=0):
        self.assertEqual(result["scope"], "diagnostic-only")
        self.assertIs(result["production_qualified"], False)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["counts"], {
            "tests": tests, "failures": failures, "errors": errors, "skipped": skipped,
        })

    def assert_unavailable(self, result, *forbidden):
        self.assertEqual(result["scope"], "diagnostic-only")
        self.assertIs(result["production_qualified"], False)
        self.assertEqual(result["status"], "unavailable")
        self.assertIsInstance(result.get("reason"), str)
        self.assertTrue(result["reason"])
        encoded = json.dumps(result) + self.summary.render(result)
        for token in (PUBLIC_TOKEN, str(self.report), *forbidden):
            self.assertNotIn(token, encoded)

    def invoke_main(self, argv, env=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env or {}, clear=True), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = self.summary.main(argv)
        self.assertEqual(code, 0)
        return stdout.getvalue() + stderr.getvalue()

    def test_counts_actual_cases_not_suite_attributes(self):
        result = self.summarize_xml('''<testsuites tests="999" failures="998" errors="997" skipped="996">
          <testsuite tests="888"><testcase classname="svc.api" name="test_ok"/>
          <testcase classname="svc.api" name="test_bad"><failure/></testcase>
          <testsuite><testcase classname="svc.api" name="test_error"><error/></testcase>
          <testcase classname="svc.api" name="test_skip"><skipped/></testcase></testsuite>
          </testsuite></testsuites>''')
        self.assert_available(result, tests=4, failures=1, errors=1, skipped=1)
        self.assertEqual(result["failed_tests"], ["svc.api::test_bad", "svc.api::test_error"])
        self.assertEqual(result["omitted_failures"], 0)

    def test_empty_supported_roots(self):
        for root in ("testsuite", "testsuites"):
            with self.subTest(root=root):
                result = self.summarize_xml(f"<{root}/>")
                self.assert_available(result)
                self.assertEqual(result["failed_tests"], [])
                self.assertEqual(result["omitted_failures"], 0)

    def test_accepts_string_path(self):
        self.write_xml("<testsuite><testcase/></testsuite>")
        self.assert_available(self.summary.summarize(str(self.report)), tests=1)

    def test_failure_list_is_bounded_with_explicit_omissions(self):
        cases = ''.join(f'<testcase classname="svc.api" name="test_case_{i}"><failure/></testcase>'
                        for i in range(21))
        result = self.summarize_xml(f"<testsuite>{cases}</testsuite>")
        self.assert_available(result, tests=21, failures=21)
        self.assertEqual(len(result["failed_tests"]), 20)
        self.assertEqual(result["omitted_failures"], 1)
        self.assertEqual(result["failed_tests"][0], "svc.api::test_case_0")

    def test_parameter_values_and_failure_payloads_are_never_reflected(self):
        result = self.summarize_xml(f'''<testsuite name="{PUBLIC_TOKEN}">
          <properties><property name="fixture" value="{PUBLIC_TOKEN}"/></properties>
          <system-out>{PUBLIC_TOKEN}</system-out><system-err>{PUBLIC_TOKEN}</system-err>
          <testcase classname="svc.api" name="test_request[{PUBLIC_TOKEN}]" file="{PUBLIC_TOKEN}">
          <failure message="{PUBLIC_TOKEN}" type="{PUBLIC_TOKEN}">{PUBLIC_TOKEN}</failure>
          <system-out>{PUBLIC_TOKEN}</system-out></testcase></testsuite>''')
        self.assert_available(result, tests=1, failures=1)
        self.assertEqual(result["failed_tests"], ["svc.api::test_request"])
        self.assertNotIn(PUBLIC_TOKEN, json.dumps(result) + self.summary.render(result))

    def test_invalid_identities_are_replaced_wholesale(self):
        identities = [
            ("svc/path", "test_ok"), ("svc..api", "test_ok"),
            ("svc.9api", "test_ok"), ("svc.api", "not_a_test"),
            ("svc.api", "test_bad-name"), ("svc.api", "test_é"),
            ("své.api", "test_ok"), ("a" * 201, "test_ok"),
            ("svc.api", "test_" + "a" * 124),
            ("", "test_ok"), ("svc.api", ""),
            (f"{PUBLIC_TOKEN}&#10;::error::injected", "test_ok"),
            ("svc.api", f"test_ok&#10;::warning::{PUBLIC_TOKEN}"),
        ]
        for classname, name in identities:
            with self.subTest(classname=classname, name=name):
                result = self.summarize_xml(
                    f'<testsuite><testcase classname="{classname}" name="{name}"><error/></testcase></testsuite>')
                self.assert_available(result, tests=1, errors=1)
                self.assertEqual(result["failed_tests"], ["[test identity unavailable]"])
                self.assertNotIn(PUBLIC_TOKEN, self.summary.render(result))

    def test_identity_length_boundaries_are_accepted(self):
        classname, name = "a" * 200, "test_" + "a" * 123
        result = self.summarize_xml(
            f'<testsuite><testcase classname="{classname}" name="{name}[{PUBLIC_TOKEN}]"><failure/></testcase></testsuite>')
        self.assertEqual(result["failed_tests"], [f"{classname}::{name}"])

    def test_conflicting_or_duplicate_outcomes_are_unavailable(self):
        for outcomes in ("<failure/><failure/>", "<error/><error/>", "<failure/><error/>",
                         "<failure/><skipped/>", "<error/><skipped/>"):
            with self.subTest(outcomes=outcomes):
                self.assert_unavailable(self.summarize_xml(
                    f'<testsuite><testcase name="{PUBLIC_TOKEN}">{outcomes}</testcase></testsuite>'))

    def test_malformed_non_utf8_and_wrong_roots_are_unavailable(self):
        fixtures = [f"<{PUBLIC_TOKEN}>", f"<{PUBLIC_TOKEN}/>", "", "<testsuite>",
                    b'<testsuite>\xff</testsuite>',
                    '<testsuite/>'.encode('utf-16-le'),
                    '<testsuite/>'.encode('utf-16-be'),
                    '<testsuite/>'.encode('utf-16'),
                    '<testsuite><testcase></testsuite>',
                    f'<testsuite bad="{PUBLIC_TOKEN}" bad="duplicate"/>']
        for xml in fixtures:
            with self.subTest(xml=xml):
                self.assert_unavailable(self.summarize_xml(xml))

    def test_dtd_and_entities_are_rejected(self):
        fixtures = [
            '<!DOCTYPE testsuite><testsuite/>',
            f'<!DOCTYPE testsuite [<!ENTITY token "{PUBLIC_TOKEN}">]><testsuite>&token;</testsuite>',
            f'<!DOCTYPE testsuite SYSTEM "file:///{PUBLIC_TOKEN}"><testsuite/>',
            '<!ENTITY token "text"><testsuite/>',
        ]
        for xml in fixtures:
            with self.subTest(xml=xml):
                self.assert_unavailable(self.summarize_xml(xml))

    def test_file_byte_limit_inclusive(self):
        limit = 4 * 1024 * 1024
        prefix, suffix = b"<testsuite><!--", b"--></testsuite>"
        exact = prefix + b"x" * (limit - len(prefix) - len(suffix)) + suffix
        self.assert_available(self.summarize_xml(exact))
        self.assert_unavailable(self.summarize_xml(exact + b" "))

    def test_read_limit_still_applies_if_file_outgrows_reported_size(self):
        self.write_xml(b"<testsuite>" + b" " * (4 * 1024 * 1024) + b"</testsuite>")
        original_fstat = os.fstat

        def stale_size(fd):
            fields = list(original_fstat(fd))
            fields[6] = 0  # A stale initial size must not permit unbounded reads.
            return os.stat_result(fields)

        with mock.patch.object(os, "fstat", side_effect=stale_size):
            self.assert_unavailable(self.summary.summarize(self.report))

    def test_open_exception_details_are_not_reflected(self):
        with mock.patch.object(os, "open", side_effect=OSError(PUBLIC_TOKEN)):
            self.assert_unavailable(self.summary.summarize(self.report))

    def test_case_count_limit_inclusive(self):
        cases = "<testcase/>" * 20000
        self.assert_available(self.summarize_xml(f"<testsuite>{cases}</testsuite>"), tests=20000)
        self.assert_unavailable(self.summarize_xml(f"<testsuite>{cases}<testcase/></testsuite>"))

    def test_missing_file_and_directory_are_unavailable(self):
        missing = self.root / PUBLIC_TOKEN
        self.assert_unavailable(self.summary.summarize(missing), str(missing))
        self.assert_unavailable(self.summary.summarize(self.root), str(self.root))

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "requires no-follow file opening")
    def test_symlink_is_rejected(self):
        self.write_xml("<testsuite/>")
        link = self.root / PUBLIC_TOKEN
        link.symlink_to(self.report)
        self.assert_unavailable(self.summary.summarize(link), str(link))

    @unittest.skipUnless(hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"), "requires POSIX FIFO")
    def test_fifo_is_rejected_without_reading(self):
        fifo = self.root / PUBLIC_TOKEN
        os.mkfifo(fifo)
        # Guard regression against a blocking FIFO open without creating a hanging test.
        original_open = os.open

        def checked_open(path, flags, *args, **kwargs):
            self.assertTrue(flags & os.O_NONBLOCK, "FIFO must be opened nonblocking")
            return original_open(path, flags, *args, **kwargs)

        with mock.patch.object(os, "open", side_effect=checked_open):
            self.assert_unavailable(self.summary.summarize(fifo), str(fifo))

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_NONBLOCK"), "requires POSIX flags")
    def test_regular_file_open_is_nofollow_and_nonblocking(self):
        self.write_xml("<testsuite/>")
        original_open, original_fstat = os.open, os.fstat
        with mock.patch.object(os, "open", wraps=original_open) as opened, \
                mock.patch.object(os, "fstat", wraps=original_fstat) as inspected:
            self.assert_available(self.summary.summarize(self.report))
        self.assertTrue(opened.called)
        flags = opened.call_args.args[1]
        self.assertTrue(flags & os.O_NOFOLLOW)
        self.assertTrue(flags & os.O_NONBLOCK)
        self.assertTrue(inspected.called)

    def test_render_contains_counts_safe_labels_and_no_success_verdict(self):
        result = self.summarize_xml('''<testsuite><testcase classname="svc.api" name="test_bad"><failure/></testcase>
            <testcase/><testcase><skipped/></testcase></testsuite>''')
        rendered = self.summary.render(result)
        self.assertIsInstance(rendered, str)
        for token in ("3", "1", "0", "svc.api::test_bad"):
            self.assertIn(token, rendered)
        self.assertNotIn("pass", rendered.lower())
        self.assertNotIn("ready", rendered.lower())
        self.assertNotIn(str(self.report), rendered)

    def test_main_no_implicit_summary_write(self):
        self.write_xml("<testsuite/>")
        with mock.patch.object(Path, "write_text", side_effect=AssertionError("unexpected write")), \
                mock.patch.object(Path, "open", side_effect=AssertionError("unexpected Path.open")):
            output = self.invoke_main([str(self.report)])
        self.assertIn("diagnostic", output.lower())
        self.assertNotIn(str(self.report), output)

    def test_main_explicit_summary_appends_rendered_result(self):
        self.write_xml('<testsuite><testcase classname="svc.api" name="test_bad"><failure/></testcase></testsuite>')
        destination = self.root / "summary.md"
        destination.write_text("existing summary\n", encoding="utf-8")
        expected = self.summary.render(self.summary.summarize(self.report))
        output = self.invoke_main([str(self.report)], {"GITHUB_STEP_SUMMARY": str(destination)})
        saved = destination.read_text(encoding="utf-8")
        self.assertTrue(saved.startswith("existing summary\n"))
        self.assertIn(expected, saved)
        self.assertIn("diagnostic", output.lower())
        self.assertNotIn(str(self.report), output + saved)
        self.assertNotIn(str(destination), output + saved)

    def test_main_adversarial_payloads_do_not_reach_notices_or_summary(self):
        self.write_xml(f'''<testsuite><testcase classname="svc.api"
            name="test_request[{PUBLIC_TOKEN}&#10;::error::injected]">
            <failure message="{PUBLIC_TOKEN}">::error::{PUBLIC_TOKEN}</failure>
            <system-out>{PUBLIC_TOKEN}</system-out></testcase></testsuite>''')
        destination = self.root / "summary.md"
        output = self.invoke_main([str(self.report)], {"GITHUB_STEP_SUMMARY": str(destination)})
        combined = output + destination.read_text(encoding="utf-8")
        self.assertIn("svc.api::test_request", combined)
        for forbidden in (PUBLIC_TOKEN, "::error::", str(self.report), str(destination)):
            self.assertNotIn(forbidden, combined)

    def test_main_invalid_arity_is_sanitized_and_nonfatal(self):
        destination = self.root / "summary.md"
        for argv in ([], [PUBLIC_TOKEN, "extra"], [PUBLIC_TOKEN, "extra", "another"]):
            with self.subTest(argv=argv):
                output = self.invoke_main(argv, {"GITHUB_STEP_SUMMARY": str(destination)})
                self.assertNotIn(PUBLIC_TOKEN, output)
                self.assertIn("diagnostic", output.lower())

    def test_main_missing_report_and_summary_write_failure_are_sanitized(self):
        missing = self.root / PUBLIC_TOKEN
        output = self.invoke_main([str(missing)], {"GITHUB_STEP_SUMMARY": str(self.root / PUBLIC_TOKEN / "summary")})
        self.assertNotIn(PUBLIC_TOKEN, output)
        self.assertNotIn(str(self.root), output)
        self.assertNotIn("Traceback", output)
        self.write_xml("<testsuite/>")
        output = self.invoke_main([str(self.report)], {"GITHUB_STEP_SUMMARY": str(self.root)})
        self.assertNotIn(str(self.root), output)
        self.assertNotIn("Traceback", output)

    def test_main_empty_summary_environment_does_not_write(self):
        self.write_xml("<testsuite/>")
        with mock.patch.object(Path, "open", side_effect=AssertionError("unexpected summary open")):
            self.invoke_main([str(self.report)], {"GITHUB_STEP_SUMMARY": ""})

    def test_import_has_no_effects_even_with_ci_environment_and_arguments(self):
        destination = self.root / "summary.md"
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(destination)}, clear=True), \
                mock.patch("sys.argv", [str(SCRIPT), PUBLIC_TOKEN]), \
                mock.patch.object(os, "open", side_effect=AssertionError("import opened a report")), \
                mock.patch.object(Path, "open", side_effect=AssertionError("import opened a file")), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            loaded = load_summary_module()
        self.assertTrue(callable(loaded.summarize))
        self.assertTrue(callable(loaded.render))
        self.assertTrue(callable(loaded.main))
        self.assertEqual(stdout.getvalue() + stderr.getvalue(), "")
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
