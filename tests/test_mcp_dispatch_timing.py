"""
Diagnostic test: profiles every step of MCP tool dispatch.

Simulates exactly what happens when Claude Code calls a tool,
with per-step timing to find bottlenecks.

Run with:
    cd C:/source/claude-collaborator
    py -3 -m pytest tests/test_mcp_dispatch_timing.py -v -s --tb=short

Or run directly:
    py -3 tests/test_mcp_dispatch_timing.py
"""

import time
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
os.environ.setdefault("CODEBASE_PATH", "C:/source/repos/BoneXpertCode")

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

CODEBASE = "C:/source/repos/BoneXpertCode"
TIMEOUT = 20  # seconds max per step


def timed(label, fn, timeout=TIMEOUT):
    """Run fn, print timing, fail if exceeds timeout."""
    start = time.time()
    try:
        result = fn()
        elapsed = time.time() - start
        status = "SLOW!" if elapsed > timeout else "OK"
        print(f"  [{elapsed:6.1f}s] {status} {label}")
        if elapsed > timeout:
            print(f"           ^ EXCEEDED {timeout}s timeout!")
        return result, elapsed
    except Exception as e:
        elapsed = time.time() - start
        print(f"  [{elapsed:6.1f}s] ERROR {label}: {e}")
        return None, elapsed


def create_server():
    """Create server (simulates MCP server startup)."""
    from claude_collaborator.server import ClaudeCollaboratorServer
    return ClaudeCollaboratorServer(CODEBASE)


def test_learn_dispatch():
    """Profile the full learn tool dispatch path."""
    print("\n=== LEARN TOOL DISPATCH ===\n")

    server, t = timed("Create server", create_server)
    assert server is not None

    # Check initial state
    print(f"\n  State after server init:")
    print(f"    vector_store: {server.vector_store is not None}")
    print(f"    codebase_path: {server.codebase_path}")
    print(f"    glm_available: {server.glm_available}")

    # Step 1: _check_initialized (triggers _ensure_codebase)
    _, t = timed("_check_initialized (lazy init)", lambda: server._check_initialized())
    print(f"    vector_store after init: {server.vector_store is not None}")
    if server.vector_store:
        print(f"    warmup_started: {server.vector_store._warmup_started}")
        print(f"    model_ready: {server.vector_store.is_model_ready()}")

    # Step 2: ensure_warmup_started
    if server.vector_store and not server.vector_store._warmup_started:
        _, t = timed("ensure_warmup_started", lambda: server.vector_store.ensure_warmup_started())

    # Step 3: _auto_retrieve_context
    _, t = timed("_auto_retrieve_context",
                 lambda: server._auto_retrieve_context("learn", {"observation": "test"}))

    # Step 4: handler (learn)
    from claude_collaborator.tool_handlers import handle_learn
    result, t = timed("handle_learn (includes warmup wait)",
                      lambda: handle_learn(server, {
                          "observation": "Diagnostic test entry",
                          "category": "patterns",
                          "importance": "low"
                      }))
    print(f"    Result: {result}")

    # Step 5: _process_tool_result (should be SKIPPED for learn)
    from mcp.types import TextContent
    _, t = timed("_process_tool_result",
                 lambda: server._process_tool_result("learn", {}, [TextContent(type="text", text=result or "")]))

    # Cleanup
    import sqlite3
    conn = sqlite3.connect(f"{CODEBASE}/.codebase-memory/vectors.db")
    conn.execute("DELETE FROM vectors WHERE topic LIKE 'Diagnostic%'")
    conn.commit()
    conn.close()
    print("\n  Cleaned up test entry")


def test_full_dispatch_learn():
    """Profile _dispatch_tool('learn') end-to-end."""
    print("\n=== FULL _dispatch_tool('learn') ===\n")

    server, _ = timed("Create server", create_server)

    result, t = timed("_dispatch_tool('learn')",
                      lambda: server._dispatch_tool("learn", {
                          "observation": "Full dispatch timing test",
                          "category": "patterns",
                          "importance": "low"
                      }))
    if result:
        print(f"    Result: {result[0].text}")

    # Cleanup
    import sqlite3
    conn = sqlite3.connect(f"{CODEBASE}/.codebase-memory/vectors.db")
    conn.execute("DELETE FROM vectors WHERE topic LIKE 'Full dispatch%'")
    conn.commit()
    conn.close()


def test_full_dispatch_semantic_search():
    """Profile _dispatch_tool('memory_semantic_search') end-to-end."""
    print("\n=== FULL _dispatch_tool('memory_semantic_search') ===\n")

    server, _ = timed("Create server", create_server)

    result, t = timed("_dispatch_tool('memory_semantic_search')",
                      lambda: server._dispatch_tool("memory_semantic_search", {
                          "query": "architecture",
                          "limit": 3
                      }))
    if result:
        print(f"    Result: {result[0].text[:200]}")


def test_full_dispatch_memory_search():
    """Profile _dispatch_tool('memory_search') end-to-end."""
    print("\n=== FULL _dispatch_tool('memory_search') ===\n")

    server, _ = timed("Create server", create_server)

    result, t = timed("_dispatch_tool('memory_search')",
                      lambda: server._dispatch_tool("memory_search", {
                          "query": "architecture"
                      }))
    if result:
        print(f"    Result: {result[0].text[:200]}")


def test_full_dispatch_brainstorm():
    """Profile _dispatch_tool('brainstorm') end-to-end."""
    print("\n=== FULL _dispatch_tool('brainstorm') ===\n")

    server, _ = timed("Create server", create_server)

    result, t = timed("_dispatch_tool('brainstorm')",
                      lambda: server._dispatch_tool("brainstorm", {
                          "challenge": "Quick test",
                          "context": "Minimal context"
                      }),
                      timeout=30)
    if result:
        print(f"    Result: {result[0].text[:200]}")


if __name__ == "__main__":
    total_start = time.time()

    test_learn_dispatch()
    test_full_dispatch_learn()
    test_full_dispatch_semantic_search()
    test_full_dispatch_memory_search()

    print(f"\n{'='*50}")
    print(f"Total time: {time.time() - total_start:.1f}s")
