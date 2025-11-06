"""
Tests for performance monitoring and optimization functionality.

This module tests the performance monitoring system including:
- Performance metrics collection
- Resource usage monitoring
- Concurrent execution optimization
- Prometheus integration
"""

import asyncio
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from hierarchical_agents.performance_monitor import (
    PerformanceMonitor,
    PerformanceOptimizer,
    ResourceMonitor,
    ResourceUsage,
    PerformanceMetrics,
    ConcurrencyMetrics,
    initialize_performance_monitor,
    get_performance_monitor,
    monitor_execution,
    record_api_metrics,
    record_agent_metrics
)


class TestPerformanceOptimizer:
    """Test performance optimization functionality."""
    
    def test_optimizer_initialization(self):
        """Test optimizer initialization."""
        optimizer = PerformanceOptimizer(max_concurrent_executions=5)
        
        assert optimizer.max_concurrent_executions == 5
        assert optimizer.execution_semaphore._value == 5
        assert optimizer.thread_pool._max_workers == 5
        assert len(optimizer.active_executions) == 0
        assert len(optimizer.execution_queue) == 0
    
    @pytest.mark.asyncio
    async def test_managed_execution(self):
        """Test managed execution context manager."""
        optimizer = PerformanceOptimizer(max_concurrent_executions=2)
        execution_id = "test_exec_001"
        
        async with optimizer.managed_execution(execution_id):
            # Check that execution is tracked
            assert execution_id in optimizer.active_executions
            
            # Simulate some work
            await asyncio.sleep(0.1)
        
        # Check that execution is cleaned up
        assert execution_id not in optimizer.active_executions
        assert len(optimizer.execution_times[execution_id]) == 1
        assert optimizer.execution_times[execution_id][0] >= 100  # At least 100ms
    
    @pytest.mark.asyncio
    async def test_concurrent_execution_limit(self):
        """Test that concurrent execution limit is enforced."""
        optimizer = PerformanceOptimizer(max_concurrent_executions=2)
        
        # Start two executions
        async def long_execution(exec_id):
            async with optimizer.managed_execution(exec_id):
                await asyncio.sleep(0.2)
        
        # Start executions
        task1 = asyncio.create_task(long_execution("exec1"))
        task2 = asyncio.create_task(long_execution("exec2"))
        
        # Wait a bit to let them start
        await asyncio.sleep(0.05)
        
        # Both should be active
        assert len(optimizer.active_executions) == 2
        
        # Start third execution - should be queued
        start_time = time.time()
        task3 = asyncio.create_task(long_execution("exec3"))
        
        # Wait for all to complete
        await asyncio.gather(task1, task2, task3)
        
        # Third execution should have been queued
        assert len(optimizer.queue_times) >= 1
        
        # All executions should be cleaned up
        assert len(optimizer.active_executions) == 0
    
    def test_get_concurrency_metrics(self):
        """Test concurrency metrics collection."""
        optimizer = PerformanceOptimizer(max_concurrent_executions=5)
        
        # Add some mock data
        optimizer.execution_times["exec1"] = [100.0, 150.0]
        optimizer.execution_times["exec2"] = [200.0]
        optimizer.queue_times = [50.0, 75.0, 100.0]
        
        metrics = optimizer.get_concurrency_metrics()
        
        assert isinstance(metrics, ConcurrencyMetrics)
        assert metrics.max_concurrent_executions == 5
        assert metrics.total_executions_started == 2
        assert metrics.total_executions_completed == 3
        assert metrics.average_queue_time_ms == 75.0


