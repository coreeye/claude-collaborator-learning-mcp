"""
Tool call handlers for the MCP server.

Each handler function takes the server instance and arguments dict,
and returns a result string.
"""

import json
import re
from datetime import datetime
from typing import Optional


def handle_get_config(server, arguments: dict) -> str:
    config_data = {
        "glm_available": server.glm_available,
        "language": "C#"
    }
    if server.codebase_path:
        config_data["codebase_path"] = str(server.codebase_path)
        config_data["memory_path"] = str(server.memory.memory_path) if server.memory else None
        config_data["initialized"] = True
    else:
        config_data["initialized"] = False
        config_data["message"] = "No codebase selected. Use switch_codebase() to select one."
    return json.dumps(config_data, indent=2)


def handle_switch_codebase(server, arguments: dict) -> str:
    result = server.switch_codebase(arguments["path"])
    if result["success"]:
        output = f"**Switched to codebase:**\n"
        output += f"- Path: {result['codebase_path']}\n"
        output += f"- C# files: {result['cs_files_count']}\n"
        output += f"- Projects: {result['projects_count']}\n"
        if result['solutions']:
            output += f"- Solutions: {', '.join(result['solutions'])}\n"
        output += f"- Memory: {result['memory_path']}\n"
        return output
    else:
        return f"Error: {result['error']}"


def handle_list_codebases(server, arguments: dict) -> str:
    search_path = arguments.get("search_path")
    result = server.list_codebases(search_path)
    if not result["success"]:
        return f"Error: {result['error']}"

    output = f"**Found {result['codebases_count']} codebase(s)** in: {result['search_path']}\n\n"
    for i, cb in enumerate(result["codebases"], 1):
        output += f"{i}. **{cb['name']}** ({cb['type']})\n"
        output += f"   Path: `{cb['root']}`\n"
        output += f"   Switch with: `switch_codebase(path=\"{cb['root']}\")`\n\n"
    return output


# ==================== MEMORY TOOLS ====================


def handle_memory_save(server, arguments: dict) -> str:
    result = server.memory.save_finding(
        topic=arguments["topic"],
        content=arguments["content"],
        category=arguments.get("category", "findings"),
        metadata={"timestamp": datetime.now().isoformat()}
    )
    return f"Saved to memory: {result}"


def handle_memory_get(server, arguments: dict) -> str:
    result = server.memory.get_topic(
        topic=arguments["topic"],
        category=arguments.get("category")
    )
    if result:
        return result["content"]
    else:
        return f"Topic '{arguments['topic']}' not found in memory"


def handle_memory_search(server, arguments: dict) -> str:
    results = server.memory.search(arguments["query"])
    if not results:
        return f"No results found for '{arguments['query']}'"

    output = f"Found {len(results)} results:\n\n"
    for r in results:
        output += f"## {r['topic']} ({r['category']})\n"
        output += f"{r['snippet']}\n\n"
    return output


def handle_memory_status(server, arguments: dict) -> str:
    status = server.memory.get_status()
    output = f"""Memory Store Status:
- Path: {status['memory_path']}
- Created: {status['created']}
- Last Updated: {status['last_updated']}
- Total Topics: {status['total_topics']}
- Topics by Category:"""
    for cat, count in status['topics_by_category'].items():
        output += f"\n  - {cat}: {count}"
    return output


# ==================== AUTO-LEARNING TOOLS ====================


