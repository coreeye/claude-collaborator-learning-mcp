"""
End-to-end MCP protocol test.

Starts the actual MCP server as a subprocess (exactly like Claude Code does)
and sends JSON-RPC messages to it, with hard timeouts.

Run: py -3 tests/test_mcp_e2e.py
"""

import subprocess
import json
import sys
import os
import time
import threading

PYTHON = sys.executable
SERVER_MODULE = "claude_collaborator.server"
CODEBASE = "C:/source/repos/BoneXpertCode"
TIMEOUT = 20  # seconds per tool call


class MCPClient:
    def __init__(self):
        env = {**os.environ, "CODEBASE_PATH": CODEBASE}
        self.proc = subprocess.Popen(
            [PYTHON, "-m", SERVER_MODULE],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=CODEBASE,
            env=env,
        )
        self._id = 0
        self._stderr_lines = []
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_thread.start()

    def _drain_stderr(self):
        while True:
            line = self.proc.stderr.readline()
            if not line:
                break
            self._stderr_lines.append(line.decode("utf-8", errors="replace").rstrip())

    def send(self, method, params=None):
        self._id += 1
        msg = {"jsonrpc": "2.0", "method": method, "id": self._id}
        if params:
            msg["params"] = params
        # MCP Python SDK reads one JSON message per line (no HTTP framing)
        line = json.dumps(msg) + "\n"
        self.proc.stdin.write(line.encode("utf-8"))
        self.proc.stdin.flush()
        return self._id

    def notify(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method}
        if params:
            msg["params"] = params
        line = json.dumps(msg) + "\n"
        self.proc.stdin.write(line.encode("utf-8"))
        self.proc.stdin.flush()

    def recv(self, timeout=TIMEOUT):
        """Read one JSON-RPC response with timeout."""
        result = [None]
        error = [None]

        def _read():
            try:
                # MCP Python SDK writes one JSON message per line
                line = self.proc.stdout.readline()
                if not line:
                    error[0] = "EOF"
                    return
                result[0] = json.loads(line)
            except Exception as e:
                error[0] = str(e)

        t = threading.Thread(target=_read, daemon=True)
        t.start()
        t.join(timeout=timeout)

        if t.is_alive():
            return None, f"TIMEOUT after {timeout}s"
        if error[0]:
            return None, error[0]
        return result[0], None

    def call_tool(self, name, arguments, timeout=TIMEOUT):
        """Send tools/call and wait for response."""
        self.send("tools/call", {"name": name, "arguments": arguments})
        return self.recv(timeout=timeout)

    def close(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()

    @property
    def stderr_output(self):
        return "\n".join(self._stderr_lines[-10:])


def main():
    print("=" * 60)
    print("MCP End-to-End Protocol Test")
    print("=" * 60)

    client = MCPClient()
    total_start = time.time()

    try:
        # 1. Initialize
        print("\n[1] initialize...", end=" ", flush=True)
        t = time.time()
        client.send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0.1"},
        })
        resp, err = client.recv(timeout=10)
        elapsed = time.time() - t
        if err:
            print(f"FAIL ({elapsed:.1f}s): {err}")
            print(f"stderr: {client.stderr_output}")
            return
        print(f"OK ({elapsed:.1f}s)")

        # 2. Send initialized notification
        client.notify("notifications/initialized")
        time.sleep(0.2)

        # 3. Test session_status (light tool, no embeddings)
        print("[2] session_status...", end=" ", flush=True)
        t = time.time()
        resp, err = client.call_tool("session_status", {})
        elapsed = time.time() - t
        if err:
            print(f"FAIL ({elapsed:.1f}s): {err}")
        else:
            text = resp.get("result", {}).get("content", [{}])[0].get("text", "")[:80]
            print(f"OK ({elapsed:.1f}s): {text}")

        # 4. Test learn (should be instant with queue)
        print("[3] learn...", end=" ", flush=True)
        t = time.time()
        resp, err = client.call_tool("learn", {
            "observation": "E2E test observation",
            "category": "patterns",
            "importance": "low",
        })
        elapsed = time.time() - t
        if err:
            print(f"FAIL ({elapsed:.1f}s): {err}")
        else:
            text = resp.get("result", {}).get("content", [{}])[0].get("text", "")
            print(f"OK ({elapsed:.1f}s): {text}")

        # 5. Test memory_search
        print("[4] memory_search...", end=" ", flush=True)
        t = time.time()
        resp, err = client.call_tool("memory_search", {"query": "architecture"})
        elapsed = time.time() - t
        if err:
            print(f"FAIL ({elapsed:.1f}s): {err}")
        else:
            text = resp.get("result", {}).get("content", [{}])[0].get("text", "")[:80]
            print(f"OK ({elapsed:.1f}s): {text}")

        # 6. Wait for model warmup, then test semantic search
        print("[5] waiting 12s for model warmup...", end=" ", flush=True)
        time.sleep(12)
        print("done")

        print("[6] memory_semantic_search...", end=" ", flush=True)
        t = time.time()
        resp, err = client.call_tool("memory_semantic_search", {
            "query": "architecture",
            "limit": 3,
        })
        elapsed = time.time() - t
        if err:
            print(f"FAIL ({elapsed:.1f}s): {err}")
            print(f"stderr: {client.stderr_output}")
        else:
            text = resp.get("result", {}).get("content", [{}])[0].get("text", "")[:120]
            print(f"OK ({elapsed:.1f}s): {text}")

        # 7. Second semantic search (should be fast)
        print("[7] memory_semantic_search (2nd)...", end=" ", flush=True)
        t = time.time()
        resp, err = client.call_tool("memory_semantic_search", {
            "query": "thread safety",
            "limit": 3,
        })
        elapsed = time.time() - t
        if err:
            print(f"FAIL ({elapsed:.1f}s): {err}")
            print(f"stderr: {client.stderr_output}")
        else:
            text = resp.get("result", {}).get("content", [{}])[0].get("text", "")[:120]
            print(f"OK ({elapsed:.1f}s): {text}")

        # 8. Test a code tool (goes through post-processing)
        print("[8] get_config...", end=" ", flush=True)
        t = time.time()
        resp, err = client.call_tool("get_config", {})
        elapsed = time.time() - t
        if err:
            print(f"FAIL ({elapsed:.1f}s): {err}")
        else:
            text = resp.get("result", {}).get("content", [{}])[0].get("text", "")[:80]
            print(f"OK ({elapsed:.1f}s): {text}")

    finally:
        client.close()

        # Cleanup test data
        import sqlite3
        try:
            conn = sqlite3.connect(f"{CODEBASE}/.codebase-memory/vectors.db")
            conn.execute("DELETE FROM vectors WHERE topic LIKE 'E2E%'")
            conn.commit()
            conn.close()
        except Exception:
            pass

        total = time.time() - total_start
        print(f"\n{'='*60}")
        print(f"Total: {total:.1f}s")
        if client._stderr_lines:
            print(f"\nServer stderr ({len(client._stderr_lines)} lines):")
            for line in client._stderr_lines[:15]:
                print(f"  {line}")


if __name__ == "__main__":
    main()
