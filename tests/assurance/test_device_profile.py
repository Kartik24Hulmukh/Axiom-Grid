"""Focused local-only tests; no hardware/model qualification is performed."""
import builtins
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'collect_device_profile.py'


def load_module():
    spec = importlib.util.spec_from_file_location('device_profile_test_subject', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


profile = load_module()


class DeviceProfileTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for target in ('socket.socket', 'socket.create_connection', 'socket.getaddrinfo',
                       'subprocess.Popen', 'subprocess.run', 'subprocess.call',
                       'subprocess.check_output', 'os.system', 'os.popen',
                       'socket.gethostname', 'socket.gethostbyname',
                       'os.getlogin'):
            self.stack.enter_context(patch(target, side_effect=AssertionError('forbidden operation')))
        self.stack.enter_context(patch.object(profile.sys, 'platform', 'linux'))
        self.stack.enter_context(patch.object(profile.os, 'uname', return_value=SimpleNamespace(
            release='6.1-test', machine='aarch64'), create=True))
        self.stack.enter_context(patch.object(profile.os, 'cpu_count', return_value=8))
        self.stack.enter_context(patch.object(profile.os, 'sysconf', side_effect=ValueError('private')))
        self.read = self.stack.enter_context(patch.object(profile, '_read_meminfo', return_value=8 * 1024**3))

    def cli(self, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = profile.main(args)
        return code, out.getvalue(), err.getvalue()

    def test_import_has_no_collection_or_writes(self):
        with ExitStack() as stack:
            for target in ('builtins.open', 'io.open', 'os.open', 'os.cpu_count', 'os.uname', 'os.sysconf'):
                stack.enter_context(patch(target, side_effect=AssertionError('import side effect')))
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                load_module()
            self.assertEqual((out.getvalue(), err.getvalue()), ('', ''))

    def test_default_stdout_and_disclaimers(self):
        code, out, err = self.cli([])
        self.assertEqual((code, err), (0, ''))
        data = json.loads(out)
        self.assertEqual(data['scope'], 'device-profile-only')
        self.assertIs(data['production_qualified'], False)
        self.assertEqual(set(data['checks'].values()), {'not_tested'})
        self.assertEqual(data['logical_cpu_count']['value'], 8)
        self.assertEqual(data['host_visible_physical_memory_bytes']['value'], 8 * 1024**3)
        self.assertEqual(data['os']['machine']['value'], 'aarch64')
        self.assertEqual(data['cgroup_memory_limit_bytes']['status'], 'unknown')
        self.assertEqual(data['operator_reported'], {})
        for forbidden in ('hostname', 'username', 'token', 'ip_address'):
            self.assertNotIn(forbidden, data)

    def test_collection_has_only_allowlisted_read_and_no_identity_access(self):
        class UnameFacts:
            release = '6.1-test'
            machine = 'aarch64'

            @property
            def nodename(self):
                raise AssertionError('hostname access forbidden')

        class NoEnvironment:
            def __getattribute__(self, name):
                raise AssertionError('environment access forbidden')

        def permitted_open(path, mode, encoding):
            self.assertEqual((path, mode, encoding), ('/proc/meminfo', 'r', 'ascii'))
            return io.StringIO('MemTotal: 1024 kB\n')

        original = load_module()._read_meminfo
        with patch.object(profile, '_read_meminfo', original), patch.object(
                builtins, 'open', side_effect=permitted_open) as opened, patch.object(
                profile.os, 'uname', return_value=UnameFacts()), patch.object(
                profile.os, 'environ', NoEnvironment()), patch.object(
                profile.os, 'scandir', side_effect=AssertionError('enumeration forbidden')), patch.object(
                profile.os, 'listdir', side_effect=AssertionError('enumeration forbidden')):
            data = profile.collect_profile()
        self.assertEqual(opened.call_count, 1)
        self.assertEqual(data['host_visible_physical_memory_bytes']['value'], 1048576)

    def test_operator_fields_are_exact_and_unverified(self):
        code, out, _ = self.cli(['--model-name', 'Exact-Model/v1', '--backend-version', 'v0.2+abc'])
        self.assertEqual(code, 0)
        reported = json.loads(out)['operator_reported']
        self.assertEqual(reported['model_name']['value'], 'Exact-Model/v1')
        self.assertEqual(reported['backend_version']['value'], 'v0.2+abc')
        self.assertTrue(all(v['provenance'] == 'operator-reported, not verified' for v in reported.values()))

    def test_invalid_config_is_sanitized(self):
        for args in (['--unknown=SECRET'], ['--model-name'], ['--model-name', ''],
                     ['--model-name', ' padded'], ['--model-name', 'line\nSECRET'],
                     ['--backend-version', 'x\x00secret'], ['--model-name', 'x' * 257],
                     ['--model-name', 'one', '--model-name=two'], ['--out', 'private'],
                     ['--output', '']):
            with self.subTest(args=args):
                code, out, err = self.cli(args)
                self.assertEqual((code, out, err), (2, '', 'device-profile: invalid configuration\n'))
        with self.assertRaises(ValueError):
            profile.collect_profile(model_name=42)

    def test_exclusive_output_missing_parent_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / 'report.json'
            self.assertEqual(self.cli(['--output', str(dest)]), (0, '', ''))
            original = dest.read_bytes()
            self.assertEqual(json.loads(original)['scope'], 'device-profile-only')
            self.assertEqual(self.cli(['--output', str(dest)]), (1, '', 'device-profile: output unavailable\n'))
            self.assertEqual(dest.read_bytes(), original)
            missing = Path(directory) / 'absent' / 'report.json'
            self.assertEqual(self.cli(['--output', str(missing)])[0], 1)
            self.assertFalse(missing.parent.exists())
            link = Path(directory) / 'link'
            link.symlink_to(dest)
            self.assertEqual(self.cli(['--output', str(link)])[0], 1)
            self.assertEqual(dest.read_bytes(), original)

    def test_operator_validation_boundaries(self):
        for name in ('model name', 'model\tname', 'é', 'x' * 257, '', 'x\x7f'):
            with self.subTest(name=name):
                self.assertEqual(self.cli(['--model-name', name])[0], 2)
        for version in ('padded ', 'two\nlines', 'x\u2028y', 'x' * 257, ''):
            with self.subTest(version=version):
                self.assertEqual(self.cli(['--backend-version', version])[0], 2)
        self.assertEqual(self.cli(['--model-name', 'x' * 256])[0], 0)
        self.assertEqual(self.cli(['--backend-version', 'build é 2'])[0], 0)

    def test_bounded_argument_iteration_before_collection(self):
        count = 0

        def endless():
            nonlocal count
            while True:
                count += 1
                if count > 17:
                    raise AssertionError('iteration was not bounded')
                yield '--help'

        with patch.object(profile, 'collect_profile', side_effect=AssertionError('must not collect')):
            self.assertEqual(self.cli(endless()), (2, '', 'device-profile: invalid configuration\n'))
        self.assertEqual(count, 17)
        for args in ([None], [12], ['x' * 1025], ['é' * 513], ['\ud800'],
                     ['x' * 1024] * 5, '--help', b'--help', 42):
            with self.subTest(kind=type(args).__name__):
                self.assertEqual(self.cli(args), (2, '', 'device-profile: invalid configuration\n'))
        self.assertEqual(len(profile._bounded_args(['x' * 1024] * 4)), 4)
        self.assertEqual(len(profile._bounded_args(['é' * 512])), 1)
        self.assertEqual(len(profile._bounded_args(['x'] * 16)), 16)

        def fails():
            raise RuntimeError('private details')
            yield

        self.assertEqual(self.cli(fails()), (2, '', 'device-profile: invalid configuration\n'))

    def test_invalid_token_stops_iterator_immediately(self):
        def tokens():
            yield 'x' * 1025
            raise AssertionError('must stop after oversized token')

        self.assertEqual(self.cli(tokens()), (2, '', 'device-profile: invalid configuration\n'))

    def test_publication_failures_leave_no_destination_or_temporary(self):
        real_fdopen = os.fdopen
        real_mkstemp = profile.tempfile.mkstemp
        real_link = os.link
        for failure in ('fdopen', 'write', 'short_write', 'flush', 'close', 'link', 'unsupported_link'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / 'report.json'
                descriptors = []
                closed = []

                def mkstemp(*args, **kwargs):
                    fd, name = real_mkstemp(*args, **kwargs)
                    descriptors.append(fd)
                    return fd, name

                def fdopen(fd, *args, **kwargs):
                    if failure == 'fdopen':
                        raise OSError('private descriptor details')
                    stream = real_fdopen(fd, *args, closefd=(failure != 'close'), **kwargs)

                    class FailingStream:
                        def write(self, payload):
                            self.assert_not_published()
                            if failure in ('write', 'short_write'):
                                stream.write(payload[:10])
                                if failure == 'write':
                                    raise OSError('private write details')
                                return 10
                            return stream.write(payload)

                        def assert_not_published(self):
                            if destination.exists():
                                raise AssertionError('published before complete close')

                        def flush(self):
                            self.assert_not_published()
                            if failure == 'flush':
                                raise OSError('private flush details')
                            stream.flush()

                        def close(self):
                            self.assert_not_published()
                            if failure == 'close':
                                # Keep the raw fd open to exercise fallback cleanup.
                                stream.close()
                                raise OSError('private close details')
                            stream.close()
                            closed.append(True)

                    return FailingStream()

                def link(source, target):
                    self.assertTrue(closed)
                    self.assertFalse(destination.exists())
                    json.loads(Path(source).read_text())
                    if failure == 'link':
                        raise OSError('private filesystem details')
                    if failure == 'unsupported_link':
                        raise NotImplementedError('private filesystem details')
                    real_link(source, target)

                with patch.object(profile.tempfile, 'mkstemp', side_effect=mkstemp), patch.object(
                        profile.os, 'fdopen', side_effect=fdopen), patch.object(profile.os, 'link', side_effect=link):
                    self.assertEqual(self.cli(['--output', str(destination)]),
                                     (1, '', 'device-profile: output unavailable\n'))
                self.assertEqual(list(Path(directory).iterdir()), [])
                for fd in descriptors:
                    with self.assertRaises(OSError):
                        os.fstat(fd)

    def test_complete_report_is_closed_before_exclusive_link(self):
        real_link = os.link
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'report.json'

            def inspect_link(source, target):
                self.assertFalse(destination.exists())
                data = json.loads(Path(source).read_text())
                self.assertEqual(data['scope'], 'device-profile-only')
                self.assertEqual(Path(source).stat().st_mode & 0o777, 0o600)
                real_link(source, target)

            with patch.object(profile.os, 'link', side_effect=inspect_link):
                self.assertEqual(self.cli(['--output', str(destination)]), (0, '', ''))
            self.assertEqual(list(Path(directory).iterdir()), [destination])

    def test_dangling_symlink_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'report.json'
            target = Path(directory) / 'absent'
            destination.symlink_to(target)
            self.assertEqual(self.cli(['--output', str(destination)]),
                             (1, '', 'device-profile: output unavailable\n'))
            self.assertTrue(destination.is_symlink())
            self.assertEqual(destination.readlink(), target)
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(directory).iterdir()), [destination])

    def test_racing_destination_creation_never_overwrites(self):
        real_link = os.link
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'report.json'

            def competing_link(source, target):
                destination.write_text('other writer')
                real_link(source, target)

            with patch.object(profile.os, 'link', side_effect=competing_link):
                self.assertEqual(self.cli(['--output', str(destination)]),
                                 (1, '', 'device-profile: output unavailable\n'))
            self.assertEqual(destination.read_text(), 'other writer')
            self.assertEqual(list(Path(directory).iterdir()), [destination])

    def test_unlink_failure_reports_error_but_preserves_complete_publication(self):
        real_unlink = os.unlink
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'report.json'
            with patch.object(profile.os, 'unlink', side_effect=OSError('private cleanup details')):
                self.assertEqual(self.cli(['--output', str(destination)]),
                                 (1, '', 'device-profile: output unavailable\n'))
            self.assertEqual(json.loads(destination.read_text())['scope'], 'device-profile-only')
            leftovers = [p for p in Path(directory).iterdir() if p != destination]
            self.assertEqual(len(leftovers), 1)
            self.assertTrue(leftovers[0].name.startswith('.device-profile-'))
            self.assertEqual(leftovers[0].stat().st_mode & 0o777, 0o600)
            real_unlink(leftovers[0])

    def test_cpu_unknown_for_invalid_measurements(self):
        for value in (None, True, -1, 0, 1.5, float('nan'), float('inf'), '8', 2**64):
            with self.subTest(value=value), patch.object(profile.os, 'cpu_count', return_value=value):
                self.assertEqual(profile.collect_profile()['logical_cpu_count']['status'], 'unknown')

    def test_meminfo_parser_and_no_unbounded_read(self):
        cases = [('MemTotal: 1024 kB\n', 1048576), ('MemTotal: 0 kB', None),
                 ('MemTotal: -1 kB', None), ('MemTotal: 1 MB', None),
                 ('MemTotal: NaN kB', None), ('MemTotal: 1.2 kB', None),
                 ('MemTotal: ١ kB', None), ('MemTotal: 1 kB extra', None),
                 ('MemTotal: 1 kB\nMemTotal: 2 kB', None), ('unrelated', None),
                 ('MemTotal: 9999999999999999999 kB', None), ('x' * 16385, None)]
        for text, expected in cases:
            with self.subTest(text=text[:40]):
                stream = io.StringIO(text)
                with patch.object(builtins, 'open', return_value=stream) as opened:
                    # Exercise original parser, not the collection fixture.
                    actual = self.read_original()
                    self.assertEqual(actual, expected)
                    opened.assert_called_once_with('/proc/meminfo', 'r', encoding='ascii')

    @staticmethod
    def read_original():
        return load_module()._read_meminfo()

    def test_sysconf_fallback_validates_both_operands(self):
        self.read.return_value = None
        with patch.object(profile.os, 'sysconf', side_effect=[2048, 4096]):
            fact = profile.collect_profile()['host_visible_physical_memory_bytes']
            self.assertEqual(fact['value'], 8388608)
            self.assertTrue(fact['source'].startswith('sysconf'))
        for values in ((True, 4096), (-1, -1), (0, 4096), (1.5, 4096), (2**62, 4096)):
            with self.subTest(values=values), patch.object(profile.os, 'sysconf', side_effect=values):
                self.assertEqual(profile.collect_profile()['host_visible_physical_memory_bytes']['status'], 'unknown')

    def test_unavailable_memory_and_os_data(self):
        for error in (OSError('private path'), UnicodeError('private'), ValueError('private')):
            self.read.side_effect = error
            self.assertEqual(profile.collect_profile()['host_visible_physical_memory_bytes']['status'], 'unknown')
        with patch.object(profile.os, 'uname', return_value=SimpleNamespace(release='', machine='bad\nvalue')):
            facts = profile.collect_profile()['os']
            self.assertEqual(facts['release']['status'], 'unknown')
            self.assertEqual(facts['machine']['status'], 'unknown')
        with patch.object(profile.sys, 'platform', 'unsupported'), patch.object(
                profile.os, 'uname', side_effect=AssertionError('must not query unknown OS')):
            data = profile.collect_profile()
            self.assertEqual(data['os']['family']['status'], 'unknown')
            self.assertEqual(data['host_visible_physical_memory_bytes']['status'], 'unknown')

    def test_other_platform_memory_is_explicitly_unknown(self):
        for platform in ('darwin', 'win32'):
            with self.subTest(platform=platform), patch.object(profile.sys, 'platform', platform):
                self.assertEqual(profile.collect_profile()['host_visible_physical_memory_bytes']['reason'], 'unsupported_platform')


if __name__ == '__main__':
    unittest.main()
