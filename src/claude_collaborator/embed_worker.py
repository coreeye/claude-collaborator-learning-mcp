"""Embedding worker process for claude-collaborator.

Runs as a child of the MCP server (see memory_vector.EmbeddingWorker) and is the
only process that imports sentence-transformers / torch / scipy. Keeping that
stack out of the server matters on Windows: loading its native libraries holds
the process-wide loader lock for as long as the load takes, and while it is held
no new thread can start in that process. ThreadPoolExecutor.submit() starts
threads under a module-global lock, so a single blocked start froze the MCP
event loop and every tool call with it (learn calls hung 5 to 49 minutes).

This file is started as a plain script (python embed_worker.py <model>) so the
child does not import the claude_collaborator package.

Protocol (JSON, one object per line):
  child -> parent   {"ready": true, "model": ..., "dim": 384, "load_seconds": 9.7, "pid": 123}
                    {"ready": false, "error": "..."}            then exit code 1
  parent -> child   {"id": 7, "texts": ["...", "..."]}
  child -> parent   {"id": 7, "vectors": [[...], [...]]}       float32 values
                    {"id": 7, "error": "..."}
The child exits when its stdin closes, i.e. when the server process ends.
"""

import json
import os
import sys
import time


def main() -> int:
    model_name = sys.argv[1] if len(sys.argv) > 1 else "all-MiniLM-L6-v2"

    # The protocol channel is a private copy of the original stdout. Anything
    # else that prints to fd 1 (model load reports, library warnings) goes to
    # stderr instead, so it can never corrupt a protocol line.
    proto = os.fdopen(os.dup(1), "wb", buffering=0)
    os.dup2(2, 1)
    sys.stdout = sys.stderr

    def send(obj) -> None:
        proto.write((json.dumps(obj) + "\n").encode("utf-8"))

    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    os.environ.setdefault("TQDM_DISABLE", "1")

    t0 = time.monotonic()
    try:
        import logging
        for name in ("sentence_transformers", "transformers", "huggingface_hub", "filelock", "torch"):
            logging.getLogger(name).setLevel(logging.ERROR)
        import torch
        # Short texts on a MiniLM model gain nothing from a 12-thread pool, and
        # several server processes may run at once.
        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
        from sentence_transformers import SentenceTransformer
        try:
            # Local cache only: a Hub metadata check on every load can stall or
            # be rate limited. Fall back to a downloading load on first use.
            model = SentenceTransformer(model_name, trust_remote_code=False, local_files_only=True)
        except Exception:
            model = SentenceTransformer(model_name, trust_remote_code=False)
        dim = model.get_sentence_embedding_dimension()
    except Exception as e:  # noqa: BLE001 - reported to the parent, then exit
        send({"ready": False, "error": f"{type(e).__name__}: {e}"})
        return 1

    send({
        "ready": True,
        "model": model_name,
        "dim": dim,
        "load_seconds": round(time.monotonic() - t0, 2),
        "pid": os.getpid(),
    })

    stdin = sys.stdin.buffer
    while True:
        raw = stdin.readline()
        if not raw:
            return 0  # parent closed the pipe or exited
        raw = raw.strip()
        if not raw:
            continue
        rid = None
        try:
            req = json.loads(raw)
            rid = req.get("id")
            texts = req.get("texts") or []
            if texts:
                vectors = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
                payload = [v.astype("float32").tolist() for v in vectors]
            else:
                payload = []
            send({"id": rid, "vectors": payload})
        except Exception as e:  # noqa: BLE001 - one bad request must not kill the worker
            send({"id": rid, "error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    sys.exit(main())
