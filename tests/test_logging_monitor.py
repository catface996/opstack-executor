"""
Tests for the logging and monitoring framework.

This module tests all aspects of the logging and monitoring system including:
- Structured JSON logging
- Metrics collection and statistics
- Audit logging functionality
- Log levels and formatting
"""

import json
import logging
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from src.hierarchical_agents.logging_monitor import (
    LoggingMonitor,
    MetricsCollector,
    LogLevel,
    AuditEventType,
    LogEntry,
    AuditEntry,
    MetricPoint,
    JSONFormatter,
    get_logging_monitor,
    initialize_logging_monitor,
    log_system,
    log_execution,
    log_agent,
    log_supervisor,
    log_api,
    log_audit
)
from src.hierarchical_agents.data_models import ErrorInfo


class TestJSONFormatter:
    """Test the JSON formatter for structured logging."""
    
    def test_json_formatter_basic(self):
        """Test basic JSON formatting."""
        formatter = JSONFormatter()
        
        # Create a log record
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Format the record
        formatted = formatter.format(record)
        
        # Parse JSON
        log_data = json.loads(formatted)
        
        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test_logger"
        assert log_data["message"] == "Test message"
        assert "timestamp" in log_data
    
    def test_json_formatter_with_context(self):
        """Test JSON formatting with execution context."""
        formatter = JSONFormatter()
        
        # Create a log record with context
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message with context",
            args=(),
            exc_info=None
        )
        
        # Add context fields
        record.execution_id = "exec_123"
        record.team_id = "team_456"
        record.agent_id = "agent_789"
        record.operation = "test_operation"
        record.duration_ms = 150.5
        
        # Format the record
        formatted = formatter.format(record)
        
        # Parse JSON
        log_data = json.loads(formatted)
        
        assert log_data["execution_id"] == "exec_123"
        assert log_data["team_id"] == "team_456"
        assert log_data["agent_id"] == "agent_789"
        assert log_data["operation"] == "test_operation"
        assert log_data["duration_ms"] == 150.5
    
    def test_json_formatter_with_metadata(self):
        """Test JSON formatting with additional metadata."""
        formatter = JSONFormatter(include_metadata=True)
        
        # Create a log record with extra fields
        record = logging.LogRecord(
            name="test_logger",
            level=logging.WARNING,
            pathname="test.py",
            lineno=10,
            msg="Test warning",
            args=(),
            exc_info=None
        )
        
        # Add custom fields
        record.custom_field = "custom_value"
        record.error_code = "ERR_001"
        
        # Format the record
        formatted = formatter.format(record)
        
        # Parse JSON
        log_data = json.loads(formatted)
        
        assert log_data["level"] == "WARNING"
        assert log_data["metadata"]["custom_field"] == "custom_value"
        assert log_data["metadata"]["error_code"] == "ERR_001"


