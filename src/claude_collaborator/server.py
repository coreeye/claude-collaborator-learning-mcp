#!/usr/bin/env python3
"""
claude-collaborator - Multi-AI MCP Server for Large Codebases

Claude (you) + GLM working together to understand complex codebases.
Generic, configurable - works with any C# codebase.
"""

import asyncio
import os
import time
import sys
import traceback
from pathlib import Path
from typing import Optional


# ---- debug trace logger ---------------------------------------------------
# Writes a timestamped line to a file in TEMP for every key step in the
# tool-call lifecycle. Survives stderr being captured/dropped by the MCP host.
# Each line is flushed immediately so a hung process leaves a usable trail.
#
# OFF by default. Enable by setting CLAUDE_COLLAB_DEBUG=1 in the MCP server's
# env block (e.g. in ~/.claude.json or ~/.claude/mcp.json). When off, _trace
# is a cheap no-op so this code path costs nothing in production.
_DEBUG_ENABLED = os.environ.get("CLAUDE_COLLAB_DEBUG", "").lower() in ("1", "true", "yes")
_DEBUG_LOG_PATH = Path(os.environ.get("TEMP", os.environ.get("TMP", "."))) / "claude_collaborator_debug.log"


def _trace(*parts) -> None:
    if not _DEBUG_ENABLED:
        return
    msg = " ".join(str(p) for p in parts)
    line = f"{time.strftime('%H:%M:%S')}.{int((time.time()%1)*1000):03d} pid={os.getpid()} {msg}\n"
    try:
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        pass
    try:
        print(line.rstrip("\n"), file=sys.stderr, flush=True)
    except Exception:
        pass


_trace("server.py module imported")
# --------------------------------------------------------------------------

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from claude_collaborator.code_analyzer import CSharpCodeAnalyzer
from claude_collaborator.memory_store import MemoryStore
from claude_collaborator.glm_client import GLMClient
from claude_collaborator.config import load_config
from claude_collaborator.server_middleware import ServerMiddleware
from claude_collaborator.tool_definitions import get_all_tools
from claude_collaborator.tool_handlers import TOOL_HANDLERS, NO_INIT_REQUIRED, GLM_STREAMING_HANDLERS

# Optional vector memory components
try:
    from claude_collaborator.memory_vector import VectorStore
    from claude_collaborator.memory_auto import AutoCapture
    from claude_collaborator.memory_context import ContextTracker
    from claude_collaborator.memory_cache import FileCache
    from claude_collaborator.memory_session import SessionState
    VECTOR_MEMORY_AVAILABLE = True
except ImportError:
    VECTOR_MEMORY_AVAILABLE = False


