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

- **Persistent Memory**: Never re-explain your architecture across sessions
- **Code Analysis**: Explore any C# project instantly
- **GLM Integration**: Offload research to another AI model
- **Auto-Detection**: Finds your codebase automatically
- **Zero Config**: Works with just `cwd` setting in Claude Desktop

## Installation

```bash
pip install claude-collaborator
```

Or install from source:
```bash
git clone https://github.com/coreye/claude-collaborator-mcp.git
cd claude-collaborator-mcp
pip install -e .
```

## Quick Start

### Simplest Configuration (Recommended)

Just add to Claude Desktop config - no `cwd` needed! The server can dynamically switch between codebases:

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "csharp": {
      "command": "claude-collaborator"
    }
  }
}
```

When you want to work with a project, simply tell Claude:
> "Switch to my backend project at C:\Projects\Backend"

Claude will call `switch_codebase` and all subsequent tools work on that codebase. Each codebase maintains its own persistent memory store.

### Dynamic Codebase Switching

The server supports multiple codebases without reconfiguration:

- **`switch_codebase(path)`** - Switch to a different repository
- **`list_codebases(search_path?)`** - Discover available codebases

```
You: "List all my C# projects in C:\Projects"
Claude: [calls list_codebases] "Found 3 codebases..."
You: "Switch to the backend project"
Claude: [calls switch_codebase] "Now working on Backend"
```

### With Config File (Optional)

Create `.claude/config.json` in your project:

```json
{
  "codebase_path": ".",
  "glm_api_key": "your_key_here"
}
```

Then in Claude Desktop:
```json
{
  "mcpServers": {
    "csharp": {
      "command": "claude-collaborator",
      "cwd": "C:\\path\\to\\your\\csharp\\project"
    }
  }
}
```

### With Environment Variables (Alternative)

```json
{
  "mcpServers": {
    "csharp": {
      "command": "claude-collaborator",
      "env": {
        "CSHARP_CODEBASE_PATH": "C:\\path\\to\\your\\project"
      }
    }
  }
}
```

## Available Tools

### Codebase Management
- `switch_codebase` - Switch to a different codebase dynamically
- `list_codebases` - Discover codebases (.sln/.git) in a directory
- `get_config` - View current configuration and status

### Memory
- `memory_save` - Save findings for future sessions
- `memory_search` - Search saved knowledge
- `memory_get` - Retrieve a specific topic
- `memory_status` - View memory statistics

### Code Analysis
- `explore_project` - Analyze a C# project
- `analyze_architecture` - Get overview of all projects
- `extract_class_structure` - Parse class structure
- `get_file_summary` - Get file statistics
- `find_similar_code` - Find code patterns
- `lookup_convention` - Lookup coding conventions

### Navigation
- `get_callers` - Find code that calls a method/class
- `find_class_usages` - Find all usages of a class
- `find_implementations` - Find interface implementations
- `find_references` - Find member references
- `list_dependencies` - Map file/project dependencies

### GLM Integration (requires API key)
- `glm_explore` - Ask GLM questions for alternative perspectives
- `summarize_large_file` - GLM summarizes large files
- `get_alternative` - Get alternative approaches from GLM
- `risk_check` - GLM identifies potential risks

## Configuration

The server looks for configuration in this priority order:

1. **Environment variables** (highest priority)
2. **Project config files** (searched upward):
   - `.claude/config.json` (recommended)
   - `.claude-collaborator.json` (legacy)
3. **Home config**: `~/.claude-collaborator/config.json`
4. **Auto-detection**: Finds `.sln` or `.git` automatically

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `codebase_path` | auto-detected | Path to C# solution |
| `glm_api_key` | (none) | GLM API key |
| `glm_model` | `glm-5` | GLM model to use |
| `memory_path` | `.codebase-memory` | Memory storage path |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `CSHARP_CODEBASE_PATH` | Path to your C# solution |
| `GLM_API_KEY` | GLM API key |
| `GLM_MODEL` | GLM model |
| `MEMORY_PATH` | Memory storage path |

## Auto-Detection

When no path is configured, the server automatically searches upward from the current directory for:
- A `.sln` file (Visual Studio Solution)
- A `.git` directory (Git repository root)

This means **zero configuration** when running from within your project!

## Multiple Projects

### Recommended: Dynamic Switching

With dynamic switching, you only need one server:

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
- "List my C# projects" → `list_codebases()`
- "Switch to MainApp" → `switch_codebase(path="C:\\Projects\\MainApp")`
- "Now switch to Tools" → `switch_codebase(path="C:\\Projects\\Tools")`

### Alternative: Separate Servers

You can still configure separate servers if you prefer:

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

## GLM Integration (Optional)

GLM serves as Claude's creative sidekick, configured for maximum creativity and deep reasoning:

```bash
# Install GLM dependencies
pip install claude-collaborator[glm]

# Set your API key (in .claude/config.json or environment)
export GLM_API_KEY=your_api_key_here
```

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

## Development

```bash
# Install in development mode
pip install -e ".[glm]"

# Run tests
py -m unittest tests.test_analyzer

# Format code
black src/
```

## Documentation

See [docs/configuration.md](docs/configuration.md) for detailed configuration options.

## License

MIT License - see [LICENSE](LICENSE) for details.
