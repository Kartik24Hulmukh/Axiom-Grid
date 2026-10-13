"""Real native compiler boundaries; no JVM, browser or network execution."""
import importlib.util
import json
import os
from html.parser import HTMLParser
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'kairo-sidecar/sidecar/exporters/quarkdown_compiler.py'
spec = importlib.util.spec_from_file_location('quarkdown_boundary_owned', SOURCE)
compiler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)
MARKER = 'window.__axiomCompilerMarker=(window.__axiomCompilerMarker||0)+1;'
SCRIPT = f'<script>{MARKER}</script>'
CASES = {
    'title': f'# Title {SCRIPT}',
    'bullet': f'# Slide\n- Bullet {SCRIPT}',
    'paragraph': f'# Slide\nParagraph {SCRIPT}',
    'fenced_code': f'# Slide\n```text\n</code></pre>{SCRIPT}\n```',
    'code_language': f'# Slide\n```text\" data-owned=\"breakout\"><script>{MARKER}</script><code class=\"\nhello\n```',
    'benign': '# Résumé & <notes>\n- Café & tea\nParagraph \'quoted\' "double"\n```python\nprint("a < b & c")\n```\n## Second\n- Next',
}
FIXED_SOURCES = [
    'https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/reveal.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/reveal.js/4.5.0/plugin/highlight/highlight.min.js',
]


class Parsed(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.data = []
        self.scripts = []
        self.active_script = None
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, attrs))
        if tag == 'script':
            self.active_script = {'attrs': dict(attrs), 'data': ''}
            self.scripts.append(self.active_script)

    def handle_endtag(self, tag):
        if tag == 'script':
            self.active_script = None

    def handle_data(self, data):
        self.data.append(data)
        if self.active_script is not None:
            self.active_script['data'] += data


@pytest.fixture(autouse=True)
def native_only():
    # Even if java is absent, do not let the test accidentally become a JVM test.
    jar = SOURCE.parent.parent.parent / 'bin/quarkdown.jar'
    assert not jar.exists(), 'Bundled JAR present: refuse to execute JVM in this lane'


def export(tmp_path, name, content, fmt):
    evidence = os.environ.get('AXIOM_COMPILER_EVIDENCE_DIR')
    directory = Path(evidence) if evidence else tmp_path
    directory.mkdir(parents=True, exist_ok=True)
    suffix = 'epub' if fmt == 'epub' else 'html'
    path = directory / f'{name}.{fmt}.{suffix}'
    assert compiler.compile_quarkdown(content, fmt, str(path)) is True
    assert path.is_file()
    return path