class TestResourceMonitor:
    """Test resource monitoring functionality."""
    
    def test_resource_monitor_initialization(self):
        """Test resource monitor initialization."""
        monitor = ResourceMonitor(monitoring_interval=1.0)
        
        assert monitor.monitoring_interval == 1.0
        assert not monitor.is_monitoring
        assert monitor.monitoring_task is None
        assert len(monitor.resource_history) == 0
    
    def test_collect_resource_usage(self):
        """Test resource usage collection."""
        monitor = ResourceMonitor()
        
        usage = monitor._collect_resource_usage()
        
        assert isinstance(usage, ResourceUsage)
        assert isinstance(usage.timestamp, datetime)
        assert usage.cpu_percent >= 0
        assert usage.memory_percent >= 0
        assert usage.memory_used_mb >= 0
        assert usage.memory_available_mb >= 0
        assert usage.disk_usage_percent >= 0
        assert usage.thread_count >= 1
    
    def test_get_current_usage(self):
        """Test getting current resource usage."""
        monitor = ResourceMonitor()
        
        usage = monitor.get_current_usage()
        
        assert isinstance(usage, ResourceUsage)
        assert usage.timestamp is not None
    
    def test_get_usage_history(self):
        """Test getting usage history."""
        monitor = ResourceMonitor()
        
        # Add some mock history
        now = datetime.now()
        for i in range(5):
            usage = ResourceUsage(
                timestamp=now - timedelta(minutes=i),
                cpu_percent=50.0 + i,
                memory_percent=60.0 + i,
                memory_used_mb=1000.0 + i * 100,
                memory_available_mb=2000.0 - i * 50,
                disk_usage_percent=70.0 + i,
                network_bytes_sent=1000 * i,
                network_bytes_recv=2000 * i,
                open_file_descriptors=100 + i,
                thread_count=10 + i,
                process_count=50 + i
            )
            monitor.resource_history.append(usage)
        
        # Get history for last 3 minutes
        history = monitor.get_usage_history(minutes=3)
        
        assert len(history) == 3  # 0, 1, 2 minutes ago (3 minutes cutoff excludes older entries)
        assert all(isinstance(usage, ResourceUsage) for usage in history)
    
    def test_get_usage_stats(self):
        """Test getting usage statistics."""
        monitor = ResourceMonitor()
        
        # Add some mock history
        now = datetime.now()
        for i in range(3):
            usage = ResourceUsage(
                timestamp=now - timedelta(minutes=i),
                cpu_percent=50.0 + i * 10,
                memory_percent=60.0 + i * 5,
                memory_used_mb=1000.0,
                memory_available_mb=2000.0,
                disk_usage_percent=70.0,
                network_bytes_sent=1000,
                network_bytes_recv=2000,
                open_file_descriptors=100,
                thread_count=10,
                process_count=50
            )
            monitor.resource_history.append(usage)
        
        stats = monitor.get_usage_stats()
        
        assert "cpu" in stats
        assert "memory" in stats
        assert "samples" in stats
        assert stats["samples"] == 3
        assert stats["cpu"]["max"] == 70.0
        assert stats["cpu"]["min"] == 50.0
        assert stats["memory"]["max"] == 70.0
        assert stats["memory"]["min"] == 60.0
    
    def test_alert_callbacks(self):
        """Test resource alert callbacks."""
        monitor = ResourceMonitor()
        monitor.cpu_threshold = 80.0
        monitor.memory_threshold = 85.0
        
        # Mock callback
        callback_calls = []
        def test_callback(alert, usage):
            callback_calls.append((alert, usage))
        
        monitor.add_alert_callback(test_callback)
        
        # Create high usage scenario
        high_usage = ResourceUsage(
            timestamp=datetime.now(),
            cpu_percent=90.0,  # Above threshold
            memory_percent=90.0,  # Above threshold
            memory_used_mb=1000.0,
            memory_available_mb=100.0,
            disk_usage_percent=70.0,
            network_bytes_sent=1000,
            network_bytes_recv=2000,
            open_file_descriptors=100,
            thread_count=10,
            process_count=50
        )
        
        monitor._check_resource_alerts(high_usage)
        
        # Should have triggered alerts
        assert len(callback_calls) == 2  # CPU and memory alerts
        assert "High CPU usage" in callback_calls[0][0]
        assert "High memory usage" in callback_calls[1][0]