class ClaudeCollaboratorServer(ServerMiddleware):
    """MCP Server for multi-AI codebase collaboration"""

    def __init__(self, codebase_path: str = None):
        """Initialize the server with configurable codebase path"""
        # Load configuration
        self.config = load_config()

        # Component placeholders (initialized when codebase is set)
        self.codebase_path = None
        self.memory = None
        self.analyzer = None

        # Vector memory components (initialized when codebase is set, if available)
        self.vector_store = None
        self.auto_capture = None
        self.context_tracker = None
        self.file_cache = None
        self.session_state = None

        # Initialize middleware (auto-capture, GLM enrich, etc.)
        self._init_middleware()

        # Initialize GLM client (optional - independent of codebase)
        try:
            self.glm = GLMClient()
            self.glm_available = True
        except ValueError:
            self.glm = None
            self.glm_available = False

        # Create MCP server
        self.app = Server("claude-collaborator")

        # Register tools
        self._register_tools()

        # Store configured codebase path for lazy initialization
        # Priority: 1) passed argument, 2) config, 3) None (requires switch_codebase)
        self._configured_codebase_path = codebase_path
        if not self._configured_codebase_path:
            config_path = self.config.get("codebase_path")
            if config_path:
                self._configured_codebase_path = str(config_path)

        # DON'T initialize here - will be lazy-loaded in _ensure_codebase()
        # This prevents blocking the MCP server from starting

    def _initialize_codebase(self, path: Path):
        """Initialize analyzer and memory store for a codebase path"""
        if not path.exists():
            raise ValueError(f"Codebase path not found: {path}")

        self.codebase_path = path
        self.memory = MemoryStore(str(path))
        self.analyzer = CSharpCodeAnalyzer(str(path))

        # Initialize vector memory components if available
        if VECTOR_MEMORY_AVAILABLE:
            try:
                self.vector_store = VectorStore(str(path))
                self.auto_capture = AutoCapture(
                    self.vector_store,
                    self.memory,
                    enabled=self.config.get("auto_capture_enabled", True)
                )
                context_threshold = self.config.get("context_threshold", 50000)
                self.context_tracker = ContextTracker(
                    self.vector_store,
                    threshold_chars=context_threshold
                )

                cache_size = self.config.get("cache_size", 100)
                cache_ttl = self.config.get("cache_ttl", 3600)
                self.file_cache = FileCache(
                    self.vector_store,
                    max_entries=cache_size,
                    default_ttl=cache_ttl
                )

                self.session_state = SessionState(str(path))

                # Start embedding model warmup immediately so it's ready
                # by the time the first tool call needs it (~8s load time)
                self.vector_store.ensure_warmup_started()

            except Exception as e:
                print(f"Warning: Vector memory initialization failed: {e}", file=sys.stderr)
                self.vector_store = None
                self.auto_capture = None
                self.context_tracker = None
                self.file_cache = None
                self.session_state = None
        else:
            self.file_cache = None
            self.session_state = None

    def _ensure_codebase(self):
        """
        Ensure codebase is initialized (lazy loading).

        Called on first tool access instead of during __init__
        to prevent blocking the MCP server from starting.
        """
        if self.codebase_path is not None:
            return

        if not self._configured_codebase_path:
            return

        try:
            self._initialize_codebase(Path(self._configured_codebase_path))
        except Exception as e:
            print(f"Warning: Could not initialize codebase: {e}", file=sys.stderr)
            print(f"  Path was: {self._configured_codebase_path}", file=sys.stderr)
            print(f"  Use switch_codebase() to select a codebase manually.", file=sys.stderr)

    def switch_codebase(self, path: str) -> dict:
        """Switch to a different codebase."""
        new_path = Path(path)

        if not new_path.is_absolute():
            new_path = Path.cwd() / new_path

        new_path = new_path.resolve()

        if not new_path.exists():
            return {"success": False, "error": f"Path not found: {new_path}"}

        if not new_path.is_dir():
            return {"success": False, "error": f"Path is not a directory: {new_path}"}

        try:
            self._initialize_codebase(new_path)

            cs_files = list(new_path.rglob("*.cs"))
            projects = list(new_path.rglob("*.csproj"))
            solutions = [s.name for s in new_path.rglob("*.sln")]

            return {
                "success": True,
                "codebase_path": str(new_path),
                "cs_files_count": len(cs_files),
                "projects_count": len(projects),
                "solutions": solutions,
                "memory_path": str(self.memory.memory_path) if self.memory else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_codebases(self, search_path: str = None) -> dict:
        """Discover codebases by searching for .sln and .git directories."""
        search_dir = Path(search_path) if search_path else Path.cwd()

        if not search_dir.exists():
            return {"success": False, "error": f"Search path not found: {search_dir}"}

        codebases = []

        # Find .sln files
        try:
            for sln in search_dir.rglob("*.sln"):
                if any(part.startswith('.') for part in sln.parts):
                    continue
                codebases.append({
                    "name": sln.stem,
                    "root": str(sln.parent),
                    "type": "solution",
                    "file": str(sln)
                })
        except PermissionError:
            pass

        # Find .git directories (limit depth)
        try:
            for git_dir in search_dir.rglob(".git"):
                if not git_dir.is_dir():
                    continue
                repo_root = git_dir.parent
                # Skip if already found via .sln
                if not any(cb["root"] == str(repo_root) for cb in codebases):
                    codebases.append({
                        "name": repo_root.name,
                        "root": str(repo_root),
                        "type": "git",
                        "file": str(git_dir)
                    })
        except PermissionError:
            pass

        return {
            "success": True,
            "search_path": str(search_dir),
            "codebases_count": len(codebases),
            "codebases": codebases
        }

    def _check_initialized(self) -> tuple[bool, str]:
        """Check if codebase is initialized. Triggers lazy init if configured."""
        self._ensure_codebase()

        if self.codebase_path is None:
            return False, (
                "No codebase selected. Use `switch_codebase` to select a codebase first.\n"
                "Example: switch_codebase(path=\"C:\\\\path\\\\to\\\\your\\\\project\")\n"
                "Or use `list_codebases` to discover available codebases."
            )
        return True, None

    def _dispatch_tool(self, name: str, arguments: dict, progress_callback=None) -> list[TextContent]:
        """Synchronous tool dispatch — runs in a thread executor to avoid blocking the event loop."""
        _trace(f"_dispatch_tool ENTRY name={name}")
        # Check if tool requires initialization
        if name not in NO_INIT_REQUIRED:
            is_ready, error_msg = self._check_initialized()
            if not is_ready:
                _trace(f"_dispatch_tool name={name} init NOT ready: {error_msg[:100]}")
                return self._process_tool_result(name, arguments,
                    [TextContent(type="text", text=error_msg)])

        # Start embedding model warmup on first tool call (AFTER codebase init)
        if self.vector_store and not self.vector_store._warmup_started:
            _trace(f"_dispatch_tool name={name} starting warmup")
            self.vector_store.ensure_warmup_started()

        def _invoke(handler):
            _trace(f"_invoke handler name={name} streaming={name in GLM_STREAMING_HANDLERS}")
            if name in GLM_STREAMING_HANDLERS:
                # Never let a GLM stream race the GIL-heavy embedding import/load
                # (e.g. brainstorm right after a session-start memory search that
                # kicked off lazy warmup). Bounded wait; no-op once loaded.
                if VECTOR_MEMORY_AVAILABLE:
                    VectorStore.wait_if_loading()
                return handler(self, arguments, progress_callback=progress_callback)
            return handler(self, arguments)

        # Memory/config tools get a fast path: no pre/post processing
        # (no auto-retrieve, no auto-capture, no GLM enrichment, no context tracking)
        FAST_PATH_TOOLS = {
            "learn", "session_learn", "memory_save", "memory_get",
            "memory_search", "memory_semantic_search", "memory_status",
            "memory_vector_stats", "context_offload", "context_retrieve",
            "context_stats", "session_status", "get_config",
            "switch_codebase", "list_codebases",
        }
        if name in FAST_PATH_TOOLS:
            handler = TOOL_HANDLERS.get(name)
            if not handler:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
            result_text = _invoke(handler)
            # Fire GLM enrichment in background for learn/session_learn
            # (non-blocking, just spawns a thread)
            try:
                self._auto_enrich_with_glm(name, arguments, result_text)
            except Exception:
                pass
            return [TextContent(type="text", text=result_text)]

        # Pre-tool: retrieve relevant context
        retrieved_context = self._auto_retrieve_context(name, arguments)
        self._current_retrieved_context = retrieved_context

        # Dispatch to handler
        handler = TOOL_HANDLERS.get(name)
        if not handler:
            return self._process_tool_result(name, arguments,
                [TextContent(type="text", text=f"Unknown tool: {name}")])

        result_text = _invoke(handler)

        # Auto-capture for certain tools
        from claude_collaborator.tool_handlers import AUTO_CAPTURE_TOOLS
        if name in AUTO_CAPTURE_TOOLS:
            self._maybe_auto_capture(name, arguments, result_text)

        return self._process_tool_result(name, arguments,
            [TextContent(type="text", text=result_text)])

    def _build_progress_callback(self, tool_name: str):
        """Build a progress_callback that bridges sync GLM streaming chunks
        back to the asyncio loop and emits MCP progress notifications.

        Throttled. GLM emits one chunk per token (~2000 chunks per
        brainstorm call); firing one MCP notification per chunk floods the
        stdio transport and overwhelms the client. We only emit a notification
        at most once per PROGRESS_INTERVAL_SEC, regardless of chunk count.

        Always logs to stderr so a stalled stream is visible in server logs.
        Sends MCP progress notifications only when the caller supplied a
        progressToken with the request.
        """
        PROGRESS_INTERVAL_SEC = 1.0  # at most one notification per second per call
        STDERR_INTERVAL_SEC = 5.0    # at most one stderr line per 5 seconds per call

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        token = None
        session = None
        try:
            ctx = self.app.request_context
            session = ctx.session
            meta = ctx.meta
            if meta is not None:
                token = getattr(meta, "progressToken", None)
        except (LookupError, AttributeError):
            pass

        _trace(f"_build_progress_callback name={tool_name} token={token!r} has_session={session is not None} has_loop={loop is not None}")

        # Mutable single-element holders so the closure can update them
        # without nonlocal declarations on each call.
        last_notification = [0.0]
        last_stderr = [0.0]
        first_chunk_logged = [False]
        notify_count = [0]

        def progress_callback(piece: str, total_chars: int) -> None:
            now = time.monotonic()
            if not first_chunk_logged[0]:
                first_chunk_logged[0] = True
                _trace(f"progress_callback FIRST chunk name={tool_name} total={total_chars}")
            if now - last_stderr[0] >= STDERR_INTERVAL_SEC:
                last_stderr[0] = now
                _trace(f"progress_callback name={tool_name} streaming total={total_chars}")
            if token is None or session is None or loop is None:
                return
            if now - last_notification[0] < PROGRESS_INTERVAL_SEC:
                return
            last_notification[0] = now
            try:
                fut = asyncio.run_coroutine_threadsafe(
                    session.send_progress_notification(
                        progress_token=token,
                        progress=float(total_chars),
                        total=None,
                        message=piece[-200:],
                    ),
                    loop,
                )
                notify_count[0] += 1
                if notify_count[0] in (1, 5, 20, 50):
                    _trace(f"progress_callback name={tool_name} notification #{notify_count[0]} scheduled (total={total_chars})")
            except Exception as e:
                _trace(f"progress_callback name={tool_name} notification FAILED: {type(e).__name__}: {e}")

        return progress_callback

    def _register_tools(self):
        """Register all MCP tools"""

        @self.app.list_tools()
        async def list_tools() -> list[Tool]:
            return get_all_tools()

        @self.app.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            _trace(f"call_tool ENTRY name={name} keys={list(arguments.keys())}")
            try:
                progress_callback = self._build_progress_callback(name)
                _trace(f"call_tool name={name} progress_callback built")

                # Run the entire tool dispatch in a thread to avoid blocking
                # the async event loop (embedding model loading, vector search,
                # and tool handlers can all block for seconds)
                _trace(f"call_tool name={name} dispatching to executor")
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self._dispatch_tool, name, arguments, progress_callback
                )
                _trace(f"call_tool name={name} EXIT ok ({sum(len(getattr(c,'text','')) for c in result)} chars)")
                return result

            except Exception as e:
                _trace(f"call_tool name={name} EXIT ERROR {type(e).__name__}: {e}")
                return self._process_tool_result(name, arguments,
                    [TextContent(type="text", text=f"Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}")])

    async def run(self):
        """Run the MCP server"""
        async with stdio_server() as (read_stream, write_stream):
            await self.app.run(
                read_stream,
                write_stream,
                self.app.create_initialization_options()
            )


