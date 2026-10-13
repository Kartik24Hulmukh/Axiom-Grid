"""Actual import-time pools must honor the declared deployment envelope.

Each test uses a fresh subprocess/private state directory. No HTTP/provider,
parser or worker workload is executed; executor creation is lazy and pools close.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
_PROBE = """
import json
import overlay.server as server
print('CAPACITY_JSON:' + json.dumps({
    'workers': server.EXTRACTION_WORKERS,
    'cpu_pool': server._extraction_pool._max_workers,
    'metadata_pool': server._document_metadata_pool._max_workers,
    'capacity': server._EXTRACTION_CAPACITY,
    'pipeline': server.orchestrator_gate.limit,
    'evidence_pool': server._evidence_pool._max_workers,
}))
for pool in (server._extraction_pool, server._document_metadata_pool, server._evidence_pool):
    pool.shutdown(wait=True)
server.memory_store.close()
server.evidence_store.close()
"""


def _probe(tmp_path, workers):
    environment = os.environ.copy()
    for name in ('MELIOUS_API_KEY', 'AXIOM_API_KEYS', 'AXIOM_API_KEYS_FILE',
                 'AXIOM_EXTRACTION_WORKERS'):
        environment.pop(name, None)
    if workers is not None:
        environment['AXIOM_EXTRACTION_WORKERS'] = workers
    environment.update(AXIOM_STATE_DIR=str(tmp_path), AXIOM_EXTRACTION_QUEUE_DEPTH='4',
                       AXIOM_PIPELINE_CONCURRENCY='2', AXIOM_EVIDENCE_WORKERS='2',
                       HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', KAIRO_NO_NET='1')
    return subprocess.run([sys.executable, '-c', _PROBE], cwd=ROOT, env=environment,
                          capture_output=True, text=True, timeout=30)


def _capacity(result):
    assert result.returncode == 0, result.stderr
    line = next(line for line in result.stdout.splitlines() if line.startswith('CAPACITY_JSON:'))
    return json.loads(line.split(':', 1)[1])


@pytest.mark.parametrize('workers', [1, 2, 32])
def test_explicit_workers_control_real_pools_and_admission(tmp_path, workers):
    data = _capacity(_probe(tmp_path, str(workers)))
    assert data == {'workers': workers, 'cpu_pool': workers,
                    'metadata_pool': min(4, workers), 'capacity': workers + 4,
                    'pipeline': 2, 'evidence_pool': 2}


@pytest.mark.parametrize('workers', [None, ''])
def test_unset_or_blank_keeps_existing_host_default(tmp_path, workers):
    data = _capacity(_probe(tmp_path, workers))
    expected = max(4, min(32, (os.cpu_count() or 2) * 2))
    assert data['workers'] == data['cpu_pool'] == expected
    assert data['metadata_pool'] == min(4, expected)
    assert data['capacity'] == expected + 4


@pytest.mark.parametrize('workers', ['0', '-1', '33', 'not-an-integer'])
def test_invalid_explicit_workers_fail_startup(tmp_path, workers):
    result = _probe(tmp_path, workers)
    assert result.returncode != 0
    assert 'AXIOM_EXTRACTION_WORKERS' in result.stderr
    assert 'CAPACITY_JSON:' not in result.stdout
