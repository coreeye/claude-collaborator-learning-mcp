"""
Diagnostic tests for GLM collaboration tools (brainstorm, risk_check, get_alternative).

These tests help identify WHY GLM tools hang/timeout when called via MCP.

Run with:
    cd C:\source\claude-collaborator
    python -m pytest tests/test_glm_diagnostic.py -v -s

Or individual tests:
    python -m pytest tests/test_glm_diagnostic.py::TestGLMDiagnostic::test_01_api_key_present -v -s
"""

import os
import sys
import time
import asyncio
import unittest
import threading
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


class TestGLMDiagnostic(unittest.TestCase):
    """Step-by-step diagnostics to find where GLM tools break."""

    # ─── Step 1: Config & Environment ───────────────────────────

    def test_01_api_key_present(self):
        """Check that GLM_API_KEY is set in environment."""
        api_key = os.getenv("GLM_API_KEY")
        self.assertIsNotNone(api_key, "GLM_API_KEY not found. Check .env file.")
        self.assertTrue(len(api_key) > 10, f"GLM_API_KEY looks too short: '{api_key[:5]}...'")
        print(f"  OK: GLM_API_KEY found: {api_key[:8]}...{api_key[-4:]}")

    def test_02_glm_model_configured(self):
        """Check GLM_MODEL setting."""
        model = os.getenv("GLM_MODEL", "glm-5")
        print(f"  OK: GLM_MODEL: {model}")

    # ─── Step 2: SDK Import ─────────────────────────────────────

    def test_03_zai_sdk_import(self):
        """Check if zai SDK is importable (primary path)."""
        try:
            from zai import ZaiClient
            print(f"  OK: zai SDK available (primary path)")
        except ImportError:
            print(f"  FAIL: zai SDK NOT available, will use OpenAI fallback")

    def test_04_openai_sdk_import(self):
        """Check if openai SDK is importable (fallback path)."""
        try:
            from openai import OpenAI
            print(f"  OK: openai SDK available (fallback path)")
        except ImportError:
            self.fail("Neither zai nor openai SDK available. Install one: pip install openai")

    # ─── Step 3: GLMClient instantiation ────────────────────────

    def test_05_glm_client_init(self):
        """Check GLMClient can be instantiated."""
        from claude_collaborator.glm_client import GLMClient
        client = GLMClient()
        self.assertIsNotNone(client.api_key)
        self.assertEqual(client.base_url, "https://api.z.ai/api/paas/v4")
        self.assertEqual(client.timeout, 120)
        print(f"  OK: GLMClient created: model={client.model}, timeout={client.timeout}s")

    # ─── Step 4: Network connectivity ───────────────────────────

    def test_06_api_endpoint_reachable(self):
        """Check if the GLM API endpoint is reachable (TCP connect only)."""
        import socket
        host = "api.z.ai"
        port = 443
        timeout = 10

        start = time.time()
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            elapsed = time.time() - start
            print(f"  OK: {host}:{port} reachable in {elapsed:.2f}s")
        except (socket.timeout, socket.error) as e:
            elapsed = time.time() - start
            self.fail(f"Cannot reach {host}:{port} after {elapsed:.2f}s: {e}")

    def test_07_api_dns_resolution(self):
        """Check DNS resolution for the API endpoint."""
        import socket
        host = "api.z.ai"
        start = time.time()
        try:
            ips = socket.getaddrinfo(host, 443)
            elapsed = time.time() - start
            ip = ips[0][4][0] if ips else "unknown"
            print(f"  OK: DNS resolved {host} -> {ip} in {elapsed:.3f}s ({len(ips)} records)")
        except socket.gaierror as e:
            self.fail(f"DNS resolution failed for {host}: {e}")

    # ─── Step 5: Actual API call (fast, small) ──────────────────

    def test_08_api_call_small(self):
        """Make a minimal API call with short timeout to test auth & response."""
        from claude_collaborator.glm_client import GLMClient
        client = GLMClient()

        start = time.time()
        # Use explore with a tiny question and low max_tokens
        result = client.explore(
            question="Say 'hello' in one word.",
            context="",
            max_tokens=50
        )
        elapsed = time.time() - start

        self.assertIsNotNone(result)
        self.assertNotIn("Error", result, f"API returned error: {result}")
        print(f"  OK: API responded in {elapsed:.2f}s")
        print(f"  Response preview: {result[:100]}...")

    # ─── Step 6: Brainstorm specifically ────────────────────────

    def test_09_brainstorm_direct(self):
        """Call brainstorm directly on GLMClient (bypassing MCP)."""
        from claude_collaborator.glm_client import GLMClient
        client = GLMClient()

        start = time.time()
        result = client.brainstorm(
            challenge="Should I use async or sync for file processing?",
            context="Small batch of 10 files, each under 1MB",
            max_tokens=200
        )
        elapsed = time.time() - start

        self.assertIsNotNone(result)
        self.assertNotIn("Error", result, f"Brainstorm returned error: {result}")
        print(f"  OK: brainstorm() returned in {elapsed:.2f}s")
        print(f"  Response preview: {result[:150]}...")

    # ─── Step 7: Test via tool handler (as MCP would call it) ──

    def test_10_brainstorm_via_handler(self):
        """Call brainstorm through the tool handler (simulates MCP dispatch)."""
        test_dir = Path(__file__).parent.parent / "examples" / "simple-csharp"
        if not test_dir.exists():
            # Use a temp dir if example not available
            import tempfile
            test_dir = Path(tempfile.mkdtemp())

        from claude_collaborator.server import ClaudeCollaboratorServer
        server = ClaudeCollaboratorServer(str(test_dir))

        if not server.glm_available:
            self.skipTest("GLM not available on server")

        from claude_collaborator.tool_handlers import handle_brainstorm

        start = time.time()
        result = handle_brainstorm(server, {
            "challenge": "Test brainstorm via handler",
            "context": "This is a diagnostic test"
        })
        elapsed = time.time() - start

        self.assertIsNotNone(result)
        print(f"  OK: handle_brainstorm() returned in {elapsed:.2f}s")
        print(f"  Response preview: {str(result)[:150]}...")

    def test_11_risk_check_via_handler(self):
        """Call risk_check through the tool handler."""
        test_dir = Path(__file__).parent.parent / "examples" / "simple-csharp"
        if not test_dir.exists():
            import tempfile
            test_dir = Path(tempfile.mkdtemp())

        from claude_collaborator.server import ClaudeCollaboratorServer
        server = ClaudeCollaboratorServer(str(test_dir))

        if not server.glm_available:
            self.skipTest("GLM not available on server")

        from claude_collaborator.tool_handlers import handle_risk_check

        start = time.time()
        result = handle_risk_check(server, {
            "proposed_change": "Add a new parameter to a public method",
            "code": "public void Process(string input) { }"
        })
        elapsed = time.time() - start

        self.assertIsNotNone(result)
        print(f"  OK: handle_risk_check() returned in {elapsed:.2f}s")
        print(f"  Response preview: {str(result)[:150]}...")

    # ─── Step 8: Timeout behavior ───────────────────────────────

    def test_12_brainstorm_with_timeout(self):
        """Ensure brainstorm doesn't hang forever — enforce 30s timeout."""
        from claude_collaborator.glm_client import GLMClient
        client = GLMClient()

        result = [None]
        error = [None]

        def run():
            try:
                result[0] = client.brainstorm(
                    challenge="Complex architecture question about microservices",
                    context="Large monolith with 50+ services being decomposed",
                    max_tokens=500
                )
            except Exception as e:
                error[0] = e

        thread = threading.Thread(target=run, daemon=True)
        start = time.time()
        thread.start()
        thread.join(timeout=30)  # 30 second hard limit
        elapsed = time.time() - start

        if thread.is_alive():
            self.fail(f"brainstorm() HUNG — still running after 30s. "
                      f"This is likely the cause of MCP timeouts.")

        if error[0]:
            self.fail(f"brainstorm() errored after {elapsed:.2f}s: {error[0]}")

        print(f"  OK: brainstorm() completed in {elapsed:.2f}s (within 30s limit)")

    # ─── Step 9: Concurrent calls (MCP may dispatch multiple) ──

    def test_13_concurrent_glm_calls(self):
        """Test that multiple GLM calls don't deadlock."""
        from claude_collaborator.glm_client import GLMClient
        client = GLMClient()

        results = {}
        errors = {}

        def call_explore(name):
            try:
                results[name] = client.explore(
                    question=f"Test concurrent call {name}",
                    max_tokens=50
                )
            except Exception as e:
                errors[name] = e

        threads = []
        for name in ["call_1", "call_2"]:
            t = threading.Thread(target=call_explore, args=(name,), daemon=True)
            threads.append(t)

        start = time.time()
        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=30)

        elapsed = time.time() - start

        alive = [t for t in threads if t.is_alive()]
        if alive:
            self.fail(f"{len(alive)} concurrent GLM call(s) still hanging after 30s")

        if errors:
            print(f"  WARN: Errors in concurrent calls: {errors}")

        print(f"  OK: {len(results)} concurrent calls completed in {elapsed:.2f}s")


if __name__ == "__main__":
    unittest.main(verbosity=2)
