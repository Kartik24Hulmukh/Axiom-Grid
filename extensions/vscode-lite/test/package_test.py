import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('vsix_packager', ROOT / 'package_vsix.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)

class PackageTests(unittest.TestCase):
    def test_reproducible_allowlisted_zip_with_valid_xml_assets(self):
        first = packager.build_bytes()
        self.assertEqual(first, packager.build_bytes())
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(archive.namelist()), {'extension/' + n for n in packager.FILES} | {'extension.vsixmanifest', '[Content_Types].xml'})
            manifest = ET.fromstring(archive.read('extension.vsixmanifest'))
            ns = {'v': packager.NS}
            self.assertEqual(manifest.find('v:Metadata/v:Identity', ns).attrib['Id'], 'axiom-grid-lite')
            for asset in manifest.findall('v:Assets/v:Asset', ns):
                self.assertIn(asset.attrib['Path'], archive.namelist())
            ET.fromstring(archive.read('[Content_Types].xml'))
            p = json.loads(archive.read('extension/package.json'))
            self.assertEqual(p['extensionKind'], ['ui'])
            self.assertNotIn('dependencies', p)
            self.assertFalse(p['capabilities']['untrustedWorkspaces']['supported'])
            self.assertFalse(p['capabilities']['virtualWorkspaces']['supported'])
    def test_exclusive_publication_refuses_existing_and_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'test.vsix'
            result = packager.write_package(out)
            self.assertEqual(result['bytes'], out.stat().st_size)
            saved = out.read_bytes()
            with self.assertRaises(FileExistsError): packager.write_package(out)
            self.assertEqual(out.read_bytes(), saved)
            self.assertEqual(list(Path(folder).glob('.axiom-vsix-*')), [])
            link = Path(folder) / 'link.vsix'
            link.symlink_to(out)
            with self.assertRaises(FileExistsError): packager.write_package(link)
            self.assertEqual(out.read_bytes(), saved)
    def test_missing_parent_fails_without_creating_it(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder) / 'missing'
            with self.assertRaises(FileNotFoundError): packager.write_package(parent / 'x.vsix')
            self.assertFalse(parent.exists())
    def test_fdopen_failure_closes_descriptor_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as folder:
            real_close = packager.os.close
            with mock.patch.object(packager.os, 'fdopen', side_effect=OSError('injected')), mock.patch.object(packager.os, 'close', wraps=real_close) as close:
                with self.assertRaises(OSError):
                    packager.write_package(Path(folder) / 'x.vsix')
                close.assert_called_once()
            self.assertEqual(list(Path(folder).iterdir()), [])

if __name__ == '__main__': unittest.main()
