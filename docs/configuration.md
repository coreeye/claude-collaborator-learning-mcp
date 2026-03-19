# Configuration Guide

The claude-collaborator server supports flexible configuration through multiple sources.

## Quick Start: Environment Variables (Recommended)

The simplest way to configure is via environment variables in your Claude Desktop config:

```json
{
  "mcpServers": {
    "csharp": {
      "command": "claude-collaborator",
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

1. **Home directory config** - `~/.claude-collaborator/config.json`
2. **Project config files** (searched upward from current directory):
   - `.claude/config.json` (recommended - Claude's standard)
   - `.claude-collaborator.json` (legacy support)
3. **Environment variables** (override everything)

## Configuration Files

### Option 1: `.claude/config.json` (Recommended)

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

### Option 2: `.claude-collaborator.json` (Legacy)

Place this file in your codebase root:

```json
{
  "codebase_path": ".",
  "glm_model": "glm-5",
  "glm_api_key": "your_api_key_here",
  "memory_path": ".codebase-memory"
}
```

### Option 3: Global Config `~/.claude-collaborator/config.json`

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

## Environment Variables

Environment variables override config file settings:

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

### Setting Environment Variables

**Windows (PowerShell):**
```powershell
$env:CSHARP_CODEBASE_PATH="C:\Projects\MyApp"
$env:GLM_API_KEY="your_api_key"
$env:AUTO_CAPTURE_ENABLED="true"
```

**Linux/macOS:**
```bash
export CSHARP_CODEBASE_PATH=/home/user/projects/my-app
export GLM_API_KEY=your_api_key
export AUTO_CAPTURE_ENABLED=true
```

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

## Claude Desktop Configuration

### Method 1: Environment Variables (Recommended)

Works with a single codebase configured upfront:

```json
{
  "mcpServers": {
    "csharp": {
      "command": "claude-collaborator",
      "env": {
        "CSHARP_CODEBASE_PATH": "C:\\Projects\\MyCSharpProject",
        "GLM_API_KEY": "your_api_key"
      }
    }
  }
}
```

### Method 2: Using `cwd` (Auto-Detect from Directory)

```json
{
  "mcpServers": {
    "csharp": {
      "command": "claude-collaborator",
      "cwd": "C:\\Projects\\MyCSharpProject"
    }
  }
}
```

The server auto-detects the codebase from the `cwd` directory.

### Method 3: Using Config File

Create `.claude/config.json` in your project:

```json
{
  "codebase_path": ".",
  "glm_api_key": "your_api_key",
  "auto_capture_enabled": true
}
```

Then in Claude Desktop config:

```json
{
  "mcpServers": {
    "csharp": {
      "command": "claude-collaborator",
      "cwd": "C:\\Projects\\MyCSharpProject"
    }
  }
}
```

### Method 4: Dynamic Switching (For Multiple Projects)

```json
{
  "mcpServers": {
    "csharp": {
      "command": "claude-collaborator"
    }
  }
}
```

Then in conversation:
```
You: "List my C# projects"
Claude: [calls list_codebases] → Shows all repos

You: "Switch to backend project"
Claude: [calls switch_codebase] → Now working on backend
```

## Multiple Projects

### Recommended: Separate Servers with Environment Variables

```json
{
  "mcpServers": {
    "csharp-main": {
      "command": "claude-collaborator",
      "env": {
        "CSHARP_CODEBASE_PATH": "C:\\Projects\\MainApp"
      }
    },
    "csharp-tools": {
      "command": "claude-collaborator",
      "env": {
        "CSHARP_CODEBASE_PATH": "C:\\Projects\\Tools"
      }
    }
  }
}
```

### Alternative: Separate Servers with cwd

```json
{
  "mcpServers": {
    "csharp-main": {
      "command": "claude-collaborator",
      "cwd": "C:\\Projects\\MainApp"
    },
    "csharp-tools": {
      "command": "claude-collaborator",
      "cwd": "C:\\Projects\\Tools"
    }
  }
}
```

### Alternative: Dynamic Switching

One server handles multiple codebases:

```json
{
  "mcpServers": {
    "csharp": {
      "command": "claude-collaborator"
    }
  }
}
```

Use the tools to switch between repos:
- `list_codebases(search_path)` - Discover available repos
- `switch_codebase(path)` - Switch to a specific repo

## Quick Setup Examples

### For a Single Project (Simplest)

1. Set `CSHARP_CODEBASE_PATH` environment variable in Claude Desktop config
2. Server starts immediately with lazy initialization

### For GLM Integration

Add to your `.claude/config.json`:

```json
{
  "codebase_path": ".",
  "glm_api_key": "your_api_key_here"
}
```

Or use environment variable:
```bash
export GLM_API_KEY=your_api_key_here
```

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

- `glm-5` - Latest model (default)
- `glm-4-flash` - Faster responses
- `glm-4-plus` - Enhanced capabilities

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
- Verify `GLM_API_KEY` is set
- Install GLM dependencies: `pip install claude-collaborator[glm]`
- Check API key is valid

### Tools not appearing in Claude Desktop
- Restart Claude Desktop after changing config
- Check Claude Desktop logs for errors
- Verify installation: `pip show claude-collaborator`

### Server startup timeout
- Ensure `CSHARP_CODEBASE_PATH` is set correctly
- Check that vector memory dependencies are installed
- Try disabling auto-capture: `AUTO_CAPTURE_ENABLED=false`