class TestMetricsCollector:
    """Test the metrics collection functionality."""
    
    def test_counter_metrics(self):
        """Test counter metrics."""
        collector = MetricsCollector()
        
        # Increment counters
        collector.increment_counter("test.counter")
        collector.increment_counter("test.counter", 5)
        collector.increment_counter("test.counter", tags={"env": "test"})
        
        # Check values
        assert collector.get_counter("test.counter") == 6
        assert collector.get_counter("test.counter", {"env": "test"}) == 1
        assert collector.get_counter("nonexistent.counter") == 0
    
    def test_gauge_metrics(self):
        """Test gauge metrics."""
        collector = MetricsCollector()
        
        # Set gauges
        collector.set_gauge("test.gauge", 42.5)
        collector.set_gauge("test.gauge", 100.0, tags={"env": "prod"})
        
        # Check values
        assert collector.get_gauge("test.gauge") == 42.5
        assert collector.get_gauge("test.gauge", {"env": "prod"}) == 100.0
        assert collector.get_gauge("nonexistent.gauge") is None
    
    def test_histogram_metrics(self):
        """Test histogram metrics."""
        collector = MetricsCollector()
        
        # Record histogram values
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        for value in values:
            collector.record_histogram("test.histogram", value)
        
        # Get statistics
        stats = collector.get_histogram_stats("test.histogram")
        
        assert stats["count"] == 10
        assert stats["min"] == 1.0
        assert stats["max"] == 10.0
        assert stats["mean"] == 5.5
        assert stats["p50"] == 5.5
        assert stats["p90"] == 9.1
    
    def test_timer_metrics(self):
        """Test timer metrics."""
        collector = MetricsCollector()
        
        # Record timer values
        durations = [10.0, 20.0, 30.0, 40.0, 50.0]
        for duration in durations:
            collector.record_timer("test.timer", duration)
        
        # Get statistics
        stats = collector.get_timer_stats("test.timer")
        
        assert stats["count"] == 5
        assert stats["min"] == 10.0
        assert stats["max"] == 50.0
        assert stats["mean"] == 30.0
    
    def test_metrics_with_tags(self):
        """Test metrics with tags."""
        collector = MetricsCollector()
        
        # Record metrics with different tags
        collector.increment_counter("requests", tags={"method": "GET", "status": "200"})
        collector.increment_counter("requests", tags={"method": "POST", "status": "201"})
        collector.increment_counter("requests", tags={"method": "GET", "status": "200"})
        
        # Check tagged values
        assert collector.get_counter("requests", {"method": "GET", "status": "200"}) == 2
        assert collector.get_counter("requests", {"method": "POST", "status": "201"}) == 1
    
    def test_get_all_metrics(self):
        """Test getting all metrics."""
        collector = MetricsCollector()
        
        # Add various metrics
        collector.increment_counter("counter1", 5)
        collector.set_gauge("gauge1", 42.0)
        collector.record_histogram("hist1", 10.0)
        collector.record_timer("timer1", 100.0)
        
        # Get all metrics
        all_metrics = collector.get_all_metrics()
        
        assert "counters" in all_metrics
        assert "gauges" in all_metrics
        assert "histograms" in all_metrics
        assert "timers" in all_metrics
        
        assert all_metrics["counters"]["counter1"] == 5
        assert all_metrics["gauges"]["gauge1"] == 42.0
    
    def test_reset_metrics(self):
        """Test resetting all metrics."""
        collector = MetricsCollector()
        
        # Add some metrics
        collector.increment_counter("test.counter", 10)
        collector.set_gauge("test.gauge", 50.0)
        
        # Reset metrics
        collector.reset_metrics()
        
        # Check that metrics are cleared
        assert collector.get_counter("test.counter") == 0
        assert collector.get_gauge("test.gauge") is None


