"""Tests for a narrow source guard; no native application is launched."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("preview_guard", ROOT / "scripts/check_authorized_preview.py")
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class PreviewGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        files = ["phantom-overlay/src-tauri/tauri.conf.json", "phantom-overlay/src-tauri/capabilities/default.json", "phantom-overlay/src-tauri/src/lib.rs", "phantom-overlay/dist/app.js", "phantom-overlay/dist/app.css", "phantom-overlay/dist/index.html", ".gitignore", ".cargo/config.toml"]
        for name in files:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def mutate_json(self, name, fn):
        path = self.root / name
        data = json.loads(path.read_text())
        fn(data)
        path.write_text(json.dumps(data))

    def test_expected_boundary_passes(self):
        self.assertEqual(guard.check(self.root), [])

    def test_hidden_window_fails(self):
        self.mutate_json("phantom-overlay/src-tauri/tauri.conf.json", lambda d: d["app"]["windows"][0].update(skipTaskbar=True))
        self.assertTrue(guard.check(self.root))

    def test_shell_permission_fails(self):
        self.mutate_json("phantom-overlay/src-tauri/capabilities/default.json", lambda d: d["permissions"].append("shell:allow-execute"))
        self.assertTrue(guard.check(self.root))

    def test_dynamic_or_extra_ipc_fails(self):
        p = self.root / "phantom-overlay/dist/app.js"
        for extra in ['window.__TAURI__.core.invoke("apply_text", {});', 'window.__TAURI__.core.invoke(command, {});']:
            with self.subTest(extra=extra):
                original = p.read_text()
                p.write_text(original + extra)
                self.assertTrue(guard.check(self.root))
                p.write_text(original)

    def test_bracket_or_aliased_ipc_fails(self):
        p = self.root / "phantom-overlay/dist/app.js"
        original = p.read_text()
        for extra in [
            'window.__TAURI__.core["invoke"]("unreviewed_command");',
            "window.__TAURI__.core['invoke']('unreviewed_command');",
            'const alias = window.__TAURI__.core.invoke; alias("unreviewed_command");',
        ]:
            with self.subTest(extra=extra):
                p.write_text(original + extra)
                self.assertTrue(guard.check(self.root))
        p.write_text(original)

    def test_additional_frontend_asset_fails(self):
        (self.root / "phantom-overlay/dist/extra.js").write_text("// unreviewed")
        self.assertTrue(guard.check(self.root))

    def test_platform_configuration_override_fails(self):
        (self.root / "phantom-overlay/src-tauri/tauri.windows.conf.json").write_text("{}")
        self.assertTrue(guard.check(self.root))

    def test_additional_capability_file_fails(self):
        p = self.root / "phantom-overlay/src-tauri/capabilities/extra.toml"
        p.write_text('identifier="extra"')
        self.assertTrue(guard.check(self.root))

    def test_inline_capability_override_fails(self):
        self.mutate_json("phantom-overlay/src-tauri/tauri.conf.json", lambda d: d["app"]["security"].update(capabilities=["extra"]))
        self.assertTrue(guard.check(self.root))

    def test_malformed_or_missing_config_fails(self):
        p = self.root / "phantom-overlay/src-tauri/tauri.conf.json"
        p.write_text("{")
        self.assertTrue(guard.check(self.root))
        p.unlink()
        self.assertTrue(guard.check(self.root))

    def test_wrong_window_shape_fails(self):
        self.mutate_json("phantom-overlay/src-tauri/tauri.conf.json", lambda d: d["app"].update(windows=["not-an-object"]))
        self.assertTrue(guard.check(self.root))

    def test_encoded_ignore_rules_fail(self):
        (self.root / ".gitignore").write_text("YmFkLWlnbm9yZS1maWxl")
        self.assertTrue(guard.check(self.root))

    def test_native_apply_command_fails(self):
        p = self.root / "phantom-overlay/src-tauri/src/lib.rs"
        p.write_text(p.read_text().replace("toggle_visibility,", "toggle_visibility, apply_text,"))
        self.assertTrue(guard.check(self.root))

    def test_per_machine_linker_fails(self):
        p = self.root / ".cargo/config.toml"
        p.write_text(p.read_text() + '\n[target.x86_64-pc-windows-gnu]\nlinker="machine-specific"\n')
        self.assertTrue(guard.check(self.root))


if __name__ == "__main__":
    unittest.main()