def main():
    """Main entry point.

    Startup ordering matters a lot here. The sentence-transformers import
    (scipy/sklearn/torch) is CPU- and GIL-heavy. If it runs in a background
    thread once the asyncio loop is live, it contends for the GIL with both the
    stdio transport loop and any concurrent GLM stream — the first
    brainstorm/explore call would then take its first token minutes late
    (measured: 243s in-server vs ~5s for a direct API call). So instead we warm
    the model SYNCHRONOUSLY on the main thread BEFORE asyncio.run(): a one-time
    ~15-20s cost (loaded from the local HF cache, no network) that runs with no
    contention and is fully done before any tool is served. Handshake is delayed
    by that warm, which MCP clients tolerate; every tool call afterward — GLM or
    memory — runs against an already-loaded model.
    """
    import os
    import threading
    import time as _time

    # Warm the embedding model SYNCHRONOUSLY on the main thread, before the
    # asyncio loop starts. The sentence-transformers import (scipy/sklearn/torch)
    # is GIL-heavy; done here (single-threaded, pre-loop) it is a one-time
    # ~15-20s cost with no contention, and it then NEVER competes with a GLM
    # stream or the stdio transport loop. Loading it lazily in a background
    # thread instead lets that import contend for the GIL with the event loop
    # and any concurrent GLM stream, which is what caused first-call brainstorm
    # to take its first token minutes late. The model load reads from the local
    # HF cache (local_files_only), so this is fast and never hits the network.
    if os.environ.get("CODEBASE_PATH"):
        try:
            from claude_collaborator.memory_vector import VectorStore
            _vs = VectorStore(os.environ["CODEBASE_PATH"])
            if _vs._check_embedding_available():
                _t0 = _time.time()
                print("[main] warming embedding model (main thread)...", file=sys.stderr, flush=True)
                _vs._get_embedding_model()  # populates VectorStore._preloaded_model
                print(f"[main] embedding model ready ({_time.time() - _t0:.1f}s)", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"[main] embedding warm skipped: {e}", file=sys.stderr, flush=True)

    # Pre-warm DNS + TCP to the GLM endpoint. The FIRST GLM call (brainstorm/
    # explore/etc.) otherwise pays a cold getaddrinfo() for api.z.ai *while* the
    # embedding-model import storm (scipy/sklearn/torch) is hogging the GIL.
    # That combination has been observed to push the stream-open past
    # open_timeout — surfacing as a "hang" on the first call that then succeeds
    # on retry only because DNS is now cached. Priming the resolver here makes
    # the first real call's connect fast. Best-effort: never blocks, never raises.
    if os.environ.get("GLM_API_KEY"):
        def _prewarm_glm_connection():
            import socket
            from urllib.parse import urlparse
            try:
                host = urlparse("https://api.z.ai/api/paas/v4").hostname or "api.z.ai"
                infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
                if infos:
                    af, socktype, proto, _canon, sa = infos[0]
                    s = socket.socket(af, socktype, proto)
                    s.settimeout(10)  # per-socket only — never touch the global default
                    try:
                        s.connect(sa)
                    finally:
                        s.close()
                print("[main] GLM endpoint pre-warmed (DNS/TCP)", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"[main] GLM pre-warm skipped: {e}", file=sys.stderr, flush=True)

        threading.Thread(
            target=_prewarm_glm_connection,
            daemon=True,
            name="glm-prewarm",
        ).start()

    server = ClaudeCollaboratorServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
