"""
Automatic Memory Capture System
Detects and captures patterns, decisions, and findings from work
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from .memory_vector import VectorStore
from .memory_store import MemoryStore


class AutoCapture:
    """
    Automatic memory capture from code analysis and work

    Detects significant findings, patterns, and decisions
    and automatically saves them to memory.
    """

    # Tools that trigger auto-capture
    AUTO_CAPTURE_TOOLS = {
        "analyze_architecture": "architecture",
        "explore_project": "architecture",
        "find_similar_code": "patterns",
        "get_alternative": "decisions",
        "risk_check": "decisions",
        "lookup_convention": "patterns",
        "extract_class_structure": "code",
        "get_file_summary": "code",
        "find_class_usages": "code",
        "find_implementations": "code",
        "get_callers": "code",
        "brainstorm": "decisions",
    }

    # Pattern detection keywords
    PATTERN_KEYWORDS = [
        "pattern", "approach", "convention", "style", "implementation",
        "architecture", "design", "structure"
    ]

    # Decision indicators
    DECISION_KEYWORDS = [
        "decision", "chosen", "selected", "preferred", "recommend",
        "should use", "best practice", "alternative"
    ]

    # Edge case indicators
    EDGE_CASE_KEYWORDS = [
        "edge case", "gotcha", "caveat", "warning", "issue", "bug",
        "doesn't work", "fails when", "only works if"
    ]

    # Category detection keywords (used by learn tool and auto-capture)
    CATEGORY_KEYWORDS = {
        "workflow": [
            "workflow", "pipeline", "process", "setup", "deploy", "deployment",
            "build", "test run", "ci/cd", "release", "branch", "merge"
        ],
        "preferences": [
            "prefer", "always", "never", "convention", "style", "format",
            "naming", "standard", "rule", "guideline"
        ],
        "workarounds": [
            "workaround", "hack", "trick", "fix for", "work around",
            "instead of", "temporary fix", "known issue", "fallback"
        ],
        "context": [
            "project", "team", "codebase", "repo", "history", "background",
            "stakeholder", "requirement", "deadline", "milestone"
        ],
        "patterns": PATTERN_KEYWORDS,
        "decisions": DECISION_KEYWORDS,
        "edge_cases": EDGE_CASE_KEYWORDS,
        "architecture": [
            "architecture", "layer", "service", "module", "dependency",
            "integration", "api", "database", "infrastructure"
        ],
    }

    @classmethod
    def categorize_text(cls, text: str) -> str:
        """
        Auto-detect the best category for a piece of text.

        Args:
            text: Text to categorize

        Returns:
            Best matching category string, defaults to "findings"
        """
        text_lower = text.lower()
        scores = {}

        for category, keywords in cls.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[category] = score

        if not scores:
            return "findings"

        return max(scores, key=scores.get)

    def __init__(
        self,
        vector_store: VectorStore,
        memory_store: MemoryStore,
        enabled: bool = True
    ):
        """
        Initialize auto-capture system

        Args:
            vector_store: VectorStore for semantic storage
            memory_store: MemoryStore for structured storage
            enabled: Whether auto-capture is enabled
        """
        self.vector_store = vector_store
        self.memory_store = memory_store
        self.enabled = enabled

    def capture_tool_result(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: str
    ) -> Optional[str]:
        """
        Auto-capture if tool result is significant

        Enhanced to capture more automatically with pattern detection.

        Args:
            tool_name: Name of the tool that was called
            arguments: Tool arguments
            result: Tool result/output

        Returns:
            ID of captured memory, or None if not captured
        """
        if not self.enabled:
            return None

        if not self.vector_store._check_embedding_available():
            return None

        # Check if this tool should be auto-captured
        if tool_name not in self.AUTO_CAPTURE_TOOLS:
            return None

        # Check if result is substantial enough (lowered from 200 to 100)
        if len(result) < 100:
            return None

        # Skip if it's an error message
        if result.startswith("Error:") or result.startswith("Warning:"):
            return None

        # Determine category from tool name
        category = self.AUTO_CAPTURE_TOOLS[tool_name]

        # Generate topic from tool name and arguments
        topic = self._generate_topic(tool_name, arguments)

        # Create metadata
        metadata = {
            "tool": tool_name,
            "arguments": str(arguments),
            "captured_at": datetime.now().isoformat(),
            "auto_captured": True
        }

        # Store in vector store
        vector_id = self.vector_store.add(
            topic=topic,
            content=result,
            category=category,
            metadata=metadata
        )

        # Also store in structured memory for certain categories
        if category in ("architecture", "decisions", "patterns"):
            self.memory_store.save_finding(
                topic=topic,
                content=f"# {topic}\n\n{result[:2000]}...",  # Truncate for markdown
                category=category,
                metadata=metadata
            )

        # Also detect patterns in the result itself and capture them
        detected = self.detect_patterns_in_text(result)
        for detection in detected:
            if detection['type'] == 'decision':
                self.capture_decision(
                    decision=f"{tool_name}: {detection['context'][:100]}",
                    context=result[:500],
                    alternatives=[]
                )
            elif detection['type'] == 'pattern':
                # Extract pattern type from context
                pattern_type = detection.get('keyword', 'unknown')
                self.capture_pattern(
                    pattern_type=pattern_type,
                    description=detection['context'][:200],
                    files=[arguments.get('file_path', arguments.get('target', 'unknown'))],
                    code_snippet=""
                )

        return vector_id

    def _generate_topic(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Generate a topic name from tool name and arguments"""
        # Extract meaningful info from arguments
        if "file_path" in arguments:
            return f"{tool_name}:{arguments['file_path'].split('/')[-1]}"
        if "project" in arguments:
            return f"{tool_name}:{arguments['project']}"
        if "query" in arguments:
            query = arguments['query'][:30]
            return f"{tool_name}:{query}"
        if "pattern" in arguments:
            return f"pattern:{arguments['pattern']}"

        return f"{tool_name}:{datetime.now().strftime('%H:%M')}"

    def capture_pattern(
        self,
        pattern_type: str,
        description: str,
        files: List[str],
        code_snippet: str = ""
    ) -> str:
        """
        Capture a discovered code pattern

        Args:
            pattern_type: Type of pattern (e.g., "dependency-injection")
            description: Description of the pattern
            files: Files where pattern was found
            code_snippet: Example code

        Returns:
            Memory ID
        """
        content = f"## Pattern: {pattern_type}\n\n"
        content += f"{description}\n\n"
        content += f"**Found in:**\n"
        for f in files:
            content += f"- {f}\n"

        if code_snippet:
            content += f"\n**Example:**\n```\n{code_snippet[:500]}\n```\n"

        # Store in vector memory
        vector_id = self.vector_store.add(
            topic=f"pattern:{pattern_type}",
            content=content,
            category="patterns",
            metadata={
                "pattern_type": pattern_type,
                "files": files,
                "captured_at": datetime.now().isoformat()
            }
        )

        # Also store in structured memory
        self.memory_store.save_finding(
            topic=pattern_type,
            content=content,
            category="patterns",
            metadata={
                "files": files,
                "auto_captured": True
            }
        )

        return vector_id

    def capture_decision(
        self,
        decision: str,
        context: str,
        alternatives: List[str] = None
    ) -> str:
        """
        Capture an architecture decision

        Args:
            decision: The decision that was made
            context: Context/reasoning for the decision
            alternatives: Alternative approaches that were considered

        Returns:
            Memory ID
        """
        content = f"## Decision: {decision}\n\n"
        content += f"**Context:**\n{context}\n\n"

        if alternatives:
            content += f"**Alternatives considered:**\n"
            for alt in alternatives:
                content += f"- {alt}\n"

        vector_id = self.vector_store.add(
            topic=f"decision:{decision[:50]}",
            content=content,
            category="decisions",
            metadata={
                "decision": decision,
                "alternatives": alternatives or [],
                "captured_at": datetime.now().isoformat()
            }
        )

        self.memory_store.save_finding(
            topic=decision[:50],
            content=content,
            category="decisions",
            metadata={"auto_captured": True}
        )

        return vector_id

    def capture_edge_case(
        self,
        description: str,
        location: str,
        reproduction: str = ""
    ) -> str:
        """
        Capture an edge case or gotcha

        Args:
            description: Description of the edge case
            location: Where it occurs (file, function, etc.)
            reproduction: How to reproduce or trigger it

        Returns:
            Memory ID
        """
        content = f"## Edge Case: {description}\n\n"
        content += f"**Location:** {location}\n\n"

        if reproduction:
            content += f"**Reproduction:**\n{reproduction}\n\n"

        vector_id = self.vector_store.add(
            topic=f"edge_case:{description[:50]}",
            content=content,
            category="edge_cases",
            metadata={
                "location": location,
                "captured_at": datetime.now().isoformat()
            }
        )

        self.memory_store.save_finding(
            topic=description[:50],
            content=content,
            category="findings",
            metadata={
                "type": "edge_case",
                "auto_captured": True
            }
        )

        return vector_id

    def detect_patterns_in_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect patterns, decisions, and edge cases in text

        Args:
            text: Text to analyze

        Returns:
            List of detected items with their types
        """
        detected = []
        text_lower = text.lower()

        # Check for patterns
        for keyword in self.PATTERN_KEYWORDS:
            if keyword in text_lower:
                # Extract surrounding context
                matches = re.finditer(
                    rf'.{{0,100}}{re.escape(keyword)}.{{0,200}}',
                    text,
                    re.IGNORECASE
                )
                for match in matches:
                    detected.append({
                        "type": "pattern",
                        "keyword": keyword,
                        "context": match.group(0)
                    })

        # Check for decisions
        for keyword in self.DECISION_KEYWORDS:
            if keyword in text_lower:
                matches = re.finditer(
                    rf'.{{0,100}}{re.escape(keyword)}.{{0,200}}',
                    text,
                    re.IGNORECASE
                )
                for match in matches:
                    detected.append({
                        "type": "decision",
                        "keyword": keyword,
                        "context": match.group(0)
                    })

        # Check for edge cases
        for keyword in self.EDGE_CASE_KEYWORDS:
            if keyword in text_lower:
                matches = re.finditer(
                    rf'.{{0,100}}{re.escape(keyword)}.{{0,200}}',
                    text,
                    re.IGNORECASE
                )
                for match in matches:
                    detected.append({
                        "type": "edge_case",
                        "keyword": keyword,
                        "context": match.group(0)
                    })

        return detected

    def auto_capture_from_text(
        self,
        text: str,
        source: str = "unknown"
    ) -> List[str]:
        """
        Detect and capture findings from text

        Args:
            text: Text to analyze and capture from
            source: Source of the text (file, tool, etc.)

        Returns:
            List of captured memory IDs
        """
        detected = self.detect_patterns_in_text(text)
        captured_ids = []

        for item in detected:
            if item["type"] == "pattern":
                vid = self.capture_pattern(
                    pattern_type=item["keyword"],
                    description=item["context"],
                    files=[source]
                )
                captured_ids.append(vid)
            elif item["type"] == "decision":
                vid = self.capture_decision(
                    decision=item["context"][:100],
                    context=item["context"]
                )
                captured_ids.append(vid)
            elif item["type"] == "edge_case":
                vid = self.capture_edge_case(
                    description=item["context"][:100],
                    location=source,
                    reproduction=item["context"]
                )
                captured_ids.append(vid)

        return captured_ids

    def get_stats(self) -> Dict[str, Any]:
        """Get auto-capture statistics"""
        return {
            "enabled": self.enabled,
            "vector_available": self.vector_store._check_embedding_available(),
            "auto_capture_tools": list(self.AUTO_CAPTURE_TOOLS.keys())
        }
