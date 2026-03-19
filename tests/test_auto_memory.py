"""
Tests for automatic memory and context management
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_collaborator.memory_cache import FileCache
from claude_collaborator.memory_session import SessionState
from claude_collaborator.memory_vector import VectorStore


def test_file_cache():
    """Test file caching functionality"""
    print("Testing FileCache...")

    # Create a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock vector store (we'll mock the methods)
        class MockVectorStore:
            def __init__(self):
                self.entries = []

            def _check_embedding_available(self):
                return False  # Disable embeddings for this test

            def add(self, topic, content, category, metadata=None):
                self.entries.append({
                    "topic": topic,
                    "content": content,
                    "category": category,
                    "metadata": metadata
                })

        vector_store = MockVectorStore()
        cache = FileCache(vector_store, max_entries=3, default_ttl=3600)

        # Test 1: Cache miss
        result = cache.get("test.cs")
        assert result is None, "Cache should return None for non-existent file"
        print("  [PASS] Cache miss works correctly")

        # Test 2: Cache set and get
        content = "using System;\npublic class Test { }"
        cache.set("test.cs", content)
        result = cache.get("test.cs")
        assert result == content, "Cached content should match original"
        print("  [PASS] Cache set/get works correctly")

        # Test 3: Cache stats
        stats = cache.get_stats()
        assert stats["entries"] == 1, "Should have 1 entry"
        print("  [PASS] Cache stats work correctly")

        # Test 4: Max entries eviction
        cache.set("file1.cs", "content1")
        cache.set("file2.cs", "content2")
        cache.set("file3.cs", "content3")
        cache.set("file4.cs", "content4")  # Should evict oldest
        stats = cache.get_stats()
        assert stats["entries"] == 3, f"Should have 3 entries (max), got {stats['entries']}"
        print("  [PASS] Cache eviction works correctly")

        # Test 5: Clear all entries
        cache.clear()
        stats = cache.get_stats()
        assert stats["entries"] == 0, "All entries should be cleared"
        print("  [PASS] Cache clearing works correctly")

    print("[PASS] FileCache tests passed!\n")


def test_session_state():
    """Test session persistence functionality"""
    print("Testing SessionState...")

    with tempfile.TemporaryDirectory() as tmpdir:
        session = SessionState(tmpdir)

        # Test 1: Save and load state
        state = {
            "active_task": "refactor-auth",
            "task_status": "in_progress",
            "last_work": "2025-03-19T10:00:00"
        }
        result = session.save_state(state)
        assert result == True, "State should save successfully"
        print("  [PASS] State save works correctly")

        loaded = session.load_state()
        assert loaded["active_task"] == "refactor-auth", "Loaded state should match"
        print("  [PASS] State load works correctly")

        # Test 2: Active task management
        session.update_active_task("test-task", "in_progress")
        task = session.get_active_task()
        assert task["name"] == "test-task", "Active task should match"
        assert task["status"] == "in_progress", "Task status should match"
        print("  [PASS] Active task management works correctly")

        # Test 3: Work context
        session.save_work_context(
            tool_name="extract_class_structure",
            arguments={"file_path": "Test.cs"},
            result_summary="Found 2 classes..."
        )
        recent = session.get_recent_work(limit=1)
        assert len(recent) == 1, "Should have 1 recent work entry"
        assert recent[0]["tool"] == "extract_class_structure", "Tool name should match"
        print("  [PASS] Work context tracking works correctly")

        # Test 4: Session summary
        summary = session.get_session_summary()
        assert "codebase_path" in summary, "Summary should have codebase_path"
        assert summary["active_task"]["name"] == "test-task", "Summary should include active task"
        print("  [PASS] Session summary works correctly")

        # Test 5: Clear state
        session.clear_state()
        loaded = session.load_state()
        assert loaded == {}, "State should be empty after clear"
        print("  [PASS] State clearing works correctly")

    print("[PASS] SessionState tests passed!\n")


def test_server_methods():
    """Test server's automatic memory methods"""
    print("Testing Server Automatic Memory Methods...")

    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from claude_collaborator.server import ClaudeCollaboratorServer

    # Create server without codebase (starts uninitialized)
    server = ClaudeCollaboratorServer()

    # Test 1: Check methods exist
    assert hasattr(server, '_auto_retrieve_context'), "Should have _auto_retrieve_context method"
    assert hasattr(server, '_process_tool_result'), "Should have _process_tool_result method"
    assert hasattr(server, '_smart_compact'), "Should have _smart_compact method"
    print("  [PASS] All automatic memory methods exist")

    # Test 2: Test auto_retrieve_context with no vector store
    result = server._auto_retrieve_context("test_tool", {"pattern": "test"})
    assert result is None, "Should return None when no vector store"
    print("  [PASS] Auto-retrieve handles missing vector store correctly")

    # Test 3: Test process_tool_result with empty result
    from mcp.types import TextContent
    result = server._process_tool_result("test_tool", {}, [])
    assert result == [], "Should return empty list for empty input"
    print("  [PASS] Process tool result handles empty input correctly")

    # Test 4: Test process_tool_result with actual content
    content = [TextContent(type="text", text="Test result")]
    result = server._process_tool_result("test_tool", {}, content)
    assert len(result) == 1, "Should return one item"
    assert result[0].text == "Test result", "Text should match"
    print("  [PASS] Process tool result handles content correctly")

    # Test 5: Test _summarize_large_context_items with no context_tracker
    server._summarize_large_context_items()  # Should not crash
    print("  [PASS] Summarize handles missing context tracker correctly")

    print("[PASS] Server methods tests passed!\n")


def test_auto_capture_tools():
    """Test expanded auto-capture tools list"""
    print("Testing Auto-Capture Tools...")

    from claude_collaborator.memory_auto import AutoCapture

    # Check that new tools are in AUTO_CAPTURE_TOOLS
    new_tools = [
        "extract_class_structure",
        "get_file_summary",
        "find_class_usages",
        "find_implementations",
        "get_callers"
    ]

    for tool in new_tools:
        assert tool in AutoCapture.AUTO_CAPTURE_TOOLS, f"{tool} should be in AUTO_CAPTURE_TOOLS"
        print(f"  [PASS] {tool} is in AUTO_CAPTURE_TOOLS")

    print("[PASS] Auto-capture tools tests passed!\n")


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("Running Automatic Memory Tests")
    print("=" * 60)
    print()

    try:
        test_file_cache()
        test_session_state()
        test_server_methods()
        test_auto_capture_tools()

        print("=" * 60)
        print("[PASS] ALL TESTS PASSED!")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n[FAIL] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
