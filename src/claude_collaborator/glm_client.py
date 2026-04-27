"""
GLM Client for AI Research Tasks
Handles communication with GLM-5.1 API
"""

import concurrent.futures
import os
from typing import Any, Callable, Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


_STREAM_END = object()

ProgressCallback = Callable[[str, int], None]


class GLMClient:
    """Client for GLM-5.1 API"""

    def __init__(self):
        """Initialize GLM client"""
        self.api_key = os.getenv("GLM_API_KEY")
        self.model = os.getenv("GLM_MODEL", "glm-5.1")
        self.base_url = "https://api.z.ai/api/paas/v4"
        self.timeout = 120  # 120 second wall-clock timeout for API calls
        self.idle_timeout = 30  # per-chunk no-data timeout for streams

        if not self.api_key:
            raise ValueError("GLM_API_KEY not found in environment variables")

    def _stream_completion(
        self,
        client_call: Callable[[], Any],
        progress_callback: Optional[ProgressCallback],
        prefer_content_over_reasoning: bool = True,
    ) -> str:
        """Run a streaming chat-completion call and return the accumulated text.

        Pulls each chunk inside a single-worker thread pool so we can apply a
        per-chunk idle timeout without depending on SDK keep-alives. Both the
        zai SDK and openai-compat path emit chunks with the same shape.
        """
        stream = client_call()
        iterator = iter(stream)

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        total_chars = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            while True:
                future = ex.submit(next, iterator, _STREAM_END)
                try:
                    chunk = future.result(timeout=self.idle_timeout)
                except concurrent.futures.TimeoutError:
                    raise RuntimeError(
                        f"GLM stream stalled (no data for {self.idle_timeout}s)"
                    )

                if chunk is _STREAM_END:
                    break

                choices = getattr(chunk, "choices", None)
                if not choices:
                    continue

                delta = choices[0].delta
                piece_content = getattr(delta, "content", None) or ""
                piece_reason = getattr(delta, "reasoning_content", None) or ""

                if piece_content:
                    content_parts.append(piece_content)
                    total_chars += len(piece_content)
                    piece = piece_content
                elif piece_reason:
                    reasoning_parts.append(piece_reason)
                    total_chars += len(piece_reason)
                    piece = piece_reason
                else:
                    continue

                if progress_callback is not None:
                    try:
                        progress_callback(piece, total_chars)
                    except Exception:
                        pass

        if prefer_content_over_reasoning:
            return "".join(content_parts) if content_parts else "".join(reasoning_parts)
        else:
            return "".join(content_parts) or "".join(reasoning_parts)

    def explore(
        self,
        question: str,
        context: str = "",
        max_tokens: int = 2048,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """
        Ask GLM to explore a codebase question

        Args:
            question: The exploration question
            context: Additional code context or snippets
            max_tokens: Maximum response tokens
            progress_callback: Optional callable(chunk_text, total_chars)

        Returns:
            GLM's analysis
        """
        try:
            from zai import ZaiClient

            client = ZaiClient(api_key=self.api_key)

            prompt = f"""You are a codebase research assistant. Analyze the following question about a codebase.

Question: {question}

{f"Context:\n{context}" if context else ""}

Provide a comprehensive analysis including:
1. Overview of what you found
2. Key components or patterns
3. Dependencies or relationships
4. Any recommendations or observations

Be specific and reference code elements when possible."""

            return self._stream_completion(
                lambda: client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=1.0,
                    timeout=self.timeout,
                    stream=True,
                ),
                progress_callback,
            )

        except ImportError:
            return self._explore_openai_compat(question, context, max_tokens, progress_callback)

    def _explore_openai_compat(
        self,
        question: str,
        context: str,
        max_tokens: int,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """Use OpenAI-compatible API for GLM"""
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

            prompt = f"""You are a codebase research assistant. Analyze the following question about a codebase.

Question: {question}

{f"Context:\n{context}" if context else ""}

Provide a comprehensive analysis including:
1. Overview of what you found
2. Key components or patterns
3. Dependencies or relationships
4. Any recommendations or observations

Be specific and reference code elements when possible."""

            return self._stream_completion(
                lambda: client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=1.0,
                    timeout=self.timeout,
                    stream=True,
                ),
                progress_callback,
            )

        except Exception as e:
            return f"Error calling GLM API: {str(e)}"

    def compare(
        self,
        code1: str,
        code2: str,
        labels: Optional[List[str]] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """
        Compare two code sections

        Args:
            code1: First code section
            code2: Second code section
            labels: Optional labels for the sections
            progress_callback: Optional callable(chunk_text, total_chars)

        Returns:
            Comparison analysis
        """
        label1 = labels[0] if labels and len(labels) > 0 else "Code 1"
        label2 = labels[1] if labels and len(labels) > 1 else "Code 2"

        try:
            from zai import ZaiClient

            client = ZaiClient(api_key=self.api_key)

            prompt = f"""Compare these two code sections:

{label1}:
```
{code1}
```

{label2}:
```
{code2}
```

Provide:
1. Similarities
2. Differences
3. Which approach is better and why
4. Any recommendations"""

            return self._stream_completion(
                lambda: client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2048,
                    temperature=1.0,
                    timeout=self.timeout,
                    stream=True,
                ),
                progress_callback,
            )

        except Exception as e:
            return f"Error comparing code: {str(e)}"

    def deep_dive(
        self,
        topic: str,
        code_files: Dict[str, str],
        focus_areas: Optional[List[str]] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """
        Perform deep dive analysis on a topic

        Args:
            topic: Topic to analyze
            code_files: Dictionary of filenames to code content
            focus_areas: Specific areas to focus on
            progress_callback: Optional callable(chunk_text, total_chars)

        Returns:
            Comprehensive analysis
        """
        try:
            from zai import ZaiClient

            client = ZaiClient(api_key=self.api_key)

            files_section = ""
            for filename, content in code_files.items():
                files_section += f"\nFile: {filename}\n```\n{content}\n```\n"

            focus_section = ""
            if focus_areas:
                focus_section = f"\nFocus on these areas:\n" + "\n".join(f"- {a}" for a in focus_areas)

            prompt = f"""Perform a deep dive analysis on: {topic}{focus_section}

Relevant code files:
{files_section}

Provide a comprehensive analysis including:
1. Overall architecture and design
2. Key patterns and conventions
3. Dependencies and relationships
4. Potential issues or improvements
5. How this integrates with the broader codebase"""

            return self._stream_completion(
                lambda: client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=4096,
                    temperature=1.0,
                    timeout=self.timeout,
                    stream=True,
                ),
                progress_callback,
            )

        except Exception as e:
            return f"Error performing deep dive: {str(e)}"

    def brainstorm(
        self,
        challenge: str,
        context: str = "",
        max_tokens: int = 2048,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """
        Creative brainstorming - think divergently about a challenge.

        Unlike explore (research) or compare (evaluation), this method
        asks GLM to challenge assumptions and suggest unconventional approaches.

        Args:
            challenge: The problem, decision, or plan to brainstorm about
            context: Additional code context or background
            max_tokens: Maximum response tokens
            progress_callback: Optional callable(chunk_text, total_chars)

        Returns:
            GLM's creative perspectives
        """
        try:
            from zai import ZaiClient

            client = ZaiClient(api_key=self.api_key)

            prompt = f"""You are a creative technical advisor. Your role is to think divergently and challenge assumptions.

Challenge: {challenge}

{f"Context:\n{context}" if context else ""}

Think creatively and provide:
1. **Unconventional approaches** - solutions that aren't the obvious first choice
2. **Hidden trade-offs** - downsides of the obvious approach that might be missed
3. **Different angles** - reframe the problem from a different perspective
4. **Creative solutions** - combine ideas from different domains or patterns
5. **Assumptions to challenge** - what is being taken for granted that might not hold?

Don't just validate the obvious approach. Push boundaries and surface ideas that a single perspective might miss. Be specific and actionable."""

            return self._stream_completion(
                lambda: client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=1.0,
                    timeout=self.timeout,
                    stream=True,
                ),
                progress_callback,
            )

        except ImportError:
            return self._brainstorm_openai_compat(challenge, context, max_tokens, progress_callback)

    def _brainstorm_openai_compat(
        self,
        challenge: str,
        context: str,
        max_tokens: int,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """Use OpenAI-compatible API for brainstorming"""
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

            prompt = f"""You are a creative technical advisor. Your role is to think divergently and challenge assumptions.

Challenge: {challenge}

{f"Context:\n{context}" if context else ""}

Think creatively and provide:
1. **Unconventional approaches** - solutions that aren't the obvious first choice
2. **Hidden trade-offs** - downsides of the obvious approach that might be missed
3. **Different angles** - reframe the problem from a different perspective
4. **Creative solutions** - combine ideas from different domains or patterns
5. **Assumptions to challenge** - what is being taken for granted that might not hold?

Don't just validate the obvious approach. Push boundaries and surface ideas that a single perspective might miss. Be specific and actionable."""

            return self._stream_completion(
                lambda: client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=1.0,
                    timeout=self.timeout,
                    stream=True,
                ),
                progress_callback,
            )

        except Exception as e:
            return f"Error brainstorming: {str(e)}"

    def code_review(
        self,
        code: str,
        file_path: str = "",
        focus: str = "",
        max_tokens: int = 1024,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """
        Review code for quality, best practices, and potential improvements.

        Args:
            code: The code to review
            file_path: Optional file path for context
            focus: Optional specific focus areas
            max_tokens: Maximum response tokens
            progress_callback: Optional callable(chunk_text, total_chars)

        Returns:
            GLM's code review findings
        """
        try:
            from zai import ZaiClient

            client = ZaiClient(api_key=self.api_key)

            prompt = f"""You are a senior C# code reviewer. Review the following code and list ONLY the issues found. Do not include your analysis process or reasoning steps in the output.

{f"File: {file_path}" if file_path else ""}
{f"Focus: {focus}" if focus else ""}

```csharp
{code}
```

Check for these categories (skip any that have no issues):
- Dead code, unused variables, commented-out code
- Unused using directives
- Modern C# features that could be used (pattern matching, records, file-scoped namespaces, primary constructors, collection expressions, raw string literals, etc.)
- Naming convention violations (PascalCase/camelCase)
- Formatting inconsistencies
- Error handling problems (swallowed exceptions, catching generic Exception)
- Null safety issues (missing ?. or ??, nullable reference types)
- Async/await mistakes (async void, sync-over-async, Task.Result deadlocks)
- Missing resource disposal (IDisposable without using)
- Security issues (hardcoded secrets, SQL injection, input validation)
- SOLID violations (god classes, tight coupling)
- Magic numbers/strings that should be constants
- Access modifiers too permissive (public when could be private/internal)
- Performance issues (unnecessary allocations, string concat in loops)

Output format - for each issue, one bullet:
* **Category**: `problematic code` -> Suggested fix.

Output ONLY the bullet list. No preamble, no analysis steps, no numbering of your thought process."""

            return self._stream_completion(
                lambda: client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=1.0,
                    timeout=self.timeout,
                    stream=True,
                ),
                progress_callback,
            )

        except ImportError:
            return self._code_review_openai_compat(code, file_path, focus, max_tokens, progress_callback)

    def _code_review_openai_compat(
        self,
        code: str,
        file_path: str,
        focus: str,
        max_tokens: int,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """Use OpenAI-compatible API for code review"""
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

            prompt = f"""You are a senior C# code reviewer. Review the following code and list ONLY the issues found. Do not include your analysis process or reasoning steps in the output.

{f"File: {file_path}" if file_path else ""}
{f"Focus: {focus}" if focus else ""}

```csharp
{code}
```

Check for these categories (skip any that have no issues):
- Dead code, unused variables, commented-out code
- Unused using directives
- Modern C# features that could be used (pattern matching, records, file-scoped namespaces, primary constructors, collection expressions, raw string literals, etc.)
- Naming convention violations (PascalCase/camelCase)
- Formatting inconsistencies
- Error handling problems (swallowed exceptions, catching generic Exception)
- Null safety issues (missing ?. or ??, nullable reference types)
- Async/await mistakes (async void, sync-over-async, Task.Result deadlocks)
- Missing resource disposal (IDisposable without using)
- Security issues (hardcoded secrets, SQL injection, input validation)
- SOLID violations (god classes, tight coupling)
- Magic numbers/strings that should be constants
- Access modifiers too permissive (public when could be private/internal)
- Performance issues (unnecessary allocations, string concat in loops)

Output format - for each issue, one bullet:
* **Category**: `problematic code` -> Suggested fix.

Output ONLY the bullet list. No preamble, no analysis steps, no numbering of your thought process."""

            return self._stream_completion(
                lambda: client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=1.0,
                    timeout=self.timeout,
                    stream=True,
                ),
                progress_callback,
            )

        except Exception as e:
            return f"Error reviewing code: {str(e)}"
