#!/usr/bin/env python3
"""
Demonstration of the logging and monitoring system.

This script shows how to use the comprehensive logging and monitoring
framework for the hierarchical multi-agent system.
"""

import json
import tempfile
import time
from pathlib import Path

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.hierarchical_agents.logging_monitor import (
    LoggingMonitor,
    LogLevel,
    AuditEventType,
    initialize_logging_monitor,
    log_system,
    log_execution,
    log_agent,
    log_supervisor,
    log_api,
    log_audit
)
from src.hierarchical_agents.data_models import ErrorInfo


def demonstrate_structured_logging():
    """Demonstrate structured JSON logging with different log levels."""
    print("=== Structured Logging Demo ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize logging monitor
        monitor = LoggingMonitor(
            log_dir=Path(temp_dir),
            log_level=LogLevel.DEBUG,
            enable_console_logging=True,
            enable_file_logging=True,
            enable_audit_logging=True
        )
        
        # Log events at different levels
        monitor.log_system_event("System initialization started", LogLevel.INFO)
        monitor.log_system_event("Debug information", LogLevel.DEBUG, operation="debug_check")
        monitor.log_system_event("Warning: Resource usage high", LogLevel.WARNING, cpu_usage=85.5)
        monitor.log_system_event("Error: Connection failed", LogLevel.ERROR, error_code="CONN_001")
        monitor.log_system_event("Critical: System overload", LogLevel.CRITICAL, memory_usage=95.2)
        
        # Show log file contents
        log_file = Path(temp_dir) / "hierarchical_agents.log"
        if log_file.exists():
            print(f"\nLog file created: {log_file}")
            with open(log_file, 'r') as f:
                lines = f.readlines()
                print(f"Number of log entries: {len(lines)}")
                
                # Show first few entries
                print("\nSample log entries (JSON format):")
                for i, line in enumerate(lines[:3]):
                    if line.strip():
                        log_data = json.loads(line.strip())
                        print(f"Entry {i+1}: Level={log_data['level']}, Message={log_data['message']}")


def demonstrate_execution_logging():
    """Demonstrate execution-specific logging."""
    print("\n=== Execution Logging Demo ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        monitor = LoggingMonitor(
            log_dir=Path(temp_dir),
            enable_console_logging=False
        )
        
        execution_id = "exec_demo_123"
        team_id = "team_research"
        agent_id = "agent_search_001"
        supervisor_id = "supervisor_main"
        
        # Simulate execution workflow
        monitor.log_execution_event(
            "Execution started",
            execution_id=execution_id,
            team_id=team_id,
            operation="start_execution"
        )
        
        monitor.log_supervisor_event(
            "Routing task to search agent",
            supervisor_id=supervisor_id,
            execution_id=execution_id,
            team_id=team_id,
            operation="route_task",
            duration_ms=25.0
        )
        
        monitor.log_agent_event(
            "Agent task completed successfully",
            agent_id=agent_id,
            execution_id=execution_id,
            team_id=team_id,
            operation="execute_task",
            duration_ms=150.0
        )
        
        monitor.log_execution_event(
            "Execution completed",
            execution_id=execution_id,
            team_id=team_id,
            operation="complete_execution",
            duration_ms=200.0
        )
        
        # Show metrics
        metrics = monitor.get_system_metrics()
        print(f"Total execution events: {len([k for k in metrics['metrics']['counters'] if 'execution.events' in k])}")
        print(f"Total agent events: {len([k for k in metrics['metrics']['counters'] if 'agent.events' in k])}")
        print(f"Total supervisor events: {len([k for k in metrics['metrics']['counters'] if 'supervisor.events' in k])}")


def demonstrate_metrics_collection():
    """Demonstrate metrics collection and statistics."""
    print("\n=== Metrics Collection Demo ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        monitor = LoggingMonitor(
            log_dir=Path(temp_dir),
            enable_console_logging=False
        )
        
        # Simulate API requests with different response times
        endpoints = ["/api/v1/teams", "/api/v1/executions", "/api/v1/results"]
        methods = ["GET", "POST"]
        status_codes = [200, 201, 400, 500]
        
        for i in range(20):
            endpoint = endpoints[i % len(endpoints)]
            method = methods[i % len(methods)]
            status_code = status_codes[i % len(status_codes)]
            duration = 50 + (i * 10)  # Varying response times
            
            monitor.log_api_event(
                f"API request processed",
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_ms=duration,
                user_id=f"user_{i % 3}"
            )
        
        # Show API metrics
        all_metrics = monitor.metrics_collector.get_all_metrics()
        print("API Request Counters:")
        for key, value in all_metrics["counters"].items():
            if "api.requests" in key:
                print(f"  {key}: {value}")
        
        print("\nAPI Response Time Statistics:")
        for key, stats in all_metrics["timers"].items():
            if "api.response_time" in key:
                print(f"  {key}: mean={stats.get('mean', 0):.1f}ms, p95={stats.get('p95', 0):.1f}ms")


def demonstrate_audit_logging():
    """Demonstrate audit logging for critical operations."""
    print("\n=== Audit Logging Demo ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        monitor = LoggingMonitor(
            log_dir=Path(temp_dir),
            enable_console_logging=False,
            enable_audit_logging=True
        )
        
        # Log various audit events
        monitor.log_audit_event(
            event_type=AuditEventType.TEAM_CREATED,
            action="create_hierarchical_team",
            result="success",
            user_id="admin_user",
            execution_id="exec_audit_demo",
            resource_id="team_research_001",
            details={
                "team_name": "Research Analysis Team",
                "sub_teams_count": 2,
                "total_agents": 3
            },
            ip_address="192.168.1.100"
        )
        
        monitor.log_audit_event(
            event_type=AuditEventType.EXECUTION_STARTED,
            action="start_team_execution",
            result="success",
            user_id="api_user",
            execution_id="exec_audit_demo",
            resource_id="team_research_001",
            details={
                "execution_config": {
                    "stream_events": True,
                    "max_parallel_teams": 1
                }
            },
            ip_address="10.0.0.50"
        )
        
        monitor.log_audit_event(
            event_type=AuditEventType.API_KEY_ACCESSED,
            action="access_openai_key",
            result="success",
            user_id="system",
            details={
                "provider": "openai",
                "model": "gpt-4o",
                "purpose": "agent_execution"
            }
        )
        
        # Show audit trail
        audit_trail = monitor.get_audit_trail()
        print(f"Total audit events: {len(audit_trail)}")
        
        # Show audit events by type
        for event_type in AuditEventType:
            events = monitor.get_audit_trail(event_type=event_type)
            if events:
                print(f"  {event_type.value}: {len(events)} events")
        
        # Show audit log file
        audit_file = Path(temp_dir) / "audit.log"
        if audit_file.exists():
            print(f"\nAudit log file created: {audit_file}")
            with open(audit_file, 'r') as f:
                lines = f.readlines()
                print(f"Audit log entries: {len(lines)}")


def demonstrate_error_logging():
    """Demonstrate error logging and metrics."""
    print("\n=== Error Logging Demo ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        monitor = LoggingMonitor(
            log_dir=Path(temp_dir),
            enable_console_logging=False
        )
        
        # Simulate different types of errors
        errors = [
            (ValueError("Invalid configuration parameter"), "CONFIG_ERROR"),
            (ConnectionError("Failed to connect to LLM API"), "NETWORK_ERROR"),
            (TimeoutError("Request timeout after 30 seconds"), "TIMEOUT_ERROR"),
            (RuntimeError("Agent execution failed"), "RUNTIME_ERROR")
        ]
        
        for i, (error, error_code) in enumerate(errors):
            error_info = ErrorInfo(
                error_code=error_code,
                message=str(error),
                context={
                    "execution_id": f"exec_error_{i}",
                    "component": "test_component",
                    "operation": f"test_operation_{i}"
                }
            )
            
            monitor.log_error_event(
                error,
                error_info,
                execution_id=f"exec_error_{i}",
                team_id=f"team_{i}",
                agent_id=f"agent_{i}"
            )
        
        # Show error metrics
        all_metrics = monitor.metrics_collector.get_all_metrics()
        print("Error Counters:")
        for key, value in all_metrics["counters"].items():
            if "errors.total" in key:
                print(f"  {key}: {value}")
        
        # Show error audit events
        error_audits = monitor.get_audit_trail(event_type=AuditEventType.ERROR_OCCURRED)
        print(f"\nError audit events: {len(error_audits)}")
        for audit in error_audits[:2]:  # Show first 2
            print(f"  Error: {audit.details.get('error_type')} - {audit.details.get('error_message')}")


def demonstrate_timing_operations():
    """Demonstrate operation timing with context manager."""
    print("\n=== Operation Timing Demo ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        monitor = LoggingMonitor(
            log_dir=Path(temp_dir),
            enable_console_logging=False
        )
        
        # Time successful operations
        with monitor.time_operation("database_query", "system"):
            time.sleep(0.1)  # Simulate database query
        
        with monitor.time_operation("llm_api_call", "agent", agent_id="agent_001"):
            time.sleep(0.05)  # Simulate API call
        
        with monitor.time_operation("supervisor_routing", "supervisor", supervisor_id="supervisor_main"):
            time.sleep(0.02)  # Simulate routing decision
        
        # Time failed operation
        try:
            with monitor.time_operation("failing_operation", "system"):
                time.sleep(0.01)
                raise ValueError("Simulated failure")
        except ValueError:
            pass  # Expected failure
        
        # Show timing metrics
        all_metrics = monitor.metrics_collector.get_all_metrics()
        print("Operation Timings:")
        for key, stats in all_metrics["timers"].items():
            if stats:
                print(f"  {key}: mean={stats.get('mean', 0):.1f}ms, count={stats.get('count', 0)}")


def demonstrate_convenience_functions():
    """Demonstrate convenience functions for logging."""
    print("\n=== Convenience Functions Demo ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize global monitor
        initialize_logging_monitor(
            log_dir=Path(temp_dir),
            log_level=LogLevel.INFO,
            enable_console_logging=False
        )
        
        # Use convenience functions
        log_system("System ready for operations", operation="startup")
        log_execution("Processing user request", "exec_convenience_demo", team_id="team_main")
        log_agent("Searching for relevant information", "agent_search", execution_id="exec_convenience_demo")
        log_supervisor("Routing to analysis team", "supervisor_main", execution_id="exec_convenience_demo")
        log_api("Team creation request", "/api/v1/teams", "POST", 201, duration_ms=120.0)
        log_audit(AuditEventType.TEAM_CREATED, "create_team", "success", execution_id="exec_convenience_demo")
        
        # Get global monitor and show metrics
        from src.hierarchical_agents.logging_monitor import get_logging_monitor
        monitor = get_logging_monitor()
        
        metrics = monitor.get_system_metrics()
        print(f"Events logged using convenience functions:")
        counter_count = len([k for k in metrics['metrics']['counters'] if any(
            event_type in k for event_type in ['execution.events', 'agent.events', 'supervisor.events', 'api.requests', 'audit.events']
        )])
        print(f"  Total event counters: {counter_count}")


def main():
    """Run all demonstrations."""
    print("🚀 Hierarchical Multi-Agent System - Logging & Monitoring Demo")
    print("=" * 60)
    
    demonstrate_structured_logging()
    demonstrate_execution_logging()
    demonstrate_metrics_collection()
    demonstrate_audit_logging()
    demonstrate_error_logging()
    demonstrate_timing_operations()
    demonstrate_convenience_functions()
    
    print("\n" + "=" * 60)
    print("✅ All logging and monitoring demonstrations completed successfully!")
    print("\nKey Features Demonstrated:")
    print("• Structured JSON logging with proper log levels")
    print("• Execution metrics collection and statistics")
    print("• Comprehensive audit logging for critical operations")
    print("• Error logging with automatic audit trail")
    print("• Operation timing with context managers")
    print("• Convenient global logging functions")
    print("• Thread-safe metrics collection")
    print("• Automatic log file rotation")
    print("• Flexible filtering and querying")


if __name__ == "__main__":
    main()