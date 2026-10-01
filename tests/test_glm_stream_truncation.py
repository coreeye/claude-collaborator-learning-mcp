"""
Tests for GLM stream handling on thinking models and topic derivation.
"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_collaborator.glm_client import GLMClient, DEFAULT_MAX_TOKENS, DEFAULT_MODEL
from claude_collaborator.tool_handlers import _topic_from_text


def _chunk(content=None, reasoning=None, finish=None):
    delta = SimpleNamespace(content=content, reasoning_content=reasoning)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=finish)])


class TestStreamCompletion(unittest.TestCase):
    def setUp(self):
        with patch.dict("os.environ", {"GLM_API_KEY": "test-key"}):
            self.client = GLMClient()

    def test_default_model_is_glm_5_3(self):
        self.assertEqual(DEFAULT_MODEL, "glm-5.3")

    def test_budget_default_leaves_room_for_reasoning(self):
        self.assertGreaterEqual(DEFAULT_MAX_TOKENS, 4096)

    def test_reasoning_only_truncation_raises(self):
        stream = [_chunk(reasoning="thinking..."), _chunk(finish="length")]
        with self.assertRaisesRegex(RuntimeError, "max_tokens"):
            self.client._stream_completion(lambda: iter(stream), None)

    def test_content_is_returned_when_present(self):
        stream = [_chunk(reasoning="thinking"), _chunk(content="* the answer"), _chunk(finish="stop")]
        self.assertEqual(self.client._stream_completion(lambda: iter(stream), None), "* the answer")

    def test_partial_content_with_length_is_kept(self):
        stream = [_chunk(content="partial answer"), _chunk(finish="length")]
        self.assertEqual(self.client._stream_completion(lambda: iter(stream), None), "partial answer")

    def test_reasoning_fallback_still_used_on_normal_stop(self):
        stream = [_chunk(reasoning="only reasoning"), _chunk(finish="stop")]
        self.assertEqual(self.client._stream_completion(lambda: iter(stream), None), "only reasoning")


class TestTopicFromText(unittest.TestCase):
    def test_version_numbers_not_split(self):
        self.assertEqual(
            _topic_from_text("Upgraded GLM model from glm-5 to glm-5.1. Same endpoint."),
            "Upgraded GLM model from glm-5 to glm-5.1",
        )

    def test_filename_not_split(self):
        self.assertTrue(_topic_from_text("Foo.cs is the entry point").startswith("Foo.cs is"))

    def test_capped_at_60_chars(self):
        self.assertEqual(len(_topic_from_text("x" * 100)), 60)


if __name__ == "__main__":
    unittest.main()
