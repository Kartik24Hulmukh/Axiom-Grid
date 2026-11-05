"""Package an unsigned development runtime ZIP; never install or execute inputs.

All input and output parent directories must be trusted and stable for the whole
operation. O_NOFOLLOW protects leaf opens where available, not parent traversal.
On platforms without O_NOFOLLOW (notably Windows), visible symlinks/junctions are
rejected and identity is checked, but this is NOT race-proof against hostile
concurrent replacement. Use an isolated, trusted staging directory there.
Binary checks establish header format/architecture only, not code safety,
provenance, compatibility, complete executable validity, or licensing approval.
VSIX checks validate bounded packaging/metadata only, not JavaScript behavior.
ZIP DEFLATE output is deterministic within the same Python/zlib environment;
record that environment separately. Cross-zlib bit reproducibility is not promised.
"""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import struct
import tempfile
import xml.etree.ElementTree as ET
import zipfile


RUNTIME_LIMIT = 64 * 1024 * 1024
VSIX_LIMIT = 1024 * 1024
EXPANDED_LIMIT = 256 * 1024
TEXT_LIMIT = 256 * 1024
TARGETS = (
    'x86_64-unknown-linux-gnu',
    'x86_64-pc-windows-msvc',
    'x86_64-apple-darwin',
    'aarch64-apple-darwin',
)
VSIX_ENTRIES = frozenset({
    '[Content_Types].xml', 'extension.vsixmanifest',
    'extension/package.json', 'extension/extension.js', 'extension/state.js',
    'extension/comment.js', 'extension/client.js', 'extension/README.md',
    'extension/LICENSE',
})
IDENTITY = ('axiom-grid-lite', 'axiom-grid-local', '0.1.3')
FIXED_DATE = (1980, 1, 1, 0, 0, 0)
ERROR = 'Development bundle packaging failed; verify trusted inputs and staging directories.'


class BundleError(ValueError):
    """Static, non-sensitive packaging failure."""


def _reject():
    raise BundleError(ERROR)


