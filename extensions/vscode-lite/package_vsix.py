"""Build only the allowlisted model-free VSIX; no external packager or downloads."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
import zipfile

FILES = ('package.json', 'extension.js', 'state.js', 'comment.js', 'client.js', 'README.md', 'LICENSE')
NS = 'http://schemas.microsoft.com/developer/vsx-schema/2011'

def build_bytes():
    root = Path(__file__).resolve().parent
    data = {}
    for name in FILES:
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Invalid package input')
        data['extension/' + name] = path.read_bytes()
    manifest = json.loads(data['extension/package.json'])
    ET.register_namespace('', NS)
    def element(parent, name, attrs=None, text=None):
        item = ET.SubElement(parent, '{' + NS + '}' + name, attrs or {})
        item.text = text
        return item
    package = ET.Element('{' + NS + '}PackageManifest', {'Version': '2.0.0'})
    metadata = element(package, 'Metadata')
    element(metadata, 'Identity', {'Language': 'en-US', 'Id': manifest['name'], 'Version': manifest['version'], 'Publisher': manifest['publisher']})
    element(metadata, 'DisplayName', text=manifest['displayName'])
    element(metadata, 'Description', {'{http://www.w3.org/XML/1998/namespace}space': 'preserve'}, manifest['description'])
    element(metadata, 'Tags', text='local,explicit,inline,prototype')
    element(metadata, 'Categories', text=','.join(manifest['categories']))
    element(metadata, 'License', text='extension/LICENSE')
    properties = element(metadata, 'Properties')
    element(properties, 'Property', {'Id': 'Microsoft.VisualStudio.Code.Engine', 'Value': manifest['engines']['vscode']})
    element(properties, 'Property', {'Id': 'Microsoft.VisualStudio.Code.ExtensionKind', 'Value': 'ui'})
    element(properties, 'Property', {'Id': 'Microsoft.VisualStudio.Code.PreRelease', 'Value': 'true'})
    installation = element(package, 'Installation')
    element(installation, 'InstallationTarget', {'Id': 'Microsoft.VisualStudio.Code'})
    element(package, 'Dependencies')
    assets = element(package, 'Assets')
    for kind, path in [('Microsoft.VisualStudio.Code.Manifest', 'extension/package.json'), ('Microsoft.VisualStudio.Services.Content.Details', 'extension/README.md'), ('Microsoft.VisualStudio.Services.Content.License', 'extension/LICENSE')]:
        element(assets, 'Asset', {'Type': kind, 'Path': path, 'Addressable': 'true'})
    data['extension.vsixmanifest'] = ET.tostring(package, encoding='utf-8', xml_declaration=True)
    content_ns = 'http://schemas.openxmlformats.org/package/2006/content-types'
    types = ET.Element('Types', {'xmlns': content_ns})
    for extension, content in [('json', 'application/json'), ('js', 'application/javascript'), ('md', 'text/plain'), ('vsixmanifest', 'text/xml')]:
        ET.SubElement(types, 'Default', {'Extension': extension, 'ContentType': content})
    ET.SubElement(types, 'Override', {'PartName': '/extension/LICENSE', 'ContentType': 'text/plain'})
    data['[Content_Types].xml'] = ET.tostring(types, encoding='utf-8', xml_declaration=True)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sorted(data.items()):
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, payload)
    return buffer.getvalue()

def write_package(destination):
    payload = build_bytes()
    destination = Path(destination)
    fd, temporary = tempfile.mkstemp(prefix='.axiom-vsix-', dir=destination.parent)
    try:
        try:
            stream = os.fdopen(fd, 'wb')
        except BaseException:
            os.close(fd)
            raise
        with stream:
            if stream.write(payload) != len(payload):
                raise OSError('Short write')
        # Complete file publication only; existing files/symlinks are not replaced.
        os.link(temporary, destination)
    finally:
        os.unlink(temporary)
    return {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}

def main(argv=None):
    parser = argparse.ArgumentParser(description='Package the model-free development VSIX; existing output is refused.')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        result = write_package(args.output)
    except (OSError, ValueError, KeyError, TypeError):
        print('VSIX packaging failed; verify inputs, output absence and a trusted existing parent directory.')
        return 1
    print(json.dumps(result))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