def test_input_manifest(tmp_path):
    directory = Path(os.environ.get('AXIOM_COMPILER_EVIDENCE_DIR', tmp_path))
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {'marker_javascript': MARKER, 'cases': [
        {'name': name, 'format': 'revealjs', 'content': content,
         'output': f'{name}.revealjs.html'} for name, content in CASES.items()
    ], 'scope': 'Actual native compiler; parser checks only, not browser execution'}
    (directory / 'input-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


@pytest.mark.parametrize('name,content', CASES.items())
def test_reveal_context_encoding(tmp_path, name, content):
    parsed = Parsed(export(tmp_path, name, content, 'revealjs').read_text(encoding='utf-8'))
    # Fixed scripts remain intentionally present; no zero-scripts assertion.
    assert len(parsed.scripts) == 3
    assert [s['attrs'].get('src') for s in parsed.scripts[:2]] == FIXED_SOURCES
    assert 'Reveal.initialize' in parsed.scripts[2]['data']
    assert all(MARKER not in s['data'] for s in parsed.scripts)
    assert all(key != 'data-owned' and not key.startswith('on')
               for _, attrs in parsed.tags for key, _ in attrs)
    if name not in ('benign', 'code_language'):
        assert MARKER in ''.join(parsed.data)
    elif name == 'benign':
        assert 'Résumé & <notes>' in ''.join(parsed.data)
        assert 'Café & tea' in ''.join(parsed.data)
        assert 'print("a < b & c")' in ''.join(parsed.data)
        assert sum(tag == 'section' for tag, _ in parsed.tags) == 2
        assert any(tag == 'li' for tag, _ in parsed.tags)
        assert any(tag == 'code' and dict(attrs).get('class') == 'language-python'
                   for tag, attrs in parsed.tags)
    if name == 'code_language':
        # The hostile marker is in an attribute value, not a text node.
        assert 'hello' in ''.join(parsed.data)
        original_lang = content.splitlines()[1][3:].strip()
        assert any(tag == 'code' and dict(attrs).get('class') == 'language-' + original_lang
                   for tag, attrs in parsed.tags)


@pytest.mark.parametrize('fmt', ['html', 'book'])
def test_real_native_documents(tmp_path, fmt, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Native document must not probe/execute JVM')
    # Fault-negative boundary, not a JVM output substitute.
    monkeypatch.setattr(compiler.shutil, 'which', forbidden)
    content = f'# Résumé & <notes>\nParagraph {SCRIPT}\n- Café'
    parsed = Parsed(export(tmp_path, 'native', content, fmt).read_text(encoding='utf-8'))
    assert not parsed.scripts
    assert 'Résumé & <notes>' in ''.join(parsed.data)
    assert SCRIPT in ''.join(parsed.data)
    assert any(tag == 'h1' for tag, _ in parsed.tags)
    assert any(tag == 'li' for tag, _ in parsed.tags)
    if fmt == 'book':
        assert any(tag == 'a' and dict(attrs).get('href') == '#h-1' for tag, attrs in parsed.tags)


def test_real_native_epub(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('EPUB must not probe/execute JVM')
    monkeypatch.setattr(compiler.shutil, 'which', forbidden)
    path = export(tmp_path, 'native', f'# Résumé & <notes>\n{SCRIPT}\n- Café', 'epub')
    with zipfile.ZipFile(path) as archive:
        assert archive.infolist()[0].filename == 'mimetype'
        assert archive.infolist()[0].compress_type == zipfile.ZIP_STORED
        assert archive.read('mimetype') == b'application/epub+zip'
        for name in ['META-INF/container.xml', 'OEBPS/content.opf', 'OEBPS/nav.xhtml', 'OEBPS/content.xhtml']:
            ET.fromstring(archive.read(name))
        parsed = Parsed(archive.read('OEBPS/content.xhtml').decode('utf-8'))
        assert not parsed.scripts
        assert SCRIPT in ''.join(parsed.data)
        assert 'Résumé & <notes>' in ''.join(parsed.data)


@pytest.mark.parametrize('fmt', ['epub', 'book', 'html', 'unknown', 'PDF', ''])
def test_direct_jvm_unsupported_before_io(tmp_path, monkeypatch, fmt):
    def forbidden(*args, **kwargs):
        raise AssertionError('Unsupported JVM format reached I/O')
    monkeypatch.setattr(compiler.tempfile, 'NamedTemporaryFile', forbidden)
    monkeypatch.setattr(compiler.subprocess, 'run', forbidden)
    path = tmp_path / 'unsupported.output'
    assert compiler.run_jvm_quarkdown('.document\ntiny', Path('absent.jar'), fmt, str(path)) is False
    assert not path.exists()


@pytest.mark.parametrize('fmt', ['pdf', 'unknown', 'PDF', ''])
def test_fallback_refuses_fake_or_unknown_format(tmp_path, fmt):
    path = tmp_path / f'output-{fmt or "empty"}.pdf'
    path.write_bytes(b'owned-sentinel')
    assert compiler.run_fallback_compiler('tiny', 'tiny', fmt, str(path)) is False
    assert path.read_bytes() == b'owned-sentinel'


@pytest.mark.parametrize('fmt', ['pdf', 'unknown', 'PDF', ''])
def test_compile_refuses_fake_or_unknown_format(tmp_path, fmt):
    path = tmp_path / 'output.pdf'
    path.write_bytes(b'owned-sentinel')
    assert compiler.compile_quarkdown('tiny', fmt, str(path)) is False
    assert path.read_bytes() == b'owned-sentinel'