def handle_learn(server, arguments: dict) -> str:
    observation = arguments["observation"]
    category = arguments.get("category")
    importance = arguments.get("importance", "medium")

    # Auto-detect category if not provided
    if not category:
        from .memory_auto import AutoCapture
        category = AutoCapture.categorize_text(observation)

    # Generate topic from first sentence or first 60 chars
    topic = observation.split('.')[0].strip()[:60] if '.' in observation[:80] else observation[:60]

    # Deduplicate: check if a very similar observation already exists
    dedup_threshold = server.config.get("learn_dedup_threshold", 0.85)
    if server.vector_store and server.vector_store._check_embedding_available():
        try:
            existing = server.vector_store.search(observation, limit=1, category=category)
            if existing and existing[0]['score'] >= dedup_threshold:
                existing_topic = existing[0]['topic']
                # If new observation is more detailed, update
                if len(observation) > len(existing[0]['content']):
                    server.vector_store.add(
                        topic=topic,
                        content=observation,
                        category=category,
                        metadata={
                            "importance": importance,
                            "learned_at": datetime.now().isoformat(),
                            "source": "learn_tool",
                            "updated_from": existing_topic
                        }
                    )
                    return f"Updated existing learning: {topic} (category: {category})"
                else:
                    return f"Already known: {existing_topic} (score: {existing[0]['score']:.2f})"
        except Exception:
            pass  # Proceed with normal save if dedup fails

    # Store in vector memory
    metadata = {
        "importance": importance,
        "learned_at": datetime.now().isoformat(),
        "source": "learn_tool"
    }

    vector_stored = False
    if server.vector_store:
        try:
            result = server.vector_store.add(
                topic=topic,
                content=observation,
                category=category,
                metadata=metadata
            )
            if result == "queued":
                vector_stored = "queued"
            elif result is not None:
                vector_stored = True
        except Exception as e:
            vector_stored = False

    # Store in structured memory
    try:
        server.memory.save_finding(
            topic=topic,
            content=f"# {topic}\n\n{observation}",
            category=category,
            metadata=metadata
        )
    except Exception:
        pass

    if vector_stored == "queued":
        vec_status = "vector: queued (model warming up)"
    elif vector_stored:
        vec_status = "vector: stored"
    else:
        vec_status = "vector: skipped"
    return f"Learned: {topic} (category: {category}, importance: {importance}, {vec_status})"


def handle_session_learn(server, arguments: dict) -> str:
    summary = arguments["summary"]
    learnings = arguments.get("learnings", [])
    captured_count = 0

    # Store individual learnings
    for learning in learnings:
        obs = learning["observation"]
        cat = learning.get("category")
        if not cat:
            from .memory_auto import AutoCapture
            cat = AutoCapture.categorize_text(obs)

        topic = obs.split('.')[0].strip()[:60] if '.' in obs[:80] else obs[:60]
        metadata = {
            "learned_at": datetime.now().isoformat(),
            "source": "session_learn"
        }

        try:
            if server.vector_store:
                server.vector_store.add(
                    topic=topic, content=obs,
                    category=cat, metadata=metadata
                )
            server.memory.save_finding(
                topic=topic, content=f"# {topic}\n\n{obs}",
                category=cat, metadata=metadata
            )
            captured_count += 1
        except Exception:
            pass

    # Store full session summary
    summary_metadata = {
        "learned_at": datetime.now().isoformat(),
        "source": "session_learn",
        "learnings_count": len(learnings)
    }
    if server.vector_store:
        try:
            server.vector_store.add(
                topic=f"session_summary:{datetime.now().strftime('%Y-%m-%d_%H:%M')}",
                content=summary,
                category="session_summary",
                metadata=summary_metadata
            )
        except Exception:
            pass

    # GLM extraction if available
    glm_extracted = 0
    if server.glm_available and server.config.get("learn_glm_extract", True):
        try:
            glm_result = server.glm.explore(
                question="Extract key learnings from this session summary",
                context=f"Session summary:\n{summary[:4000]}\n\nExtract specific learnings about: codebase patterns, workarounds, user preferences, architecture insights, edge cases. Return each as a bullet point.",
                max_tokens=2048
            )
            if glm_result and not glm_result.startswith("Error"):
                if server.vector_store:
                    server.vector_store.add(
                        topic=f"glm_session_insights:{datetime.now().strftime('%Y-%m-%d_%H:%M')}",
                        content=glm_result,
                        category="findings",
                        metadata={"source": "session_learn_glm", "learned_at": datetime.now().isoformat()}
                    )
                    glm_extracted = 1
        except Exception:
            pass

    # Flush session state
    if server.session_state:
        try:
            server.session_state._flush()
        except Exception:
            pass

    output = f"Session learnings captured:\n"
    output += f"- Individual learnings: {captured_count}/{len(learnings)}\n"
    output += f"- Session summary: saved\n"
    if glm_extracted:
        output += f"- GLM-extracted insights: saved\n"
    return output


