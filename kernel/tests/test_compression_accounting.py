"""Compression telemetry must not retain per-request objects or torn totals."""
import concurrent.futures
import gc
import threading
import weakref

from kairo.context import compressor


def test_completed_compressions_are_not_retained():
    compressor._global_stats.clear()
    refs = []
    for _ in range(1000):
        stats = compressor.CompressionStats(tokens_before=10, tokens_after=6, tokens_saved=4)
        refs.append(weakref.ref(stats))
        compressor.record_compression(stats)
    del stats
    gc.collect()
    assert sum(ref() is not None for ref in refs) == 0
    result = compressor.get_compression_stats()
    assert result["total_runs"] == 1000
    assert result["total_tokens_saved"] == 4000


def test_stats_do_not_alias_caller_or_reader():
    compressor._global_stats.clear()
    stats = compressor.CompressionStats(tokens_before=10, transforms_applied=["original"])
    compressor.record_compression(stats)
    stats.transforms_applied.append("caller mutation")
    first = compressor.get_compression_stats()
    assert first["last_run"]["transforms_applied"] == ["original"]
    first["last_run"]["transforms_applied"].append("reader mutation")
    assert compressor.get_compression_stats()["last_run"]["transforms_applied"] == ["original"]


def test_concurrent_writes_and_snapshots_have_exact_totals():
    compressor._global_stats.clear()
    start = threading.Barrier(100)
    def worker(_):
        start.wait(timeout=10)
        for _ in range(100):
            compressor.record_compression(compressor.CompressionStats(
                tokens_before=10, tokens_after=6, tokens_saved=4))
            snap = compressor.get_compression_stats()
            assert snap["total_tokens_before"] == snap["total_runs"] * 10
            assert snap["total_tokens_after"] == snap["total_runs"] * 6
            assert snap["total_tokens_saved"] == snap["total_runs"] * 4
    with concurrent.futures.ThreadPoolExecutor(100) as pool:
        list(pool.map(worker, range(100)))
    assert compressor.get_compression_stats()["total_runs"] == 10000
