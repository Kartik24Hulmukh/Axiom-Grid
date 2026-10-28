"""Bounded, opt-in device facts; not a qualification or hardware-pass check.

No collection occurs on import. No model, environment, identity, or network
inspection is performed. Cgroup limits deliberately remain unresolved.
"""
import argparse
import json
import os
import sys
import tempfile
import unicodedata

_MAX_BYTES = 16384
_MAX_INT = (1 << 63) - 1


def _text(value):
    return (isinstance(value, str) and 0 < len(value) <= 256
            and value == value.strip()
            and not any(unicodedata.category(c).startswith('C') for c in value))


def _positive(value):
    return type(value) is int and 0 < value <= _MAX_INT


def _fact(value=None, source=None, reason='unavailable'):
    if value is None:
        return {'status': 'unknown', 'value': None, 'reason': reason}
    return {'status': 'reported', 'value': value, 'source': source}


def _read_meminfo():
    with open('/proc/meminfo', 'r', encoding='ascii') as stream:
        data = stream.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        return None
    entries = [line.split() for line in data.splitlines()
               if line.startswith('MemTotal:')]
    if len(entries) != 1:
        return None
    parts = entries[0]
    if (len(parts) != 3 or parts[2] != 'kB' or not parts[1].isascii()
            or not parts[1].isdigit() or len(parts[1]) > 19):
        return None
    value = int(parts[1]) * 1024
    return value if _positive(value) else None


def _physical_memory(family):
    if family != 'Linux':
        return _fact(reason='unsupported_platform')
    try:
        value = _read_meminfo()
        if value is not None:
            return _fact(value, '/proc/meminfo:MemTotal')
    except (OSError, UnicodeError, ValueError):
        pass
    try:
        pages = os.sysconf('SC_PHYS_PAGES')
        size = os.sysconf('SC_PAGE_SIZE')
        if _positive(pages) and _positive(size) and _positive(pages * size):
            return _fact(pages * size, 'sysconf:SC_PHYS_PAGES*SC_PAGE_SIZE')
    except (AttributeError, OSError, ValueError, OverflowError):
        pass
    return _fact(reason='unavailable_or_malformed')


def collect_profile(model_name=None, backend_version=None):
    """Collect only specified facts, never evaluate hardware/model suitability."""
    if model_name is not None and not (
            type(model_name) is str and 1 <= len(model_name) <= 256
            and all(33 <= ord(c) <= 126 for c in model_name)):
        raise ValueError('invalid operator field')
    if backend_version is not None and not (
            _text(backend_version) and backend_version.isprintable()):
        raise ValueError('invalid operator field')
    family = {'linux': 'Linux', 'darwin': 'Darwin', 'win32': 'Windows'}.get(sys.platform)
    os_facts = {'family': _fact(family, 'sys.platform'),
                'release': _fact(), 'machine': _fact()}
    # Use only release/machine members, never node/hostname. No platform helper
    # that might invoke an external command (e.g. processor detection) is used.
    if family is not None and hasattr(os, 'uname'):
        try:
            info = os.uname()
            for key in ('release', 'machine'):
                value = getattr(info, key)
                if _text(value):
                    os_facts[key] = _fact(value, 'os.uname:' + key)
        except (OSError, ValueError):
            pass
    try:
        count = os.cpu_count()
    except (OSError, ValueError):
        count = None
    report = {
        'schema_version': 1,
        'scope': 'device-profile-only',
        'production_qualified': False,
        'checks': {key: 'not_tested' for key in
                   ('readiness', 'real_model', 'native', 'offline')},
        'os': os_facts,
        'logical_cpu_count': (_fact(count, 'os.cpu_count') if _positive(count)
                              else _fact(reason='unavailable_or_malformed')),
        'host_visible_physical_memory_bytes': _physical_memory(family),
        'cgroup_memory_limit_bytes': _fact(reason='not_resolved'),
        'operator_reported': {},
        'caveats': [
            'Run intentionally only on an authorized device.',
            'OS-reported facts are not independently verified.',
            'Host-visible physical memory may not equal installed RAM or available memory.',
            'Logical CPU count may not reflect affinity, quotas, or usable capacity.',
            'Cgroup limits are unknown: membership, mounts and ancestor limits are not resolved.',
            'No hardware minimum, model compatibility, approved model, digest trust, or qualification is established.',
        ],
    }
    for key, value in (('model_name', model_name), ('backend_version', backend_version)):
        if value is not None:
            report['operator_reported'][key] = {
                'value': value, 'provenance': 'operator-reported, not verified'}
    return report


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default message can echo arbitrary arguments/secrets/paths.
        raise ValueError('invalid arguments')



def _bounded_args(argv):
    """Consume at most 17 tokens; accept at most 16/1024 bytes each/4096 total."""
    if isinstance(argv, (str, bytes)):
        raise ValueError('invalid arguments')
    result = []
    total = 0
    try:
        for index, token in enumerate(argv):
            if index >= 16 or type(token) is not str or len(token) > 1024:
                raise ValueError('invalid arguments')
            size = len(token.encode('utf-8'))
            total += size
            if size > 1024 or total > 4096:
                raise ValueError('invalid arguments')
            result.append(token)
    except Exception:
        raise ValueError('invalid arguments') from None
    return result


def _publish(payload, destination):
    """Link a fully closed private file exclusively; never replace destination.

    Requires a trusted, stable parent directory and hard-link support. No crash
    durability guarantee is made. Cleanup failure is reported, but may leave a
    private temporary file (and a complete destination if already linked).
    """
    parent = os.path.dirname(destination) or '.'
    fd, temporary = tempfile.mkstemp(prefix='.device-profile-', dir=parent)
    try:
        # Keep fd tracked until close succeeds: fdopen/flush/close can all fail.
        stream = os.fdopen(fd, 'w', encoding='utf-8')
        try:
            if stream.write(payload) != len(payload):
                raise OSError('incomplete write')
            stream.flush()
        finally:
            stream.close()
        fd = None
        try:
            os.link(temporary, destination)
        except (AttributeError, NotImplementedError):
            raise OSError('exclusive publication unavailable') from None
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                # A failed stream close/fdopen may already have closed it.
                pass
        os.unlink(temporary)


def main(argv=None):
    parser = _Parser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--model-name', help='1..256 ASCII graphic characters (no spaces); operator-reported, not verified')
    parser.add_argument('--backend-version', help='1..256 trimmed printable characters; operator-reported, not verified')
    parser.add_argument('--output', help='Publish complete JSON exclusively; existing trusted parent and hard links required')
    try:
        if argv is None:
            argv = iter(sys.argv)
            next(argv, None)
        args_list = _bounded_args(argv)
        seen = set()
        for token in args_list:
            if token.startswith('--'):
                key = token.split('=', 1)[0]
                if key in seen:
                    raise ValueError('duplicate argument')
                seen.add(key)
        args = parser.parse_args(args_list)
        if args.output is not None and (not _text(args.output) or '\x00' in args.output):
            raise ValueError('invalid output')
        report = collect_profile(args.model_name, args.backend_version)
        payload = json.dumps(report, ensure_ascii=True, allow_nan=False, indent=2) + '\n'
        if args.output is None:
            sys.stdout.write(payload)
        else:
            _publish(payload, args.output)
        return 0
    except (ValueError, TypeError):
        sys.stderr.write('device-profile: invalid configuration\n')
        return 2
    except (OSError, UnicodeError):
        sys.stderr.write('device-profile: output unavailable\n')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
