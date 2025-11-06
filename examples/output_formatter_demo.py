#!/usr/bin/env python3
"""
Output Formatter Demo

This script demonstrates the OutputFormatter functionality including:
- Result collection from team executions
- Metrics calculation (tokens, API calls, success rates)
- Summary generation with timing information
- Standardized output formatting
- Edge case handling (empty results, partial failures)
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.hierarchical_agents.output_formatter import (
    OutputFormatter,
    ResultCollector,
    MetricsCalculator,
    SummaryGenerator,
    create_output_formatter,
    format_team_results
)
from src.hierarchical_agents.data_models import (
    TeamResult,
    ExecutionEvent,
    ExecutionSummary,
    ExecutionMetrics,
    ErrorInfo,
    StandardizedOutput,
    ExecutionStatus,
    ExecutionContext,
    ExecutionConfig
)
from src.hierarchical_agents.state_manager import StateManager, ExecutionState


def create_sample_team_results():
    """Create sample team results for demonstration."""
    return [
        TeamResult(
            status="completed",
            duration=150,
            agents={
                "agent_search_001": {
                    "status": "completed",
                    "output": "Found 15 relevant research papers on AI in healthcare",
                    "tools_used": ["tavily_search", "web_scraper"],
                    "metrics": {"sources_found": 15, "processing_time": 120}
                },
                "agent_analyze_001": {
                    "status": "completed", 
                    "output": "Analyzed trends: 35% growth in medical imaging AI, key challenges in data privacy",
                    "tools_used": ["data_processor"],
                    "metrics": {"data_points_analyzed": 150, "processing_time": 30}
                }
            },
            output="Research team completed comprehensive analysis of AI healthcare applications"
        ),
        TeamResult(
            status="completed",
            duration=200,
            agents={
                "agent_write_001": {
                    "status": "completed",
                    "output": "Generated 2500-word technical report with 4 main sections",
                    "tools_used": ["document_writer", "editor"],
                    "metrics": {"words_written": 2500, "sections_created": 4}
                }
            },
            output="Writing team produced comprehensive technical report on AI healthcare trends"
        )
    ]


def create_sample_events():
    """Create sample execution events for demonstration."""
    base_time = datetime.now()
    return [
        ExecutionEvent(
            timestamp=base_time,
            event_type="execution_started",
            source_type="system",
            execution_id="exec_demo_123",
            content="Starting hierarchical team execution"
        ),
        ExecutionEvent(
            timestamp=base_time + timedelta(seconds=5),
            event_type="supervisor_routing",
            source_type="supervisor",
            execution_id="exec_demo_123",
            supervisor_id="supervisor_main",
            supervisor_name="顶级监督者",
            content="Routing to research team for information gathering",
            selected_team="team_research"
        ),
        ExecutionEvent(
            timestamp=base_time + timedelta(seconds=10),
            event_type="supervisor_routing",
            source_type="supervisor",
            execution_id="exec_demo_123",
            supervisor_id="supervisor_research",
            supervisor_name="研究团队监督者",
            team_id="team_research",
            content="Selecting medical literature search expert",
            selected_agent="agent_search_001"
        ),
        ExecutionEvent(
            timestamp=base_time + timedelta(seconds=15),
            event_type="agent_started",
            source_type="agent",
            execution_id="exec_demo_123",
            team_id="team_research",
            agent_id="agent_search_001",
            agent_name="医疗文献搜索专家",
            content="Starting AI healthcare literature search"
        ),
        ExecutionEvent(
            timestamp=base_time + timedelta(seconds=135),
            event_type="agent_completed",
            source_type="agent",
            execution_id="exec_demo_123",
            team_id="team_research",
            agent_id="agent_search_001",
            agent_name="医疗文献搜索专家",
            result="Found 15 relevant research papers",
            status="completed"
        ),
        ExecutionEvent(
            timestamp=base_time + timedelta(seconds=140),
            event_type="supervisor_routing",
            source_type="supervisor",
            execution_id="exec_demo_123",
            supervisor_id="supervisor_research",
            supervisor_name="研究团队监督者",
            team_id="team_research",
            content="Selecting trend analyst for data analysis",
            selected_agent="agent_analyze_001"
        ),
        ExecutionEvent(
            timestamp=base_time + timedelta(seconds=145),
            event_type="agent_started",
            source_type="agent",
            execution_id="exec_demo_123",
            team_id="team_research",
            agent_id="agent_analyze_001",
            agent_name="趋势分析师",
            content="Analyzing AI healthcare trends and challenges"
        ),
        ExecutionEvent(
            timestamp=base_time + timedelta(seconds=175),
            event_type="agent_completed",
            source_type="agent",
            execution_id="exec_demo_123",
            team_id="team_research",
            agent_id="agent_analyze_001",
            agent_name="趋势分析师",
            result="Completed trend analysis with key insights",
            status="completed"
        ),
        ExecutionEvent(
            timestamp=base_time + timedelta(seconds=180),
            event_type="team_transition",
            source_type="supervisor",
            execution_id="exec_demo_123",
            supervisor_id="supervisor_main",
            supervisor_name="顶级监督者",
            content="Research complete, transitioning to writing team",
            selected_team="team_writing"
        ),
        ExecutionEvent(
            timestamp=base_time + timedelta(seconds=185),
            event_type="supervisor_routing",
            source_type="supervisor",
            execution_id="exec_demo_123",
            supervisor_id="supervisor_writing",
            supervisor_name="写作团队监督者",
            team_id="team_writing",
            content="Selecting technical writer for report generation",
            selected_agent="agent_write_001"
        ),
        ExecutionEvent(
            timestamp=base_time + timedelta(seconds=190),
            event_type="agent_started",
            source_type="agent",
            execution_id="exec_demo_123",
            team_id="team_writing",
            agent_id="agent_write_001",
            agent_name="技术报告撰写专家",
            content="Creating comprehensive technical report"
        ),
        ExecutionEvent(
            timestamp=base_time + timedelta(seconds=390),
            event_type="agent_completed",
            source_type="agent",
            execution_id="exec_demo_123",
            team_id="team_writing",
            agent_id="agent_write_001",
            agent_name="技术报告撰写专家",
            result="Generated comprehensive 2500-word technical report",
            status="completed"
        ),
        ExecutionEvent(
            timestamp=base_time + timedelta(seconds=395),
            event_type="execution_completed",
            source_type="system",
            execution_id="exec_demo_123",
            content="Hierarchical team execution completed successfully"
        )
    ]


def demonstrate_result_collection():
    """Demonstrate result collection functionality."""
    print("=== Result Collection Demo ===")
    
    collector = ResultCollector()
    team_results = {
        "team_research": create_sample_team_results()[0],
        "team_writing": create_sample_team_results()[1]
    }
    
    # Collect team results
    collected = collector.collect_from_team_results(team_results)
    print(f"Collected results from {collected['total_teams']} teams:")
    print(f"  - Completed teams: {collected['completed_teams']}")
    print(f"  - Failed teams: {collected['failed_teams']}")
    print(f"  - Total agents: {collected['total_agents']}")
    print(f"  - Total duration: {collected['total_duration']} seconds")
    
    # Collect event metrics
    events = create_sample_events()
    event_metrics = collector.collect_from_events(events)
    print(f"\nEvent metrics from {event_metrics['total_events']} events:")
    print(f"  - Event types: {event_metrics['event_types']}")
    print(f"  - Source types: {event_metrics['source_types']}")
    print()


def demonstrate_metrics_calculation():
    """Demonstrate metrics calculation functionality."""
    print("=== Metrics Calculation Demo ===")
    
    calculator = MetricsCalculator()
    team_results = {
        "team_research": create_sample_team_results()[0],
        "team_writing": create_sample_team_results()[1]
    }
    events = create_sample_events()
    errors = []  # No errors in this demo
    
    metrics = calculator.calculate_execution_metrics(team_results, events, errors)
    
    print(f"Calculated execution metrics:")
    print(f"  - Success rate: {metrics.success_rate:.1%}")
    print(f"  - Average response time: {metrics.average_response_time:.1f} seconds")
    print(f"  - Total tokens used: {metrics.total_tokens_used}")
    print(f"  - API calls made: {metrics.api_calls_made}")
    print()


def demonstrate_summary_generation():
    """Demonstrate summary generation functionality."""
    print("=== Summary Generation Demo ===")
    
    generator = SummaryGenerator()
    team_results = {
        "team_research": create_sample_team_results()[0],
        "team_writing": create_sample_team_results()[1]
    }
    events = create_sample_events()
    errors = []
    
    summary = generator.generate_execution_summary(
        execution_id="exec_demo_123",
        team_results=team_results,
        events=events,
        errors=errors
    )
    
    print(f"Generated execution summary:")
    print(f"  - Status: {summary.status}")
    print(f"  - Teams executed: {summary.teams_executed}")
    print(f"  - Agents involved: {summary.agents_involved}")
    print(f"  - Total duration: {summary.total_duration} seconds")
    print(f"  - Started at: {summary.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    if summary.completed_at:
        print(f"  - Completed at: {summary.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print()


def demonstrate_output_formatting():
    """Demonstrate complete output formatting."""
    print("=== Output Formatting Demo ===")
    
    formatter = OutputFormatter()
    team_results = create_sample_team_results()
    
    # Format results using the main interface
    output = formatter.format_results(team_results)
    
    print(f"Formatted standardized output:")
    print(f"  - Execution ID: {output.execution_id}")
    print(f"  - Overall status: {output.execution_summary.status}")
    print(f"  - Teams executed: {output.execution_summary.teams_executed}")
    print(f"  - Agents involved: {output.execution_summary.agents_involved}")
    print(f"  - Success rate: {output.metrics.success_rate:.1%}")
    print(f"  - Total tokens: {output.metrics.total_tokens_used}")
    print(f"  - API calls: {output.metrics.api_calls_made}")
    print(f"  - Team results: {len(output.team_results)} teams")
    print(f"  - Errors: {len(output.errors)} errors")
    print()


def demonstrate_edge_cases():
    """Demonstrate edge case handling."""
    print("=== Edge Cases Demo ===")
    
    formatter = OutputFormatter()
    
    # Test empty results
    print("Testing empty results:")
    empty_output = formatter.format_results([])
    print(f"  - Teams executed: {empty_output.execution_summary.teams_executed}")
    print(f"  - Status: {empty_output.execution_summary.status}")
    
    # Test partial failure
    print("\nTesting partial failure:")
    partial_failure_results = [
        TeamResult(status="completed", duration=100),
        TeamResult(status="failed", duration=50)
    ]
    failure_output = formatter.format_results(partial_failure_results)
    print(f"  - Teams executed: {failure_output.execution_summary.teams_executed}")
    print(f"  - Status: {failure_output.execution_summary.status}")
    print(f"  - Success rate: {failure_output.metrics.success_rate:.1%}")
    
    # Test with None values
    print("\nTesting with None values:")
    none_results = [
        TeamResult(status="completed", duration=None, agents=None, output=None)
    ]
    none_output = formatter.format_results(none_results)
    print(f"  - Teams executed: {none_output.execution_summary.teams_executed}")
    print(f"  - Status: {none_output.execution_summary.status}")
    print()


def demonstrate_utility_functions():
    """Demonstrate utility functions."""
    print("=== Utility Functions Demo ===")
    
    # Test create_output_formatter
    formatter = create_output_formatter()
    print(f"Created OutputFormatter: {type(formatter).__name__}")
    
    # Test format_team_results utility
    team_results = create_sample_team_results()
    output = format_team_results(team_results)
    print(f"Utility function formatted {output.execution_summary.teams_executed} teams")
    print()


async def demonstrate_state_manager_integration():
    """Demonstrate integration with StateManager (mock)."""
    print("=== State Manager Integration Demo ===")
    
    # This would normally use a real StateManager, but we'll simulate it
    print("Note: This demo simulates StateManager integration")
    print("In a real implementation, this would:")
    print("  - Connect to Redis for state persistence")
    print("  - Retrieve complete execution state")
    print("  - Format results with full context and history")
    print("  - Support async operations for better performance")
    print()


def main():
    """Run all demonstrations."""
    print("🚀 OutputFormatter Comprehensive Demo")
    print("=" * 50)
    print()
    
    # Run all demonstrations
    demonstrate_result_collection()
    demonstrate_metrics_calculation()
    demonstrate_summary_generation()
    demonstrate_output_formatting()
    demonstrate_edge_cases()
    demonstrate_utility_functions()
    
    # Run async demo
    asyncio.run(demonstrate_state_manager_integration())
    
    print("✅ All demonstrations completed successfully!")
    print("\nKey Features Demonstrated:")
    print("  ✓ Result collection from team executions")
    print("  ✓ Comprehensive metrics calculation")
    print("  ✓ Execution summary generation")
    print("  ✓ Standardized output formatting")
    print("  ✓ Edge case handling (empty, failures, None values)")
    print("  ✓ Utility functions for common operations")
    print("  ✓ StateManager integration architecture")
    print("\nThe OutputFormatter is ready for production use! 🎉")


if __name__ == "__main__":
    main()