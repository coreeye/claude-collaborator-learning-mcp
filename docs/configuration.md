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
      "args": ["-u", "-m", "claude_collaborator.server"],
      "env": {
        "CODEBASE_PATH": "C:\\path\\to\\your\\project",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

> **Windows note:** Use `python` (or the absolute path to `python.exe`) as
> the `command`. **Do not use `py`** — Windows' Python launcher stays alive
> as a parent process forwarding stdio between the MCP host and the actual
> interpreter, and it adds a pipe-buffer layer that can hold responses
> indefinitely. Symptoms: tool calls appear to hang for minutes, the host
> times out and silently respawns the server, and you see "no codebase
> selected" errors after a successful `switch_codebase`. The `-u` arg and
> `PYTHONUNBUFFERED=1` env are belt-and-braces against any other buffering
> layer; both are safe to include.

### Claude Desktop

Add to your Claude Desktop config:

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "claude-collaborator": {
      "command": "python",
      "args": ["-u", "-m", "claude_collaborator.server"],
      "env": {
        "CODEBASE_PATH": "C:\\path\\to\\your\\project",
        "GLM_API_KEY": "your_api_key_here",
        "PYTHONUNBUFFERED": "1"
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
| `glm_model` | string | `glm-5.1` | GLM model to use |
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
| `GLM_MODEL` | GLM model (default: glm-5.1) |
| `MEMORY_PATH` | Memory storage path |
| `EMBEDDING_MODEL` | Embedding model for semantic search |
| `AUTO_GLM_ENRICH` | Enable GLM auto-enrich (true/false) |
| `PYTHONUNBUFFERED` | Set to `1` to force unbuffered stdout (recommended for stdio MCP transport) |
| `CLAUDE_COLLAB_DEBUG` | Set to `1` to enable verbose tool-call tracing to `%TEMP%/claude_collaborator_debug.log` and a 30 s GLM-stream watchdog that dumps thread stacks. Off by default. |

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

- `glm-5.1` - Flagship model with deep thinking (**default**, verified working)
- `glm-4.6` - Previous generation, also available
- `glm-4-plus` - Enhanced capabilities
- `glm-5.2` - Newest flagship (announced 2026-06-13). Requires API entitlement
  that is still rolling out to direct-API keys; using it before your key has
  access returns `HTTP 403 "You do not have permission to access glm-5.2"`.
  Switch via `GLM_MODEL=glm-5.2` once z.ai enables it for your account.

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

### Tool calls hang for minutes / "session stopped responding" / "no codebase selected" after a successful switch_codebase

These symptoms usually share one of two root causes:

1. **Duplicate MCP server registration.** The same `claude-collaborator`
   server is defined in more than one config file (e.g. both
   `~/.claude.json` and `~/.claude/mcp.json`, or both a global config and
   a project-level `.mcp.json`). The MCP host spawns one server per
   registration; each has its own state, and tool calls round-robin
   between them. Audit with `claude mcp list` and remove duplicates.

2. **Stdio buffering.** The server's response sits in a pipe buffer and
   never reaches the host. Make sure your config has `-u` in `args` AND
   `"PYTHONUNBUFFERED": "1"` in `env`. On Windows, **do not use the `py`
   launcher** — call `python` (or an absolute path to `python.exe`)
   directly.

To get a precise diagnosis, set `CLAUDE_COLLAB_DEBUG=1` in the server's
`env` block, restart the host, reproduce the hang, then read
`%TEMP%\claude_collaborator_debug.log`. Each tool-call lifecycle event is
logged with timestamps and PID. If the GLM stream itself hangs, a built-in
watchdog dumps every Python thread's stack after 30 s of silence so you
can see exactly where the SDK is blocked.

### Reproducing transport hangs deterministically

`tests/test_brainstorm_repro.py` drives the MCP server end-to-end via the
official `mcp` Python client and times a brainstorm call. Run it with:

```bash
python -u tests/test_brainstorm_repro.py
```

Exit code `0` = brainstorm completed under 180 s. Exit code `1` =
exceeded the 600 s hard timeout (real hang). If this passes but Claude
Code still hangs, the issue is host-specific (e.g. a duplicate
registration or a buffering middleman) and not the server.
