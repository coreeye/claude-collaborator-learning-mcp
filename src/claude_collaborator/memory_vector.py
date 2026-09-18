"""
Vector Memory Store for Semantic Similarity Search
Provides embedding-based semantic search capabilities.

Embeddings are computed in a separate worker process (embed_worker.py); the
sentence-transformers / torch / scipy stack is never imported into the MCP
server process. Loading those native libraries holds the process-wide loader
lock (Windows) for as long as the load takes, and while it is held no new
thread can start in the process. ThreadPoolExecutor.submit() starts threads
under a module-global lock, so one blocked thread start froze the asyncio loop
and every tool call with it: learn calls hung for 5 to 49 minutes whenever the
second call arrived while the model was still loading. Moving the model to a
child process removes both the loader-lock exposure and the GIL-heavy import
from the server. The server only ever waits on the worker with a timeout.
"""

import json
import os
import queue
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np

# Default wall-clock budget for one embedding request to the worker.
EMBEDDING_TIMEOUT_SEC = float(os.environ.get("EMBEDDING_TIMEOUT", "20"))

_DEBUG_ENABLED = os.environ.get("CLAUDE_COLLAB_DEBUG") == "1"
_DEBUG_LOG_PATH = Path(os.environ.get("TEMP", os.environ.get("TMP", "."))) / "claude_collaborator_debug.log"


def _log(msg: str) -> None:
    """stderr (captured by the MCP host) plus the debug trace file when enabled."""
    print(msg, file=sys.stderr, flush=True)
    if _DEBUG_ENABLED:
        try:
            with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} pid={os.getpid()} {msg}\n")
        except Exception:
            pass