@pytest.mark.skipif(
    not pytest.importorskip("prometheus_client", minversion=None),
    reason="prometheus_client not available"
)
class TestPrometheusExporter:
    """Test Prometheus metrics export functionality."""
    
    def test_prometheus_exporter_initialization(self):
        """Test Prometheus exporter initialization."""
        from hierarchical_agents.performance_monitor import PrometheusExporter
        
        exporter = PrometheusExporter()
        
        assert exporter.registry is not None
        assert exporter.execution_counter is not None
        assert exporter.execution_duration is not None
        assert exporter.active_executions is not None
        assert exporter.api_requests is not None
        assert exporter.cpu_usage is not None
        assert exporter.memory_usage is not None
    
    def test_record_execution_metrics(self):
        """Test recording execution metrics."""
        from hierarchical_agents.performance_monitor import PrometheusExporter
        
        exporter = PrometheusExporter()
        
        # Record some metrics
        exporter.record_execution("success", "team1", 1.5)
        exporter.record_execution("failure", "team2", 0.8)
        
        # Get metrics output
        metrics_output = exporter.get_metrics()
        
        assert "hierarchical_agents_executions_total" in metrics_output
        assert "hierarchical_agents_execution_duration_seconds" in metrics_output
    
    def test_record_api_metrics(self):
        """Test recording API metrics."""
        from hierarchical_agents.performance_monitor import PrometheusExporter
        
        exporter = PrometheusExporter()
        
        # Record API metrics
        exporter.record_api_request("GET", "/api/v1/teams", 200, 0.5)
        exporter.record_api_request("POST", "/api/v1/executions", 201, 1.2)
        
        # Get metrics output
        metrics_output = exporter.get_metrics()
        
        assert "hierarchical_agents_api_requests_total" in metrics_output
        assert "hierarchical_agents_api_duration_seconds" in metrics_output
    
    def test_update_resource_metrics(self):
        """Test updating resource metrics."""
        from hierarchical_agents.performance_monitor import PrometheusExporter
        
        exporter = PrometheusExporter()
        
        usage = ResourceUsage(
            timestamp=datetime.now(),
            cpu_percent=75.5,
            memory_percent=82.3,
            memory_used_mb=1500.0,
            memory_available_mb=500.0,
            disk_usage_percent=65.0,
            network_bytes_sent=1000,
            network_bytes_recv=2000,
            open_file_descriptors=150,
            thread_count=25,
            process_count=75
        )
        
        exporter.update_resource_metrics(usage)
        
        # Check that gauges are updated
        metrics_output = exporter.get_metrics()
        
        assert "hierarchical_agents_cpu_usage_percent" in metrics_output
        assert "hierarchical_agents_memory_usage_percent" in metrics_output
        assert "hierarchical_agents_memory_used_bytes" in metrics_output


class TestPerformanceMonitor:
    """Test main performance monitor functionality."""
    
    def test_performance_monitor_initialization(self):
        """Test performance monitor initialization."""
        monitor = PerformanceMonitor(
            max_concurrent_executions=8,
            enable_prometheus=False,  # Disable for testing
            monitoring_interval=2.0
        )
        
        assert monitor.max_concurrent_executions == 8
        assert not monitor.enable_prometheus
        assert monitor.monitoring_interval == 2.0
        assert monitor.optimizer is not None
        assert monitor.resource_monitor is not None
        assert monitor.prometheus_exporter is None
    
    @pytest.mark.asyncio
    async def test_monitor_execution_context(self):
        """Test execution monitoring context manager."""
        monitor = PerformanceMonitor(
            max_concurrent_executions=5,
            enable_prometheus=False
        )
        
        execution_id = "test_exec_001"
        team_id = "test_team"
        
        async with monitor.monitor_execution(execution_id, team_id):
            # Simulate some work
            await asyncio.sleep(0.1)
        
        # Check that metrics were recorded
        assert execution_id in monitor.operation_metrics
        assert len(monitor.operation_metrics[execution_id]) == 1
        assert monitor.operation_metrics[execution_id][0] >= 100  # At least 100ms
    
    def test_get_performance_summary(self):
        """Test getting performance summary."""
        monitor = PerformanceMonitor(
            max_concurrent_executions=5,
            enable_prometheus=False
        )
        
        # Add some mock operation metrics
        monitor.operation_metrics["exec1"] = [100.0, 150.0, 120.0]
        monitor.operation_metrics["exec2"] = [200.0, 180.0]
        
        summary = monitor.get_performance_summary()
        
        assert "uptime_seconds" in summary
        assert "resource_usage" in summary
        assert "concurrency" in summary
        assert "operations" in summary
        assert "prometheus_enabled" in summary
        
        # Check operation stats
        assert "exec1" in summary["operations"]
        assert "exec2" in summary["operations"]
        assert summary["operations"]["exec1"]["count"] == 3
        assert summary["operations"]["exec1"]["avg_ms"] == 123.33333333333333
        assert summary["operations"]["exec2"]["count"] == 2
        assert summary["operations"]["exec2"]["avg_ms"] == 190.0
    
    def test_get_health_status(self):
        """Test getting health status."""
        monitor = PerformanceMonitor(
            max_concurrent_executions=5,
            enable_prometheus=False
        )
        
        health = monitor.get_health_status()
        
        assert "status" in health
        assert "issues" in health
        assert "cpu_percent" in health
        assert "memory_percent" in health
        assert "active_executions" in health
        assert "timestamp" in health
        
        # Should be healthy initially
        assert health["status"] in ["healthy", "degraded", "unhealthy"]
        assert isinstance(health["issues"], list)


