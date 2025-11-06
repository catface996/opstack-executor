#!/usr/bin/env python3
"""
Demonstration of SupervisorAgent intelligent routing capabilities.

This script shows how the SupervisorAgent can intelligently route tasks
to appropriate agents using different routing methods.
"""

import os
import sys
from unittest.mock import Mock

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from hierarchical_agents.agents import SupervisorAgent
from hierarchical_agents.data_models import SupervisorConfig, LLMConfig


def create_mock_supervisor():
    """Create a supervisor with mock LLM for demonstration."""
    config = SupervisorConfig(
        llm_config=LLMConfig(
            provider="openai",
            model="gpt-4o",
            temperature=0.3
        ),
        system_prompt="You are an intelligent supervisor that routes tasks to the most appropriate team members based on their capabilities and expertise.",
        user_prompt="Analyze the task requirements and select the best team member to handle it. Consider their skills, tools, and current workload.",
        max_iterations=10
    )
    
    supervisor = SupervisorAgent(config)
    
    # Mock the LLM client for demonstration
    mock_client = Mock()
    supervisor.llm_client = mock_client
    
    return supervisor, mock_client


def demo_basic_routing():
    """Demonstrate basic routing functionality."""
    print("=== Basic Routing Demo ===")
    
    supervisor, mock_client = create_mock_supervisor()
    
    # Mock LLM response
    mock_response = Mock()
    mock_response.content = "Data Analyst"
    mock_client.invoke.return_value = mock_response
    
    task = "Analyze customer purchase patterns and identify trends"
    available_options = ["Data Analyst", "Report Writer", "Quality Checker"]
    
    print(f"Task: {task}")
    print(f"Available options: {available_options}")
    
    selected = supervisor.execute(task, available_options)
    print(f"Selected: {selected}")
    print()


def demo_structured_routing():
    """Demonstrate structured routing with reasoning."""
    print("=== Structured Routing Demo ===")
    
    supervisor, mock_client = create_mock_supervisor()
    
    # Mock structured LLM response
    mock_response = Mock()
    mock_response.content = """SELECTED: Data Analyst
REASONING: The task requires analyzing customer purchase patterns and identifying trends, which directly matches the Data Analyst's expertise in data analysis and pattern recognition."""
    mock_client.invoke.return_value = mock_response
    
    task = "Analyze customer purchase patterns and identify trends"
    available_agents = [
        {
            "name": "Data Analyst",
            "description": "Specializes in data analysis, statistical modeling, and trend identification"
        },
        {
            "name": "Report Writer", 
            "description": "Creates comprehensive reports and documentation"
        },
        {
            "name": "Quality Checker",
            "description": "Reviews and validates work quality and accuracy"
        }
    ]
    
    print(f"Task: {task}")
    print("Available agents:")
    for agent in available_agents:
        print(f"  - {agent['name']}: {agent['description']}")
    
    selected_agent, reasoning = supervisor.route_task_structured(task, available_agents)
    print(f"Selected: {selected_agent}")
    print(f"Reasoning: {reasoning}")
    print()


def demo_intelligent_routing():
    """Demonstrate intelligent routing with capabilities."""
    print("=== Intelligent Routing Demo ===")
    
    supervisor, mock_client = create_mock_supervisor()
    
    # Mock LLM response
    mock_response = Mock()
    mock_response.content = "Data Analyst"
    mock_client.invoke.return_value = mock_response
    
    task = "Analyze customer purchase patterns and create visualizations"
    available_agents = [
        {
            "name": "Data Analyst",
            "description": "Specializes in data analysis and statistical modeling",
            "capabilities": ["data_analysis", "statistical_modeling", "trend_analysis", "visualization"],
            "tools": ["pandas", "numpy", "matplotlib", "seaborn"]
        },
        {
            "name": "Report Writer",
            "description": "Creates comprehensive reports and documentation", 
            "capabilities": ["writing", "documentation", "formatting"],
            "tools": ["word_processor", "template_engine", "markdown"]
        },
        {
            "name": "Quality Checker",
            "description": "Reviews and validates work quality",
            "capabilities": ["quality_assurance", "validation", "testing"],
            "tools": ["testing_framework", "validation_tools"]
        }
    ]
    
    print(f"Task: {task}")
    print("Available agents with capabilities:")
    for agent in available_agents:
        print(f"  - {agent['name']}: {agent['description']}")
        print(f"    Capabilities: {', '.join(agent['capabilities'])}")
        print(f"    Tools: {', '.join(agent['tools'])}")
    
    selected_agent = supervisor.route_task_intelligently(task, available_agents)
    print(f"Selected: {selected_agent}")
    print()


def demo_error_handling():
    """Demonstrate error handling for edge cases."""
    print("=== Error Handling Demo ===")
    
    supervisor, mock_client = create_mock_supervisor()
    
    # Test empty options
    try:
        supervisor.execute("Some task", [])
        print("ERROR: Should have raised exception for empty options")
    except Exception as e:
        print(f"✓ Correctly handled empty options: {e}")
    
    # Test empty task
    try:
        supervisor.execute("", ["Agent A", "Agent B"])
        print("ERROR: Should have raised exception for empty task")
    except Exception as e:
        print(f"✓ Correctly handled empty task: {e}")
    
    # Test malformed structured response
    mock_response = Mock()
    mock_response.content = "This is a malformed response without proper structure"
    mock_client.invoke.return_value = mock_response
    
    available_agents = [
        {"name": "Agent A", "description": "First agent"},
        {"name": "Agent B", "description": "Second agent"}
    ]
    
    try:
        selected_agent, reasoning = supervisor.route_task_structured("Test task", available_agents)
        print(f"✓ Handled malformed response: Selected {selected_agent}, Reasoning: {reasoning}")
    except Exception as e:
        print(f"ERROR: Failed to handle malformed response: {e}")
    
    print()


def main():
    """Run all demonstrations."""
    print("SupervisorAgent Intelligent Routing Demonstration")
    print("=" * 50)
    print()
    
    demo_basic_routing()
    demo_structured_routing()
    demo_intelligent_routing()
    demo_error_handling()
    
    print("All demonstrations completed successfully!")


if __name__ == "__main__":
    main()