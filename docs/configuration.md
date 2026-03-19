# Configuration Guide

The claude-collaborator server supports flexible configuration through multiple sources, including **dynamic codebase switching** for working with multiple repositories.

## Dynamic Codebase Switching (Recommended)

The server can now switch between codebases on-the-fly without reconfiguration:

```json
{
  "mcpServers": {
    "csharp": {
      "command": "claude-collaborator"
    }
  }
}
```

Then simply tell Claude which codebase to work with:
- "Switch to my backend project" → Claude calls `switch_codebase`
- "List all C# projects in C:\Projects" → Claude calls `list_codebases`

**No `cwd` needed!** The server starts uninitialized and you switch to repos as needed. Each codebase gets its own persistent memory store (stored at `{codebase_path}/.codebase-memory`).

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
  "memory_path": ".codebase-memory"
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
  "glm_api_key": "your_global_api_key"
}
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `codebase_path` | string | auto-detected | Path to C# solution root (`.sln` file) |
| `glm_api_key` | string | (none) | API key for GLM integration |
| `glm_model` | string | `glm-5` | GLM model to use |
| `memory_path` | string | `.codebase-memory` | Path for memory storage |

## Environment Variables

Environment variables override config file settings:

| Variable | Maps To |
|----------|---------|
| `CSHARP_CODEBASE_PATH` | `codebase_path` |
| `CODEBASE_PATH` | `codebase_path` (alias) |
| `GLM_API_KEY` | `glm_api_key` |
| `GLM_MODEL` | `glm_model` |
| `MEMORY_PATH` | `memory_path` |

### Setting Environment Variables

**Windows (PowerShell):**
```powershell
$env:CSHARP_CODEBASE_PATH="C:\Projects\MyApp"
$env:GLM_API_KEY="your_api_key"
```

**Linux/macOS:**
```bash
export CSHARP_CODEBASE_PATH=/home/user/projects/my-app
export GLM_API_KEY=your_api_key
```

## Auto-Detection

When `codebase_path` is not explicitly set, the server automatically detects it by searching upward from the current directory for:

1. A `.sln` file (Visual Studio Solution)
2. A `.git` directory (Git repository root)

This means **no configuration is needed** when running the server from within your project!

## New Tools for Dynamic Switching

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

### Method 1: Dynamic Switching (Recommended - Simplest!)

Works with multiple codebases, no reconfiguration needed:

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

### Method 3: Using Environment Variables

Create `.claude/config.json` in your project:

```json
{
  "codebase_path": ".",
  "glm_api_key": "your_api_key"
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

## Multiple Projects

### Recommended: Dynamic Switching

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

Use the new tools to switch between repos:
- `list_codebases(search_path)` - Discover available repos
- `switch_codebase(path)` - Switch to a specific repo

### Alternative: Separate Servers

Configure multiple servers if you prefer:

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

## Quick Setup Examples

### For a Single Project (Simplest)

1. Navigate to your project in terminal
2. The server auto-detects your codebase
3. In Claude Desktop, just set `cwd` to your project path

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
- Or explicitly set `codebase_path` in config
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
