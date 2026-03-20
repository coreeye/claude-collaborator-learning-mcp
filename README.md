# claude-collaborator

Multi-AI MCP server for C# codebases. Claude + GLM working together.

## Philosophy

**Claude is the architect. GLM is the creative sidekick.**

This MCP server empowers Claude with a creative companion:

- **Claude (the Boss)**: Makes decisions, directs work, and synthesizes information
- **GLM (the Sidekick)**: Explores alternatives, challenges assumptions, and offers fresh perspectives

GLM is configured for **creativity** and **deep thinking** — it doesn't just answer questions, it considers multiple angles and unconventional ideas. Claude then evaluates these insights and makes the final call. This two-AI approach surfaces possibilities that a single model might miss.

> "The enemy of art is the absence of limitations." — GLM explores the space; Claude finds the best path.

## Features

- **Auto-Learning**: Claude proactively captures knowledge during work -- patterns, workarounds, preferences, architecture insights
- **Two-AI Collaboration**: GLM brainstorms creative approaches; Claude evaluates and decides
- **Persistent Memory**: Never re-explain your architecture across sessions
- **Automatic Memory Capture**: Tool results automatically saved to semantic memory
- **Context Management**: Smart context tracking with automatic compaction
- **Code Analysis**: Explore any C# project instantly
- **GLM Auto-Enrich**: GLM automatically provides insights in the background
- **GLM Proactive Tips**: Context-aware suggestions for when to use GLM
- **Fast Startup**: Lazy initialization prevents server startup timeout

## Installation

```bash
pip install claude-collaborator
```

Or install from source with all extras:
```bash
git clone https://github.com/coreeye/claude-collaborator-mcp.git
cd claude-collaborator-mcp
pip install -e ".[all]"
```

## Quick Start

### Claude Code (Recommended)

Register the MCP server globally so it works in any project:

```bash
claude mcp add --scope user claude-collaborator -- python -m claude_collaborator.server
```

Or register it for a specific project only:

```bash
claude mcp add --scope project claude-collaborator -- python -m claude_collaborator.server
```

This writes to `.mcp.json` in the project root.

### Claude Desktop

