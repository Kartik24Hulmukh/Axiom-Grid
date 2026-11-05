"""Synthetic binary/container tests only; no runtime is executed or qualified."""
from __future__ import annotations

import builtins
import errno
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/package_runtime_bundle.py"
REVISION = "a" * 40
TARGETS = (
    "x86_64-unknown-linux-gnu",
    "x86_64-pc-windows-msvc",
    "x86_64-apple-darwin",
    "aarch64-apple-darwin",
)
SECRET = "PRIVATE_BUNDLE_INPUT_9182"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def elf(machine=62):
    # Valid ELF64 little-endian executable header, with no executable payload.
    ident = b"\x7fELF" + bytes((2, 1, 1, 0)) + bytes(8)
    return ident + struct.pack("<HHIQQQIHHHHHH", 2, machine, 1, 0, 0, 0, 0, 64, 56, 0, 64, 0, 0)


def pe(machine=0x8664):
    # DOS stub + PE signature + AMD64 COFF + minimal PE32+ optional header.
    data = bytearray(64 + 4 + 20 + 240)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 64)
    data[64:68] = b"PE\x00\x00"
    struct.pack_into("<HHIIIHH", data, 68, machine, 0, 0, 0, 0, 240, 0x22)
    struct.pack_into("<H", data, 88, 0x20B)
    return bytes(data)


def macho(cpu):
    # Thin, little-endian Mach-O64 header, no load commands or code.
    return struct.pack("<IIIIIIII", 0xFEEDFACF, cpu, 0, 2, 0, 0, 0, 0)


def binary_for(target):
    return {
        TARGETS[0]: elf(), TARGETS[1]: pe(),
        TARGETS[2]: macho(0x01000007), TARGETS[3]: macho(0x0100000C),
    }[target]


def replace_zip(payload, changes=None, *, extra=(), omit=()):
    changes = changes or {}
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(payload)) as source, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dest:
        for entry in source.infolist():
            if entry.filename not in omit:
                dest.writestr(entry, changes.get(entry.filename, source.read(entry)))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            for name, data in extra:
                dest.writestr(name, data)
    return out.getvalue()


class RuntimeBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = load_module("owned_runtime_bundle", SCRIPT)
        packager = load_module("owned_runtime_bundle_vsix_fixture", ROOT / "extensions/vscode-lite/package_vsix.py")
        cls.vsix_bytes = packager.build_bytes()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="runtime-bundle-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root / "synthetic-runtime"
        self.runtime.write_bytes(elf())
        self.vsix = self.root / "source-fixture.vsix"
        self.vsix.write_bytes(self.vsix_bytes)
        self.output = self.root / "bundle.zip"

    def build(self, *, target=TARGETS[0], revision=REVISION, runtime=None, vsix=None):
        return self.bundle.build_bundle(
            self.runtime if runtime is None else runtime,
            self.vsix if vsix is None else vsix,
            target=target, revision=revision,
        )

    def symlink_or_skip(self, path, target):
        if not hasattr(os, "symlink"):
            self.skipTest("platform has no symbolic-link creation API")
        try:
            path.symlink_to(target)
        except NotImplementedError:
            self.skipTest("filesystem symbolic links are not implemented")
        except OSError as error:
            unavailable = {errno.ENOSYS, getattr(errno, "ENOTSUP", -1), getattr(errno, "EOPNOTSUPP", -1)}
            if getattr(error, "winerror", None) == 1314:
                self.skipTest("Windows account lacks symbolic-link creation privilege")
            if error.errno in unavailable:
                self.skipTest("filesystem does not support symbolic-link creation")
            raise

    def reject(self, action):
        with self.assertRaises((ValueError, OSError)) as caught:
            action()
        self.assertIsInstance(caught.exception, self.bundle.BundleError)
        self.assertEqual(str(caught.exception), self.bundle.ERROR)
        self.assertIsNone(caught.exception.__cause__)
        self.assertNotIn(SECRET, str(caught.exception))
        self.assertNotIn(str(self.root), str(caught.exception))
        self.assertLess(len(str(caught.exception)), 240)
        return caught.exception

    def test_import_has_no_input_or_output_io(self):
        source = SCRIPT.read_text(encoding="utf-8")
        code = compile(source, str(SCRIPT), "exec")
        namespace = {"__name__": "owned_bundle_import_probe", "__file__": str(SCRIPT)}
        with mock.patch.object(builtins, "open", side_effect=AssertionError("import IO")), \
                mock.patch.object(os, "open", side_effect=AssertionError("import IO")), \
                mock.patch.object(Path, "open", side_effect=AssertionError("import IO")):
            exec(code, namespace)
        self.assertTrue(callable(namespace["build_bundle"]))
        self.assertTrue(callable(namespace["write_bundle"]))

    def test_all_four_synthetic_architectures_accept_and_are_deterministic(self):
        for target in TARGETS:
            with self.subTest(target=target):
                self.runtime.write_bytes(binary_for(target))
                first = self.build(target=target)
                self.assertIsInstance(first, bytes)
                self.assertEqual(first, self.build(target=target))
                self.assertTrue(zipfile.is_zipfile(io.BytesIO(first)))

    def test_archive_metadata_hashes_modes_and_allowlist(self):
        for target in TARGETS:
            with self.subTest(target=target):
                binary = binary_for(target)
                self.runtime.write_bytes(binary)
                payload = self.build(target=target)
                runtime_name = "axiom-grid.exe" if target == TARGETS[1] else "axiom-grid"
                vsix_name = "axiom-grid-lite-0.1.3.vsix"
                names = {runtime_name, vsix_name, "LICENSE", "THIRD_PARTY_NOTICES.md", "README.txt", "bundle.json"}
                with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                    self.assertEqual(set(archive.namelist()), names)
                    self.assertEqual(archive.namelist(), sorted(names))
                    self.assertEqual(len(archive.infolist()), len(names))
                    self.assertEqual(archive.read(runtime_name), binary)
                    self.assertEqual(archive.read(vsix_name), self.vsix_bytes)
                    metadata = json.loads(archive.read("bundle.json"))
                    self.assertEqual(metadata["schema_version"], 1)
                    self.assertEqual(metadata["scope"], "development-runtime-bundle")
                    self.assertIs(metadata["production_qualified"], False)
                    self.assertEqual(metadata["target"], target)
                    self.assertEqual(metadata["target_validation"], "format-only")
                    self.assertEqual(metadata["revision"], REVISION)
                    self.assertEqual(metadata["revision_provenance"], "operator-supplied-not-attested")
                    self.assertEqual(metadata["extension"], {"id": "axiom-grid-lite", "publisher": "axiom-grid-local",
                        "version": "0.1.3", "validation": "packaging-and-metadata-only"})
                    self.assertEqual(metadata["qualification"], {"host": "not_tested", "model": "not_tested",
                        "offline": "not_tested", "license_review": "not_complete"})
                    self.assertEqual(set(metadata["files"]), names - {"bundle.json"})
                    for entry in archive.infolist():
                        self.assertEqual(entry.date_time, (1980, 1, 1, 0, 0, 0))
                        self.assertEqual(entry.create_system, 3)
                        mode = entry.external_attr >> 16
                        self.assertTrue(stat.S_ISREG(mode))
                        self.assertEqual(stat.S_IMODE(mode), 0o755 if entry.filename == runtime_name else 0o644)
                        if entry.filename != "bundle.json":
                            content = archive.read(entry)
                            self.assertEqual(metadata["files"][entry.filename], {
                                "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})

    def test_input_timestamps_and_modes_do_not_change_output_bytes(self):
        before = self.build()
        os.utime(self.runtime, (123456789, 123456789))
        self.runtime.chmod(0o700)
        self.vsix.chmod(0o600)
        self.assertEqual(self.build(), before)

    def test_target_is_exact_not_coerced_or_trimmed(self):
        for target in (None, 1, "", "linux", "x86_64-pc-windows-gnu", TARGETS[0] + "\n", " " + TARGETS[0]):
            with self.subTest(target=target):
                self.reject(lambda: self.build(target=target))

    def test_invalid_revision_is_rejected(self):
        for revision in (None, 1, "", "a" * 39, "a" * 41, "g" * 40, " " + REVISION, REVISION + "\n", SECRET):
            with self.subTest(revision=revision):
                self.reject(lambda: self.build(revision=revision))

    def test_target_and_binary_architecture_must_agree(self):
        for actual in TARGETS:
            self.runtime.write_bytes(binary_for(actual))
            for claimed in TARGETS:
                if claimed != actual:
                    with self.subTest(actual=actual, claimed=claimed):
                        self.reject(lambda: self.build(target=claimed))

    def test_malformed_and_truncated_binary_headers_rejected(self):
        for raw in (b"", b"\x7fELF", elf()[:20], b"#! /bin/sh\n" + SECRET.encode(),
                    elf(machine=183), b"MZ", pe()[:70], macho(0x01000007)[:12]):
            self.runtime.write_bytes(raw)
            with self.subTest(raw=raw[:8]):
                self.reject(self.build)

    def test_header_class_endianness_machine_and_offsets_are_checked(self):
        linux_cases = []
        for offset, byte in ((4, 1), (5, 2), (6, 0)):
            raw = bytearray(elf()); raw[offset] = byte; linux_cases.append(bytes(raw))
        for raw in linux_cases:
            self.runtime.write_bytes(raw)
            self.reject(self.build)
        for offset in (0, 63, 0xFFFFFFFF):
            raw = bytearray(pe()); struct.pack_into("<I", raw, 60, offset)
            self.runtime.write_bytes(raw)
            self.reject(lambda: self.build(target=TARGETS[1]))
        self.runtime.write_bytes(pe(machine=0x14C))
        self.reject(lambda: self.build(target=TARGETS[1]))
        for target in TARGETS[2:]:
            for raw in (b"\xca\xfe\xba\xbe" + bytes(28), macho(7), macho(12), b"\xce\xfa\xed\xfe" + bytes(28)):
                self.runtime.write_bytes(raw)
                self.reject(lambda: self.build(target=target))

    def test_elf_executable_type_version_and_header_size(self):
        for offset, format_string, value in ((16, "<H", 0), (16, "<H", 1), (16, "<H", 4),
                                              (20, "<I", 0), (20, "<I", 2),
                                              (52, "<H", 0), (52, "<H", 63), (52, "<H", 65)):
            with self.subTest(offset=offset, value=value):
                raw = bytearray(elf()); struct.pack_into(format_string, raw, offset, value)
                self.runtime.write_bytes(raw)
                self.reject(self.build)
        shared_executable = bytearray(elf())
        struct.pack_into("<H", shared_executable, 16, 3)
        self.runtime.write_bytes(shared_executable)
        self.assertIsInstance(self.build(), bytes)

    def test_pe_requires_executable_not_dll_and_bounded_pe32plus_header(self):
        # PE offset 64; COFF optional length at 84, characteristics at 86.
        for offset, value in ((86, 0), (86, 0x20), (86, 0x2022),
                              (84, 0), (84, 111), (84, 241), (88, 0x10B), (88, 0)):
            with self.subTest(offset=offset, value=value):
                raw = bytearray(pe()); struct.pack_into("<H", raw, offset, value)
                self.runtime.write_bytes(raw)
                self.reject(lambda: self.build(target=TARGETS[1]))
        self.runtime.write_bytes(pe()[:87])
        self.reject(lambda: self.build(target=TARGETS[1]))

    def test_macho_requires_executable_and_bounded_load_command_region(self):
        for target, cpu in ((TARGETS[2], 0x01000007), (TARGETS[3], 0x0100000C)):
            for offset, value, tail in ((12, 0, b""), (12, 1, b""), (12, 6, b""),
                                        (20, 1, b""), (20, 0xFFFFFFFF, b""),
                                        (16, 1, b"")):
                with self.subTest(target=target, offset=offset, value=value):
                    raw = bytearray(macho(cpu) + tail)
                    struct.pack_into("<I", raw, offset, value)
                    self.runtime.write_bytes(raw)
                    self.reject(lambda: self.build(target=target))
            # Eight bytes cannot hold two minimum-size load commands.
            raw = bytearray(macho(cpu) + bytes(8))
            struct.pack_into("<II", raw, 16, 2, 8)
            self.runtime.write_bytes(raw)
            self.reject(lambda: self.build(target=target))
            self.runtime.write_bytes(macho(cpu)[:31])
            self.reject(lambda: self.build(target=target))

    def test_vsix_member_allowlist_rejects_duplicates_traversal_and_unknown_files(self):
        for name in ("extension/package.json", "../escape", "/absolute", "extension/../escape",
                     "extension\\evil.js", "extension/node_modules/extra.js", "extra.txt"):
            self.vsix.write_bytes(replace_zip(self.vsix_bytes, extra=[(name, b"{}")] ))
            with self.subTest(name=name):
                self.reject(self.build)
        for name in ("extension/package.json", "extension.vsixmanifest", "[Content_Types].xml", "extension/client.js"):
            self.vsix.write_bytes(replace_zip(self.vsix_bytes, omit=[name]))
            with self.subTest(omitted=name):
                self.reject(self.build)

    def test_zip_symlink_member_and_nonallowlisted_compression_rejected(self):
        for mode, compression in ((stat.S_IFLNK | 0o777, zipfile.ZIP_DEFLATED),
                                  (stat.S_IFIFO | 0o644, zipfile.ZIP_DEFLATED),
                                  (stat.S_IFREG | 0o644, zipfile.ZIP_BZIP2)):
            out = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(self.vsix_bytes)) as source, zipfile.ZipFile(out, "w") as dest:
                for original in source.infolist():
                    entry = zipfile.ZipInfo(original.filename)
                    entry.external_attr = (mode if original.filename == "extension/client.js" else stat.S_IFREG | 0o644) << 16
                    entry.compress_type = compression
                    dest.writestr(entry, source.read(original))
            self.vsix.write_bytes(out.getvalue())
            self.reject(self.build)

    def test_manifest_identity_fields_and_duplicate_json_keys_rejected(self):
        with zipfile.ZipFile(io.BytesIO(self.vsix_bytes)) as archive:
            original = json.loads(archive.read("extension/package.json"))
        for key in ("name", "publisher", "version"):
            for value in (None, 1, "", SECRET, "../escape"):
                manifest = dict(original)
                manifest[key] = value
                self.vsix.write_bytes(replace_zip(self.vsix_bytes, {"extension/package.json": json.dumps(manifest).encode()}))
                self.reject(self.build)
        raw = json.dumps(original).encode()
        raw = b'{"name":"wrong",' + raw[1:]
        self.vsix.write_bytes(replace_zip(self.vsix_bytes, {"extension/package.json": raw}))
        self.reject(self.build)

    def test_xml_identity_mismatch_and_entity_declarations_rejected(self):
        with zipfile.ZipFile(io.BytesIO(self.vsix_bytes)) as archive:
            original = archive.read("extension.vsixmanifest")
        for replacement in (original.replace(b'Version="0.1.3"', b'Version="9.9.9"'),
                            b"<wrong/>", b"<!DOCTYPE x [<!ENTITY leak '" + SECRET.encode() + b"'>]><x/>"):
            self.vsix.write_bytes(replace_zip(self.vsix_bytes, {"extension.vsixmanifest": replacement}))
            self.reject(self.build)
        self.vsix.write_bytes(replace_zip(self.vsix_bytes, {"[Content_Types].xml": b"<wrong/>"}))
        self.reject(self.build)

    def test_bounded_inputs_and_uncompressed_zip_limit_without_large_allocations(self):
        with mock.patch.object(self.bundle, "RUNTIME_LIMIT", 63):
            self.reject(self.build)
        with mock.patch.object(self.bundle, "VSIX_LIMIT", len(self.vsix_bytes) - 1):
            self.reject(self.build)
        with zipfile.ZipFile(io.BytesIO(self.vsix_bytes)) as archive:
            expanded = sum(entry.file_size for entry in archive.infolist())
        with mock.patch.object(self.bundle, "EXPANDED_LIMIT", expanded - 1):
            self.reject(self.build)
        with mock.patch.object(self.bundle, "EXPANDED_LIMIT", expanded):
            self.assertIsInstance(self.build(), bytes)
        # A genuine compressed expansion bomb, still only a few hundred KiB in RAM.
        self.vsix.write_bytes(replace_zip(self.vsix_bytes, {"extension/README.md": b"x" * (256 * 1024 + 1)}))
        self.reject(self.build)

    def test_forged_uncompressed_size_cannot_hide_malformed_zip_content(self):
        raw = bytearray(self.vsix_bytes)
        cursor = 0
        while True:
            cursor = raw.find(b"PK\x01\x02", cursor)
            self.assertGreaterEqual(cursor, 0)
            length = struct.unpack_from("<H", raw, cursor + 28)[0]
            name = bytes(raw[cursor + 46:cursor + 46 + length])
            if name == b"extension/client.js":
                struct.pack_into("<I", raw, cursor + 24, 1)
                break
            cursor += 46 + length
        self.vsix.write_bytes(raw)
        self.reject(self.build)

    def test_invalid_json_or_manifest_identity_is_rejected(self):
        for raw in (b"{", b"null", b"[]", b"{}", b"\xff", json.dumps({"name": SECRET}).encode()):
            self.vsix.write_bytes(replace_zip(self.vsix_bytes, {"extension/package.json": raw}))
            self.reject(self.build)

    def test_invalid_zip_inputs_rejected(self):
        for raw in (b"", b"not a zip " + SECRET.encode(), self.vsix_bytes[:30]):
            self.vsix.write_bytes(raw)
            self.reject(self.build)

    def test_symlink_inputs_rejected_without_following(self):
        for which in ("runtime", "vsix"):
            path = getattr(self, which)
            saved = self.root / (which + "-saved")
            path.rename(saved)
            self.symlink_or_skip(path, saved)
            with self.subTest(which=which):
                self.reject(self.build)
            path.unlink()
            saved.rename(path)

    def test_directories_are_not_regular_inputs(self):
        for which in ("runtime", "vsix"):
            kwargs = {which: self.root}
            with self.subTest(which=which):
                self.reject(lambda: self.build(**kwargs))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires FIFO support")
    def test_fifo_is_rejected_before_open_and_cannot_block(self):
        fifo = self.root / "input-fifo"
        os.mkfifo(fifo)
        real_open = os.open
        attempted_fifo = []
        def never_open_fifo(path, *args, **kwargs):
            if os.fspath(path) == str(fifo):
                attempted_fifo.append(path)
                raise AssertionError("FIFO must be refused before open")
            return real_open(path, *args, **kwargs)
        with mock.patch.object(self.bundle.os, "open", side_effect=never_open_fifo):
            self.reject(lambda: self.build(runtime=fifo))
            self.reject(lambda: self.build(vsix=fifo))
        self.assertEqual(attempted_fifo, [])

    def test_regular_input_open_flags_and_descriptor_cleanup(self):
        real_open = os.open
        opened = []
        def tracked(path, flags, *args, **kwargs):
            fd = real_open(path, flags, *args, **kwargs)
            opened.append((fd, flags))
            return fd
        with mock.patch.object(self.bundle.os, "open", side_effect=tracked):
            self.build()
        self.assertGreaterEqual(len(opened), 2)
        for fd, flags in opened:
            if hasattr(os, "O_NOFOLLOW"):
                self.assertEqual(flags & os.O_NOFOLLOW, os.O_NOFOLLOW)
            if hasattr(os, "O_NONBLOCK"):
                self.assertEqual(flags & os.O_NONBLOCK, os.O_NONBLOCK)
            with self.assertRaises(OSError):
                os.fstat(fd)
        opened.clear()
        with mock.patch.object(self.bundle.os, "open", side_effect=tracked), \
                mock.patch.object(self.bundle.os, "read", side_effect=OSError(SECRET)):
            self.reject(self.build)
        self.assertEqual(len(opened), 1)
        with self.assertRaises(OSError):
            os.fstat(opened[0][0])

    def test_stale_input_size_is_not_trusted(self):
        # Simulate input growth after fstat with a tiny actual buffer.
        chunks = iter([elf() + b"x", b""])
        with mock.patch.object(self.bundle.os, "read", side_effect=lambda *_: next(chunks)):
            self.reject(self.build)

    def test_post_open_stat_failure_still_closes_descriptor(self):
        real_open = os.open
        opened = []
        def tracked(*args, **kwargs):
            fd = real_open(*args, **kwargs); opened.append(fd); return fd
        with mock.patch.object(self.bundle.os, "open", side_effect=tracked), \
                mock.patch.object(self.bundle.os, "fstat", side_effect=OSError(SECRET)):
            self.reject(self.build)
        self.assertEqual(len(opened), 1)
        with self.assertRaises(OSError):
            os.fstat(opened[0])

    def test_output_fdopen_failure_closes_descriptor_and_removes_temporary(self):
        real_mkstemp = tempfile.mkstemp
        descriptors = []
        def tracked(*args, **kwargs):
            fd, name = real_mkstemp(*args, **kwargs)
            descriptors.append((fd, Path(name)))
            return fd, name
        with mock.patch.object(self.bundle.tempfile, "mkstemp", side_effect=tracked), \
                mock.patch.object(self.bundle.os, "fdopen", side_effect=OSError(SECRET)):
            self.reject(lambda: self.bundle.write_bundle(self.runtime, self.vsix, self.output,
                target=TARGETS[0], revision=REVISION))
        self.assertEqual(len(descriptors), 1)
        fd, name = descriptors[0]
        with self.assertRaises(OSError):
            os.fstat(fd)
        self.assertFalse(name.exists())
        self.assertFalse(self.output.exists())

    def test_publication_failure_is_sanitized_and_leaves_no_partial_or_temporary(self):
        before = set(self.root.iterdir())
        with mock.patch.object(self.bundle.os, "link", side_effect=OSError(SECRET)):
            self.reject(lambda: self.bundle.write_bundle(self.runtime, self.vsix, self.output,
                target=TARGETS[0], revision=REVISION))
        self.assertEqual(set(self.root.iterdir()), before)

    def test_write_returns_bytes_and_hash_and_never_replaces_existing_file(self):
        expected = self.build()
        result = self.bundle.write_bundle(self.runtime, self.vsix, self.output, target=TARGETS[0], revision=REVISION)
        self.assertEqual(self.output.read_bytes(), expected)
        self.assertEqual(result, {"bytes": len(expected), "sha256": hashlib.sha256(expected).hexdigest()})
        self.output.write_bytes(b"existing-private-output")
        self.reject(lambda: self.bundle.write_bundle(self.runtime, self.vsix, self.output, target=TARGETS[0], revision=REVISION))
        self.assertEqual(self.output.read_bytes(), b"existing-private-output")

    @unittest.skipUnless(os.name == "posix", "native Unix permission bits are not available on this platform")
    def test_published_file_has_posix_mode_0644(self):
        self.bundle.write_bundle(self.runtime, self.vsix, self.output, target=TARGETS[0], revision=REVISION)
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o644)

    def test_existing_output_symlink_is_not_replaced_or_followed(self):
        victim = self.root / "victim"
        victim.write_bytes(b"keep-victim")
        self.symlink_or_skip(self.output, victim)
        self.reject(lambda: self.bundle.write_bundle(self.runtime, self.vsix, self.output, target=TARGETS[0], revision=REVISION))
        self.assertTrue(self.output.is_symlink())
        self.assertEqual(victim.read_bytes(), b"keep-victim")


    def test_dangling_output_symlink_is_refused_and_preserved(self):
        missing = self.root / "does-not-exist"
        self.symlink_or_skip(self.output, missing)
        self.reject(lambda: self.bundle.write_bundle(self.runtime, self.vsix, self.output,
            target=TARGETS[0], revision=REVISION))
        self.assertTrue(self.output.is_symlink())
        self.assertFalse(missing.exists())



if __name__ == "__main__":
    unittest.main()