class TestGlobalFunctions:
    """Test global performance monitoring functions."""
    
    def test_initialize_performance_monitor(self):
        """Test initializing global performance monitor."""
        monitor = initialize_performance_monitor(
            max_concurrent_executions=6,
            enable_prometheus=False,
            monitoring_interval=3.0
        )
        
        assert monitor is not None
        assert monitor.max_concurrent_executions == 6
        assert not monitor.enable_prometheus
        assert monitor.monitoring_interval == 3.0
        
        # Check that global instance is set
        global_monitor = get_performance_monitor()
        assert global_monitor is monitor
    
    @pytest.mark.asyncio
    async def test_monitor_execution_function(self):
        """Test monitor_execution function."""
        # Initialize global monitor
        initialize_performance_monitor(
            max_concurrent_executions=5,
            enable_prometheus=False
        )
        
        execution_id = "test_func_exec"
        team_id = "test_func_team"
        
        async with monitor_execution(execution_id, team_id):
            await asyncio.sleep(0.05)
        
        # Check that metrics were recorded
        global_monitor = get_performance_monitor()
        assert execution_id in global_monitor.operation_metrics
    
    def test_record_api_metrics_function(self):
        """Test record_api_metrics function."""
        # Initialize global monitor with Prometheus disabled
        initialize_performance_monitor(
            enable_prometheus=False
        )
        
        # This should not raise an error even without Prometheus
        record_api_metrics("GET", "/test", 200, 0.5)
    
    def test_record_agent_metrics_function(self):
        """Test record_agent_metrics function."""
        # Initialize global monitor with Prometheus disabled
        initialize_performance_monitor(
            enable_prometheus=False
        )
        
        # This should not raise an error even without Prometheus
        record_agent_metrics("agent_001", "success", 1.2)


@pytest.mark.asyncio
async def test_concurrent_execution_performance():
    """Test performance under concurrent execution load."""
    monitor = PerformanceMonitor(
        max_concurrent_executions=3,
        enable_prometheus=False
    )
    
    await monitor.initialize()
    
    # Create multiple concurrent executions
    async def test_execution(exec_id):
        async with monitor.monitor_execution(exec_id, "load_test"):
            await asyncio.sleep(0.1)
            return f"result_{exec_id}"
    
    # Start 10 concurrent executions (more than limit)
    tasks = [
        asyncio.create_task(test_execution(f"exec_{i}"))
        for i in range(10)
    ]
    
    start_time = time.time()
    results = await asyncio.gather(*tasks)
    total_time = time.time() - start_time
    
    # All executions should complete
    assert len(results) == 10
    assert all(result.startswith("result_") for result in results)
    
    # Should take longer than 0.1s due to concurrency limit
    assert total_time > 0.3  # At least 3 batches of 0.1s each
    
    # Check performance summary
    summary = monitor.get_performance_summary()
    assert summary["concurrency"]["total_completed"] >= 10
    
    await monitor.shutdown()


def test_performance_metrics_data_structure():
    """Test performance metrics data structures."""
    # Test ResourceUsage
    usage = ResourceUsage(
        timestamp=datetime.now(),
        cpu_percent=75.0,
        memory_percent=80.0,
        memory_used_mb=1500.0,
        memory_available_mb=500.0,
        disk_usage_percent=65.0,
        network_bytes_sent=1000,
        network_bytes_recv=2000,
        open_file_descriptors=150,
        thread_count=25,
        process_count=75
    )
    
    assert usage.cpu_percent == 75.0
    assert usage.memory_percent == 80.0
    assert isinstance(usage.timestamp, datetime)
    
    # Test ConcurrencyMetrics
    concurrency = ConcurrencyMetrics(
        active_executions=5,
        queued_executions=2,
        max_concurrent_executions=10,
        total_executions_started=100,
        total_executions_completed=95,
        average_queue_time_ms=150.0,
        thread_pool_size=8,
        thread_pool_active=5,
        thread_pool_queue_size=3
    )
    
    assert concurrency.active_executions == 5
    assert concurrency.max_concurrent_executions == 10
    assert concurrency.average_queue_time_ms == 150.0


if __name__ == "__main__":
    pytest.main([__file__])