class EmbeddingWorker:
    """Parent-side handle of the embedding worker process.

    One worker per model per server process, shared by every VectorStore.
    Requests are serialized (one in flight) and every wait is bounded. A worker
    that dies or stops answering is killed and respawned up to MAX_RESTARTS
    times; after that embeddings stay unavailable and callers degrade (writes
    are queued by VectorStore, searches return nothing).
    """

    MAX_RESTARTS = 3
    _instances: Dict[str, "EmbeddingWorker"] = {}
    _instances_lock = threading.Lock()

    @classmethod
    def get(cls, model_name: str) -> "EmbeddingWorker":
        with cls._instances_lock:
            worker = cls._instances.get(model_name)
            if worker is None:
                worker = cls(model_name)
                cls._instances[model_name] = worker
            return worker

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.dim: Optional[int] = None
        self.load_seconds: Optional[float] = None
        self.last_error: Optional[str] = None
        self._lock = threading.Lock()          # process lifecycle
        self._request_lock = threading.Lock()  # one request in flight
        self._ready = threading.Event()
        self._proc: Optional[subprocess.Popen] = None
        self._responses: "queue.Queue[Optional[dict]]" = queue.Queue()
        self._next_id = 0
        self._restarts = 0
        self._failed = False
        self._on_ready: List[Callable[[], None]] = []

    # ---- lifecycle -------------------------------------------------------

    def start(self) -> None:
        """Spawn the worker if it is not running. Never blocks on the model load."""
        with self._lock:
            if self._failed:
                return
            if self._proc is not None and self._proc.poll() is None:
                return
            self._spawn_locked()

    def _spawn_locked(self) -> None:
        script = Path(__file__).with_name("embed_worker.py")
        env = dict(os.environ)
        env.setdefault("TOKENIZERS_PARALLELISM", "false")
        env.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        env.setdefault("TRANSFORMERS_VERBOSITY", "error")
        env.setdefault("PYTHONUNBUFFERED", "1")
        kwargs: Dict[str, Any] = {}
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._ready.clear()
        try:
            proc = subprocess.Popen(
                [sys.executable, "-u", str(script), self.model_name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None,  # inherit: the host's MCP log keeps the worker's messages
                env=env,
                **kwargs,
            )
        except Exception as e:  # noqa: BLE001
            self._failed = True
            self.last_error = f"{type(e).__name__}: {e}"
            _log(f"[embed] cannot start worker: {self.last_error}")
            return
        self._proc = proc
        threading.Thread(
            target=self._read_loop, args=(proc,), daemon=True, name=f"embed-reader-{proc.pid}"
        ).start()
        _log(f"[embed] worker pid={proc.pid} starting ({self.model_name})")

    def _read_loop(self, proc: subprocess.Popen) -> None:
        try:
            for raw in proc.stdout:
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                if "ready" in msg:
                    if msg["ready"]:
                        self.dim = msg.get("dim")
                        self.load_seconds = msg.get("load_seconds")
                        self._ready.set()
                        _log(f"[embed] worker pid={proc.pid} ready: dim={self.dim} load={self.load_seconds}s")
                        # Callbacks flush queued writes, which means encode() and waiting
                        # for an answer that only THIS thread can deliver. Run them on
                        # their own thread, never on the reader.
                        callbacks = list(self._on_ready)
                        if callbacks:
                            threading.Thread(
                                target=self._run_ready_callbacks, args=(callbacks,),
                                daemon=True, name="embed-on-ready",
                            ).start()
                    else:
                        # The model itself cannot load; a respawn would fail the same way.
                        self.last_error = msg.get("error")
                        self._failed = True
                        _log(f"[embed] worker pid={proc.pid} FAILED to load model: {self.last_error}")
                    continue
                self._responses.put(msg)
        finally:
            try:
                rc = proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                rc = proc.poll()
            self._ready.clear()
            self._responses.put(None)  # wake a caller blocked in encode()
            _log(f"[embed] worker pid={proc.pid} exited rc={rc}")
            with self._lock:
                if self._proc is not proc:
                    return
                self._proc = None
                if not self._failed and self._restarts < self.MAX_RESTARTS:
                    self._restarts += 1
                    _log(f"[embed] respawning worker ({self._restarts}/{self.MAX_RESTARTS})")
                    self._spawn_locked()
                elif not self._failed:
                    self._failed = True
                    _log("[embed] worker restart budget exhausted; embeddings disabled for this process")

    def add_on_ready(self, callback: Callable[[], None]) -> None:
        self._on_ready.append(callback)

    def _run_ready_callbacks(self, callbacks: List[Callable[[], None]]) -> None:
        for cb in callbacks:
            try:
                cb()
            except Exception as e:  # noqa: BLE001
                _log(f"[embed] on_ready callback failed: {type(e).__name__}: {e}")

    def is_ready(self) -> bool:
        return self._ready.is_set()

    def wait_until_ready(self, timeout: float) -> bool:
        return self._ready.wait(timeout)

    # ---- requests --------------------------------------------------------

    def encode(self, texts: List[str], timeout: float = EMBEDDING_TIMEOUT_SEC) -> Optional[List[np.ndarray]]:
        """Embed texts. Returns None when the worker is not ready, dies, or misses the deadline."""
        if not self._ready.is_set():
            return None
        proc = self._proc
        if proc is None or proc.stdin is None:
            return None
        with self._request_lock:
            while True:  # drop stale answers from a request that timed out earlier
                try:
                    self._responses.get_nowait()
                except queue.Empty:
                    break
            self._next_id += 1
            rid = self._next_id
            try:
                proc.stdin.write((json.dumps({"id": rid, "texts": texts}) + "\n").encode("utf-8"))
                proc.stdin.flush()
            except (OSError, ValueError) as e:
                _log(f"[embed] write to worker failed: {type(e).__name__}: {e}")
                return None
            end = time.monotonic() + timeout
            while True:
                remaining = end - time.monotonic()
                if remaining <= 0:
                    _log(f"[embed] no answer within {timeout:.0f}s; killing worker pid={proc.pid}")
                    self._kill(proc)
                    return None
                try:
                    msg = self._responses.get(timeout=remaining)
                except queue.Empty:
                    continue
                if msg is None:  # worker exited
                    return None
                if msg.get("id") != rid:
                    continue  # late answer to an earlier, timed-out request
                if "vectors" not in msg:
                    _log(f"[embed] worker error: {msg.get('error')}")
                    return None
                return [np.asarray(v, dtype=np.float32) for v in msg["vectors"]]

    def _kill(self, proc: subprocess.Popen) -> None:
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass


class VectorStore:
    """
    Vector storage for semantic similarity search.

    Stores embeddings in SQLite for persistent semantic memory. Embeddings come
    from the EmbeddingWorker process; until it is ready, writes are queued and
    searches return nothing. Gracefully degrades if sentence-transformers is not
    installed.
    """

    # Cache at module level - check once, use forever
    _ST_AVAILABLE = None
    _ST_CHECKED = False

    # Kept for compatibility with older callers/tests. The model no longer lives
    # in this process, so these stay None / unused.
    _preloaded_model = None
    _LOAD_LOCK = threading.Lock()

    def __init__(self, codebase_path: str, embedding_model: str = "all-MiniLM-L6-v2",
                 encode_timeout: float = EMBEDDING_TIMEOUT_SEC):
        """
        Initialize vector store

        Args:
            codebase_path: Path to the codebase
            embedding_model: Name of the sentence-transformers model
            encode_timeout: Seconds to wait for one embedding request
        """
        self.codebase_path = Path(codebase_path)
        self.memory_path = self.codebase_path / ".codebase-memory"
        self.db_path = self.memory_path / "vectors.db"
        self.embedding_model_name = embedding_model
        self.encode_timeout = float(encode_timeout)

        self._embedding_model = None  # compat; never set
        self._embedding_available = None
        self._warmup_thread = None
        self._warmup_started = False
        self._worker: Optional[EmbeddingWorker] = None
        self._pending_writes: List[tuple] = []
        self._pending_lock = threading.Lock()

        # Initialize database
        self._init_db()

    def _check_embedding_available(self) -> bool:
        """Check if sentence-transformers is installed (cached; never imports it)."""
        if VectorStore._ST_CHECKED:
            return VectorStore._ST_AVAILABLE
        if self._embedding_available is not None:
            return self._embedding_available

        VectorStore._ST_CHECKED = True
        try:
            import importlib.util
            spec = importlib.util.find_spec("sentence_transformers")
            if spec is not None:
                VectorStore._ST_AVAILABLE = True
                self._embedding_available = True
                return True
        except Exception:
            pass

        VectorStore._ST_AVAILABLE = False
        self._embedding_available = False
        return False

    def ensure_warmup_started(self):
        """Start the embedding worker process (idempotent, never blocks on the load)."""
        if self._warmup_started:
            return
        self._warmup_started = True
        if not self._check_embedding_available():
            _log("[embed] sentence-transformers not installed; semantic memory disabled")
            return
        self._worker = EmbeddingWorker.get(self.embedding_model_name)
        self._worker.add_on_ready(self._flush_pending_writes)
        self._worker.start()
        if self._worker.is_ready():
            self._flush_pending_writes()

    def _start_warmup(self):
        """Compatibility alias for ensure_warmup_started()."""
        self._warmup_started = False
        self.ensure_warmup_started()

    def is_model_ready(self) -> bool:
        """True once the worker process has loaded the model (non-blocking)."""
        return self._worker is not None and self._worker.is_ready()

    def wait_until_ready(self, timeout: float = 120.0) -> bool:
        """Block until embeddings are available or the timeout passes (tests, scripts)."""
        self.ensure_warmup_started()
        return self._worker.wait_until_ready(timeout) if self._worker else False

    @classmethod
    def wait_if_loading(cls, timeout: float = 90.0) -> None:
        """No-op kept for callers: the model load happens in another process, so
        nothing in this process contends with it."""
        return

    def _get_embedding_model(self):
        """Compatibility shim: returns the worker handle once ready, else None."""
        return self._worker if self.is_model_ready() else None

    def _init_db(self):
        """Initialize SQLite database with vectors table"""
        self.memory_path.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create vectors table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vectors (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                metadata_json TEXT,
                embedding BLOB,
                created_at TEXT NOT NULL
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_category
            ON vectors(category)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_created
            ON vectors(created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_topic
            ON vectors(topic)
        """)

        conn.commit()
        conn.close()

    def _embedding_to_blob(self, embedding: np.ndarray) -> bytes:
        """Convert numpy array to SQLite BLOB"""
        return embedding.astype(np.float32).tobytes()

    def _blob_to_embedding(self, blob: bytes) -> np.ndarray:
        """Convert SQLite BLOB to numpy array"""
        return np.frombuffer(blob, dtype=np.float32)

    def _compute_embedding(self, text: str) -> Optional[np.ndarray]:
        """Compute embedding for text via the worker; None if unavailable within the timeout."""
        if not self.is_model_ready():
            return None
        vectors = self._worker.encode([text], timeout=self.encode_timeout)
        return vectors[0] if vectors else None

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors"""
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def add(
        self,
        topic: str,
        content: str,
        category: str = "findings",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Add content with embedding to vector store

        Args:
            topic: Topic name
            content: Content to store
            category: Category for organization
            metadata: Additional metadata

        Returns:
            Vector ID if successful, "queued" while the worker is still loading,
            None if embeddings are unavailable
        """
        if not self._check_embedding_available():
            return None
        self.ensure_warmup_started()

        # Worker not ready yet: queue the write instead of blocking the caller
        if not self.is_model_ready():
            self._queue_pending_write(topic, content, category, metadata)
            return "queued"

        self._flush_pending_writes()
        return self._do_add(topic, content, category, metadata)

    def _do_add(self, topic, content, category, metadata):
        """Actually compute embedding and store in DB."""
        vector_id = str(uuid.uuid4())

        embedding = self._compute_embedding(f"{topic}. {content}")
        if embedding is None:
            return None

        metadata_json = json.dumps(metadata or {})

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO vectors (id, topic, content, category, metadata_json, embedding, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            vector_id,
            topic,
            content,
            category,
            metadata_json,
            self._embedding_to_blob(embedding),
            datetime.now().isoformat()
        ))

        conn.commit()
        conn.close()

        return vector_id

    def _queue_pending_write(self, topic, content, category, metadata):
        """Queue a write to be processed once the worker is ready."""
        with self._pending_lock:
            self._pending_writes.append((topic, content, category, metadata))

    def _flush_pending_writes(self):
        """Flush queued writes now that the worker is ready (also run from the worker's ready callback)."""
        if not self.is_model_ready():
            return
        with self._pending_lock:
            pending = list(self._pending_writes)
            self._pending_writes.clear()
        for t, c, cat, meta in pending:
            try:
                if self._do_add(t, c, cat, meta) is None:
                    self._queue_pending_write(t, c, cat, meta)  # worker went away; keep it for later
            except Exception:
                pass

    def search(
        self,
        query: str,
        limit: int = 5,
        category: Optional[str] = None,
        min_score: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Semantic similarity search

        Args:
            query: Search query in natural language
            limit: Maximum number of results
            category: Filter by category (optional)
            min_score: Minimum similarity score (0-1)

        Returns:
            List of results with similarity scores
        """
        if not self._check_embedding_available():
            return []
        self.ensure_warmup_started()

        # Never block on the worker's load: return empty until it is ready
        if not self.is_model_ready():
            return []

        self._flush_pending_writes()

        # Compute query embedding
        query_embedding = self._compute_embedding(query)
        if query_embedding is None:
            return []

        # Query database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        sql = "SELECT id, topic, content, category, metadata_json, embedding FROM vectors"
        params = []

        if category:
            sql += " WHERE category = ?"
            params.append(category)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        # Compute similarities and rank
        results = []
        for row in rows:
            vector_id, topic, content, cat, metadata_json, embedding_blob = row
            embedding = self._blob_to_embedding(embedding_blob)

            score = self._cosine_similarity(query_embedding, embedding)

            if score >= min_score:
                results.append({
                    "id": vector_id,
                    "topic": topic,
                    "content": content,
                    "category": cat,
                    "metadata": json.loads(metadata_json) if metadata_json else {},
                    "score": score
                })

        # Sort by score descending and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def get_by_id(self, vector_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve specific entry by ID

        Args:
            vector_id: The vector entry ID

        Returns:
            Entry data or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, topic, content, category, metadata_json, created_at
            FROM vectors WHERE id = ?
        """, (vector_id,))

        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        vector_id, topic, content, category, metadata_json, created_at = row

        return {
            "id": vector_id,
            "topic": topic,
            "content": content,
            "category": category,
            "metadata": json.loads(metadata_json) if metadata_json else {},
            "created_at": created_at
        }

    def delete(self, vector_id: str) -> bool:
        """
        Remove entry from vector store

        Args:
            vector_id: The vector entry ID to delete

        Returns:
            True if deleted, False if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM vectors WHERE id = ?", (vector_id,))
        affected = cursor.rowcount

        conn.commit()
        conn.close()

        return affected > 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector store

        Returns:
            Statistics including count, categories, model info
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total count
        cursor.execute("SELECT COUNT(*) FROM vectors")
        total = cursor.fetchone()[0]

        # Count by category
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM vectors
            GROUP BY category
        """)
        categories = dict(cursor.fetchall())

        conn.close()

        return {
            "db_path": str(self.db_path),
            "total_entries": total,
            "categories": categories,
            "embedding_model": self.embedding_model_name,
            "embeddings_available": self._check_embedding_available(),
            "embedding_worker_ready": self.is_model_ready(),
            "pending_writes": len(self._pending_writes),
        }

    def list_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        List all entries in a category

        Args:
            category: Category name

        Returns:
            List of entries in the category
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, topic, content, created_at
            FROM vectors
            WHERE category = ?
            ORDER BY created_at DESC
        """, (category,))

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "topic": row[1],
                "content": row[2],
                "created_at": row[3]
            }
            for row in rows
        ]
