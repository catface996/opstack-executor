# Hierarchical Multi-Agent System

A Python framework for building and executing hierarchical teams of AI agents with supervisor-worker architecture and dependency management.

## Features

- **Hierarchical Architecture**: Top-level supervisor → Team supervisors → Worker agents
- **Streaming Execution**: Real-time status updates and result streaming
- **Standardized Output**: Unified result format and error handling
- **Extensible Design**: Plugin-based agent and tool management
- **Multi-LLM Support**: OpenAI, OpenRouter, AWS Bedrock integration
- **Secure Key Management**: Encrypted API key storage and management

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/hierarchical-agents/hierarchical-agents.git
cd hierarchical-agents

# Install in development mode
pip install -e ".[dev]"

# Copy environment configuration
cp .env.example .env
# Edit .env with your API keys and configuration
```

### Basic Usage

```python
from hierarchical_agents import HierarchicalManager, HierarchicalTeam

# Create a hierarchical team configuration
team_config = {
    "team_name": "research_team",
    "description": "Research and analysis team",
    # ... (see examples for full configuration)
}

# Build and execute the team
manager = HierarchicalManager()
team = manager.build_hierarchy(team_config)
results = await manager.execute_team(team)
```

## Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run with coverage
pytest --cov=src/hierarchical_agents --cov-report=html
```

### Code Quality

```bash
# Format code
black src/ tests/
isort src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/ tests/
```

## Architecture

The system follows a three-tier hierarchical architecture:

1. **Top-level Supervisor**: Coordinates overall execution and team selection
2. **Team Supervisors**: Manage individual teams and agent routing
3. **Worker Agents**: Execute specific tasks with tool integration

## Configuration

See `.env.example` for configuration options and `examples/` directory for sample team configurations.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

## Support

- Documentation: [Read the Docs](https://hierarchical-agents.readthedocs.io)
- Issues: [GitHub Issues](https://github.com/hierarchical-agents/hierarchical-agents/issues)
- Discussions: [GitHub Discussions](https://github.com/hierarchical-agents/hierarchical-agents/discussions)