def _read_regular(path, limit):
    """Bounded descriptor-owned read; never follow a visible leaf link."""
    path = os.fspath(path)
    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode):
        _reject()
    isjunction = getattr(os.path, 'isjunction', None)
    if isjunction is not None and isjunction(path):
        _reject()
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0)
    flags |= getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        if (not stat.S_ISREG(opened.st_mode) or opened.st_size > limit
                or opened.st_size < 0
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
            _reject()
        # Keep descriptor ownership here: no fdopen failure can leak this fd.
        chunks = []
        size = 0
        while size <= limit:
            chunk = os.read(fd, min(64 * 1024, limit + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        after = os.fstat(fd)
        if (size > limit or size != opened.st_size
                or (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                != (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)):
            _reject()
        return b''.join(chunks)
    finally:
        os.close(fd)


def _validate_runtime(data, target):
    if target == 'x86_64-unknown-linux-gnu':
        # ELF64, little endian, current ident version, EM_X86_64.
        if (len(data) < 64 or data[:4] != b'\x7fELF'
                or data[4:7] != b'\x02\x01\x01'
                or struct.unpack_from('<H', data, 16)[0] not in (2, 3)
                or struct.unpack_from('<H', data, 18)[0] != 62
                or struct.unpack_from('<I', data, 20)[0] != 1
                or struct.unpack_from('<H', data, 52)[0] != 64):
            _reject()
    elif target == 'x86_64-pc-windows-msvc':
        if len(data) < 64 or data[:2] != b'MZ':
            _reject()
        offset = struct.unpack_from('<I', data, 60)[0]
        if (offset < 64 or offset > len(data) - 24
                or data[offset:offset + 4] != b'PE\0\0'
                or struct.unpack_from('<H', data, offset + 4)[0] != 0x8664):
            _reject()
        optional_size, characteristics = struct.unpack_from('<HH', data, offset + 20)
        if (not characteristics & 0x0002 or characteristics & 0x2000
                or optional_size < 112
                or optional_size > len(data) - (offset + 24)
                or struct.unpack_from('<H', data, offset + 24)[0] != 0x020B):
            _reject()
    else:
        endian = {b'\xcf\xfa\xed\xfe': '<', b'\xfe\xed\xfa\xcf': '>'}.get(data[:4])
        cpu = 0x01000007 if target == 'x86_64-apple-darwin' else 0x0100000C
        if (len(data) < 32 or endian is None
                or struct.unpack_from(endian + 'I', data, 4)[0] != cpu
                or struct.unpack_from(endian + 'I', data, 12)[0] != 2):
            _reject()
        ncmds, sizeofcmds = struct.unpack_from(endian + 'II', data, 16)
        if sizeofcmds > len(data) - 32 or ncmds > sizeofcmds // 8:
            _reject()


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _reject()
        result[key] = value
    return result


def _xml(data):
    # Reject DTD/entity declarations, including UTF-16/32 encodings, before ET.
    normalized = data.replace(b'\0', b'').upper()
    if b'<!DOCTYPE' in normalized or b'<!ENTITY' in normalized:
        _reject()
    return ET.fromstring(data)


def _validate_vsix(data):
    payloads = {}
    with zipfile.ZipFile(io.BytesIO(data), 'r') as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if len(infos) != 9 or len(set(names)) != 9 or set(names) != VSIX_ENTRIES:
            _reject()
        total = 0
        for info in infos:
            mode = info.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if (info.is_dir() or info.flag_bits & 1
                    or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                    or kind not in (0, stat.S_IFREG)
                    or info.file_size < 0 or info.file_size > EXPANDED_LIMIT - total):
                _reject()
            # Read the actual expansion, not just attacker-supplied size fields.
            with archive.open(info, 'r') as member:
                content = member.read(EXPANDED_LIMIT - total + 1)
                if len(content) > EXPANDED_LIMIT - total or member.read(1):
                    _reject()
            if len(content) != info.file_size:
                _reject()
            total += len(content)
            payloads[info.filename] = content
    manifest = json.loads(payloads['extension/package.json'].decode('utf-8'),
                          object_pairs_hook=_json_object)
    if not isinstance(manifest, dict):
        _reject()
    identity = tuple(manifest.get(key) for key in ('name', 'publisher', 'version'))
    if identity != IDENTITY:
        _reject()
    # Fixed safe identity also prevents metadata-derived archive path injection.
    ns = '{http://schemas.microsoft.com/developer/vsx-schema/2011}'
    package = _xml(payloads['extension.vsixmanifest'])
    identities = package.findall(ns + 'Metadata/' + ns + 'Identity')
    if (package.tag != ns + 'PackageManifest' or len(identities) != 1
            or tuple(identities[0].get(key) for key in ('Id', 'Publisher', 'Version')) != identity):
        _reject()
    types = _xml(payloads['[Content_Types].xml'])
    if types.tag != '{http://schemas.openxmlformats.org/package/2006/content-types}Types':
        _reject()
    return identity[2]


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + '\n').encode('ascii')


def _build_bundle(runtime_path, vsix_path, *, target, revision):
    if (not isinstance(target, str) or target not in TARGETS
            or not isinstance(revision, str) or re.fullmatch(r'[0-9a-f]{40}', revision) is None):
        _reject()
    runtime = _read_regular(runtime_path, RUNTIME_LIMIT)
    _validate_runtime(runtime, target)
    vsix = _read_regular(vsix_path, VSIX_LIMIT)
    version = _validate_vsix(vsix)
    root = Path(__file__).resolve().parents[2]
    runtime_name = 'axiom-grid.exe' if target == 'x86_64-pc-windows-msvc' else 'axiom-grid'
    files = {
        runtime_name: runtime,
        'axiom-grid-lite-' + version + '.vsix': vsix,
        'LICENSE': _read_regular(root / 'LICENSE', TEXT_LIMIT),
        'THIRD_PARTY_NOTICES.md': _read_regular(root / 'THIRD_PARTY_NOTICES.md', TEXT_LIMIT),
        'README.txt': (
            'Axiom Grid development runtime bundle -- NOT an installer.\n'
            'Unsigned development software; production qualification is false.\n'
            'Target: ' + target + '\n'
            'Binary headers identify format/architecture only; compatibility and safety are untested.\n'
            'Revision is operator-supplied, not attested. Hashes are not publisher authentication.\n'
            'Requires an authorized device, desktop VS Code 1.96+ and a trusted local file.\n'
            'Requires an existing compatible local Ollama backend at 127.0.0.1:11434,\n'
            'an approved installed model, and independently approved expected model digest.\n'
            'Configure AXIOM_MODEL and AXIOM_MODEL_DIGEST through your approved local process.\n'
            'Provision private runtime IPC pairing; never use a GitHub token or share secrets.\n'
            'Runtime endpoint: 127.0.0.1:7437. Windows protected pairing needs separate provisioning.\n'
            'Install the VSIX through VS Code; pair via Axiom: Set Runtime Token.\n'
            'Ctrl+Alt+K explicitly requests a preview; review and explicitly accept in the editor.\n'
            'Nothing here installs prerequisites, downloads weights, configures tokens, or starts services.\n'
            'No full-setup, host-test, real-model, offline/zero-egress, or license-review guarantee.\n'
            'Review LICENSE and THIRD_PARTY_NOTICES.md; dependency/model review is not complete.\n'
        ).encode('utf-8'),
    }
    files['bundle.json'] = _json_bytes({
        'schema_version': 1,
        'scope': 'development-runtime-bundle',
        'production_qualified': False,
        'target': target,
        'target_validation': 'format-only',
        'revision': revision,
        'revision_provenance': 'operator-supplied-not-attested',
        'extension': {'id': IDENTITY[0], 'publisher': IDENTITY[1], 'version': version,
                      'validation': 'packaging-and-metadata-only'},
        'qualification': {'host': 'not_tested', 'model': 'not_tested',
                          'offline': 'not_tested', 'license_review': 'not_complete'},
        'files': {name: {'bytes': len(content), 'sha256': _digest(content)}
                  for name, content in sorted(files.items())},
        'hash_scope': 'all bundle entries except bundle.json; not provenance or attestation',
    })
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in sorted(files.items()):
            entry = zipfile.ZipInfo(name, FIXED_DATE)
            entry.create_system = 3
            entry.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if name == runtime_name else 0o644
            entry.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(entry, content, compresslevel=9)
    return buffer.getvalue()


def build_bundle(runtime_path, vsix_path, *, target, revision):
    """Return a deterministic bounded ZIP; validate packaging, never execute it."""
    try:
        return _build_bundle(runtime_path, vsix_path, target=target, revision=revision)
    except Exception:
        raise BundleError(ERROR) from None


def write_bundle(runtime_path, vsix_path, output_path, *, target, revision):
    """Publish only a complete ZIP using an exclusive hard link; never overwrite.

    Requires trusted stable parent directories and hard-link support. Existing
    destinations, including dangling symlinks, are refused without replacement.
    """
    temporary = None
    fd = None
    try:
        payload = build_bundle(runtime_path, vsix_path, target=target, revision=revision)
        destination = Path(output_path)
        fd, temporary = tempfile.mkstemp(prefix='.axiom-runtime-bundle-', dir=destination.parent)
        if hasattr(os, 'fchmod'):
            os.fchmod(fd, 0o644)
        # Transfer descriptor ownership only once fdopen succeeds.
        stream = os.fdopen(fd, 'wb')
        fd = None
        with stream:
            if stream.write(payload) != len(payload):
                _reject()
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, destination, follow_symlinks=False)
        return {'bytes': len(payload), 'sha256': _digest(payload)}
    except Exception:
        raise BundleError(ERROR) from None
    finally:
        try:
            try:
                if fd is not None:
                    os.close(fd)
            finally:
                if temporary is not None:
                    try:
                        os.unlink(temporary)
                    except FileNotFoundError:
                        pass
        except OSError:
            raise BundleError(ERROR) from None


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default error embeds untrusted arguments and paths.
        raise BundleError(ERROR)


def main(argv=None):
    parser = _ArgumentParser(
        prog='package_runtime_bundle',
        description='Package an unsigned development runtime ZIP, not an installer.',
        epilog='Use trusted stable staging parents; no downloads or execution occur.')
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--vsix', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--output', required=True)
    # Do not echo raw arguments/paths through argparse diagnostics.
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    except BundleError:
        print(ERROR)
        return 1
    try:
        result = write_bundle(args.runtime, args.vsix, args.output,
                              target=args.target, revision=args.revision)
    except BundleError:
        print(ERROR)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
