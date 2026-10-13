"""Real loopback contracts for the exact-image owned-document smoke probe."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from scripts.smoke_document_intake import main

ROOT = Path(__file__).resolve().parents[1]
KEY = "ci-only-intake-key"


@pytest.fixture
def live_intake(tmp_path):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    env = {
        **os.environ, "AXIOM_API_KEYS": KEY, "AXIOM_REQUIRE_AUTH": "1",
        "AXIOM_STATE_DIR": str(tmp_path / "state"),
        "AXIOM_EXTRACTION_WORKERS": "2", "AXIOM_PIPELINE_CONCURRENCY": "2",
        "AXIOM_EXTRACTION_QUEUE_DEPTH": "4", "AXIOM_EXTRACTION_ISOLATION": "process",
        "AXIOM_INGEST_RSS_BYTES": "268435456", "AXIOM_INGEST_CPU_SECONDS": "25",
        "OTEL_TRACES_EXPORTER": "none", "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1", "KAIRO_NO_NET": "1",
    }
    env.pop("MELIOUS_API_KEY", None)
    env.pop("AXIOM_API_KEYS_FILE", None)
    with (tmp_path / "server.log").open("wb") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "overlay.server:app",
             "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
            cwd=ROOT, env=env, stdout=log, stderr=log,
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                assert process.poll() is None, "intake server exited during startup"
                try:
                    with urllib.request.urlopen(base + "/readyz", timeout=1) as response:
                        if response.status == 200:
                            break
                except (urllib.error.URLError, TimeoutError):
                    pass
                assert time.monotonic() < deadline, "intake server readiness deadline"
                time.sleep(.05)  # bounded readiness-condition polling, not work retry
            yield base
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                pytest.fail("intake server did not shut down cleanly")


def test_authenticated_probe_uploads_and_extracts_real_pdf_docx(live_intake, capsys):
    main(base_url=live_intake, api_key=KEY)
    output = capsys.readouterr().out
    assert ".pdf authenticated real document intake: PASS" in output
    assert ".docx authenticated real document intake: PASS" in output


def test_authenticated_arbitrary_temp_path_is_still_denied(live_intake, tmp_path):
    outside = tmp_path / "not-owned.txt"
    outside.write_text("CLASSIFICATION: UNCLASSIFIED\nSUBJECT: release intake")
    request = urllib.request.Request(
        live_intake + "/api/extract-document",
        data=json.dumps({"file": str(outside)}).encode(),
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(request, timeout=30)
    with error.value:
        assert error.value.code == 404