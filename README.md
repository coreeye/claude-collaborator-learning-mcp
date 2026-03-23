# claude-collaborator

Multi-AI MCP server for C# codebases. Claude + GLM working together.

## Philosophy

**Claude is the architect. GLM is the creative sidekick.**

- **Claude (the Boss)**: Makes decisions, directs work, synthesizes information
- **GLM (the Sidekick)**: Explores alternatives, challenges assumptions, offers fresh perspectives

GLM is configured for **creativity** and **deep thinking** — it considers multiple angles and unconventional ideas. Claude evaluates these insights and makes the final call.

> "The enemy of art is the absence of limitations." — GLM explores the space; Claude finds the best path.

## Features

- **Auto-Learning**: Proactively captures knowledge during work — patterns, workarounds, preferences, architecture insights
- **Two-AI Collaboration**: GLM brainstorms creative approaches; Claude evaluates and decides
- **Persistent Memory**: Semantic vector memory that persists across sessions
- **GLM Auto-Enrich**: GLM automatically provides deeper insights on learnings and architecture analysis in the background
- **Context Management**: Smart context tracking with automatic compaction
- **Pattern Discovery**: Find similar code by concept, lookup codebase conventions

## What This Server Does (and Doesn't Do)

This server focuses on **memory, learning, and two-AI collaboration**. It does NOT provide semantic code navigation — use a Roslyn-based MCP server for find-references, go-to-definition, rename, etc.

| This server | Roslyn-based MCP server |
|-------------|------------------------|
| Learn & remember across sessions | Find references |
| Semantic memory search | Go to definition |
| GLM brainstorm / risk check / alternatives | Find implementations |
| Find similar code by concept | Rename symbol |
| Lookup codebase conventions | Extract method |
| Session & task tracking | Diagnostics & code fixes |

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

Register globally:
```bash
claude mcp add --scope user claude-collaborator -- python -m claude_collaborator.server
```

Or project-only:
```bash
claude mcp add --scope project claude-collaborator -- python -m claude_collaborator.server
```

### Configure GLM API Key

```bash
# Windows
setx GLM_API_KEY "your_api_key_here"

# Linux/macOS
echo 'export GLM_API_KEY=your_api_key_here' >> ~/.bashrc
```

Or use a `.env` file in the project root:
```
GLM_API_KEY=your_api_key_here
GLM_MODEL=glm-5
```

## Available Tools

### Codebase Management
- `switch_codebase` - Switch to a different codebase
- `list_codebases` - Discover codebases (.sln/.git) in a directory
- `get_config` - View current configuration

### Auto-Learning
- `learn` - Record observations during work (auto-categorized, deduplicated, GLM-enriched)
- `session_learn` - Capture session learnings in batch (GLM-enriched)

### Memory
- `memory_save` - Save findings for future sessions
- `memory_search` - Search by keywords
- `memory_semantic_search` - Search by meaning (semantic similarity)
- `memory_get` - Retrieve a specific topic
- `memory_status` / `memory_vector_stats` - View statistics

### Context Management
- `context_retrieve` - Retrieve relevant context for a query
- `context_offload` - Manually trigger context offload to memory
- `context_stats` - View context tracking statistics

### Session & Task Tracking
- `session_status` - View current session state
- `task_start` / `task_update` / `task_status` - Track long-running tasks

### Pattern Discovery & Analysis
- `find_similar_code` - Find code patterns by concept description
- `lookup_convention` - Learn codebase conventions from examples
- `get_file_summary` - Quick file overview with complexity hints

### GLM Collaboration (requires API key)
- `brainstorm` - GLM thinks divergently — unconventional approaches, hidden trade-offs
- `get_alternative` - Get alternative approaches for comparison
- `risk_check` - Identify potential risks before changes
- `summarize_large_file` - GLM summarizes large files to save context

### GLM Auto-Enrich

GLM automatically enriches certain tool results in the background:

| Tool | What GLM adds |
|------|--------------|
| `learn` | Deeper pattern extraction from observations |
| `session_learn` | Recurring themes and knowledge gaps |
| `find_similar_code` | Pattern comparison and best approach analysis |
| `lookup_convention` | Whether conventions should evolve |

Enriched insights are stored in vector memory for future semantic search.

## Configuration

See [docs/configuration.md](docs/configuration.md) for full details.

### Key Settings

| Option | Default | Description |
|--------|---------|-------------|
| `codebase_path` | auto-detected | Path to C# solution |
| `glm_api_key` | (none) | GLM API key |
| `glm_model` | `glm-5` | GLM model to use |
| `embedding_model` | `all-MiniLM-L6-v2` | Embedding model for semantic search |
| `auto_glm_enrich` | `true` | Enable background GLM enrichment |

## CLAUDE.md Setup (Optional)

For richer proactive behavior, add guidance to your CLAUDE.md:

```bash
# Global (all projects)
cp docs/CLAUDE.md.example ~/.claude/CLAUDE.md
```

See [docs/CLAUDE.md.example](docs/CLAUDE.md.example) for the template.

## Development

```bash
pip install -e ".[all]"
python -m pytest tests/ -v -s
```

## License

MIT License - see [LICENSE](LICENSE) for details.
