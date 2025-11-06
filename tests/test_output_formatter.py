"""
Tests for output formatter.

This module tests the OutputFormatter class and its components including
result collection, metrics calculation, and standardized output formatting.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

from src.hierarchical_agents.output_formatter import (
    OutputFormatter,
    ResultCollector,
    MetricsCalculator,
    SummaryGenerator,
    TemplateProcessor,
    TemplateProcessingError,
    OutputFormatterError,
    create_output_formatter,
    format_team_results,
    format_with_template
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
    ExecutionConfig,
    OutputTemplate,
    ExtractionRules,
    FormatRequest
)
from src.hierarchical_agents.state_manager import StateManager, ExecutionState


class TestResultCollector:
    """Test the ResultCollector class."""
    
    @pytest.fixture
    def collector(self):
        """Create a ResultCollector instance."""
        return ResultCollector()
    
    @pytest.fixture
    def sample_execution_state(self):
        """Create a sample execution state."""
        context = ExecutionContext(
            execution_id="exec_123",
            team_id="team_456",
            config=ExecutionConfig(),
            started_at=datetime.now()
        )
        
        return ExecutionState(
            execution_id="exec_123",
            team_id="team_456",
            status=ExecutionStatus.COMPLETED,
            context=context,
            events=[
                ExecutionEvent(
                    timestamp=datetime.now(),
                    event_type="execution_started",
                    source_type="system",
                    execution_id="exec_123"
                )
            ],
            team_states={},
            results={
                "team_1": TeamResult(
                    status="completed",
                    duration=100,
                    agents={"agent_1": {"status": "completed"}},
                    output="Test output"
                )
            },
            errors=[],
            metrics=ExecutionMetrics(),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    
    def test_collect_from_execution_state(self, collector, sample_execution_state):
        """Test collecting results from execution state."""
        results = collector.collect_from_execution_state(sample_execution_state)
        
        assert results["execution_id"] == "exec_123"
        assert results["team_id"] == "team_456"
        assert results["status"] == ExecutionStatus.COMPLETED
        assert len(results["events"]) == 1
        assert len(results["team_results"]) == 1
        assert "team_1" in results["team_results"]
    
    def test_collect_from_execution_state_error(self, collector):
        """Test error handling in execution state collection."""
        # Mock the logger to raise an exception during the debug call
        with patch.object(collector.logger, 'debug', side_effect=Exception("Mock error")):
            # Create a valid state that will pass the initial processing but fail on logging
            context = ExecutionContext(
                execution_id="exec_123",
                team_id="team_456",
                config=ExecutionConfig(),
                started_at=datetime.now()
            )
            
            execution_state = ExecutionState(
                execution_id="exec_123",
                team_id="team_456",
                status=ExecutionStatus.COMPLETED,
                context=context,
                events=[],
                team_states={},
                results={},
                errors=[],
                metrics=ExecutionMetrics(),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            with pytest.raises(OutputFormatterError, match="Result collection failed"):
                collector.collect_from_execution_state(execution_state)
    
    def test_collect_from_team_results(self, collector):
        """Test collecting results from team results dictionary."""
        team_results = {
            "team_1": TeamResult(
                status="completed",
                duration=100,
                agents={"agent_1": {"status": "completed"}, "agent_2": {"status": "completed"}},
                output="Output 1"
            ),
            "team_2": TeamResult(
                status="failed",
                duration=50,
                agents={"agent_3": {"status": "failed"}},
                output="Output 2"
            )
        }
        
        collected = collector.collect_from_team_results(team_results)
        
        assert collected["total_teams"] == 2
        assert collected["completed_teams"] == 1
        assert collected["failed_teams"] == 1
        assert collected["total_agents"] == 3
        assert collected["total_duration"] == 150
    
    def test_collect_from_team_results_empty(self, collector):
        """Test collecting from empty team results."""
        collected = collector.collect_from_team_results({})
        
        assert collected["total_teams"] == 0
        assert collected["completed_teams"] == 0
        assert collected["failed_teams"] == 0
        assert collected["total_agents"] == 0
        assert collected["total_duration"] == 0
    
    def test_collect_from_events(self, collector):
        """Test collecting metrics from execution events."""
        events = [
            ExecutionEvent(
                timestamp=datetime.now(),
                event_type="execution_started",
                source_type="system",
                execution_id="exec_123"
            ),
            ExecutionEvent(
                timestamp=datetime.now(),
                event_type="agent_started",
                source_type="agent",
                execution_id="exec_123",
                agent_id="agent_1"
            ),
            ExecutionEvent(
                timestamp=datetime.now(),
                event_type="agent_completed",
                source_type="agent",
                execution_id="exec_123",
                agent_id="agent_1"
            )
        ]
        
        collected = collector.collect_from_events(events)
        
        assert collected["total_events"] == 3
        assert collected["event_types"]["execution_started"] == 1
        assert collected["event_types"]["agent_started"] == 1
        assert collected["event_types"]["agent_completed"] == 1
        assert collected["source_types"]["system"] == 1
        assert collected["source_types"]["agent"] == 2
        assert len(collected["timeline"]) == 3
    
    def test_collect_from_events_empty(self, collector):
        """Test collecting from empty events list."""
        collected = collector.collect_from_events([])
        
        assert collected["total_events"] == 0
        assert collected["event_types"] == {}
        assert collected["source_types"] == {}
        assert collected["timeline"] == []


class TestMetricsCalculator:
    """Test the MetricsCalculator class."""
    
    @pytest.fixture
    def calculator(self):
        """Create a MetricsCalculator instance."""
        return MetricsCalculator()
    
    @pytest.fixture
    def sample_team_results(self):
        """Create sample team results."""
        return {
            "team_1": TeamResult(
                status="completed",
                duration=100,
                agents={"agent_1": {"status": "completed"}, "agent_2": {"status": "completed"}},
                output="This is a test output with some content"
            ),
            "team_2": TeamResult(
                status="completed",
                duration=200,
                agents={"agent_3": {"status": "completed"}},
                output="Another output"
            )
        }
    
    @pytest.fixture
    def sample_events(self):
        """Create sample execution events."""
        base_time = datetime.now()
        return [
            ExecutionEvent(
                timestamp=base_time,
                event_type="execution_started",
                source_type="system",
                execution_id="exec_123"
            ),
            ExecutionEvent(
                timestamp=base_time + timedelta(seconds=1),
                event_type="supervisor_routing",
                source_type="supervisor",
                execution_id="exec_123"
            ),
            ExecutionEvent(
                timestamp=base_time + timedelta(seconds=2),
                event_type="agent_started",
                source_type="agent",
                execution_id="exec_123",
                agent_id="agent_1"
            ),
            ExecutionEvent(
                timestamp=base_time + timedelta(seconds=10),
                event_type="agent_completed",
                source_type="agent",
                execution_id="exec_123",
                agent_id="agent_1"
            )
        ]
    
    def test_calculate_execution_metrics(self, calculator, sample_team_results, sample_events):
        """Test calculating comprehensive execution metrics."""
        errors = [
            ErrorInfo(
                error_code="TEST_ERROR",
                message="Test error message",
                timestamp=datetime.now()
            )
        ]
        
        metrics = calculator.calculate_execution_metrics(
            team_results=sample_team_results,
            events=sample_events,
            errors=errors
        )
        
        assert isinstance(metrics, ExecutionMetrics)
        assert metrics.success_rate == 1.0  # All teams completed
        assert metrics.average_response_time == 8.0  # 10-2 = 8 seconds
        assert metrics.total_tokens_used > 0
        assert metrics.api_calls_made > 0
    
    def test_calculate_execution_metrics_partial_failure(self, calculator):
        """Test metrics calculation with partial failures."""
        team_results = {
            "team_1": TeamResult(status="completed", duration=100),
            "team_2": TeamResult(status="failed", duration=50)
        }
        
        metrics = calculator.calculate_execution_metrics(
            team_results=team_results,
            events=[],
            errors=[]
        )
        
        assert metrics.success_rate == 0.5  # 1 out of 2 teams succeeded
    
    def test_calculate_execution_metrics_empty(self, calculator):
        """Test metrics calculation with empty inputs."""
        metrics = calculator.calculate_execution_metrics(
            team_results={},
            events=[],
            errors=[]
        )
        
        assert metrics.success_rate == 0.0
        assert metrics.average_response_time == 0.0
        assert metrics.total_tokens_used == 0
        assert metrics.api_calls_made == 0
    
    def test_estimate_token_usage(self, calculator, sample_team_results, sample_events):
        """Test token usage estimation."""
        tokens = calculator._estimate_token_usage(sample_team_results, sample_events)
        
        # Should have base tokens (3 agents * 100) + supervisor tokens + output tokens
        assert tokens > 300  # At least base tokens
    
    def test_estimate_api_calls(self, calculator, sample_events):
        """Test API calls estimation."""
        api_calls = calculator._estimate_api_calls(sample_events)
        
        # Should count agent_completed and supervisor_routing events
        assert api_calls == 2


class TestSummaryGenerator:
    """Test the SummaryGenerator class."""
    
    @pytest.fixture
    def generator(self):
        """Create a SummaryGenerator instance."""
        return SummaryGenerator()
    
    @pytest.fixture
    def sample_team_results(self):
        """Create sample team results."""
        return {
            "team_1": TeamResult(
                status="completed",
                duration=100,
                agents={"agent_1": {"status": "completed"}}
            ),
            "team_2": TeamResult(
                status="completed",
                duration=200,
                agents={"agent_2": {"status": "completed"}, "agent_3": {"status": "completed"}}
            )
        }
    
    @pytest.fixture
    def sample_events(self):
        """Create sample execution events."""
        base_time = datetime.now()
        return [
            ExecutionEvent(
                timestamp=base_time,
                event_type="execution_started",
                source_type="system",
                execution_id="exec_123"
            ),
            ExecutionEvent(
                timestamp=base_time + timedelta(seconds=300),
                event_type="execution_completed",
                source_type="system",
                execution_id="exec_123"
            )
        ]
    
    def test_generate_execution_summary(self, generator, sample_team_results, sample_events):
        """Test generating execution summary."""
        summary = generator.generate_execution_summary(
            execution_id="exec_123",
            team_results=sample_team_results,
            events=sample_events,
            errors=[]
        )
        
        assert isinstance(summary, ExecutionSummary)
        assert summary.status == "completed"
        assert summary.teams_executed == 2
        assert summary.agents_involved == 3
        assert summary.total_duration == 300
        assert summary.started_at is not None
        assert summary.completed_at is not None
    
    def test_generate_execution_summary_with_failures(self, generator):
        """Test generating summary with failed teams."""
        team_results = {
            "team_1": TeamResult(status="completed", duration=100),
            "team_2": TeamResult(status="failed", duration=50)
        }
        
        summary = generator.generate_execution_summary(
            execution_id="exec_123",
            team_results=team_results,
            events=[],
            errors=[]
        )
        
        assert summary.status == "failed"
        assert summary.teams_executed == 2
    
    def test_generate_execution_summary_empty(self, generator):
        """Test generating summary with empty inputs."""
        summary = generator.generate_execution_summary(
            execution_id="exec_123",
            team_results={},
            events=[],
            errors=[]
        )
        
        assert summary.status == "pending"
        assert summary.teams_executed == 0
        assert summary.agents_involved == 0
    
    def test_determine_overall_status(self, generator):
        """Test overall status determination."""
        # All completed
        team_results = {
            "team_1": TeamResult(status="completed"),
            "team_2": TeamResult(status="completed")
        }
        status = generator._determine_overall_status(team_results, [])
        assert status == "completed"
        
        # Some failed
        team_results["team_2"].status = "failed"
        status = generator._determine_overall_status(team_results, [])
        assert status == "failed"
        
        # Some running
        team_results["team_2"].status = "running"
        status = generator._determine_overall_status(team_results, [])
        assert status == "running"
        
        # Empty
        status = generator._determine_overall_status({}, [])
        assert status == "pending"
    
    def test_extract_timing_info(self, generator, sample_events):
        """Test timing information extraction."""
        started_at, completed_at, duration = generator._extract_timing_info(sample_events, None)
        
        assert started_at is not None
        assert completed_at is not None
        assert duration == 300


class TestOutputFormatter:
    """Test the main OutputFormatter class."""
    
    @pytest.fixture
    def formatter(self):
        """Create an OutputFormatter instance."""
        return OutputFormatter()
    
    @pytest.fixture
    def formatter_with_state_manager(self):
        """Create an OutputFormatter with mock StateManager."""
        mock_state_manager = Mock(spec=StateManager)
        return OutputFormatter(state_manager=mock_state_manager)
    
    @pytest.fixture
    def sample_team_results(self):
        """Create sample team results list."""
        return [
            TeamResult(
                status="completed",
                duration=100,
                agents={"agent_1": {"status": "completed"}},
                output="Test output 1"
            ),
            TeamResult(
                status="completed",
                duration=200,
                agents={"agent_2": {"status": "completed"}},
                output="Test output 2"
            )
        ]
    
    def test_format_results_basic(self, formatter, sample_team_results):
        """Test basic result formatting."""
        output = formatter.format_results(sample_team_results)
        
        assert isinstance(output, StandardizedOutput)
        assert output.execution_id.startswith("exec_")
        assert output.execution_summary.teams_executed == 2
        assert len(output.team_results) == 2
        assert output.errors == []
        assert isinstance(output.metrics, ExecutionMetrics)
    
    def test_format_results_empty(self, formatter):
        """Test formatting empty results."""
        output = formatter.format_results([])
        
        assert isinstance(output, StandardizedOutput)
        assert output.execution_summary.teams_executed == 0
        assert len(output.team_results) == 0
    
    def test_format_results_error_handling(self, formatter):
        """Test error handling in format_results."""
        # Mock the summary generator to raise an exception
        formatter.summary_generator.generate_execution_summary = Mock(
            side_effect=Exception("Test error")
        )
        
        with pytest.raises(OutputFormatterError, match="Result formatting failed"):
            formatter.format_results([])
    
    @pytest.mark.asyncio
    async def test_format_execution_results_success(self, formatter_with_state_manager):
        """Test formatting execution results from StateManager."""
        # Setup mock execution state
        context = ExecutionContext(
            execution_id="exec_123",
            team_id="team_456",
            config=ExecutionConfig(),
            started_at=datetime.now()
        )
        
        execution_state = ExecutionState(
            execution_id="exec_123",
            team_id="team_456",
            status=ExecutionStatus.COMPLETED,
            context=context,
            events=[],
            team_states={},
            results={
                "team_1": TeamResult(status="completed", duration=100)
            },
            errors=[],
            metrics=ExecutionMetrics(),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        formatter_with_state_manager.state_manager.get_execution_state = AsyncMock(
            return_value=execution_state
        )
        
        output = await formatter_with_state_manager.format_execution_results("exec_123")
        
        assert isinstance(output, StandardizedOutput)
        assert output.execution_id == "exec_123"
        assert len(output.team_results) == 1
    
    @pytest.mark.asyncio
    async def test_format_execution_results_no_state_manager(self, formatter):
        """Test formatting execution results without StateManager."""
        with pytest.raises(OutputFormatterError, match="StateManager required"):
            await formatter.format_execution_results("exec_123")
    
    @pytest.mark.asyncio
    async def test_format_execution_results_not_found(self, formatter_with_state_manager):
        """Test formatting execution results when execution not found."""
        formatter_with_state_manager.state_manager.get_execution_state = AsyncMock(
            return_value=None
        )
        
        with pytest.raises(OutputFormatterError, match="Execution exec_123 not found"):
            await formatter_with_state_manager.format_execution_results("exec_123")
    
    def test_collect_team_results(self, formatter):
        """Test collecting team results."""
        team_results = {
            "team_1": TeamResult(status="completed", duration=100),
            "team_2": TeamResult(status="failed", duration=50)
        }
        
        collected = formatter.collect_team_results(team_results)
        
        assert collected["total_teams"] == 2
        assert collected["completed_teams"] == 1
        assert collected["failed_teams"] == 1
    
    def test_collect_event_metrics(self, formatter):
        """Test collecting event metrics."""
        events = [
            ExecutionEvent(
                timestamp=datetime.now(),
                event_type="test_event",
                source_type="system",
                execution_id="exec_123"
            )
        ]
        
        metrics = formatter.collect_event_metrics(events)
        
        assert metrics["total_events"] == 1
        assert "test_event" in metrics["event_types"]
    
    def test_calculate_metrics(self, formatter):
        """Test calculating metrics."""
        team_results = {
            "team_1": TeamResult(status="completed", duration=100)
        }
        
        metrics = formatter.calculate_metrics(team_results)
        
        assert isinstance(metrics, ExecutionMetrics)
        assert metrics.success_rate == 1.0
    
    def test_generate_summary(self, formatter):
        """Test generating summary."""
        team_results = {
            "team_1": TeamResult(status="completed", duration=100)
        }
        
        summary = formatter.generate_summary("exec_123", team_results)
        
        assert isinstance(summary, ExecutionSummary)
        assert summary.teams_executed == 1


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_create_output_formatter(self):
        """Test creating output formatter."""
        formatter = create_output_formatter()
        
        assert isinstance(formatter, OutputFormatter)
        assert formatter.state_manager is None
    
    def test_create_output_formatter_with_state_manager(self):
        """Test creating output formatter with state manager."""
        mock_state_manager = Mock(spec=StateManager)
        formatter = create_output_formatter(state_manager=mock_state_manager)
        
        assert isinstance(formatter, OutputFormatter)
        assert formatter.state_manager == mock_state_manager
    
    def test_format_team_results_utility(self):
        """Test format team results utility function."""
        team_results = [
            TeamResult(status="completed", duration=100)
        ]
        
        output = format_team_results(team_results)
        
        assert isinstance(output, StandardizedOutput)
        assert output.execution_summary.teams_executed == 1


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.fixture
    def formatter(self):
        """Create an OutputFormatter instance."""
        return OutputFormatter()
    
    def test_format_results_with_none_values(self, formatter):
        """Test formatting results with None values in team results."""
        team_results = [
            TeamResult(
                status="completed",
                duration=None,  # None duration
                agents=None,    # None agents
                output=None     # None output
            )
        ]
        
        output = formatter.format_results(team_results)
        
        assert isinstance(output, StandardizedOutput)
        assert output.execution_summary.teams_executed == 1
    
    def test_format_results_with_invalid_team_result(self, formatter):
        """Test formatting with invalid team result that causes errors."""
        # Create a mock that will cause errors during processing
        invalid_result = Mock(spec=TeamResult)
        invalid_result.status = "completed"
        invalid_result.duration = "invalid"  # Invalid type
        invalid_result.agents = {"agent": "invalid"}
        invalid_result.output = None
        
        # This should still work due to error handling
        output = formatter.format_results([invalid_result])
        assert isinstance(output, StandardizedOutput)
    
    def test_metrics_calculation_with_malformed_events(self):
        """Test metrics calculation with malformed events."""
        calculator = MetricsCalculator()
        
        # Create events with missing required fields
        malformed_events = [
            ExecutionEvent(
                timestamp=datetime.now(),
                event_type="agent_started",
                source_type="agent",
                execution_id="exec_123",
                agent_id=None  # Missing agent_id
            ),
            ExecutionEvent(
                timestamp=datetime.now(),
                event_type="agent_completed",
                source_type="agent",
                execution_id="exec_123",
                agent_id="agent_1"
            )
        ]
        
        # Should handle malformed events gracefully
        metrics = calculator.calculate_execution_metrics(
            team_results={},
            events=malformed_events,
            errors=[]
        )
        
        assert isinstance(metrics, ExecutionMetrics)
    
    def test_summary_generation_with_inconsistent_data(self):
        """Test summary generation with inconsistent data."""
        generator = SummaryGenerator()
        
        # Create inconsistent data
        team_results = {
            "team_1": TeamResult(status="completed", duration=100)
        }
        
        # Events that don't match the team results
        events = [
            ExecutionEvent(
                timestamp=datetime.now(),
                event_type="execution_started",
                source_type="system",
                execution_id="different_exec_id"  # Different execution ID
            )
        ]
        
        # Should still generate a valid summary
        summary = generator.generate_execution_summary(
            execution_id="exec_123",
            team_results=team_results,
            events=events,
            errors=[]
        )
        
        assert isinstance(summary, ExecutionSummary)
        assert summary.teams_executed == 1


class TestIntegration:
    """Integration tests for OutputFormatter components."""
    
    def test_full_formatting_pipeline(self):
        """Test the complete formatting pipeline."""
        formatter = OutputFormatter()
        
        # Create comprehensive test data
        team_results = [
            TeamResult(
                status="completed",
                duration=150,
                agents={
                    "agent_1": {"status": "completed", "output": "Agent 1 result"},
                    "agent_2": {"status": "completed", "output": "Agent 2 result"}
                },
                output="Team 1 completed successfully"
            ),
            TeamResult(
                status="failed",
                duration=75,
                agents={
                    "agent_3": {"status": "failed", "error": "Agent 3 failed"}
                },
                output="Team 2 failed"
            )
        ]
        
        # Format results
        output = formatter.format_results(team_results)
        
        # Verify comprehensive output
        assert isinstance(output, StandardizedOutput)
        assert output.execution_id.startswith("exec_")
        
        # Check summary
        summary = output.execution_summary
        assert summary.teams_executed == 2
        assert summary.agents_involved == 3
        assert summary.status == "failed"  # Overall status should be failed
        
        # Check team results
        assert len(output.team_results) == 2
        assert "team_0" in output.team_results
        assert "team_1" in output.team_results
        
        # Check metrics
        metrics = output.metrics
        assert metrics.success_rate == 0.5  # 1 out of 2 teams succeeded
        assert metrics.total_tokens_used > 0
        assert metrics.api_calls_made >= 0
    
    def test_component_interaction(self):
        """Test interaction between formatter components."""
        formatter = OutputFormatter()
        
        # Test that all components are properly initialized
        assert isinstance(formatter.result_collector, ResultCollector)
        assert isinstance(formatter.metrics_calculator, MetricsCalculator)
        assert isinstance(formatter.summary_generator, SummaryGenerator)
        
        # Test that components can work together
        team_results = {"team_1": TeamResult(status="completed", duration=100)}
        events = [
            ExecutionEvent(
                timestamp=datetime.now(),
                event_type="execution_started",
                source_type="system",
                execution_id="exec_123"
            )
        ]
        
        # Use individual components
        collected = formatter.collect_team_results(team_results)
        metrics = formatter.calculate_metrics(team_results, events)
        summary = formatter.generate_summary("exec_123", team_results, events)
        
        # Verify results
        assert collected["total_teams"] == 1
        assert isinstance(metrics, ExecutionMetrics)
        assert isinstance(summary, ExecutionSummary)


class TestTemplateProcessor:
    """Test the TemplateProcessor class for template-based output formatting."""
    
    @pytest.fixture
    def processor(self):
        """Create a TemplateProcessor instance."""
        return TemplateProcessor()
    
    @pytest.fixture
    def sample_template(self):
        """Create a sample output template."""
        return {
            "report_title": "AI医疗应用分析报告",
            "executive_summary": "{executive_summary}",
            "research_findings": {
                "key_technologies": "{key_technologies}",
                "market_trends": "{market_trends}",
                "challenges": "{challenges}"
            },
            "recommendations": "{recommendations}",
            "appendix": {
                "data_sources": "{data_sources}",
                "methodology": "{methodology}"
            }
        }
    
    @pytest.fixture
    def sample_extraction_rules(self):
        """Create sample extraction rules."""
        return {
            "executive_summary": "总结所有团队的核心发现，不超过200字",
            "key_technologies": "从搜索结果中提取3-5个关键技术",
            "market_trends": "从分析结果中提取市场趋势，以列表形式呈现",
            "challenges": "识别并列出主要技术和商业挑战",
            "recommendations": "基于分析结果提供3-5条具体建议",
            "data_sources": "列出所有数据来源",
            "methodology": "描述研究方法"
        }
    
    @pytest.fixture
    def sample_execution_results(self):
        """Create sample execution results for template processing."""
        return StandardizedOutput(
            execution_id="exec_123",
            execution_summary=ExecutionSummary(
                status="completed",
                started_at=datetime.now(),
                completed_at=datetime.now(),
                total_duration=1800,
                teams_executed=2,
                agents_involved=3
            ),
            team_results={
                "research_team": TeamResult(
                    status="completed",
                    duration=900,
                    agents={
                        "search_agent": {
                            "agent_name": "医疗文献搜索专家",
                            "status": "completed",
                            "output": "收集了15篇AI医疗应用研究论文，包括深度学习在医学影像、自然语言处理在病历分析等领域的最新进展。发现机器学习在药物发现、计算机视觉在手术辅助等技术正在快速发展。",
                            "tools_used": ["tavily_search", "web_scraper"]
                        },
                        "analysis_agent": {
                            "agent_name": "趋势分析师",
                            "status": "completed",
                            "output": "分析了技术趋势、挑战和机遇。AI医疗市场预计2030年达到1000亿美元，医学影像AI应用增长率达35%。主要挑战包括数据隐私保护、算法可解释性、监管合规等问题。建议建立统一的医疗AI数据标准。",
                            "tools_used": ["data_processor"]
                        }
                    },
                    output="研究团队完成了AI医疗应用的全面调研和分析"
                ),
                "writing_team": TeamResult(
                    status="completed",
                    duration=900,
                    agents={
                        "writer_agent": {
                            "agent_name": "技术报告撰写专家",
                            "status": "completed",
                            "output": "基于研究团队提供的材料，撰写了详细的AI医疗应用分析报告。报告包含技术背景、应用案例、挑战分析和未来展望。推荐加强跨学科人才培养、完善AI医疗监管框架、推进产学研合作创新。",
                            "tools_used": ["document_writer", "editor"]
                        }
                    },
                    output="写作团队完成了综合分析报告的撰写"
                )
            },
            errors=[],
            metrics=ExecutionMetrics(
                total_tokens_used=5000,
                api_calls_made=10,
                success_rate=1.0,
                average_response_time=300.0
            )
        )
    
    def test_parse_template_success(self, processor, sample_template):
        """Test successful template parsing."""
        parsed = processor.parse_template(sample_template)
        
        assert isinstance(parsed, dict)
        assert parsed["report_title"] == "AI医疗应用分析报告"
        assert "{executive_summary}" in parsed["executive_summary"]
        assert isinstance(parsed["research_findings"], dict)
        assert "{key_technologies}" in parsed["research_findings"]["key_technologies"]
    
    def test_parse_template_invalid_input(self, processor):
        """Test template parsing with invalid input."""
        # Test non-dict input
        with pytest.raises(TemplateProcessingError, match="Template must be a dictionary"):
            processor.parse_template("invalid")
        
        # Test empty template
        with pytest.raises(TemplateProcessingError, match="Template cannot be empty"):
            processor.parse_template({})
    
    def test_parse_template_nested_structure(self, processor):
        """Test parsing template with nested structures."""
        nested_template = {
            "level1": {
                "level2": {
                    "level3": "{nested_field}",
                    "list_field": [
                        {"item1": "{list_item}"},
                        "static_item"
                    ]
                }
            }
        }
        
        parsed = processor.parse_template(nested_template)
        
        assert parsed["level1"]["level2"]["level3"] == "{nested_field}"
        assert parsed["level1"]["level2"]["list_field"][0]["item1"] == "{list_item}"
        assert parsed["level1"]["level2"]["list_field"][1] == "static_item"
    
    def test_extract_information_success(self, processor, sample_extraction_rules, sample_execution_results):
        """Test successful information extraction."""
        extracted = processor.extract_information(sample_extraction_rules, sample_execution_results)
        
        assert isinstance(extracted, dict)
        assert "executive_summary" in extracted
        assert "key_technologies" in extracted
        assert "market_trends" in extracted
        assert "challenges" in extracted
        assert "recommendations" in extracted
        
        # Verify extracted content types
        assert isinstance(extracted["key_technologies"], list)
        assert isinstance(extracted["market_trends"], list)
        assert isinstance(extracted["challenges"], list)
        assert isinstance(extracted["recommendations"], list)
        assert isinstance(extracted["executive_summary"], str)
    
    def test_extract_information_with_specific_rules(self, processor, sample_execution_results):
        """Test information extraction with specific rule patterns."""
        rules = {
            "summary_field": "总结所有团队的核心发现，不超过100字",
            "tech_field": "从搜索结果中提取3个关键技术",
            "trend_field": "从分析结果中提取市场趋势",
            "challenge_field": "识别主要挑战",
            "recommendation_field": "提供3条建议",
            "source_field": "列出数据来源",
            "method_field": "描述方法"
        }
        
        extracted = processor.extract_information(rules, sample_execution_results)
        
        # Verify all fields are extracted
        for field_name in rules.keys():
            assert field_name in extracted
            assert extracted[field_name] is not None
    
    def test_extract_information_error_handling(self, processor, sample_execution_results):
        """Test error handling in information extraction."""
        # Rules that might cause extraction issues
        problematic_rules = {
            "valid_field": "正常的提取规则",
            "problematic_field": ""  # Empty rule
        }
        
        extracted = processor.extract_information(problematic_rules, sample_execution_results)
        
        # Should handle errors gracefully
        assert "valid_field" in extracted
        assert "problematic_field" in extracted
        # Problematic field should have error message or fallback value
        assert isinstance(extracted["problematic_field"], str)
    
    def test_format_output_success(self, processor, sample_template):
        """Test successful output formatting."""
        extracted_info = {
            "executive_summary": "这是一个执行摘要",
            "key_technologies": ["深度学习", "自然语言处理", "机器学习"],
            "market_trends": ["市场增长", "技术进步"],
            "challenges": ["数据隐私", "算法可解释性"],
            "recommendations": ["建议1", "建议2", "建议3"],
            "data_sources": ["来源1", "来源2"],
            "methodology": "研究方法描述"
        }
        
        formatted = processor.format_output(sample_template, extracted_info)
        
        assert isinstance(formatted, dict)
        assert formatted["report_title"] == "AI医疗应用分析报告"
        assert formatted["executive_summary"] == "这是一个执行摘要"
        assert formatted["research_findings"]["key_technologies"] == "深度学习, 自然语言处理, 机器学习"
        assert formatted["research_findings"]["market_trends"] == "市场增长, 技术进步"
    
    def test_format_output_missing_placeholders(self, processor):
        """Test output formatting with missing placeholders."""
        template = {
            "field1": "{existing_field}",
            "field2": "{missing_field}",
            "field3": "static_value"
        }
        
        extracted_info = {
            "existing_field": "existing_value"
        }
        
        formatted = processor.format_output(template, extracted_info)
        
        assert formatted["field1"] == "existing_value"
        assert "[Missing: missing_field]" in formatted["field2"]
        assert formatted["field3"] == "static_value"
    
    def test_format_output_nested_placeholders(self, processor):
        """Test output formatting with nested field access."""
        template = {
            "simple": "{simple_field}",
            "nested": "{nested.field}",
            "invalid_nested": "{invalid.path}"
        }
        
        extracted_info = {
            "simple_field": "simple_value",
            "nested": {
                "field": "nested_value"
            }
        }
        
        formatted = processor.format_output(template, extracted_info)
        
        assert formatted["simple"] == "simple_value"
        assert formatted["nested"] == "nested_value"
        assert "[Invalid path: invalid.path]" in formatted["invalid_nested"]
    
    def test_validate_extraction_rules_success(self, processor, sample_extraction_rules):
        """Test successful extraction rules validation."""
        validated = processor.validate_extraction_rules(sample_extraction_rules)
        
        assert isinstance(validated, dict)
        assert len(validated) == len(sample_extraction_rules)
        for key, value in sample_extraction_rules.items():
            assert key in validated
            assert validated[key] == value.strip()
    
    def test_validate_extraction_rules_invalid_input(self, processor):
        """Test extraction rules validation with invalid input."""
        # Test non-dict input
        with pytest.raises(TemplateProcessingError, match="Extraction rules must be a dictionary"):
            processor.validate_extraction_rules("invalid")
        
        # Test empty rules
        with pytest.raises(TemplateProcessingError, match="Extraction rules cannot be empty"):
            processor.validate_extraction_rules({})
        
        # Test invalid field name
        with pytest.raises(TemplateProcessingError, match="Invalid field name"):
            processor.validate_extraction_rules({"": "valid rule"})
        
        # Test invalid rule
        with pytest.raises(TemplateProcessingError, match="Invalid rule for field"):
            processor.validate_extraction_rules({"valid_field": ""})
    
    def test_process_template_request_success(self, processor, sample_template, sample_extraction_rules, sample_execution_results):
        """Test complete template request processing."""
        format_request = FormatRequest(
            output_template=OutputTemplate(**sample_template),
            extraction_rules=ExtractionRules(**sample_extraction_rules)
        )
        
        result = processor.process_template_request(format_request, sample_execution_results)
        
        assert isinstance(result, dict)
        assert result["report_title"] == "AI医疗应用分析报告"
        assert "executive_summary" in result
        assert "research_findings" in result
        assert "recommendations" in result
        assert "appendix" in result
        
        # Verify nested structure
        assert "key_technologies" in result["research_findings"]
        assert "market_trends" in result["research_findings"]
        assert "challenges" in result["research_findings"]
        assert "data_sources" in result["appendix"]
        assert "methodology" in result["appendix"]
    
    def test_process_template_request_error_handling(self, processor, sample_execution_results):
        """Test error handling in template request processing."""
        # Invalid template
        invalid_request = FormatRequest(
            output_template=OutputTemplate(),  # Empty template
            extraction_rules=ExtractionRules(valid_rule="valid rule")
        )
        
        with pytest.raises(TemplateProcessingError):
            processor.process_template_request(invalid_request, sample_execution_results)


class TestOutputFormatterTemplateIntegration:
    """Test template processing integration with OutputFormatter."""
    
    @pytest.fixture
    def formatter(self):
        """Create an OutputFormatter instance."""
        return OutputFormatter()
    
    @pytest.fixture
    def sample_template(self):
        """Create a sample output template."""
        return {
            "title": "Test Report",
            "summary": "{summary}",
            "details": {
                "findings": "{findings}",
                "metrics": "{metrics}"
            }
        }
    
    @pytest.fixture
    def sample_rules(self):
        """Create sample extraction rules."""
        return {
            "summary": "Summarize the execution results",
            "findings": "Extract key findings from team outputs",
            "metrics": "Extract performance metrics"
        }
    
    @pytest.fixture
    def sample_results(self):
        """Create sample standardized results."""
        return StandardizedOutput(
            execution_id="exec_test",
            execution_summary=ExecutionSummary(
                status="completed",
                started_at=datetime.now(),
                completed_at=datetime.now(),
                total_duration=300,
                teams_executed=1,
                agents_involved=2
            ),
            team_results={
                "team_1": TeamResult(
                    status="completed",
                    duration=300,
                    agents={
                        "agent_1": {
                            "status": "completed",
                            "output": "Agent 1 completed successfully with key findings about AI applications."
                        }
                    },
                    output="Team completed the analysis task successfully."
                )
            },
            errors=[],
            metrics=ExecutionMetrics(
                total_tokens_used=1000,
                api_calls_made=5,
                success_rate=1.0,
                average_response_time=60.0
            )
        )
    
    def test_format_with_template_success(self, formatter, sample_results, sample_template, sample_rules):
        """Test successful template formatting through OutputFormatter."""
        result = formatter.format_with_template(sample_results, sample_template, sample_rules)
        
        assert isinstance(result, dict)
        assert result["title"] == "Test Report"
        assert "summary" in result
        assert "details" in result
        assert "findings" in result["details"]
        assert "metrics" in result["details"]
    
    def test_format_with_template_error_handling(self, formatter, sample_results):
        """Test error handling in template formatting."""
        invalid_template = {}  # Empty template
        valid_rules = {"field": "rule"}
        
        with pytest.raises(OutputFormatterError, match="Template formatting failed"):
            formatter.format_with_template(sample_results, invalid_template, valid_rules)
    
    @pytest.mark.asyncio
    async def test_format_execution_with_template_success(self):
        """Test formatting execution with template using StateManager."""
        # Create formatter with mock state manager
        mock_state_manager = Mock(spec=StateManager)
        formatter = OutputFormatter(state_manager=mock_state_manager)
        
        # Setup mock execution state
        context = ExecutionContext(
            execution_id="exec_123",
            team_id="team_456",
            config=ExecutionConfig(),
            started_at=datetime.now()
        )
        
        execution_state = ExecutionState(
            execution_id="exec_123",
            team_id="team_456",
            status=ExecutionStatus.COMPLETED,
            context=context,
            events=[],
            team_states={},
            results={
                "team_1": TeamResult(
                    status="completed",
                    duration=100,
                    output="Test output"
                )
            },
            errors=[],
            metrics=ExecutionMetrics(),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        mock_state_manager.get_execution_state = AsyncMock(return_value=execution_state)
        
        template = {"title": "Test", "content": "{content}"}
        rules = {"content": "Extract content from results"}
        
        result = await formatter.format_execution_with_template("exec_123", template, rules)
        
        assert isinstance(result, dict)
        assert result["title"] == "Test"
        assert "content" in result
    
    def test_parse_template_integration(self, formatter):
        """Test template parsing through OutputFormatter."""
        template = {
            "field1": "{placeholder1}",
            "nested": {
                "field2": "{placeholder2}"
            }
        }
        
        parsed = formatter.parse_template(template)
        
        assert isinstance(parsed, dict)
        assert parsed["field1"] == "{placeholder1}"
        assert parsed["nested"]["field2"] == "{placeholder2}"
    
    def test_validate_extraction_rules_integration(self, formatter):
        """Test extraction rules validation through OutputFormatter."""
        rules = {
            "field1": "Rule for field 1",
            "field2": "Rule for field 2"
        }
        
        validated = formatter.validate_extraction_rules(rules)
        
        assert isinstance(validated, dict)
        assert len(validated) == 2
        assert validated["field1"] == "Rule for field 1"
        assert validated["field2"] == "Rule for field 2"
    
    def test_extract_information_integration(self, formatter, sample_results):
        """Test information extraction through OutputFormatter."""
        rules = {
            "status": "Extract execution status",
            "duration": "Extract total duration",
            "teams": "Extract number of teams"
        }
        
        extracted = formatter.extract_information(rules, sample_results)
        
        assert isinstance(extracted, dict)
        assert "status" in extracted
        assert "duration" in extracted
        assert "teams" in extracted
    
    def test_apply_template_integration(self, formatter):
        """Test template application through OutputFormatter."""
        template = {
            "title": "Report",
            "content": "{main_content}",
            "footer": "Generated on {date}"
        }
        
        extracted_info = {
            "main_content": "This is the main content",
            "date": "2024-01-15"
        }
        
        result = formatter.apply_template(template, extracted_info)
        
        assert isinstance(result, dict)
        assert result["title"] == "Report"
        assert result["content"] == "This is the main content"
        assert result["footer"] == "Generated on 2024-01-15"


class TestTemplateUtilityFunctions:
    """Test template-related utility functions."""
    
    def test_format_with_template_utility(self):
        """Test the format_with_template utility function."""
        # Create sample data
        execution_results = StandardizedOutput(
            execution_id="exec_test",
            execution_summary=ExecutionSummary(
                status="completed",
                started_at=datetime.now(),
                completed_at=datetime.now(),
                total_duration=100,
                teams_executed=1,
                agents_involved=1
            ),
            team_results={
                "team_1": TeamResult(
                    status="completed",
                    duration=100,
                    output="Test output"
                )
            },
            errors=[],
            metrics=ExecutionMetrics()
        )
        
        template = {
            "title": "Test Report",
            "content": "{content}"
        }
        
        rules = {
            "content": "Extract content from results"
        }
        
        result = format_with_template(execution_results, template, rules)
        
        assert isinstance(result, dict)
        assert result["title"] == "Test Report"
        assert "content" in result
    
    def test_create_template_processor_utility(self):
        """Test the create_template_processor utility function."""
        from src.hierarchical_agents.output_formatter import create_template_processor
        
        processor = create_template_processor()
        
        assert isinstance(processor, TemplateProcessor)
        assert hasattr(processor, 'parse_template')
        assert hasattr(processor, 'extract_information')
        assert hasattr(processor, 'format_output')