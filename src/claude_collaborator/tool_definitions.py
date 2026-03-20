"""
Tool definitions (schemas) for the MCP server.

Each function returns a list of Tool objects for a specific category.
"""

from mcp.types import Tool


def get_configuration_tools() -> list[Tool]:
    return [
        Tool(
            name="get_config",
            description="Get current configuration",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="switch_codebase",
            description="Switch to a different codebase. Use this to work with multiple repositories.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the codebase root (can be absolute or relative)"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="list_codebases",
            description="Discover codebases by searching for .sln files and .git directories",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_path": {
                        "type": "string",
                        "description": "Directory to search (default: current working directory)"
                    }
                },
                "required": []
            }
        ),
    ]


def get_memory_tools() -> list[Tool]:
    return [
        Tool(
            name="memory_save",
            description="Save a finding to persistent memory",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic name"},
                    "content": {"type": "string", "description": "Finding content (markdown)"},
                    "category": {"type": "string", "description": "Category (default: findings)"}
                },
                "required": ["topic", "content"]
            }
        ),
        Tool(
            name="memory_get",
            description="Retrieve a topic from memory",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic name"},
                    "category": {"type": "string", "description": "Category to search in (optional)"}
                },
                "required": ["topic"]
            }
        ),
        Tool(
            name="memory_search",
            description="Search memory for keywords",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="memory_status",
            description="Get memory store statistics",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
    ]


def get_learning_tools() -> list[Tool]:
    return [
        Tool(
            name="learn",
            description="""PROACTIVE: Record an observation or learning from the current work session.

Call this whenever you discover something worth remembering. Don't wait to be asked.

WHEN TO CALL:
- Non-obvious codebase patterns or conventions you discover
- Debugging root causes and workarounds
- User workflow preferences or development practices
- Edge cases, gotchas, or "things that don't work as expected"
- Architecture insights or design decision rationale
- Setup, build, test, or deployment knowledge
- Common issues and their solutions
- How specific tools or pipelines work in this project

WHEN NOT TO CALL:
- Trivial file reads or routine operations
- Temporary debugging hypotheses (only save confirmed findings)
- Information that's already obvious from the code itself

Category is auto-detected if not provided. Deduplicates against existing memories.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "observation": {
                        "type": "string",
                        "description": "What you learned or observed (freeform text)"
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category: workflow, preferences, workarounds, context, patterns, decisions, edge_cases, architecture, findings"
                    },
                    "importance": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Importance level (default: medium)"
                    }
                },
                "required": ["observation"]
            }
        ),
        Tool(
            name="session_learn",
            description="""Capture learnings from the current work session in batch.

Call at the end of meaningful work sessions to summarize what was learned.
Stores each learning individually and saves the full summary for future reference.
If GLM is available, extracts additional structured insights from the summary.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Summary of what was learned during this session"
                    },
                    "learnings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "observation": {"type": "string"},
                                "category": {"type": "string"}
                            },
                            "required": ["observation"]
                        },
                        "description": "Optional array of individual learnings to store"
                    }
                },
                "required": ["summary"]
            }
        ),
    ]