Add to your Claude Desktop config:

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "claude-collaborator": {
      "command": "python",
      "args": ["-m", "claude_collaborator.server"],
      "env": {
        "CSHARP_CODEBASE_PATH": "C:\\path\\to\\your\\csharp\\project",
        "GLM_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

### Configure GLM API Key

Set the API key using any of these methods (in priority order):

1. **System environment variable** (recommended — works everywhere):
   ```bash
   # Windows
   setx GLM_API_KEY "your_api_key_here"

   # Linux/macOS
   echo 'export GLM_API_KEY=your_api_key_here' >> ~/.bashrc
   ```

2. **`.env` file** in the project root:
   ```
   GLM_API_KEY=your_api_key_here
   GLM_MODEL=glm-5
   ```

3. **Config file** (`.claude/config.json` in the project root):
   ```json
   {
     "glm_api_key": "your_api_key_here"
   }
   ```

### Dynamic Codebase Switching

You can switch codebases during conversation:

- **`switch_codebase(path)`** - Switch to a different repository
- **`list_codebases(search_path?)`** - Discover available codebases

```
You: "List all my C# projects in C:\Projects"
Claude: [calls list_codebases] "Found 3 codebases..."
You: "Switch to the backend project"
Claude: [calls switch_codebase] "Now working on Backend"
```

## Available Tools

### Codebase Management
- `switch_codebase` - Switch to a different codebase dynamically
- `list_codebases` - Discover codebases (.sln/.git) in a directory
- `get_config` - View current configuration and status

### Auto-Learning
- `learn` - **Proactive**: Record observations and learnings during work (auto-categorized, deduplicated)
- `session_learn` - Capture session learnings in batch at end of work

### Memory
- `memory_save` - Save findings for future sessions
- `memory_search` - Search saved knowledge by keywords
- `memory_semantic_search` - Search by meaning (semantic similarity)
- `memory_get` - Retrieve a specific topic
- `memory_status` - View memory statistics
- `memory_vector_stats` - View vector database statistics

### Context Management
- `context_retrieve` - Retrieve relevant context for a query
- `context_offload` - Manually trigger context offload to memory
- `context_stats` - View context tracking statistics

### Session & Task Tracking
- `session_status` - View current session state and active task
- `task_start` - Start a new long-running task
- `task_status` - Get task status and history
- `task_update` - Update task with findings

### Code Analysis
- `explore_project` - Analyze a C# project
- `analyze_architecture` - Get overview of all projects
- `extract_class_structure` - Parse class structure
- `get_file_summary` - Get file statistics
- `summarize_large_file` - GLM summarizes large files
- `find_similar_code` - Find code patterns
- `lookup_convention` - Lookup coding conventions

### Navigation
- `get_callers` - Find code that calls a method/class
- `find_class_usages` - Find all usages of a class
- `find_implementations` - Find interface implementations
- `find_references` - Find member references
- `list_dependencies` - Map file/project dependencies

### GLM Integration (requires API key)
- `brainstorm` - **Proactive**: GLM thinks divergently about challenges -- unconventional approaches, hidden trade-offs
- `get_alternative` - Get alternative approaches from GLM for comparison
- `risk_check` - GLM identifies potential risks before changes
- `summarize_large_file` - GLM summarizes large files to save context

## Configuration

### Configuration Priority

Settings are loaded in this order (later sources override earlier ones):

1. **Defaults** (built-in)
2. **Home config**: `~/.claude-collaborator/config.json`
3. **Project config files** (searched upward from current directory):
   - `.claude/config.json` (recommended)
   - `.claude-collaborator.json` (legacy)
4. **`.env` file** in the project root (loaded via python-dotenv)
5. **Environment variables** (highest priority)

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `codebase_path` | auto-detected | Path to C# solution |
| `glm_api_key` | (none) | GLM API key |
| `glm_model` | `glm-5` | GLM model to use |
| `memory_path` | `.codebase-memory` | Memory storage path |

### Vector Memory Settings

| Option | Default | Description |
|--------|---------|-------------|
| `embedding_model` | `all-MiniLM-L6-v2` | Sentence transformer model |
| `vector_db_path` | `.codebase-memory/vectors.db` | Vector database path |
| `context_threshold` | `50000` | Chars before context offload |
| `auto_capture_enabled` | `true` | Auto-capture tool results |

### Cache Settings

| Option | Default | Description |
|--------|---------|-------------|
| `cache_size` | `100` | Max files to cache |
| `cache_ttl` | `3600` | Cache TTL in seconds |

### GLM Settings

| Option | Default | Description |
|--------|---------|-------------|
| `auto_glm_enrich` | `true` | Enable background GLM enrichment |
| `glm_proactive_suggestions` | `true` | Show context-aware GLM tips |

### Auto-Learning Settings

| Option | Default | Description |
|--------|---------|-------------|
| `learn_dedup_threshold` | `0.85` | Similarity threshold for deduplication (0-1) |
| `learn_glm_extract` | `true` | Use GLM to extract insights from session summaries |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `CSHARP_CODEBASE_PATH` | Path to your C# solution |
| `CODEBASE_PATH` | Alias for `CSHARP_CODEBASE_PATH` |
| `GLM_API_KEY` | GLM API key |
| `GLM_MODEL` | GLM model |
| `MEMORY_PATH` | Memory storage path |
| `EMBEDDING_MODEL` | Embedding model for semantic search |
| `VECTOR_DB_PATH` | Vector database path |
| `CONTEXT_THRESHOLD` | Context threshold for offload |
| `AUTO_CAPTURE_ENABLED` | Enable auto-capture (true/false) |
| `CACHE_SIZE` | File cache size |
| `CACHE_TTL` | File cache TTL |
| `AUTO_GLM_ENRICH` | Enable GLM auto-enrich (true/false) |
| `GLM_PROACTIVE_SUGGESTIONS` | Enable GLM tips (true/false) |

## Automatic Memory Capture

The server automatically captures tool results to semantic memory when:
- Result length exceeds 100 characters
- Tool is in auto-capture list (e.g., `extract_class_structure`, `get_file_summary`, `find_class_usages`)

Captured results are:
1. Stored in vector database for semantic search
2. Truncated in responses to manage context (1500 char limit)
3. Available for retrieval via `context_retrieve` and `memory_semantic_search`

## Multiple Projects

### Recommended: Dynamic Switching

Use a single server and switch between projects:

```
You: "List my C# projects" → list_codebases()
You: "Switch to MainApp" → switch_codebase(path="C:\\Projects\\MainApp")
```

### Alternative: Separate Servers

Configure multiple servers in Claude Desktop:

```json
{
  "mcpServers": {
    "csharp-main": {
      "command": "python",
      "args": ["-m", "claude_collaborator.server"],
      "env": {
        "CSHARP_CODEBASE_PATH": "C:\\Projects\\MainApp"
      }
    },
    "csharp-tools": {
      "command": "python",
      "args": ["-m", "claude_collaborator.server"],
      "env": {
        "CSHARP_CODEBASE_PATH": "C:\\Projects\\Tools"
      }
    }
  }
}
```

## GLM Integration (Optional)

GLM serves as Claude's creative sidekick, configured for maximum creativity and deep reasoning:

```bash
# Install GLM dependencies
pip install claude-collaborator[glm]

# Set your API key
setx GLM_API_KEY "your_api_key_here"      # Windows (persistent)
export GLM_API_KEY=your_api_key_here       # Linux/macOS
```

### Auto-Enrich Mode

GLM automatically provides insights in the background for certain tools:

- `extract_class_structure` - GLM analyzes patterns and refactoring opportunities
- `find_class_usages` - GLM identifies coupling issues
- `find_implementations` - GLM compares implementation approaches
- `find_similar_code` - GLM provides deeper pattern analysis
- `lookup_convention` - GLM evaluates if the convention should evolve

These run **non-blocking** in the background, so Claude never waits.

### Proactive Suggestions

The server intelligently suggests using GLM based on context:

| Context | Suggestion |
|---------|------------|
| Result is large (>5000 chars) | "Use `summarize_large_file` to have GLM analyze it" |
| After discovery tools | "Use `get_alternative` for different approaches" |
| After analysis tools | "Use `risk_check` before making changes" |

### GLM Configuration

GLM runs with **temperature 1.0** and **deep thinking enabled** — optimized to:
- Generate diverse, creative ideas
- Consider unconventional approaches
- Challenge Claude's assumptions
- Provide alternative viewpoints

### Available GLM Models

- `glm-5` - Latest model with deep thinking (default)
- `glm-4-flash` - Faster responses
- `glm-4-plus` - Enhanced capabilities

## Auto-Learning & Two-AI Collaboration

### How It Works

The MCP server has proactive tool descriptions that guide Claude to automatically:

1. **Learn during work** -- Call `learn` when discovering patterns, workarounds, edge cases, or architecture insights
2. **Brainstorm with GLM** -- Call `brainstorm` before committing to significant approaches
3. **Recall past learnings** -- Call `memory_semantic_search` when starting new work

This works automatically in any project where the MCP server is connected.

### Enhanced Setup with CLAUDE.md (Optional)

For richer proactive behavior, copy the sample CLAUDE.md to your global Claude config:

```bash
# Global (all projects)
cp docs/CLAUDE.md.example ~/.claude/CLAUDE.md

# Or project-specific
cp docs/CLAUDE.md.example /path/to/your/project/CLAUDE.md
```

The CLAUDE.md adds detailed guidance for when to learn, when to brainstorm, and how to use GLM's input effectively.

### What Gets Learned

The `learn` tool auto-categorizes observations into:

| Category | Examples |
|----------|---------|
| `workflow` | Build processes, deployment steps, CI/CD pipelines |
| `preferences` | User conventions, naming standards, style preferences |
| `workarounds` | Known issues and fixes, temporary solutions |
| `patterns` | Code patterns, architecture conventions |
| `decisions` | Design decisions and their rationale |
| `edge_cases` | Gotchas, caveats, things that don't work as expected |
| `architecture` | System structure, service boundaries, dependencies |
| `context` | Project background, team context, requirements |

Observations are automatically deduplicated -- if a similar learning already exists, it's updated rather than duplicated.

## Development

```bash
# Install in development mode
pip install -e ".[all]"

# Run tests
py -m unittest tests.test_analyzer
py tests/test_auto_memory.py

# Format code
black src/
```

## Documentation

See [docs/configuration.md](docs/configuration.md) for detailed configuration options.

## License

MIT License - see [LICENSE](LICENSE) for details.