class TestLoggingMonitor:
    """Test the main logging monitor functionality."""
    
    def test_logging_monitor_initialization(self):
        """Test logging monitor initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            
            monitor = LoggingMonitor(
                log_dir=log_dir,
                log_level=LogLevel.DEBUG,
                enable_console_logging=False,
                enable_file_logging=True
            )
            
            assert monitor.log_dir == log_dir
            assert monitor.log_level == LogLevel.DEBUG
            assert not monitor.enable_console_logging
            assert monitor.enable_file_logging
            
            # Check that log directory was created
            assert log_dir.exists()
    
    def test_system_event_logging(self):
        """Test system event logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = LoggingMonitor(
                log_dir=Path(temp_dir),
                enable_console_logging=False
            )
            
            # Log system events with different levels
            monitor.log_system_event("System started", LogLevel.INFO)
            monitor.log_system_event("Debug information", LogLevel.DEBUG)
            monitor.log_system_event("Warning occurred", LogLevel.WARNING)
            monitor.log_system_event("Error happened", LogLevel.ERROR)
            
            # Check that log file was created
            log_file = Path(temp_dir) / "hierarchical_agents.log"
            assert log_file.exists()
    
    def test_execution_event_logging(self):
        """Test execution event logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = LoggingMonitor(
                log_dir=Path(temp_dir),
                enable_console_logging=False
            )
            
            # Log execution events
            monitor.log_execution_event(
                "Execution started",
                execution_id="exec_123",
                team_id="team_456",
                operation="start_execution",
                duration_ms=50.0
            )
            
            # Check metrics were updated
            assert monitor.metrics_collector.get_counter("execution.events") > 0
    
    def test_agent_event_logging(self):
        """Test agent event logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = LoggingMonitor(
                log_dir=Path(temp_dir),
                enable_console_logging=False
            )
            
            # Log agent events
            monitor.log_agent_event(
                "Agent task completed",
                agent_id="agent_789",
                execution_id="exec_123",
                team_id="team_456",
                operation="execute_task",
                duration_ms=200.0
            )
            
            # Check metrics were updated
            assert monitor.metrics_collector.get_counter("agent.events") > 0
    
    def test_supervisor_event_logging(self):
        """Test supervisor event logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = LoggingMonitor(
                log_dir=Path(temp_dir),
                enable_console_logging=False
            )
            
            # Log supervisor events
            monitor.log_supervisor_event(
                "Supervisor routing decision",
                supervisor_id="supervisor_001",
                execution_id="exec_123",
                team_id="team_456",
                operation="route_task",
                duration_ms=30.0
            )
            
            # Check metrics were updated
            assert monitor.metrics_collector.get_counter("supervisor.events") > 0
    
    def test_api_event_logging(self):
        """Test API event logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = LoggingMonitor(
                log_dir=Path(temp_dir),
                enable_console_logging=False
            )
            
            # Log API events
            monitor.log_api_event(
                "API request processed",
                endpoint="/api/v1/teams",
                method="POST",
                status_code=201,
                duration_ms=150.0,
                user_id="user_123",
                ip_address="192.168.1.1"
            )
            
            # Check metrics were updated
            assert monitor.metrics_collector.get_counter("api.requests") > 0
    
    def test_error_event_logging(self):
        """Test error event logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = LoggingMonitor(
                log_dir=Path(temp_dir),
                enable_console_logging=False
            )
            
            # Create error info
            error = ValueError("Test error")
            error_info = ErrorInfo(
                error_code="TEST_ERROR",
                message="Test error occurred",
                context={"test": "context"}
            )
            
            # Log error event
            monitor.log_error_event(
                error,
                error_info,
                execution_id="exec_123",
                team_id="team_456"
            )
            
            # Check metrics were updated
            assert monitor.metrics_collector.get_counter("errors.total") > 0
    
    def test_audit_event_logging(self):
        """Test audit event logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = LoggingMonitor(
                log_dir=Path(temp_dir),
                enable_console_logging=False,
                enable_audit_logging=True
            )
            
            # Log audit events
            monitor.log_audit_event(
                event_type=AuditEventType.TEAM_CREATED,
                action="create_team",
                result="success",
                user_id="user_123",
                execution_id="exec_123",
                resource_id="team_456",
                details={"team_name": "test_team"},
                ip_address="192.168.1.1"
            )
            
            # Check audit entry was stored
            assert len(monitor.audit_entries) > 0
            
            # Check audit log file was created
            audit_file = Path(temp_dir) / "audit.log"
            assert audit_file.exists()
            
            # Check metrics were updated
            assert monitor.metrics_collector.get_counter("audit.events") > 0
    
    def test_time_operation_context_manager(self):
        """Test the time_operation context manager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = LoggingMonitor(
                log_dir=Path(temp_dir),
                enable_console_logging=False
            )
            
            # Test successful operation
            with monitor.time_operation("test_operation", "system"):
                time.sleep(0.01)  # Small delay to measure
            
            # Test failed operation
            with pytest.raises(ValueError):
                with monitor.time_operation("failing_operation", "system"):
                    raise ValueError("Test error")
    
    def test_get_execution_metrics(self):
        """Test getting execution metrics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = LoggingMonitor(
                log_dir=Path(temp_dir),
                enable_console_logging=False
            )
            
            # Add some metrics
            monitor.metrics_collector.increment_counter("tokens.used", 1000)
            monitor.metrics_collector.increment_counter("api.calls", 50)
            
            # Get execution metrics
            metrics = monitor.get_execution_metrics("exec_123")
            
            assert isinstance(metrics.total_tokens_used, int)
            assert isinstance(metrics.api_calls_made, int)
            assert isinstance(metrics.success_rate, float)
            assert isinstance(metrics.average_response_time, float)
    
    def test_get_system_metrics(self):
        """Test getting system metrics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = LoggingMonitor(
                log_dir=Path(temp_dir),
                enable_console_logging=False
            )
            
            # Get system metrics
            metrics = monitor.get_system_metrics()
            
            assert "metrics" in metrics
            assert "audit_events_count" in metrics
            assert "recent_errors" in metrics
            assert "uptime_seconds" in metrics
            assert "log_files" in metrics
    
    def test_get_audit_trail(self):
        """Test getting filtered audit trail."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = LoggingMonitor(
                log_dir=Path(temp_dir),
                enable_console_logging=False
            )
            
            # Add audit events
            monitor.log_audit_event(
                AuditEventType.TEAM_CREATED,
                "create_team",
                "success",
                user_id="user_123",
                execution_id="exec_123"
            )
            
            monitor.log_audit_event(
                AuditEventType.EXECUTION_STARTED,
                "start_execution",
                "success",
                user_id="user_456",
                execution_id="exec_456"
            )
            
            # Test filtering
            all_entries = monitor.get_audit_trail()
            assert len(all_entries) >= 2  # Including system startup event
            
            user_entries = monitor.get_audit_trail(user_id="user_123")
            assert len(user_entries) == 1
            assert user_entries[0].user_id == "user_123"
            
            exec_entries = monitor.get_audit_trail(execution_id="exec_456")
            assert len(exec_entries) == 1
            assert exec_entries[0].execution_id == "exec_456"
    
    def test_log_levels_mapping(self):
        """Test that different log levels are handled correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = LoggingMonitor(
                log_dir=Path(temp_dir),
                log_level=LogLevel.DEBUG,
                enable_console_logging=False
            )
            
            # Test all log levels
            monitor.log_system_event("Debug message", LogLevel.DEBUG)
            monitor.log_system_event("Info message", LogLevel.INFO)
            monitor.log_system_event("Warning message", LogLevel.WARNING)
            monitor.log_system_event("Error message", LogLevel.ERROR)
            monitor.log_system_event("Critical message", LogLevel.CRITICAL)
            
            # Check that log file contains entries
            log_file = Path(temp_dir) / "hierarchical_agents.log"
            assert log_file.exists()
            
            # Read log file and verify JSON format
            with open(log_file, 'r') as f:
                lines = f.readlines()
                
            # Each line should be valid JSON
            for line in lines:
                if line.strip():
                    log_data = json.loads(line.strip())
                    assert "level" in log_data
                    assert log_data["level"] in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class TestConvenienceFunctions:
    """Test the convenience functions for logging."""
    
    def test_global_logging_functions(self):
        """Test global logging convenience functions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Initialize global monitor
            initialize_logging_monitor(
                log_dir=Path(temp_dir),
                enable_console_logging=False
            )
            
            # Test convenience functions
            log_system("System message")
            log_execution("Execution message", "exec_123")
            log_agent("Agent message", "agent_456")
            log_supervisor("Supervisor message", "supervisor_789")
            log_api("API message", "/api/test", "GET", 200)
            log_audit(AuditEventType.TEAM_CREATED, "create_team", "success")
            
            # Get global monitor and check metrics
            monitor = get_logging_monitor()
            assert monitor.metrics_collector.get_counter("execution.events") > 0
            assert monitor.metrics_collector.get_counter("agent.events") > 0
            assert monitor.metrics_collector.get_counter("supervisor.events") > 0
            assert monitor.metrics_collector.get_counter("api.requests") > 0
            assert monitor.metrics_collector.get_counter("audit.events") > 0


