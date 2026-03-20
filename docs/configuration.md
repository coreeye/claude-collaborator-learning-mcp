# Configuration Guide

The claude-collaborator server supports flexible configuration through multiple sources.

## Quick Start

### Claude Code (Recommended)

Register the MCP server globally:

```bash
claude mcp add --scope user claude-collaborator -- python -m claude_collaborator.server
```

This stores the config in `~/.claude.json` and makes it available in all projects.

For project-only scope:

```bash
claude mcp add --scope project claude-collaborator -- python -m claude_collaborator.server
```

This creates a `.mcp.json` file in the project root:

```json
{
  "mcpServers": {
    "claude-collaborator": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "claude_collaborator.server"],
      "env": {}
    }
  }
}
```

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
        "CSHARP_CODEBASE_PATH": "C:\\path\\to\\your\\project",
        "GLM_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

## Configuration Priority

Settings are loaded in this order (later sources override earlier ones):

1. **Defaults** (built-in)
2. **Home directory config** - `~/.claude-collaborator/config.json`
3. **Project config files** (searched upward from current directory):
   - `.claude/config.json` (recommended — Claude's standard)
   - `.claude-collaborator.json` (legacy support)
4. **`.env` file** in the project root (loaded via python-dotenv)
5. **Environment variables** (highest priority — override everything)

## Configuration Sources

### Option 1: System Environment Variable (Recommended for API Keys)

Set environment variables persistently so they work in all projects:

**Windows:**
```cmd
setx GLM_API_KEY "your_api_key_here"
setx GLM_MODEL "glm-5"
```

**Linux/macOS:**
```bash
echo 'export GLM_API_KEY=your_api_key_here' >> ~/.bashrc
echo 'export GLM_MODEL=glm-5' >> ~/.bashrc
source ~/.bashrc
```

### Option 2: `.env` File (Recommended for Project-Specific Settings)

Create a `.env` file in your project root:

```
CSHARP_CODEBASE_PATH=/path/to/your/csharp/project
GLM_API_KEY=your_api_key_here
GLM_MODEL=glm-5
```

The server loads this automatically via python-dotenv.

### Option 3: `.claude/config.json` (Project Config)

Place this file in your codebase root:

```json
{
  "codebase_path": ".",
  "glm_model": "glm-5",
  "glm_api_key": "your_api_key_here",
  "memory_path": ".codebase-memory",
  "auto_capture_enabled": true
}
```

### Option 4: `.claude-collaborator.json` (Legacy)

Place this file in your codebase root:

```json
{
  "codebase_path": ".",
  "glm_model": "glm-5",
  "glm_api_key": "your_api_key_here",
  "memory_path": ".codebase-memory"
}
```

### Option 5: Global Config `~/.claude-collaborator/config.json`

For settings that apply to all projects:

```json
{
  "glm_model": "glm-5",
  "glm_api_key": "your_global_api_key",
  "auto_capture_enabled": true
}
```

## Configuration Options

### Basic Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `codebase_path` | string | auto-detected | Path to C# solution root (`.sln` file) |
| `glm_api_key` | string | (none) | API key for GLM integration |
| `glm_model` | string | `glm-5` | GLM model to use |
| `memory_path` | string | `.codebase-memory` | Path for memory storage |

### Vector Memory Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `embedding_model` | string | `all-MiniLM-L6-v2` | Sentence transformer model for embeddings |
| `vector_db_path` | string | `.codebase-memory/vectors.db` | Vector database file path |
| `context_threshold` | integer | `50000` | Context size in chars before offload |
| `auto_capture_enabled` | boolean | `true` | Auto-capture tool results to memory |

### Cache Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `cache_size` | integer | `100` | Maximum number of files to cache |
| `cache_ttl` | integer | `3600` | Cache TTL in seconds (1 hour) |

### Compaction Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `compaction_threshold` | float | `0.8` | Utilization % before compaction (0.0-1.0) |
| `compaction_aggressive` | boolean | `false` | Enable aggressive compaction |

### GLM Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `auto_glm_enrich` | boolean | `true` | Automatically enrich with GLM in background |
| `glm_proactive_suggestions` | boolean | `true` | Show context-aware GLM tips |

## Environment Variables

Environment variables override all other config sources:

### Basic Variables

| Variable | Maps To | Example |
|----------|---------|---------|
| `CSHARP_CODEBASE_PATH` | `codebase_path` | `C:\Projects\MyApp` |
| `CODEBASE_PATH` | `codebase_path` (alias) | `C:\Projects\MyApp` |
| `GLM_API_KEY` | `glm_api_key` | `your_api_key` |
| `GLM_MODEL` | `glm_model` | `glm-5` |
| `MEMORY_PATH` | `memory_path` | `.codebase-memory` |

### Vector Memory Variables

| Variable | Maps To | Example |
|----------|---------|---------|
| `EMBEDDING_MODEL` | `embedding_model` | `all-MiniLM-L6-v2` |
| `VECTOR_DB_PATH` | `vector_db_path` | `.codebase-memory/vectors.db` |
| `CONTEXT_THRESHOLD` | `context_threshold` | `50000` |
| `AUTO_CAPTURE_ENABLED` | `auto_capture_enabled` | `true` |

### Cache Variables

| Variable | Maps To | Example |
|----------|---------|---------|
| `CACHE_SIZE` | `cache_size` | `100` |
| `CACHE_TTL` | `cache_ttl` | `3600` |

### GLM Variables

| Variable | Maps To | Example |
|----------|---------|---------|
| `AUTO_GLM_ENRICH` | `auto_glm_enrich` | `true` |
| `GLM_PROACTIVE_SUGGESTIONS` | `glm_proactive_suggestions` | `true` |

## Auto-Detection

When `codebase_path` is not explicitly set, the server automatically detects it by searching upward from the current directory for:

1. A `.sln` file (Visual Studio Solution)
2. A `.git` directory (Git repository root)

This means **no configuration is needed** when running the server from within your project!

## Automatic Memory Capture

When enabled (`auto_capture_enabled: true`), the server automatically captures tool results to semantic memory. This helps:

- **Preserve information**: Tool results are saved even if truncated in responses
- **Semantic search**: Find related information via `memory_semantic_search`
- **Context retrieval**: Auto-retrieve relevant context before tool calls

Tools with auto-capture enabled:
- `extract_class_structure`
- `get_file_summary`
- `find_class_usages`
- `find_implementations`
- `get_callers`

## Dynamic Codebase Switching

You can switch codebases during conversation using these tools:

### `switch_codebase(path)`
Switch to a different codebase during conversation.

```python
switch_codebase(path="C:\\Projects\\MyBackend")
```

### `list_codebases(search_path?)`
Discover all codebases in a directory.

```python
list_codebases(search_path="C:\\Projects")
# Returns: List of .sln files and .git repos found
```

## Multiple Projects

### Recommended: Dynamic Switching

One server handles multiple codebases. Use the tools to switch between repos:
- `list_codebases(search_path)` - Discover available repos
- `switch_codebase(path)` - Switch to a specific repo

### Alternative: Separate Servers (Claude Desktop)

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

## GLM Integration

GLM provides additional AI-powered code exploration capabilities.

### Getting an API Key

1. Visit [https://open.bigmodel.cn/](https://open.bigmodel.cn/)
2. Create an account
3. Generate an API key

### Installing GLM Dependencies

```bash
pip install claude-collaborator[glm]
```

Or manually:
```bash
pip install zai-sdk openai
```

### Available Models

- `glm-5` - Latest model with deep thinking (default)
- `glm-4-flash` - Faster responses
- `glm-4-plus` - Enhanced capabilities

## Auto-Learning & CLAUDE.md Setup

### Proactive Learning (Works Automatically)

The `learn` and `brainstorm` tools have proactive descriptions that guide Claude to use them automatically. No extra configuration needed -- just install the MCP server.

### Enhanced Setup with CLAUDE.md (Optional)

For richer proactive behavior, copy the sample CLAUDE.md:

```bash
# Global (all projects) -- recommended
cp docs/CLAUDE.md.example ~/.claude/CLAUDE.md

# Or project-specific
cp docs/CLAUDE.md.example /path/to/your/project/CLAUDE.md
```

The CLAUDE.md adds detailed guidance for:
- When to call `learn` (and when not to)
- When to use `brainstorm`, `get_alternative`, `risk_check`
- Checking `memory_semantic_search` at session start
- Calling `session_learn` at session end

### Auto-Learning Settings

| Option | Default | Description |
|--------|---------|-------------|
| `learn_dedup_threshold` | `0.85` | Similarity threshold for deduplication |
| `learn_glm_extract` | `true` | Use GLM to extract insights from session summaries |

| Variable | Description |
|----------|-------------|
| `LEARN_DEDUP_THRESHOLD` | Similarity threshold (0-1) |
| `LEARN_GLM_EXTRACT` | Enable GLM extraction (true/false) |

## Project Structure Detection

The analyzer auto-detects common C# project layouts:

### Flat Layout
```
MySolution/
├── MySolution.sln
├── Project1/
│   └── Project1.csproj
└── Project2/
    └── Project2.csproj
```

### Src Layout
```
MySolution/
├── MySolution.sln
└── src/
    ├── Project1/
    │   └── Project1.csproj
    └── Project2/
        └── Project2.csproj
```

## Troubleshooting

### "Codebase path not found"
- Ensure your project has a `.sln` file or is a git repository
- Or explicitly set `codebase_path` in config or environment variable
- Check that the path exists

### Config file not being read
- Ensure the file is valid JSON
- Check file name matches exactly (`.claude/config.json` or `.claude-collaborator.json`)
- Verify the file is in the project root or a parent directory

### GLM not working
- Verify `GLM_API_KEY` is set: check with `echo $GLM_API_KEY` (or `echo %GLM_API_KEY%` on Windows)
- Install GLM dependencies: `pip install claude-collaborator[glm]`
- Check API key is valid at [https://open.bigmodel.cn/](https://open.bigmodel.cn/)

### Tools not appearing
- **Claude Code**: Run `claude mcp list` to check server status
- **Claude Desktop**: Restart Claude Desktop after changing config
- Verify installation: `pip show claude-collaborator`

### Server startup timeout
- Ensure `CSHARP_CODEBASE_PATH` is set correctly
- Check that vector memory dependencies are installed: `pip install claude-collaborator[vector]`
- Try disabling auto-capture: `AUTO_CAPTURE_ENABLED=false`
