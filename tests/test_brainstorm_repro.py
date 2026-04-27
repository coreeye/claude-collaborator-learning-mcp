"""Reproducer for the brainstorm-via-MCP hang.

Spawns a fresh MCP server (`py -m claude_collaborator.server`), drives it over
stdio with the official mcp client, and times a brainstorm tool call end-to-end.

Run directly:

    py -u tests/test_brainstorm_repro.py

Exit code:
    0  => brainstorm completed under 180s (acceptable)
    1  => brainstorm exceeded the 600s hard timeout (hung)
    2  => any earlier-stage failure (init, switch_codebase, etc.)

The point: this matches what Claude Code does when invoking brainstorm,
including a `progressToken` so the throttled progress-notification path is
exercised. If THIS hangs, the throttling/notification logic is the bug.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


HARD_TIMEOUT_SEC = 600       # if a single tool call takes longer, declare a hang
ACCEPT_TIMEOUT_SEC = 180     # under this we call it healthy

CODEBASE = r"C:\source\repos\BoneXpertCode"


async def run() -> int:
    params = StdioServerParameters(
        command="py",
        args=["-m", "claude_collaborator.server"],
        env={
            **os.environ,
            "CODEBASE_PATH": CODEBASE,
            # ensure stdout from the *server* doesn't get buffered
            "PYTHONUNBUFFERED": "1",
        },
    )

    print(f"[t+0.00] spawning fresh MCP server", flush=True)
    t_spawn = time.monotonic()

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            print(f"[t+{time.monotonic()-t_spawn:.2f}] initializing", flush=True)
            await asyncio.wait_for(session.initialize(), timeout=60)

            print(f"[t+{time.monotonic()-t_spawn:.2f}] switching codebase", flush=True)
            try:
                await asyncio.wait_for(
                    session.call_tool("switch_codebase", {"path": CODEBASE}),
                    timeout=120,
                )
            except asyncio.TimeoutError:
                print("FAIL: switch_codebase hung > 120s", flush=True)
                return 2
            print(f"[t+{time.monotonic()-t_spawn:.2f}] switch_codebase ok", flush=True)

            # --- the actual reproducer: brainstorm with a progressToken ---
            t_brainstorm = time.monotonic()
            print(f"[t+{time.monotonic()-t_spawn:.2f}] calling brainstorm (hard timeout {HARD_TIMEOUT_SEC}s)", flush=True)

            # ClientSession.call_tool sets _meta.progressToken automatically,
            # which is what triggers the server's progress-notification path.
            try:
                result = await asyncio.wait_for(
                    session.call_tool(
                        "brainstorm",
                        {
                            "challenge": "Test BoneXpert mTLS without a real PACS. "
                                         "Quickest ways to exercise both incoming and "
                                         "outgoing channels?",
                            "context": "BoneXpert is on Windows, MSIX-installed, runs as a service. "
                                       "Listener port 2047/2762, fo-dicom 5.2.5 underneath."
                        },
                    ),
                    timeout=HARD_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                elapsed = time.monotonic() - t_brainstorm
                print(f"\n*** HANG REPRODUCED ***", flush=True)
                print(f"brainstorm did not return within {HARD_TIMEOUT_SEC}s "
                      f"(actual wait: {elapsed:.1f}s)", flush=True)
                return 1

            elapsed = time.monotonic() - t_brainstorm
            content_chars = sum(
                len(getattr(c, "text", "")) for c in result.content
            ) if result and result.content else 0

            print(f"[t+{time.monotonic()-t_spawn:.2f}] brainstorm returned in "
                  f"{elapsed:.1f}s ({content_chars} chars)", flush=True)

            if elapsed > ACCEPT_TIMEOUT_SEC:
                print(f"WARN: completed but slow (>{ACCEPT_TIMEOUT_SEC}s threshold)",
                      flush=True)

            print("\n--- first 300 chars of result ---", flush=True)
            text = "".join(getattr(c, "text", "") for c in result.content or [])
            print(text[:300], flush=True)

            return 0 if elapsed <= ACCEPT_TIMEOUT_SEC else 0  # soft pass even if slow


def main() -> int:
    try:
        return asyncio.run(run())
    except KeyboardInterrupt:
        print("\nInterrupted by user", flush=True)
        return 130


if __name__ == "__main__":
    sys.exit(main())
