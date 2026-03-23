"""
Server middleware for automatic memory capture, context retrieval,
GLM auto-enrich, proactive suggestions, and result post-processing.
"""

import threading
import time
from typing import Any, Dict, Optional

from mcp.types import TextContent


class ServerMiddleware:
    """
    Mixin class providing middleware functionality for the MCP server.

    Handles:
    - Automatic memory capture of tool results
    - Pre-tool context retrieval from vector memory
    - GLM auto-enrichment in background threads
    - Proactive GLM suggestions
    - Tool result post-processing (truncation, context tracking)
    - Smart context compaction
    """

    # Context limits
    MAX_GLM_CONTEXT = 10000   # characters
    MAX_CODE_LINES = 500      # lines to send to GLM
    MAX_MEMORY_RESULTS = 3    # number of memory results to include
    MAX_TOOL_RESULT_SIZE = 1500  # max chars for tool result before truncation

    def _init_middleware(self):
        """Initialize middleware state. Call from server __init__."""
        self._current_retrieved_context = None
        self._glm_enrich_results: Dict[str, Any] = {}
        self._glm_enrich_lock = threading.Lock()

        # Tools that auto-enrich with GLM
        # Auto-enrich with GLM for tools where a second AI perspective adds depth.
        # Runs in background, stores insights in vector memory.
        self._auto_enrich_tools = {
            "learn": "Extract deeper insights from this observation. What non-obvious implications or related patterns should be noted?\n\n{result}",
            "session_learn": "Analyze this session summary. Identify recurring themes, knowledge gaps, or patterns across the work done:\n\n{result}",
            "lookup_convention": "Evaluate this convention. Should it evolve? Are there better alternatives used in modern C#?\n\n{result}",
            "get_file_summary": "Based on this file summary, what areas deserve closer inspection? Any complexity or design concerns?\n\n{result}",
            "find_similar_code": "Compare these similar code patterns. Which approach is better and why? Any consistency issues?\n\n{result}",
        }

    def _truncate_for_glm(self, content: str, max_chars: int = None) -> str:
        """Truncate content to avoid GLM context errors"""
        limit = max_chars or self.MAX_GLM_CONTEXT
        if len(content) > limit:
            return content[:limit] + "\n\n... [truncated]"
        return content

    def _maybe_auto_capture(self, tool_name: str, arguments: dict, result: str) -> Optional[str]:
        """Attempt auto-capture of tool result if available and significant"""
        if self.auto_capture:
            captured_id = self.auto_capture.capture_tool_result(tool_name, arguments, result)
            return captured_id
        return None

    # ==================== AUTOMATIC MEMORY & CONTEXT MANAGEMENT ====================

    def _auto_retrieve_context(self, tool_name: str, arguments: dict) -> Optional[str]:
        """
        Automatically retrieve relevant memories before tool execution.
        """
        if not self.vector_store:
            return None

        if not self.vector_store._check_embedding_available():
            return None

        # Don't block waiting for model to load — skip if still warming up
        if not self.vector_store.is_model_ready():
            return None

        # Build query from tool name and key arguments
        query_parts = [tool_name]

        # Include active task name for better relevance
        if self.session_state:
            try:
                state = self.session_state.get_state()
                active_task = state.get("active_task")
                if active_task:
                    query_parts.append(active_task)
            except Exception:
                pass

        # Extract meaningful arguments for query
        for key in ["pattern", "topic", "file_path", "class_name", "target", "project", "query", "interface_name",
                     "observation", "challenge"]:
            if key in arguments and arguments[key]:
                query_parts.append(str(arguments[key]))

        query = " ".join(query_parts)

        # Retrieve relevant memories
        try:
            results = self.vector_store.search(query, limit=3)

            if not results:
                return None

            context_lines = ["**Relevant Memory:**"]
            for r in results:
                content_preview = r['content'][:150] + "..." if len(r['content']) > 150 else r['content']
                context_lines.append(f"- {r['topic']}: {content_preview}")

            return "\n".join(context_lines)
        except Exception:
            return None

    # ==================== GLM AUTO-ENRICH & PROACTIVE SUGGESTIONS ====================

    def _auto_enrich_with_glm(self, tool_name: str, arguments: dict, result_text: str):
        """Run GLM enrichment in background thread (non-blocking).

        Stores insights in vector memory so they're available for future
        semantic searches, not just discarded into a dict.
        """
        if not self.glm_available:
            return

        if not self.config.get("auto_glm_enrich", True):
            return

        if tool_name not in self._auto_enrich_tools:
            return

        def run_glm_enrich():
            try:
                prompt_template = self._auto_enrich_tools[tool_name]
                prompt = prompt_template.format(result=self._truncate_for_glm(result_text, 5000))

                glm_response = self.glm.explore(
                    question=f"Auto-enrich for {tool_name}",
                    context=prompt,
                    max_tokens=512
                )

                # Store GLM insights in vector memory for future retrieval
                if self.vector_store and glm_response and len(glm_response) > 50:
                    arg_summary = str(arguments)[:80]
                    self.vector_store.add(
                        topic=f"glm:{tool_name}:{arg_summary}",
                        content=glm_response,
                        category="decisions",
                        metadata={
                            "source": "auto_enrich",
                            "tool": tool_name,
                            "arguments": str(arguments)[:200],
                        }
                    )
            except Exception:
                pass

        thread = threading.Thread(target=run_glm_enrich, daemon=True)
        thread.start()

    def _get_glm_suggestion(self, tool_name: str, arguments: dict, result_text: str) -> Optional[str]:
        """Generate proactive GLM suggestions based on context."""
        if not self.glm_available:
            return None

        if not self.config.get("glm_proactive_suggestions", True):
            return None

        # Scenario 1: Large result
        if len(result_text) > 5000:
            return (
                "\n\n---\n"
                "**\U0001f4a1 GLM Tip:** This result is quite large. "
                "Use `summarize_large_file` to have GLM analyze it comprehensively."
            )

        # Scenario 2: After discovery tools
        discovery_tools = ["find_class_usages", "find_implementations", "find_references",
                          "list_dependencies", "find_similar_code", "lookup_convention"]
        if tool_name in discovery_tools:
            return (
                "\n\n---\n"
                f"**\U0001f4a1 GLM Tip:** Want deeper insights? Use `glm_explore` to ask "
                "GLM for research perspectives on these findings."
            )

        # Scenario 3: Analysis tools
        analysis_tools = ["extract_class_structure", "get_file_summary",
                         "explore_project", "analyze_architecture"]
        if tool_name in analysis_tools:
            return (
                "\n\n---\n"
                f"**\U0001f4a1 GLM Tip:** Use `get_alternative` to get GLM's perspective "
                "on different approaches before proceeding."
            )

        # Scenario 4: Pattern matching
        if "pattern" in arguments or tool_name in ["find_similar_code", "lookup_convention"]:
            return (
                "\n\n---\n"
                "**\U0001f4a1 GLM Tip:** Use `risk_check` before making changes to identify "
                "potential issues and edge cases."
            )

        return None

    # ==================== RESULT POST-PROCESSING ====================

    def _process_tool_result(
        self,
        tool_name: str,
        arguments: dict,
        result: list[TextContent]
    ) -> list[TextContent]:
        """
        Post-process tool result: capture, track context, check compaction.
        Truncates large results to prevent conversation context overflow.
        """
        if not result or len(result) == 0:
            return result

        result_text = result[0].text if hasattr(result[0], 'text') else str(result[0])

        # 1. Truncate for response
        display_text = result_text
        if len(result_text) > self.MAX_TOOL_RESULT_SIZE:
            first_part = result_text[:500]
            last_part = result_text[-200:] if len(result_text) > 700 else ""
            truncated_note = f"\n\n... [RESULT TRUNCATED: {len(result_text)} chars total, saved to memory] ...\n\n"
            display_text = first_part + truncated_note + last_part

        # 2. Auto-capture to vector memory (full result)
        try:
            self._maybe_auto_capture(tool_name, arguments, result_text)
        except Exception:
            pass

        # 3. Track context size
        try:
            if self.context_tracker:
                self.context_tracker.add_context(
                    content=result_text,
                    metadata={"tool": tool_name, "arguments": str(arguments)},
                    item_type="tool_result"
                )
        except Exception:
            pass

        # 4. Save work context to session state
        try:
            if self.session_state:
                result_summary = display_text[:100] + "..." if len(display_text) > 100 else display_text
                self.session_state.save_work_context(
                    tool_name=tool_name,
                    arguments=arguments,
                    result_summary=result_summary
                )
        except Exception:
            pass

        # 5. GLM Auto-enrich (background)
        try:
            self._auto_enrich_with_glm(tool_name, arguments, result_text)
        except Exception:
            pass

        # 6. GLM Proactive Suggestions
        try:
            suggestion = self._get_glm_suggestion(tool_name, arguments, result_text)
            if suggestion:
                display_text += suggestion
        except Exception:
            pass

        return [TextContent(type="text", text=display_text)]

    # ==================== SMART COMPACTION ====================

    def _smart_compact(self, current_tool: str, current_args: dict):
        """Intelligently compact context when approaching limits."""
        if not self.context_tracker or not self.vector_store:
            return

        stats = self.context_tracker.get_stats()
        utilization = stats['utilization']

        query_parts = [current_tool]
        for key in ('pattern', 'topic', 'query', 'file_path'):
            if key in current_args:
                query_parts.append(current_args[key])
        query = " ".join(query_parts)

        # Strategy 1: Offload low-relevance items (>80%)
        if utilization > 0.8:
            try:
                self.context_tracker._trigger_offload(current_query=query)
            except Exception:
                pass

        # Strategy 2: Summarize large items (>90%)
        if utilization > 0.9:
            self._summarize_large_context_items()

        # Strategy 3: Clear very old items (>95%)
        if utilization > 0.95:
            self.context_tracker.clear_old(age_seconds=1800)

    def _summarize_large_context_items(self):
        """Summarize context items that are too large"""
        if not self.context_tracker:
            return

        for item in self.context_tracker.context_items:
            if len(item.content) > 2000:
                item.content = (
                    item.content[:500] +
                    f"\n\n... [SUMMARIZED: {len(item.content)} chars total] ...\n\n" +
                    item.content[-500:]
                )