# ==================== SEMANTIC MEMORY TOOLS ====================


def handle_memory_semantic_search(server, arguments: dict) -> str:
    if not server.vector_store:
        return "Semantic search not available. Install with: pip install -e '.[vector]'"

    query = arguments["query"]
    limit = arguments.get("limit", 5)
    category = arguments.get("category")

    results = server.vector_store.search(query, limit=limit, category=category)

    if not results:
        return f"No semantic matches found for '{query}'"

    output = f"## Semantic Search Results: '{query}'\n\n"
    for i, r in enumerate(results, 1):
        output += f"### {i}. [{r['category']}] {r['topic']}\n"
        output += f"**Relevance:** {r['score']:.2f}\n\n"
        snippet = r['content'][:300] + "..." if len(r['content']) > 300 else r['content']
        output += f"{snippet}\n\n"
    return output


def handle_memory_vector_stats(server, arguments: dict) -> str:
    if not server.vector_store:
        return "Vector memory not available. Install with: pip install -e '.[vector]'"

    stats = server.vector_store.get_stats()
    output = f"""Vector Memory Status:
- Database: {stats['db_path']}
- Embeddings Available: {stats['embeddings_available']}
- Model: {stats['embedding_model']}
- Total Entries: {stats['total_entries']}
- Entries by Category:"""
    for cat, count in stats['categories'].items():
        output += f"\n  - {cat}: {count}"
    return output


def handle_context_offload(server, arguments: dict) -> str:
    if not server.context_tracker:
        return "Context tracking not available. Install with: pip install -e '.[vector]'"

    current_query = arguments.get("current_query", "")
    result = server.context_tracker._trigger_offload(current_query)

    output = f"## Context Offload Complete\n\n"
    output += f"- Offloaded {result['offloaded_count']} items\n"
    output += f"- Offloaded size: {result['offloaded_size']} chars\n"
    output += f"- Remaining size: {result['remaining_size']} chars\n"
    return output


def handle_context_retrieve(server, arguments: dict) -> str:
    if not server.context_tracker:
        return "Context tracking not available. Install with: pip install -e '.[vector]'"

    query = arguments["query"]
    limit = arguments.get("limit", 3)

    results = server.context_tracker.retrieve_relevant(query, limit=limit)

    output = f"## Relevant Context: '{query}'\n\n"
    for i, r in enumerate(results, 1):
        output += f"### {i}. [{r.get('source', 'unknown')}] {r.get('item_type', 'general')}\n"
        if 'score' in r:
            output += f"**Relevance:** {r['score']:.2f}\n\n"
        output += f"{r.get('content', '')[:300]}\n\n"
    return output


def handle_context_stats(server, arguments: dict) -> str:
    if not server.context_tracker:
        return "Context tracking not available. Install with: pip install -e '.[vector]'"

    stats = server.context_tracker.get_stats()
    output = f"""Context Tracking Status:
- Current Size: {stats['current_size']} chars
- Item Count: {stats['item_count']}
- Threshold: {stats['threshold']} chars
- Utilization: {stats['utilization']:.1%}
- Offloaded Items: {stats['offloaded_count']}
- Items by Type:"""
    for item_type, count in stats['items_by_type'].items():
        output += f"\n  - {item_type}: {count}"
    return output