def get_semantic_memory_tools() -> list[Tool]:
    return [
        Tool(
            name="memory_semantic_search",
            description="""Search memory by meaning (semantic similarity), not just keywords. Finds related concepts even without exact word matches.

PROACTIVE: Check this at the start of new work or when beginning a new topic to recall past learnings.
Also useful mid-task when you suspect something relevant was learned before.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query in natural language"},
                    "limit": {"type": "number", "description": "Max results (default: 5)"},
                    "category": {"type": "string", "description": "Filter by category (optional)"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="memory_vector_stats",
            description="Get vector memory statistics including embedding info and entry counts",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="context_offload",
            description="Manually trigger context offload to memory. Useful when context is getting large.",
            inputSchema={
                "type": "object",
                "properties": {
                    "current_query": {
                        "type": "string",
                        "description": "Current work query for relevance scoring (helps keep relevant context)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="context_retrieve",
            description="Retrieve relevant memories from both working memory and offloaded context for a query",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "number", "description": "Max results (default: 3)"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="context_stats",
            description="Get context tracking statistics including size, utilization, and item counts",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="session_status",
            description="Get session state including active task and recent work",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
    ]


def get_code_navigation_tools() -> list[Tool]:
    return [
        Tool(
            name="find_similar_code",
            description="""Find similar code patterns in the codebase.

RETURNS: Code snippets with file paths showing how similar things are done
YOU (Claude) then: Compare patterns, choose best approach, explain reasoning

USE THIS TO:
- Understand established patterns before making changes
- Find examples of how similar problems were solved
- Ensure consistency with existing codebase
- Compare different implementation approaches

COMMON WORKFLOWS:
- Understanding a feature: lookup_convention -> find_similar_code -> extract_class_structure
- Planning changes: find_similar_code -> get_callers -> find_references

FOLLOW UP WITH:
- extract_class_structure() to dive deeper into specific files
- get_callers() to understand usage patterns
- find_implementations() to compare approaches

This tool DOES the finding, YOU do the thinking and deciding.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Pattern to search for (e.g., 'DICOM handling', 'file processing')"
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "File pattern (default: *.cs)",
                        "default": "*.cs"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["pattern"]
            }
        ),
        Tool(
            name="lookup_convention",
            description="""Lookup how things are typically done in the codebase.

RETURNS: Examples showing established patterns and conventions
YOU (Claude) then: Decide whether to follow the convention or intentionally adapt

USE THIS FOR:
- Finding naming conventions
- Understanding error handling patterns
- Learning configuration approaches
- Seeing how logging is typically done
- Understanding async/await vs callback patterns

COMMON WORKFLOWS:
- Starting a task: lookup_convention -> find_similar_code
- Before implementing: lookup_convention -> find_implementations

This tool GATHERS examples, YOU decide whether to follow them.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Convention to lookup (e.g., 'error handling', 'logging', 'DI registration')"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results (default: 3)",
                        "default": 3
                    }
                },
                "required": ["topic"]
            }
        ),
        Tool(
            name="get_callers",
            description="""Find all code that calls a specific method or class.

RETURNS: List of all callers with file paths and code context
YOU (Claude) then: Analyze impact, plan safe refactoring, understand what might break

USE THIS WHEN:
- Planning changes to a method
- Understanding what might break if you change something
- Finding ripple effects of changes
- Need to understand usage patterns

FOLLOW UP WITH:
- find_references() for detailed member usage
- trace_execution() to understand full flow""",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Method or class name (e.g., 'ProcessFile', 'BaseDistiller')"
                    }
                },
                "required": ["target"]
            }
        ),
        Tool(
            name="find_class_usages",
            description="""Find all usages of a class or interface.

RETURNS: List of all places where class is used/instantiated/inherited
YOU (Claude) then: Analyze dependencies, understand coupling

USE THIS WHEN:
- Understanding how a class is used throughout codebase
- Planning changes to an interface
- Finding tight coupling issues

FOLLOW UP WITH:
- get_callers() for method-level usage
- find_implementations() to see implementations""",
            inputSchema={
                "type": "object",
                "properties": {
                    "class_name": {
                        "type": "string",
                        "description": "Class or interface name (e.g., 'BaseDistiller')"
                    }
                },
                "required": ["class_name"]
            }
        ),
        Tool(
            name="find_implementations",
            description="""Find all implementations of an interface or abstract class.

RETURNS: List of all implementing classes with their key methods
YOU (Claude) then: Compare implementations, find patterns, choose reference

USE THIS WHEN:
- Understanding different implementations of a contract
- Comparing approaches across components
- Finding which implementation to use as reference

FOLLOW UP WITH:
- extract_class_structure() to compare specific implementations
- find_similar_code() to see related patterns""",
            inputSchema={
                "type": "object",
                "properties": {
                    "interface_name": {
                        "type": "string",
                        "description": "Interface or abstract class name"
                    }
                },
                "required": ["interface_name"]
            }
        ),
    ]


def get_code_analysis_tools() -> list[Tool]:
    return [
        Tool(
            name="extract_class_structure",
            description="""Parse a C# class and extract its structure.

RETURNS: Structured list of methods, properties, fields, events with signatures
YOU (Claude) then: Understand relationships, plan integration, design changes

SAVES YOUR CONTEXT: Instead of reading the whole file, get the structure first

USE THIS WHEN:
- Understanding a class before diving into details
- Planning how to extend or modify a class
- Comparing class structures

COMMON WORKFLOWS:
- Understanding a class: get_file_summary -> extract_class_structure
- Refactoring: extract_class_structure -> get_callers -> find_references""",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the C# file (relative to codebase root)"
                    },
                    "include_body": {
                        "type": "boolean",
                        "description": "Include method bodies (default: false)",
                        "default": False
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="get_file_summary",
            description="""Get summary statistics for a file.

RETURNS: Line count, class count, namespace, imports, complexity metrics
YOU (Claude) then: Decide if deep analysis is needed

USE THIS WHEN:
- Quickly understanding file scope
- Deciding where to focus attention
- Assessing file complexity

FOLLOW UP WITH:
- extract_class_structure() for detailed analysis
- find_similar_code() to compare with other files""",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file (relative to codebase root)"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="list_dependencies",
            description="""Map all dependencies for a file or project.

RETURNS: List of all imports, references, project dependencies
YOU (Claude) then: Understand coupling, plan changes

USE THIS WHEN:
- Understanding what a file depends on
- Planning refactors that might affect dependencies
- Assessing coupling

FOLLOW UP WITH:
- get_callers() for reverse dependencies
- find_class_usages() for specific class usage""",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "File path or project name"
                    }
                },
                "required": ["target"]
            }
        ),
        Tool(
            name="find_references",
            description="""Find all references to a member (method, property, field).

RETURNS: List of all usages with context
YOU (Claude) then: Plan safe refactoring

USE THIS WHEN:
- Planning to rename or modify a member
- Understanding how something is used
- Finding all places that need updates

FOLLOW UP WITH:
- get_callers() for method/class level
- trace_execution() to understand flow""",
            inputSchema={
                "type": "object",
                "properties": {
                    "member_name": {
                        "type": "string",
                        "description": "Member name to find references for"
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "File pattern to search (default: *.cs)",
                        "default": "*.cs"
                    }
                },
                "required": ["member_name"]
            }
        ),
    ]


def get_glm_tools() -> list[Tool]:
    return [
        Tool(
            name="summarize_large_file",
            description="""GLM summarizes a large file to save your context.

GLM DOES: Read file, extract key points, summarize structure (limit: 10K chars)
YOU THEN: Use the summary to do your important thinking and reasoning

SAVES YOUR CONTEXT for: Complex reasoning about architecture, design decisions

USE THIS WHEN:
- File is too large to read in your context
- Want high-level understanding before diving deep
- Need to grasp structure quickly

NOTE: GLM only receives the file content (truncated), no extra context.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file (relative to codebase root)"
                    },
                    "focus": {
                        "type": "string",
                        "description": "Specific focus (optional): 'classes', 'methods', 'dependencies'"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="get_alternative",
            description="""PROACTIVE: Get an alternative approach from GLM for comparison.

GLM PROVIDES: Different way to solve the problem (with your code only, no extra context)
YOU (Claude) THEN: Evaluate pros/cons, decide whether to adopt

USE THIS WHEN:
- You already have an approach and want to compare it against GLM's suggestion
- You want to validate your approach isn't missing something obvious
- Comparing multiple implementation strategies

Works with brainstorm (divergent thinking) and risk_check (risk analysis) as a two-AI collaboration system.

IMPORTANT: You (Claude) make the final decision. GLM just provides input.

CONTEXT LIMIT: Only your code is sent (max 10K chars), no memory dumping.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "your_approach": {
                        "type": "string",
                        "description": "Describe your proposed solution or approach"
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context (optional, keep brief)"
                    }
                },
                "required": ["your_approach"]
            }
        ),
        Tool(
            name="risk_check",
            description="""PROACTIVE: GLM identifies potential risks in your proposed approach.

GLM PROVIDES: List of potential issues, edge cases, problems (brief input only)
YOU (Claude) THEN: Validate which risks are real, prioritize them

USE THIS WHEN:
- Before implementing significant changes
- Making architectural decisions
- Planning changes that affect multiple files or systems
- When the approach feels risky or you're unsure about edge cases

Works with brainstorm (divergent thinking) and get_alternative (approach comparison) as a two-AI collaboration system.

IMPORTANT: You (Claude) validate the risks. GLM might hallucinate.

CONTEXT LIMIT: Your approach only (max 10K chars), no extra context.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "proposed_change": {
                        "type": "string",
                        "description": "Describe the change you're planning"
                    },
                    "code": {
                        "type": "string",
                        "description": "Relevant code snippet (optional, keep brief)"
                    }
                },
                "required": ["proposed_change"]
            }
        ),
        Tool(
            name="brainstorm",
            description="""PROACTIVE: Get creative perspectives from GLM before committing to an approach.

GLM PROVIDES: Unconventional approaches, hidden trade-offs, different angles, creative solutions
YOU (Claude) THEN: Evaluate GLM's ideas critically, decide what to adopt

USE THIS WHEN:
- Planning architecture changes or significant implementations
- Designing something new where multiple approaches exist
- Stuck on a problem and want fresh perspectives
- Making decisions with long-term consequences
- Before committing to a complex approach

Unlike get_alternative (compares your approach vs GLM's) or risk_check (finds risks),
brainstorm asks GLM to think divergently and challenge assumptions.

IMPORTANT: You (Claude) make the final decision. GLM provides creative input only.

CONTEXT LIMIT: Your challenge only (max 10K chars), no extra context.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "challenge": {
                        "type": "string",
                        "description": "The problem, decision, or plan to brainstorm about"
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional code context or background (optional, keep brief)"
                    }
                },
                "required": ["challenge"]
            }
        ),
    ]


def get_project_tools() -> list[Tool]:
    return [
        Tool(
            name="explore_project",
            description="Explore a C# project and generate comprehensive summary",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project name (e.g., 'MyProject')"}
                },
                "required": ["project"]
            }
        ),
        Tool(
            name="analyze_architecture",
            description="Analyze overall solution architecture",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
    ]


def get_task_tools() -> list[Tool]:
    return [
        Tool(
            name="task_start",
            description="Start a new long-running task",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Task name"},
                    "description": {"type": "string", "description": "Task description"}
                },
                "required": ["name", "description"]
            }
        ),
        Tool(
            name="task_update",
            description="Update a task with findings",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Task name"},
                    "content": {"type": "string", "description": "Update content (markdown)"}
                },
                "required": ["name", "content"]
            }
        ),
        Tool(
            name="task_status",
            description="Get task status and history",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Task name"}
                },
                "required": ["name"]
            }
        ),
    ]


def get_all_tools() -> list[Tool]:
    """Return all tool definitions."""
    return (
        get_configuration_tools()
        + get_memory_tools()
        + get_learning_tools()
        + get_semantic_memory_tools()
        + get_code_navigation_tools()
        + get_code_analysis_tools()
        + get_glm_tools()
        + get_project_tools()
        + get_task_tools()
    )