class TestDataModels:
    """Test the data models used in logging and monitoring."""
    
    def test_log_entry_serialization(self):
        """Test LogEntry serialization."""
        entry = LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            logger_name="test_logger",
            message="Test message",
            execution_id="exec_123",
            metadata={"key": "value"}
        )
        
        # Test dictionary conversion
        entry_dict = entry.to_dict()
        assert entry_dict["level"] == "INFO"
        assert entry_dict["logger"] == "test_logger"
        assert entry_dict["message"] == "Test message"
        assert entry_dict["execution_id"] == "exec_123"
        assert entry_dict["metadata"]["key"] == "value"
        
        # Test JSON conversion
        entry_json = entry.to_json()
        parsed = json.loads(entry_json)
        assert parsed["level"] == "INFO"
    
    def test_audit_entry_serialization(self):
        """Test AuditEntry serialization."""
        entry = AuditEntry(
            timestamp=datetime.now(),
            event_type=AuditEventType.TEAM_CREATED,
            user_id="user_123",
            execution_id="exec_456",
            resource_id="team_789",
            action="create_team",
            result="success",
            details={"team_name": "test_team"}
        )
        
        # Test dictionary conversion
        entry_dict = entry.to_dict()
        assert entry_dict["event_type"] == "team_created"
        assert entry_dict["user_id"] == "user_123"
        assert entry_dict["action"] == "create_team"
        assert entry_dict["result"] == "success"
        
        # Test JSON conversion
        entry_json = entry.to_json()
        parsed = json.loads(entry_json)
        assert parsed["event_type"] == "team_created"
    
    def test_metric_point_serialization(self):
        """Test MetricPoint serialization."""
        point = MetricPoint(
            timestamp=datetime.now(),
            name="test.metric",
            value=42.5,
            tags={"env": "test", "service": "api"}
        )
        
        # Test dictionary conversion
        point_dict = point.to_dict()
        assert point_dict["name"] == "test.metric"
        assert point_dict["value"] == 42.5
        assert point_dict["tags"]["env"] == "test"
        assert point_dict["tags"]["service"] == "api"


