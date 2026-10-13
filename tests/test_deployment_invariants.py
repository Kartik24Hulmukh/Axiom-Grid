"""Static contracts keep the candidate container inside its measured envelope."""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _duration_seconds(value: str) -> int:
    match = re.fullmatch(r"(\d+)s", value)
    assert match, f"unsupported duration: {value}"
    return int(match.group(1))


def test_candidate_capacity_is_explicit_and_consistent():
    compose = yaml.safe_load((ROOT / "deploy/docker-compose.prod.yml").read_text())
    environment = compose["services"]["api"]["environment"]
    expected = {
        "WEB_CONCURRENCY": "1",
        "AXIOM_API_KEYS_FILE": "/run/secrets/axiom_api_keys",
        "AXIOM_EXTRACTION_WORKERS": "2",
        "AXIOM_PIPELINE_CONCURRENCY": "2",
        "AXIOM_EXTRACTION_QUEUE_DEPTH": "4",
        "AXIOM_EVIDENCE_WORKERS": "2",
        "AXIOM_INGEST_RSS_BYTES": "268435456",
        "AXIOM_INGEST_CPU_SECONDS": "25",
    }
    assert {key: str(environment[key]) for key in expected} == expected
    limits = compose["services"]["api"]["deploy"]["resources"]["limits"]
    assert str(limits["cpus"]) == "2.0"
    assert limits["memory"] == "768M"
    assert "AXIOM_API_KEYS" not in environment
    assert compose["services"]["api"]["secrets"] == ["axiom_api_keys"]
    assert "file" in compose["secrets"]["axiom_api_keys"]


def test_shutdown_order_exceeds_application_deadline():
    compose = yaml.safe_load((ROOT / "deploy/docker-compose.prod.yml").read_text())
    stop_grace = _duration_seconds(compose["services"]["api"]["stop_grace_period"])
    dockerfile = (ROOT / "docker/Dockerfile.overlay").read_text()
    graceful = int(re.search(
        r'UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN=(\d+)', dockerfile
    ).group(1))
    server = (ROOT / "overlay/server.py").read_text()
    extraction_default = int(re.search(
        r'AXIOM_EXTRACTION_DEADLINE_SECONDS", "(\d+)"', server
    ).group(1))
    assert stop_grace > graceful > extraction_default
    assert f'"--timeout-graceful-shutdown", "{graceful}"' in dockerfile


def test_alerts_reference_only_application_owned_memory_metric():
    alerts = (ROOT / "deploy/alerts.yml").read_text()
    assert "axiom_process_resident_memory_bytes" in alerts
    assert "container_memory_working_set_bytes" not in alerts
    assert "cAdvisor" not in alerts