def handle_session_status(server, arguments: dict) -> str:
    if not server.session_state:
        return "Session state not available."

    summary = server.session_state.get_session_summary()
    recent_work = server.session_state.get_recent_work(limit=5)

    output = f"""Session Status:
- Codebase: {summary['codebase_path']}
- Session File: {summary.get('session_file', 'N/A')}
- Last Session: {summary.get('last_session_time', 'N/A')}"""

    active_task = summary.get('active_task')
    if active_task:
        output += f"\n- Active Task: {active_task['name']} ({active_task['status']})"
        output += f"\n- Last Work: {active_task.get('last_work', 'N/A')}"

    output += f"\n- Recent Work Entries: {summary.get('recent_work_count', 0)}"

    if recent_work:
        output += "\n\n**Recent Work:**\n"
        for i, work in enumerate(recent_work, 1):
            output += f"{i}. {work['tool']}"
            if 'arguments' in work:
                args_str = str(work['arguments'])[:50]
                output += f" ({args_str}...)"
            output += f" - {work.get('timestamp', 'N/A')}\n"

    return output


# ==================== CODE NAVIGATION TOOLS ====================


def handle_find_similar_code(server, arguments: dict) -> str:
    pattern = arguments["pattern"]
    file_pattern = arguments.get("file_pattern", "*.cs")
    max_results = arguments.get("max_results", 5)

    matches = server.analyzer.find_pattern(pattern, file_pattern)

    output = f"## Found {len(matches)} matches for '{pattern}':\n\n"

    for i, match in enumerate(matches[:max_results], 1):
        output += f"### {i}. {match['file']}\n\n"
        for j, match_line in enumerate(match['matches'][:3], 1):
            output += f"  Line {match_line['line_number']}: {match_line['content']}\n"
        if len(match['matches']) > 3:
            output += f"  ... and {len(match['matches']) - 3} more matches\n"
        output += "\n"

    output += "\n**YOU (Claude)** should analyze these examples and decide how to proceed."
    return output


def handle_lookup_convention(server, arguments: dict) -> str:
    topic = arguments["topic"]
    max_results = arguments.get("max_results", 3)

    memory_results = server.memory.search(topic)
    code_matches = server.analyzer.find_pattern(topic, "*.cs")

    output = f"## Convention lookup: '{topic}'\n\n"

    if memory_results:
        output += f"### From memory:\n"
        for r in memory_results[:max_results]:
            output += f"- {r['topic']}: {r['snippet'][:100]}...\n"
        output += "\n"

    if code_matches:
        output += f"### Code examples:\n\n"
        for i, match in enumerate(code_matches[:max_results], 1):
            output += f"{i}. **{match['file']}**\n"
            for match_line in match['matches'][:2]:
                output += f"   {match_line['content']}\n"
            output += "\n"

    output += "\n**YOU (Claude)** should analyze these conventions and decide whether to follow them."
    return output