class TestIntegration:
    """Integration tests for the logging and monitoring system."""
    
    def test_full_logging_workflow(self):
        """Test a complete logging workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = LoggingMonitor(
                log_dir=Path(temp_dir),
                enable_console_logging=False,
                enable_audit_logging=True
            )
            
            # Simulate a complete execution workflow
            execution_id = "exec_integration_test"
            team_id = "team_test"
            agent_id = "agent_test"
            supervisor_id = "supervisor_test"
            
            # 1. Log team creation
            monitor.log_audit_event(
                AuditEventType.TEAM_CREATED,
                "create_team",
                "success",
                execution_id=execution_id,
                resource_id=team_id
            )
            
            # 2. Log execution start
            monitor.log_execution_event(
                "Execution started",
                execution_id=execution_id,
                team_id=team_id,
                operation="start_execution"
            )
            
            # 3. Log supervisor routing
            monitor.log_supervisor_event(
                "Routing task to agent",
                supervisor_id=supervisor_id,
                execution_id=execution_id,
                team_id=team_id,
                operation="route_task",
                duration_ms=25.0
            )
            
            # 4. Log agent execution
            monitor.log_agent_event(
                "Agent task completed",
                agent_id=agent_id,
                execution_id=execution_id,
                team_id=team_id,
                operation="execute_task",
                duration_ms=150.0
            )
            
            # 5. Log execution completion
            monitor.log_execution_event(
                "Execution completed",
                execution_id=execution_id,
                team_id=team_id,
                operation="complete_execution",
                duration_ms=200.0
            )
            
            # Verify metrics were collected
            metrics = monitor.get_system_metrics()
            assert metrics["metrics"]["counters"]["execution.events"] >= 2
            assert metrics["metrics"]["counters"]["agent.events"] >= 1
            assert metrics["metrics"]["counters"]["supervisor.events"] >= 1
            assert metrics["audit_events_count"] >= 2  # Including system startup
            
            # Verify audit trail
            audit_trail = monitor.get_audit_trail(execution_id=execution_id)
            assert len(audit_trail) >= 1
            
            # Verify log files were created
            log_file = Path(temp_dir) / "hierarchical_agents.log"
            audit_file = Path(temp_dir) / "audit.log"
            assert log_file.exists()
            assert audit_file.exists()
            
            # Verify log file contains structured JSON
            with open(log_file, 'r') as f:
                lines = f.readlines()
                
            json_logs = []
            for line in lines:
                if line.strip():
                    log_data = json.loads(line.strip())
                    json_logs.append(log_data)
            
            # Find logs related to our execution
            execution_logs = [
                log for log in json_logs 
                if log.get("execution_id") == execution_id
            ]
            
            assert len(execution_logs) >= 3  # At least execution start, agent, and completion
            
            # Verify log structure
            for log in execution_logs:
                assert "timestamp" in log
                assert "level" in log
                assert "logger" in log
                assert "message" in log
                assert log["execution_id"] == execution_id
    
    def test_error_handling_integration(self):
        """Test error handling integration with logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = LoggingMonitor(
                log_dir=Path(temp_dir),
                enable_console_logging=False
            )
            
            # Simulate an error scenario
            error = RuntimeError("Test runtime error")
            error_info = ErrorInfo(
                error_code="RUNTIME_ERROR",
                message="Test runtime error occurred",
                context={
                    "operation": "test_operation",
                    "component": "test_component"
                }
            )
            
            # Log the error
            monitor.log_error_event(
                error,
                error_info,
                execution_id="exec_error_test",
                team_id="team_error_test",
                agent_id="agent_error_test"
            )
            
            # Verify error metrics
            assert monitor.metrics_collector.get_counter("errors.total") > 0
            
            # Verify audit event was created
            error_audits = monitor.get_audit_trail(
                event_type=AuditEventType.ERROR_OCCURRED
            )
            assert len(error_audits) > 0
            
            # Verify error audit details
            error_audit = error_audits[0]
            assert error_audit.event_type == AuditEventType.ERROR_OCCURRED
            assert error_audit.result == "failure"
            assert "error_type" in error_audit.details
            assert "error_code" in error_audit.details


if __name__ == "__main__":
    pytest.main([__file__])