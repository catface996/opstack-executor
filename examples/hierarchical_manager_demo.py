#!/usr/bin/env python3
"""
Hierarchical Manager Demo

This script demonstrates the basic usage of the HierarchicalManager
for creating and managing hierarchical multi-agent teams.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.hierarchical_agents.hierarchical_manager import (
    HierarchicalManager,
    create_hierarchical_manager,
    build_team_from_config
)
from src.hierarchical_agents.data_models import ExecutionConfig


def create_sample_team_config() -> Dict[str, Any]:
    """Create a sample hierarchical team configuration."""
    return {
        "team_name": "ai_research_team",
        "description": "AI Research and Analysis Team",
        "top_supervisor_config": {
            "llm_config": {
                "provider": "openai",
                "model": "gpt-4o",
                "temperature": 0.3,
                "max_tokens": 1000
            },
            "system_prompt": "You are a top-level supervisor coordinating AI research teams. Your role is to analyze incoming tasks and intelligently route them to the most appropriate sub-team based on their capabilities and current workload.",
            "user_prompt": "Coordinate the execution of AI research and analysis tasks. Select the most appropriate sub-team for each task based on their specializations.",
            "max_iterations": 10
        },
        "sub_teams": [
            {
                "id": "research_team_001",
                "name": "Research Team",
                "description": "Specialized in information gathering and research",
                "supervisor_config": {
                    "llm_config": {
                        "provider": "openai",
                        "model": "gpt-4o",
                        "temperature": 0.3
                    },
                    "system_prompt": "You are a research team supervisor. Coordinate information gathering and research activities among your team members.",
                    "user_prompt": "Manage research tasks and assign them to the most suitable researcher based on their expertise.",
                    "max_iterations": 8
                },
                "agent_configs": [
                    {
                        "agent_id": "researcher_001",
                        "agent_name": "AI Literature Researcher",
                        "llm_config": {
                            "provider": "openai",
                            "model": "gpt-4o",
                            "temperature": 0.3
                        },
                        "system_prompt": "You are an AI literature researcher specializing in finding and analyzing academic papers and research publications.",
                        "user_prompt": "Search for and analyze the latest AI research papers, focusing on recent developments and breakthrough technologies.",
                        "tools": ["search", "document_analysis"],
                        "max_iterations": 5
                    },
                    {
                        "agent_id": "data_analyst_001",
                        "agent_name": "Data Trend Analyst",
                        "llm_config": {
                            "provider": "openai",
                            "model": "gpt-4o",
                            "temperature": 0.2
                        },
                        "system_prompt": "You are a data analyst specializing in identifying trends and patterns in AI research and industry data.",
                        "user_prompt": "Analyze data trends in AI research, identify emerging patterns, and provide insights on future directions.",
                        "tools": ["data_analysis", "visualization"],
                        "max_iterations": 3
                    }
                ]
            },
            {
                "id": "writing_team_001",
                "name": "Writing Team",
                "description": "Specialized in documentation and report writing",
                "supervisor_config": {
                    "llm_config": {
                        "provider": "openai",
                        "model": "gpt-4o",
                        "temperature": 0.5
                    },
                    "system_prompt": "You are a writing team supervisor. Coordinate documentation and report writing activities.",
                    "user_prompt": "Manage writing tasks and ensure high-quality documentation and reports are produced.",
                    "max_iterations": 6
                },
                "agent_configs": [
                    {
                        "agent_id": "technical_writer_001",
                        "agent_name": "Technical Report Writer",
                        "llm_config": {
                            "provider": "openai",
                            "model": "gpt-4o",
                            "temperature": 0.7
                        },
                        "system_prompt": "You are a technical writer specializing in creating comprehensive research reports and documentation.",
                        "user_prompt": "Create detailed technical reports based on research findings, ensuring clarity and professional presentation.",
                        "tools": ["document_writer", "editor", "formatter"],
                        "max_iterations": 5
                    }
                ]
            }
        ],
        "dependencies": {
            "writing_team_001": ["research_team_001"]
        },
        "global_config": {
            "max_execution_time": 3600,
            "enable_streaming": True,
            "output_format": "detailed"
        }
    }


def demonstrate_basic_usage():
    """Demonstrate basic HierarchicalManager usage."""
    print("=== Hierarchical Manager Basic Usage Demo ===\n")
    
    # Create manager
    print("1. Creating HierarchicalManager...")
    manager = HierarchicalManager()
    print("   ✓ Manager created successfully")
    
    # Create sample configuration
    print("\n2. Creating sample team configuration...")
    config = create_sample_team_config()
    print(f"   ✓ Configuration created for team: {config['team_name']}")
    print(f"   ✓ Sub-teams: {len(config['sub_teams'])}")
    print(f"   ✓ Total agents: {sum(len(team['agent_configs']) for team in config['sub_teams'])}")
    
    # Validate configuration
    print("\n3. Validating team configuration...")
    is_valid, errors = manager.validate_team_config(config)
    if is_valid:
        print("   ✓ Configuration is valid")
    else:
        print(f"   ✗ Configuration errors: {errors}")
        return
    
    # Build hierarchy (this will work with mocked components)
    print("\n4. Building hierarchical team...")
    try:
        # This will fail in a real environment without proper LLM setup
        # but demonstrates the interface
        print("   Note: This would build the actual team with proper LLM configuration")
        print("   ✓ Interface demonstration complete")
    except Exception as e:
        print(f"   Note: Expected in demo environment - {type(e).__name__}")
    
    # Show team statistics
    print("\n5. Team configuration analysis:")
    providers = {}
    models = {}
    
    # Analyze LLM usage
    for team in config['sub_teams']:
        # Count supervisor LLM
        provider = team['supervisor_config']['llm_config']['provider']
        model = team['supervisor_config']['llm_config']['model']
        providers[provider] = providers.get(provider, 0) + 1
        models[model] = models.get(model, 0) + 1
        
        # Count agent LLMs
        for agent in team['agent_configs']:
            provider = agent['llm_config']['provider']
            model = agent['llm_config']['model']
            providers[provider] = providers.get(provider, 0) + 1
            models[model] = models.get(model, 0) + 1
    
    # Add top supervisor
    provider = config['top_supervisor_config']['llm_config']['provider']
    model = config['top_supervisor_config']['llm_config']['model']
    providers[provider] = providers.get(provider, 0) + 1
    models[model] = models.get(model, 0) + 1
    
    print(f"   ✓ LLM Providers: {dict(providers)}")
    print(f"   ✓ Models: {dict(models)}")
    print(f"   ✓ Dependencies: {config['dependencies']}")


async def demonstrate_async_usage():
    """Demonstrate async HierarchicalManager usage."""
    print("\n=== Hierarchical Manager Async Usage Demo ===\n")
    
    # Create and initialize manager
    print("1. Creating and initializing manager...")
    try:
        # This would work with proper dependencies
        print("   Note: Would initialize with StateManager, EventManager, etc.")
        manager = HierarchicalManager()
        print("   ✓ Manager created (initialization skipped in demo)")
    except Exception as e:
        print(f"   Note: Expected in demo environment - {type(e).__name__}")
        return
    
    # Demonstrate utility functions
    print("\n2. Testing utility functions...")
    
    # Test manager stats
    try:
        stats = await manager.get_manager_stats()
        print(f"   ✓ Manager stats retrieved: {len(stats)} fields")
    except Exception as e:
        print(f"   Note: Stats retrieval - {type(e).__name__}")
    
    # Test execution status (would return None for non-existent execution)
    try:
        status = await manager.get_execution_status("test_exec_id")
        print(f"   ✓ Execution status check: {status}")
    except Exception as e:
        print(f"   Note: Status check - {type(e).__name__}")
    
    # Test active executions list
    try:
        executions = await manager.list_active_executions()
        print(f"   ✓ Active executions: {len(executions)}")
    except Exception as e:
        print(f"   Note: Executions list - {type(e).__name__}")


def demonstrate_configuration_examples():
    """Show different configuration examples."""
    print("\n=== Configuration Examples ===\n")
    
    # Simple configuration
    simple_config = {
        "team_name": "simple_team",
        "description": "Simple single-team configuration",
        "top_supervisor_config": {
            "llm_config": {
                "provider": "openai",
                "model": "gpt-4o",
                "temperature": 0.5
            },
            "system_prompt": "Simple supervisor",
            "user_prompt": "Coordinate simple tasks",
            "max_iterations": 5
        },
        "sub_teams": [
            {
                "id": "simple_team_001",
                "name": "Simple Team",
                "description": "A simple team with one agent",
                "supervisor_config": {
                    "llm_config": {
                        "provider": "openai",
                        "model": "gpt-4o",
                        "temperature": 0.3
                    },
                    "system_prompt": "Simple team supervisor",
                    "user_prompt": "Manage simple tasks",
                    "max_iterations": 3
                },
                "agent_configs": [
                    {
                        "agent_id": "simple_agent_001",
                        "agent_name": "Simple Agent",
                        "llm_config": {
                            "provider": "openai",
                            "model": "gpt-4o",
                            "temperature": 0.3
                        },
                        "system_prompt": "Simple agent",
                        "user_prompt": "Perform simple tasks",
                        "tools": [],
                        "max_iterations": 2
                    }
                ]
            }
        ],
        "dependencies": {},
        "global_config": {
            "max_execution_time": 1800,
            "enable_streaming": True,
            "output_format": "summary"
        }
    }
    
    print("1. Simple Configuration:")
    print(f"   ✓ Team: {simple_config['team_name']}")
    print(f"   ✓ Sub-teams: {len(simple_config['sub_teams'])}")
    print(f"   ✓ Agents: {len(simple_config['sub_teams'][0]['agent_configs'])}")
    print(f"   ✓ Dependencies: {len(simple_config['dependencies'])}")
    
    # Complex configuration with multiple providers
    complex_config = create_sample_team_config()
    
    # Modify to show different providers
    complex_config['sub_teams'][0]['supervisor_config']['llm_config']['provider'] = 'openrouter'
    complex_config['sub_teams'][0]['supervisor_config']['llm_config']['base_url'] = 'https://openrouter.ai/api/v1'
    complex_config['sub_teams'][0]['agent_configs'][1]['llm_config']['provider'] = 'aws_bedrock'
    complex_config['sub_teams'][0]['agent_configs'][1]['llm_config']['region'] = 'us-east-1'
    
    print("\n2. Complex Multi-Provider Configuration:")
    print(f"   ✓ Team: {complex_config['team_name']}")
    print(f"   ✓ Sub-teams: {len(complex_config['sub_teams'])}")
    print(f"   ✓ Total agents: {sum(len(team['agent_configs']) for team in complex_config['sub_teams'])}")
    print(f"   ✓ Dependencies: {complex_config['dependencies']}")
    print("   ✓ Providers: OpenAI, OpenRouter, AWS Bedrock")


def main():
    """Main demo function."""
    print("Hierarchical Manager Demonstration")
    print("=" * 50)
    
    # Basic usage demo
    demonstrate_basic_usage()
    
    # Async usage demo
    asyncio.run(demonstrate_async_usage())
    
    # Configuration examples
    demonstrate_configuration_examples()
    
    print("\n" + "=" * 50)
    print("Demo completed successfully!")
    print("\nKey Features Demonstrated:")
    print("✓ HierarchicalManager instantiation")
    print("✓ Team configuration validation")
    print("✓ Component integration")
    print("✓ Async operations support")
    print("✓ Multi-provider LLM configuration")
    print("✓ Dependency management")
    print("✓ Error handling")
    
    print("\nNext Steps:")
    print("- Set up environment variables for LLM providers")
    print("- Initialize manager with proper dependencies")
    print("- Build and execute actual hierarchical teams")
    print("- Implement custom tools and agents")


if __name__ == "__main__":
    main()