def handle_get_callers(server, arguments: dict) -> str:
    target = arguments["target"]

    callers = []
    for cs_file in server.codebase_path.rglob("*.cs"):
        try:
            with open(cs_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')

            for i, line in enumerate(lines, 1):
                if re.search(rf'\b{re.escape(target)}\s*\(', line):
                    start = max(0, i - 3)
                    context_lines = lines[start:min(len(lines), i + 2)]
                    callers.append({
                        "file": str(cs_file.relative_to(server.codebase_path)),
                        "line": i,
                        "context": '\n'.join(context_lines)
                    })

                    if len(callers) >= 50:
                        break
        except Exception:
            continue

    output = f"## Callers of '{target}':\n\n"
    if not callers:
        output += f"No callers found for '{target}'\n"
    else:
        output += f"Found {len(callers)} callers:\n\n"
        for caller in callers[:20]:
            output += f"### {caller['file']}:{caller['line']}\n"
            output += f"```\n{caller['context']}\n```\n\n"
        if len(callers) > 20:
            output += f"... and {len(callers) - 20} more\n"

    output += "\n**YOU (Claude)** should analyze these callers to understand impact."
    return output


def handle_find_class_usages(server, arguments: dict) -> str:
    class_name = arguments["class_name"]

    result = server.analyzer.find_class_usages(class_name)

    output = f"## Usages of '{class_name}':\n\n"
    output += f"Total usages: {result['total_usages']}\n"
    output += f"Files affected: {result['files_affected']}\n\n"

    for file, usages in list(result['by_file'].items())[:10]:
        output += f"### {file}\n"
        output += f"Usage count: {len(usages)}\n"
        for usage in usages[:3]:
            output += f"  Line {usage['line']} ({usage['type']}): {usage['context'][:60]}...\n"
        output += "\n"

    if len(result['by_file']) > 10:
        output += f"... and {len(result['by_file']) - 10} more files\n"

    output += "\n**YOU (Claude)** should analyze these usages to understand dependencies."
    return output


def handle_find_implementations(server, arguments: dict) -> str:
    interface_name = arguments["interface_name"]

    implementations = server.analyzer.find_implementations(interface_name)

    output = f"## Implementations of '{interface_name}':\n\n"
    if not implementations:
        output += f"No implementations found for '{interface_name}'\n"
    else:
        for impl in implementations:
            output += f"### {impl['class']} ({impl['file']})\n"
            output += f"Key methods: {', '.join(impl['methods'][:5])}"
            if len(impl['methods']) > 5:
                output += f" ... and {len(impl['methods']) - 5} more"
            output += "\n\n"

    output += "\n**YOU (Claude)** should compare these implementations and recommend patterns."
    return output


# ==================== CODE ANALYSIS TOOLS ====================


def handle_extract_class_structure(server, arguments: dict) -> str:
    file_path = server.codebase_path / arguments["file_path"]
    include_body = arguments.get("include_body", False)

    if not file_path.exists():
        return f"File not found: {arguments['file_path']}"

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract namespace
    ns_match = re.search(r'namespace\s+([\w.]+)', content)
    namespace = ns_match.group(1) if ns_match else None

    # Extract class/interface names
    class_matches = re.finditer(
        r'(public|internal|private|protected)?\s*(abstract|sealed|static)?\s*(class|interface|struct|record)\s+(\w+)',
        content
    )

    output = f"## Structure of {arguments['file_path']}\n\n"
    if namespace:
        output += f"**Namespace:** {namespace}\n\n"

    structures = []
    for match in class_matches:
        struct_type = match.group(2) or ""
        kind = match.group(3)
        name = match.group(4)

        # Find members for this class
        class_start = match.end()
        brace_count = 0
        in_class = False
        class_content = ""

        for char in content[class_start:]:
            if char == '{':
                brace_count += 1
                in_class = True
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    break
            if in_class:
                class_content += char

        # Extract members
        if include_body:
            member_matches = re.finditer(
                rf'(public|internal|protected|private).*?(\w+)\s*\([^)]*\)\s*{{',
                class_content,
                re.MULTILINE | re.DOTALL
            )
        else:
            member_matches = re.finditer(
                rf'(public|internal|protected|private).*?(\w+(?:<[^>]+>)?)\s*\([^)]*\)\s*{{?',
                class_content,
                re.MULTILINE
            )

        members = []
        for m in member_matches:
            members.append(f"  {m.group(0).strip().replace('{', '').strip()}")

        structures.append({
            "type": struct_type,
            "kind": kind,
            "name": name,
            "members": members
        })

    # Format output
    for struct in structures:
        modifiers = " ".join(filter(None, [struct["type"], struct["kind"]]))
        output += f"### {modifiers} {struct['name']}\n\n"
        if struct["members"]:
            output += f"**Members:**\n"
            for member in struct["members"][:20]:
                output += f"{member}\n"
            if len(struct["members"]) > 20:
                output += f"  ... and {len(struct['members']) - 20} more\n"
        else:
            output += "No members found\n"
        output += "\n"

    output += "\n**YOU (Claude)** should analyze this structure to understand relationships."
    return output


def handle_get_file_summary(server, arguments: dict) -> str:
    file_path = server.codebase_path / arguments["file_path"]

    if not file_path.exists():
        return f"File not found: {arguments['file_path']}"

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')

    total_lines = len(lines)
    code_lines = len([l for l in lines if l.strip() and not l.strip().startswith('//')])
    empty_lines = len([l for l in lines if not l.strip()])
    usings = len(re.findall(r'using\s+', content))
    classes = len(re.findall(r'\bclass\s+\w+', content))
    methods = len(re.findall(r'\s+\w+\s*\([^)]*\)\s*{', content))

    ns_match = re.search(r'namespace\s+([\w.]+)', content)
    namespace = ns_match.group(1) if ns_match else "None"

    if total_lines > 500:
        complexity = "High"
    elif total_lines > 200:
        complexity = "Medium"
    else:
        complexity = "Low"

    output = f"## File Summary: {arguments['file_path']}\n\n"
    output += f"**Total Lines:** {total_lines}\n"
    output += f"**Code Lines:** {code_lines}\n"
    output += f"**Empty Lines:** {empty_lines}\n"
    output += f"**Using Statements:** {usings}\n"
    output += f"**Classes:** {classes}\n"
    output += f"**Methods:** {methods}\n"
    output += f"**Namespace:** {namespace}\n\n"
    output += f"**Complexity:** {complexity}\n\n"
    output += "\n**YOU (Claude)** should decide if this file needs deeper analysis."
    return output


def handle_list_dependencies(server, arguments: dict) -> str:
    target = arguments["target"]
    target_path = server.codebase_path / target

    output = f"## Dependencies for '{target}'\n\n"

    if target_path.exists() and target_path.is_file():
        with open(target_path, 'r', encoding='utf-8') as f:
            content = f.read()

        usings = re.findall(r'using\s+([\w.]+);', content)

        system_usings = []
        project_usings = []
        for using in usings:
            if using.startswith('System'):
                system_usings.append(using)
            else:
                project_usings.append(using)

        output += f"**File:** {target}\n\n"
        output += f"### System Dependencies ({len(system_usings)})\n"
        for u in sorted(set(system_usings))[:20]:
            output += f"- {u}\n"

        output += f"\n### Project Dependencies ({len(project_usings)})\n"
        for u in sorted(set(project_usings))[:20]:
            output += f"- {u}\n"

    else:
        proj_file = server.codebase_path / f"{target}.csproj"
        if proj_file.exists():
            with open(proj_file, 'r', encoding='utf-8') as f:
                proj_content = f.read()

            packages = re.findall(r'<PackageReference\s+Include="([^"]+)"', proj_content)

            output += f"**Project:** {target}\n\n"
            output += f"### NuGet Packages ({len(packages)})\n"
            for pkg in packages:
                output += f"- {pkg}\n"
        else:
            output += f"Project '{target}' not found.\n"

    output += "\n**YOU (Claude)** should analyze dependencies to understand coupling."
    return output


def handle_find_references(server, arguments: dict) -> str:
    member_name = arguments["member_name"]
    file_pattern = arguments.get("file_pattern", "*.cs")

    references = []
    for cs_file in server.codebase_path.rglob(file_pattern):
        try:
            with open(cs_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')

            for i, line in enumerate(lines, 1):
                if re.search(rf'\b{re.escape(member_name)}\b', line):
                    references.append({
                        "file": str(cs_file.relative_to(server.codebase_path)),
                        "line": i,
                        "code": line.strip()
                    })

                    if len(references) >= 50:
                        break
        except Exception:
            continue

    output = f"## References to '{member_name}':\n\n"
    output += f"Found {len(references)} references:\n\n"

    by_file = {}
    for ref in references:
        file = ref["file"]
        if file not in by_file:
            by_file[file] = []
        by_file[file].append(ref)

    for file, refs in list(by_file.items())[:10]:
        output += f"### {file}\n"
        output += f"Count: {len(refs)}\n"
        for ref in refs[:5]:
            output += f"  Line {ref['line']}: {ref['code'][:80]}\n"
        output += "\n"

    if len(by_file) > 10:
        output += f"... and {len(by_file) - 10} more files\n"

    output += "\n**YOU (Claude)** should use this to plan safe refactoring."
    return output


# ==================== GLM WORKER TOOLS ====================


def handle_summarize_large_file(server, arguments: dict) -> str:
    if not server.glm_available:
        return "GLM API key not configured. Add GLM_API_KEY to environment variables or .env file."

    file_path = server.codebase_path / arguments["file_path"]
    focus = arguments.get("focus", "")

    if not file_path.exists():
        return f"File not found: {arguments['file_path']}"

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    truncated_content = server._truncate_for_glm(content)

    prompt = f"""Summarize this file:

{f"File: {arguments['file_path']}"}
{f"Focus: {focus}" if focus else ""}

File content (truncated to {len(truncated_content)} chars):
```
{truncated_content}
```

Provide:
1. Overall purpose
2. Main classes and their roles
3. Key methods and what they do
4. Important patterns or conventions"""

    result = server.glm.explore(
        question=f"Summarize file: {arguments['file_path']}",
        context=prompt,
        max_tokens=512
    )

    return f"**GLM Summary:**\n\n{result}"


def handle_get_alternative(server, arguments: dict) -> str:
    if not server.glm_available:
        return "GLM API key not configured."

    your_approach = arguments["your_approach"]
    context = arguments.get("context", "")

    prompt = f"""I have this approach for solving a problem:

{your_approach}

{f"Additional context: {context}" if context else ""}

Can you suggest an alternative approach? Keep it practical and concise."""

    result = server.glm.explore(
        question="Alternative approach",
        context=prompt,
        max_tokens=512
    )

    return f"**GLM's Alternative:**\n\n{result}\n\n**YOU (Claude)** should evaluate this and decide whether to adopt it."


def handle_risk_check(server, arguments: dict) -> str:
    if not server.glm_available:
        return "GLM API key not configured."

    proposed_change = arguments["proposed_change"]
    code = arguments.get("code", "")

    prompt = f"""I'm planning this change:

{proposed_change}

{f"Relevant code:\n```\n{server._truncate_for_glm(code, 3000)}\n```" if code else ""}

What are the potential risks, edge cases, or problems? Be concise and practical."""

    result = server.glm.explore(
        question="Risk check",
        context=prompt,
        max_tokens=512
    )

    return f"**GLM's Risk Assessment:**\n\n{result}\n\n**YOU (Claude)** should validate which risks are real and prioritize them."


def handle_brainstorm(server, arguments: dict) -> str:
    if not server.glm_available:
        return "GLM API key not configured. Brainstorm requires GLM."

    challenge = arguments["challenge"]
    context = arguments.get("context", "")

    result = server.glm.brainstorm(
        challenge=server._truncate_for_glm(challenge, 5000),
        context=server._truncate_for_glm(context, 5000) if context else "",
        max_tokens=512
    )

    return f"**GLM's Creative Perspectives:**\n\n{result}\n\n**YOU (Claude)** should evaluate these ideas critically. Adopt what makes sense, discard what doesn't. You make the final decision."


# ==================== PROJECT-LEVEL TOOLS ====================


def handle_explore_project(server, arguments: dict) -> str:
    result = server.analyzer.analyze_project(arguments["project"])

    if "error" in result:
        return result["error"]

    summary = f"""# {result['project_name']} Project Summary

**Path:** `{result['path']}`
**Total Files:** {result['total_files']}

## Namespaces
{chr(10).join(f"- {ns}" for ns in result['namespaces'])}

## Classes ({len(result['classes'])})
{chr(10).join(f"- **{c['name']}** ({c.get('namespace', 'N/A')})" for c in result['classes'][:20])}
{f"{chr(10)}_... and {len(result['classes']) - 20} more_" if len(result['classes']) > 20 else ""}

## Project References
{chr(10).join(f"- {ref}" for ref in result['project_references']) if result['project_references'] else "None"}

## Package References
{chr(10).join(f"- **{pkg['name']}** ({pkg['version']})" for pkg in result['package_references'])}
"""

    server.memory.save_finding(
        topic=result['project_name'],
        content=summary,
        category="architecture"
    )

    return summary


def handle_analyze_architecture(server, arguments: dict) -> str:
    result = server.analyzer.analyze_architecture()

    output = f"""# Solution Architecture Overview

**Total Projects:** {result['total_projects']}

## Applications
{chr(10).join(f"- {p}" for p in result['categories']['apps'])}

## Libraries
{chr(10).join(f"- {p}" for p in result['categories']['libraries'])}

## Tests
{chr(10).join(f"- {p}" for p in result['categories']['tests'])}
"""

    server.memory.save_finding(
        topic="architecture-overview",
        content=output,
        category="architecture"
    )

    return output


# ==================== TASK TOOLS ====================


def handle_task_start(server, arguments: dict) -> str:
    task_content = f"""# Task: {arguments['name']}

**Started:** {datetime.now().isoformat()}

## Description
{arguments['description']}

## Progress

"""
    server.memory.save_finding(
        topic=arguments['name'],
        content=task_content,
        category=f"tasks/active"
    )

    return f"Task '{arguments['name']}' started. Use task_update to add progress."


def handle_task_update(server, arguments: dict) -> str:
    existing = server.memory.get_topic(arguments['name'], category="tasks/active")

    if not existing:
        return f"Task '{arguments['name']}' not found. Use task_start first."

    updated_content = existing['content'] + f"\n### Update {datetime.now().isoformat()}\n\n{arguments['content']}\n"

    server.memory.save_finding(
        topic=arguments['name'],
        content=updated_content,
        category="tasks/active"
    )

    return f"Task '{arguments['name']}' updated."


def handle_task_status(server, arguments: dict) -> str:
    result = server.memory.get_topic(arguments['name'], category="tasks/active")

    if result:
        return result['content']
    else:
        return f"Task '{arguments['name']}' not found."


# ==================== DISPATCH ====================

# Map tool names to handler functions
TOOL_HANDLERS = {
    "get_config": handle_get_config,
    "switch_codebase": handle_switch_codebase,
    "list_codebases": handle_list_codebases,
    "memory_save": handle_memory_save,
    "memory_get": handle_memory_get,
    "memory_search": handle_memory_search,
    "memory_status": handle_memory_status,
    "learn": handle_learn,
    "session_learn": handle_session_learn,
    "memory_semantic_search": handle_memory_semantic_search,
    "memory_vector_stats": handle_memory_vector_stats,
    "context_offload": handle_context_offload,
    "context_retrieve": handle_context_retrieve,
    "context_stats": handle_context_stats,
    "session_status": handle_session_status,
    "find_similar_code": handle_find_similar_code,
    "lookup_convention": handle_lookup_convention,
    "get_file_summary": handle_get_file_summary,
    "summarize_large_file": handle_summarize_large_file,
    "get_alternative": handle_get_alternative,
    "risk_check": handle_risk_check,
    "brainstorm": handle_brainstorm,
    "task_start": handle_task_start,
    "task_update": handle_task_update,
    "task_status": handle_task_status,
}

# Tools that don't require codebase initialization
NO_INIT_REQUIRED = {"get_config", "switch_codebase", "list_codebases"}

# Tools that auto-capture results to memory
AUTO_CAPTURE_TOOLS = {
    "get_alternative", "risk_check", "brainstorm",
}
