"""
Tests for the embedding worker process (memory_vector.EmbeddingWorker).

Run with: pytest tests/test_embed_worker.py -v -s
Needs sentence-transformers with the all-MiniLM-L6-v2 model in the local HF cache.
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_collaborator.memory_vector import EmbeddingWorker, VectorStore  # noqa: E402

pytest.importorskip("sentence_transformers")

READY_TIMEOUT = 180


def _wait(predicate, timeout, step=0.1):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(step)
    return predicate()


def test_worker_roundtrip():
    worker = EmbeddingWorker.get("all-MiniLM-L6-v2")
    worker.start()
    assert worker.wait_until_ready(READY_TIMEOUT), f"worker never became ready: {worker.last_error}"
    assert worker.dim == 384

    vectors = worker.encode(["database connection pattern", "unrelated text about cooking"])
    assert vectors is not None and len(vectors) == 2
    assert vectors[0].shape == (384,)
    assert vectors[0].dtype.name == "float32"

    # Same text -> same vector; different texts -> less similar than identical ones
    again = worker.encode(["database connection pattern"])
    assert again is not None
    self_sim = float((vectors[0] * vectors[0]).sum())
    assert abs(float((again[0] * vectors[0]).sum()) - self_sim) < 1e-3
    assert float((vectors[0] * vectors[1]).sum()) < self_sim


def test_worker_respawns_after_crash():
    worker = EmbeddingWorker.get("all-MiniLM-L6-v2")
    worker.start()
    assert worker.wait_until_ready(READY_TIMEOUT)
    old_proc = worker._proc
    restarts_before = worker._restarts

    old_proc.kill()
    assert _wait(lambda: worker._proc is not None and worker._proc is not old_proc, 30), "no respawn"
    assert worker._restarts == restarts_before + 1
    assert worker.wait_until_ready(READY_TIMEOUT)
    assert worker.encode(["after restart"]) is not None


def test_store_degrades_while_loading_then_flushes(tmp_path):
    """A store whose worker is not ready must degrade at once, never block."""
    vs = VectorStore(str(tmp_path))
    t0 = time.monotonic()
    result = vs.add("topic", "content while loading", "findings")
    assert result is not None  # "queued" while loading, or an id if the shared worker is already up
    assert vs.search("nothing yet") is not None
    assert time.monotonic() - t0 < 5

    # Once ready, the queued write is flushed and searchable.
    assert vs.wait_until_ready(READY_TIMEOUT)
    assert _wait(lambda: vs.get_stats()["pending_writes"] == 0, 30)
    results = vs.search("content while loading", limit=1)
    assert results and results[0]["topic"] == "topic"
