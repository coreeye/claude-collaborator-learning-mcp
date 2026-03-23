# Configuration Guide

The claude-collaborator server supports flexible configuration through multiple sources.

## Quick Start

### Claude Code (Recommended)

Register the MCP server globally:

```bash
claude mcp add --scope user claude-collaborator -- python -m claude_collaborator.server
```

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
      "env": {
        "CODEBASE_PATH": "C:\\path\\to\\your\\project"
      }
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
        "CODEBASE_PATH": "C:\\path\\to\\your\\project",
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
   - `.claude/config.json` (recommended)
   - `.claude-collaborator.json` (legacy)
4. **`.env` file** in the project root (loaded via python-dotenv)
5. **Environment variables** (highest priority)

## Configuration Options

### Basic Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `codebase_path` | string | auto-detected | Path to C# solution root |
| `glm_api_key` | string | (none) | API key for GLM integration |
| `glm_model` | string | `glm-5` | GLM model to use |
| `memory_path` | string | `.codebase-memory` | Path for memory storage |

### Vector Memory Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `embedding_model` | string | `all-MiniLM-L6-v2` | Sentence transformer model |
| `vector_db_path` | string | `.codebase-memory/vectors.db` | Vector database path |
| `context_threshold` | integer | `50000` | Context size before offload |
| `auto_capture_enabled` | boolean | `true` | Auto-capture tool results |

### Cache Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `cache_size` | integer | `100` | Max files to cache |
| `cache_ttl` | integer | `3600` | Cache TTL in seconds |

### GLM Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `auto_glm_enrich` | boolean | `true` | Background GLM enrichment for learn/architecture tools |
| `glm_proactive_suggestions` | boolean | `true` | Context-aware GLM tips |

### Auto-Learning Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `learn_dedup_threshold` | float | `0.85` | Similarity threshold for deduplication |
| `learn_glm_extract` | boolean | `true` | Use GLM to extract insights from session summaries |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CODEBASE_PATH` | Path to your C# solution |
| `GLM_API_KEY` | GLM API key |
| `GLM_MODEL` | GLM model (default: glm-5) |
| `MEMORY_PATH` | Memory storage path |
| `EMBEDDING_MODEL` | Embedding model for semantic search |
| `AUTO_GLM_ENRICH` | Enable GLM auto-enrich (true/false) |

## Auto-Detection

When `codebase_path` is not set, the server searches upward from the current directory for `.sln` files or `.git` directories. No configuration needed when running from within your project.

## GLM Integration

### Getting an API Key

1. Visit [https://open.bigmodel.cn/](https://open.bigmodel.cn/)
2. Create an account
3. Generate an API key

### Installing GLM Dependencies

```bash
pip install claude-collaborator[glm]
```

### Available Models

- `glm-5` - Latest model with deep thinking (default)
- `glm-4-flash` - Faster responses
- `glm-4-plus` - Enhanced capabilities

## Troubleshooting

### "Codebase path not found"
- Ensure your project has a `.sln` file or is a git repository
- Or set `CODEBASE_PATH` environment variable

### GLM not working
- Verify `GLM_API_KEY` is set
- Install dependencies: `pip install claude-collaborator[glm]`

### Embedding model slow on first call
- The model (~80MB) is pre-loaded at server startup (takes ~8s)
- Subsequent calls are instant
- Model is cached locally in `~/.cache/huggingface/`

### Tools not appearing
- **Claude Code**: Run `claude mcp list` to check server status
- **Claude Desktop**: Restart after config changes
