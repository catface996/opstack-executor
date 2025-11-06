"""
Performance monitoring and optimization module for hierarchical multi-agent system.

This module provides:
- Performance metrics collection and exposure
- Concurrent execution optimization
- Resource usage monitoring
- Prometheus integration for external monitoring
- Performance alerting and optimization recommendations
"""

import asyncio
import gc
import os
import psutil
import resource
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable, Awaitable
from collections import defaultdict, deque
import weakref

try:
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary, Info,
        CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST,
        start_http_server, push_to_gateway
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

from .logging_monitor import LoggingMonitor, LogLevel


@dataclass
class ResourceUsage:
    """System resource usage metrics."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    network_bytes_sent: int
    network_bytes_recv: int
    open_file_descriptors: int
    thread_count: int
    process_count: int


@dataclass
class PerformanceMetrics:
    """Performance metrics for operations."""
    operation_name: str
    total_calls: int
    successful_calls: int
    failed_calls: int
    average_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    p50_duration_ms: float
    p95_duration_ms: float
    p99_duration_ms: float
    last_call_timestamp: datetime
    error_rate: float
    throughput_per_second: float


@dataclass
class ConcurrencyMetrics:
    """Concurrency and execution metrics."""
    active_executions: int
    queued_executions: int
    max_concurrent_executions: int
    total_executions_started: int
    total_executions_completed: int
    average_queue_time_ms: float
    thread_pool_size: int
    thread_pool_active: int
    thread_pool_queue_size: int


class PerformanceOptimizer:
    """Performance optimization engine."""
    
    def __init__(self, max_concurrent_executions: int = 10):
        """Initialize performance optimizer."""
        self.max_concurrent_executions = max_concurrent_executions
        self.execution_semaphore = asyncio.Semaphore(max_concurrent_executions)
        self.thread_pool = ThreadPoolExecutor(
            max_workers=max_concurrent_executions,
            thread_name_prefix="hierarchical_agent"
        )
        self.active_executions: Dict[str, datetime] = {}
        self.execution_queue: deque = deque()
        self._lock = threading.Lock()
        
        # Performance tracking
        self.execution_times: Dict[str, List[float]] = defaultdict(list)
        self.queue_times: List[float] = []
        self.resource_history: deque = deque(maxlen=1000)
        
        # Weak references to avoid memory leaks
        self.execution_callbacks: weakref.WeakSet = weakref.WeakSet()
    
    @asynccontextmanager
    async def managed_execution(self, execution_id: str):
        """Context manager for managed concurrent execution."""
        queue_start = time.time()
        
        # Wait for available slot
        async with self.execution_semaphore:
            queue_time = (time.time() - queue_start) * 1000
            self.queue_times.append(queue_time)
            
            # Keep only recent queue times
            if len(self.queue_times) > 1000:
                self.queue_times = self.queue_times[-1000:]
            
            execution_start = time.time()
            
            with self._lock:
                self.active_executions[execution_id] = datetime.now()
            
            try:
                yield
                
                # Record successful execution
                execution_time = (time.time() - execution_start) * 1000
                self.execution_times[execution_id].append(execution_time)
                
            finally:
                with self._lock:
                    self.active_executions.pop(execution_id, None)
    
    def optimize_thread_pool_size(self) -> int:
        """Dynamically optimize thread pool size based on performance."""
        current_size = self.thread_pool._max_workers
        
        # Get recent performance metrics
        if len(self.queue_times) < 10:
            return current_size
        
        recent_queue_times = self.queue_times[-100:]
        avg_queue_time = sum(recent_queue_times) / len(recent_queue_times)
        
        # If average queue time is high, consider increasing pool size
        if avg_queue_time > 1000:  # 1 second
            new_size = min(current_size + 2, self.max_concurrent_executions * 2)
        elif avg_queue_time < 100:  # 100ms
            new_size = max(current_size - 1, self.max_concurrent_executions // 2)
        else:
            new_size = current_size
        
        if new_size != current_size:
            # Create new thread pool with optimized size
            old_pool = self.thread_pool
            self.thread_pool = ThreadPoolExecutor(
                max_workers=new_size,
                thread_name_prefix="hierarchical_agent"
            )
            
            # Schedule old pool shutdown
            def shutdown_old_pool():
                old_pool.shutdown(wait=False)
            
            threading.Timer(5.0, shutdown_old_pool).start()
        
        return new_size
    
    def get_concurrency_metrics(self) -> ConcurrencyMetrics:
        """Get current concurrency metrics."""
        with self._lock:
            active_count = len(self.active_executions)
        
        queue_size = len(self.execution_queue)
        avg_queue_time = sum(self.queue_times) / len(self.queue_times) if self.queue_times else 0
        
        return ConcurrencyMetrics(
            active_executions=active_count,
            queued_executions=queue_size,
            max_concurrent_executions=self.max_concurrent_executions,
            total_executions_started=len(self.execution_times),
            total_executions_completed=sum(len(times) for times in self.execution_times.values()),
            average_queue_time_ms=avg_queue_time,
            thread_pool_size=self.thread_pool._max_workers,
            thread_pool_active=self.thread_pool._threads.__len__() if hasattr(self.thread_pool, '_threads') else 0,
            thread_pool_queue_size=self.thread_pool._work_queue.qsize() if hasattr(self.thread_pool, '_work_queue') else 0
        )


class ResourceMonitor:
    """System resource monitoring."""
    
    def __init__(self, monitoring_interval: float = 5.0):
        """Initialize resource monitor."""
        self.monitoring_interval = monitoring_interval
        self.process = psutil.Process()
        self.resource_history: deque = deque(maxlen=1000)
        self.monitoring_task: Optional[asyncio.Task] = None
        self.is_monitoring = False
        
        # Resource thresholds for alerts
        self.cpu_threshold = 80.0  # %
        self.memory_threshold = 85.0  # %
        self.disk_threshold = 90.0  # %
        
        # Alert callbacks
        self.alert_callbacks: List[Callable[[str, ResourceUsage], None]] = []
    
    async def start_monitoring(self):
        """Start resource monitoring."""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
    
    async def stop_monitoring(self):
        """Stop resource monitoring."""
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
    
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                usage = self._collect_resource_usage()
                self.resource_history.append(usage)
                
                # Check for alerts
                self._check_resource_alerts(usage)
                
                await asyncio.sleep(self.monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue monitoring
                print(f"Error in resource monitoring: {e}")
                await asyncio.sleep(self.monitoring_interval)
    
    def _collect_resource_usage(self) -> ResourceUsage:
        """Collect current resource usage."""
        # CPU usage
        cpu_percent = self.process.cpu_percent()
        
        # Memory usage
        memory_info = self.process.memory_info()
        system_memory = psutil.virtual_memory()
        memory_percent = (memory_info.rss / system_memory.total) * 100
        memory_used_mb = memory_info.rss / (1024 * 1024)
        memory_available_mb = system_memory.available / (1024 * 1024)
        
        # Disk usage
        disk_usage = psutil.disk_usage('/')
        disk_usage_percent = (disk_usage.used / disk_usage.total) * 100
        
        # Network usage
        network_io = psutil.net_io_counters()
        
        # Process info
        try:
            open_fds = self.process.num_fds() if hasattr(self.process, 'num_fds') else 0
        except (psutil.AccessDenied, AttributeError):
            open_fds = 0
        
        thread_count = self.process.num_threads()
        process_count = len(psutil.pids())
        
        return ResourceUsage(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_mb=memory_used_mb,
            memory_available_mb=memory_available_mb,
            disk_usage_percent=disk_usage_percent,
            network_bytes_sent=network_io.bytes_sent,
            network_bytes_recv=network_io.bytes_recv,
            open_file_descriptors=open_fds,
            thread_count=thread_count,
            process_count=process_count
        )
    
    def _check_resource_alerts(self, usage: ResourceUsage):
        """Check for resource usage alerts."""
        alerts = []
        
        if usage.cpu_percent > self.cpu_threshold:
            alerts.append(f"High CPU usage: {usage.cpu_percent:.1f}%")
        
        if usage.memory_percent > self.memory_threshold:
            alerts.append(f"High memory usage: {usage.memory_percent:.1f}%")
        
        if usage.disk_usage_percent > self.disk_threshold:
            alerts.append(f"High disk usage: {usage.disk_usage_percent:.1f}%")
        
        # Trigger alert callbacks
        for alert in alerts:
            for callback in self.alert_callbacks:
                try:
                    callback(alert, usage)
                except Exception as e:
                    print(f"Error in alert callback: {e}")
    
    def add_alert_callback(self, callback: Callable[[str, ResourceUsage], None]):
        """Add alert callback."""
        self.alert_callbacks.append(callback)
    
    def get_current_usage(self) -> ResourceUsage:
        """Get current resource usage."""
        return self._collect_resource_usage()
    
    def get_usage_history(self, minutes: int = 60) -> List[ResourceUsage]:
        """Get resource usage history for the last N minutes."""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [usage for usage in self.resource_history if usage.timestamp >= cutoff_time]
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get resource usage statistics."""
        if not self.resource_history:
            return {}
        
        cpu_values = [u.cpu_percent for u in self.resource_history]
        memory_values = [u.memory_percent for u in self.resource_history]
        
        return {
            "cpu": {
                "current": cpu_values[-1] if cpu_values else 0,
                "average": sum(cpu_values) / len(cpu_values),
                "max": max(cpu_values),
                "min": min(cpu_values)
            },
            "memory": {
                "current": memory_values[-1] if memory_values else 0,
                "average": sum(memory_values) / len(memory_values),
                "max": max(memory_values),
                "min": min(memory_values)
            },
            "samples": len(self.resource_history)
        }


class PrometheusExporter:
    """Prometheus metrics exporter."""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """Initialize Prometheus exporter."""
        if not PROMETHEUS_AVAILABLE:
            raise ImportError("prometheus_client is not available. Install with: pip install prometheus-client")
        
        self.registry = registry or CollectorRegistry()
        self._setup_metrics()
        self.http_server_port: Optional[int] = None
    
    def _setup_metrics(self):
        """Setup Prometheus metrics."""
        # Execution metrics
        self.execution_counter = Counter(
            'hierarchical_agents_executions_total',
            'Total number of executions',
            ['status', 'team_id'],
            registry=self.registry
        )
        
        self.execution_duration = Histogram(
            'hierarchical_agents_execution_duration_seconds',
            'Execution duration in seconds',
            ['operation', 'team_id'],
            registry=self.registry
        )
        
        self.active_executions = Gauge(
            'hierarchical_agents_active_executions',
            'Number of currently active executions',
            registry=self.registry
        )
        
        self.queue_size = Gauge(
            'hierarchical_agents_queue_size',
            'Number of queued executions',
            registry=self.registry
        )
        
        # Agent metrics
        self.agent_invocations = Counter(
            'hierarchical_agents_agent_invocations_total',
            'Total agent invocations',
            ['agent_id', 'status'],
            registry=self.registry
        )
        
        self.agent_duration = Histogram(
            'hierarchical_agents_agent_duration_seconds',
            'Agent execution duration in seconds',
            ['agent_id'],
            registry=self.registry
        )
        
        # API metrics
        self.api_requests = Counter(
            'hierarchical_agents_api_requests_total',
            'Total API requests',
            ['method', 'endpoint', 'status_code'],
            registry=self.registry
        )
        
        self.api_duration = Histogram(
            'hierarchical_agents_api_duration_seconds',
            'API request duration in seconds',
            ['method', 'endpoint'],
            registry=self.registry
        )
        
        # Resource metrics
        self.cpu_usage = Gauge(
            'hierarchical_agents_cpu_usage_percent',
            'CPU usage percentage',
            registry=self.registry
        )
        
        self.memory_usage = Gauge(
            'hierarchical_agents_memory_usage_percent',
            'Memory usage percentage',
            registry=self.registry
        )
        
        self.memory_used = Gauge(
            'hierarchical_agents_memory_used_bytes',
            'Memory used in bytes',
            registry=self.registry
        )
        
        self.thread_count = Gauge(
            'hierarchical_agents_threads_total',
            'Number of threads',
            registry=self.registry
        )
        
        # Error metrics
        self.error_counter = Counter(
            'hierarchical_agents_errors_total',
            'Total number of errors',
            ['error_type', 'component'],
            registry=self.registry
        )
        
        # System info
        self.system_info = Info(
            'hierarchical_agents_system_info',
            'System information',
            registry=self.registry
        )
        
        # Set system info
        self.system_info.info({
            'version': '0.1.0',
            'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
            'platform': os.name,
            'prometheus_available': str(PROMETHEUS_AVAILABLE)
        })
    
    def record_execution(self, status: str, team_id: str, duration_seconds: float):
        """Record execution metrics."""
        self.execution_counter.labels(status=status, team_id=team_id).inc()
        self.execution_duration.labels(operation='execution', team_id=team_id).observe(duration_seconds)
    
    def record_agent_invocation(self, agent_id: str, status: str, duration_seconds: float):
        """Record agent invocation metrics."""
        self.agent_invocations.labels(agent_id=agent_id, status=status).inc()
        self.agent_duration.labels(agent_id=agent_id).observe(duration_seconds)
    
    def record_api_request(self, method: str, endpoint: str, status_code: int, duration_seconds: float):
        """Record API request metrics."""
        self.api_requests.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()
        self.api_duration.labels(method=method, endpoint=endpoint).observe(duration_seconds)
    
    def update_resource_metrics(self, usage: ResourceUsage):
        """Update resource usage metrics."""
        self.cpu_usage.set(usage.cpu_percent)
        self.memory_usage.set(usage.memory_percent)
        self.memory_used.set(usage.memory_used_mb * 1024 * 1024)  # Convert to bytes
        self.thread_count.set(usage.thread_count)
    
    def update_concurrency_metrics(self, metrics: ConcurrencyMetrics):
        """Update concurrency metrics."""
        self.active_executions.set(metrics.active_executions)
        self.queue_size.set(metrics.queued_executions)
    
    def record_error(self, error_type: str, component: str):
        """Record error metrics."""
        self.error_counter.labels(error_type=error_type, component=component).inc()
    
    def start_http_server(self, port: int = 8001):
        """Start Prometheus HTTP server."""
        if self.http_server_port is not None:
            return  # Already started
        
        start_http_server(port, registry=self.registry)
        self.http_server_port = port
    
    def get_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        return generate_latest(self.registry).decode('utf-8')
    
    def push_to_gateway(self, gateway_url: str, job_name: str = 'hierarchical_agents'):
        """Push metrics to Prometheus pushgateway."""
        push_to_gateway(gateway_url, job=job_name, registry=self.registry)


class PerformanceMonitor:
    """
    Main performance monitoring system.
    
    Integrates resource monitoring, performance optimization, and metrics export.
    """
    
    def __init__(
        self,
        max_concurrent_executions: int = 10,
        enable_prometheus: bool = True,
        prometheus_port: int = 8001,
        monitoring_interval: float = 5.0,
        logging_monitor: Optional[LoggingMonitor] = None
    ):
        """Initialize performance monitor."""
        self.max_concurrent_executions = max_concurrent_executions
        self.enable_prometheus = enable_prometheus and PROMETHEUS_AVAILABLE
        self.prometheus_port = prometheus_port
        self.monitoring_interval = monitoring_interval
        self.logging_monitor = logging_monitor
        
        # Initialize components
        self.optimizer = PerformanceOptimizer(max_concurrent_executions)
        self.resource_monitor = ResourceMonitor(monitoring_interval)
        
        # Initialize Prometheus exporter if available
        self.prometheus_exporter: Optional[PrometheusExporter] = None
        if self.enable_prometheus:
            try:
                self.prometheus_exporter = PrometheusExporter()
            except ImportError:
                self.enable_prometheus = False
                if self.logging_monitor:
                    self.logging_monitor.log_system_event(
                        "Prometheus client not available, metrics export disabled",
                        LogLevel.WARNING
                    )
        
        # Performance tracking
        self.operation_metrics: Dict[str, List[float]] = defaultdict(list)
        self.start_time = datetime.now()
        
        # Setup resource alert callback
        self.resource_monitor.add_alert_callback(self._handle_resource_alert)
    
    async def initialize(self):
        """Initialize the performance monitor."""
        # Start resource monitoring
        await self.resource_monitor.start_monitoring()
        
        # Start Prometheus HTTP server
        if self.prometheus_exporter:
            try:
                self.prometheus_exporter.start_http_server(self.prometheus_port)
                if self.logging_monitor:
                    self.logging_monitor.log_system_event(
                        f"Prometheus metrics server started on port {self.prometheus_port}",
                        LogLevel.INFO
                    )
            except Exception as e:
                if self.logging_monitor:
                    self.logging_monitor.log_system_event(
                        f"Failed to start Prometheus server: {e}",
                        LogLevel.ERROR
                    )
        
        # Start periodic optimization
        asyncio.create_task(self._optimization_loop())
        
        if self.logging_monitor:
            self.logging_monitor.log_system_event(
                "Performance monitor initialized",
                LogLevel.INFO,
                max_concurrent_executions=self.max_concurrent_executions,
                prometheus_enabled=self.enable_prometheus
            )
    
    async def shutdown(self):
        """Shutdown the performance monitor."""
        await self.resource_monitor.stop_monitoring()
        self.optimizer.thread_pool.shutdown(wait=True)
        
        if self.logging_monitor:
            self.logging_monitor.log_system_event(
                "Performance monitor shutdown",
                LogLevel.INFO
            )
    
    @asynccontextmanager
    async def monitor_execution(self, execution_id: str, team_id: str = "unknown"):
        """Context manager for monitoring execution performance."""
        start_time = time.time()
        
        try:
            async with self.optimizer.managed_execution(execution_id):
                yield
            
            # Record successful execution
            duration = time.time() - start_time
            self._record_execution_metrics(execution_id, team_id, "success", duration)
            
        except Exception as e:
            # Record failed execution
            duration = time.time() - start_time
            self._record_execution_metrics(execution_id, team_id, "failure", duration)
            
            if self.prometheus_exporter:
                self.prometheus_exporter.record_error(
                    error_type=type(e).__name__,
                    component="execution"
                )
            
            raise
    
    def _record_execution_metrics(self, execution_id: str, team_id: str, status: str, duration: float):
        """Record execution metrics."""
        self.operation_metrics[execution_id].append(duration * 1000)  # Store in ms
        
        if self.prometheus_exporter:
            self.prometheus_exporter.record_execution(status, team_id, duration)
        
        if self.logging_monitor:
            self.logging_monitor.log_execution_event(
                f"Execution {status}: {execution_id}",
                execution_id=execution_id,
                team_id=team_id,
                duration_ms=duration * 1000,
                status=status
            )
    
    async def _optimization_loop(self):
        """Periodic optimization loop."""
        while True:
            try:
                # Optimize thread pool size
                new_size = self.optimizer.optimize_thread_pool_size()
                
                # Update metrics
                if self.prometheus_exporter:
                    # Update resource metrics
                    current_usage = self.resource_monitor.get_current_usage()
                    self.prometheus_exporter.update_resource_metrics(current_usage)
                    
                    # Update concurrency metrics
                    concurrency_metrics = self.optimizer.get_concurrency_metrics()
                    self.prometheus_exporter.update_concurrency_metrics(concurrency_metrics)
                
                await asyncio.sleep(30)  # Optimize every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.logging_monitor:
                    self.logging_monitor.log_system_event(
                        f"Error in optimization loop: {e}",
                        LogLevel.ERROR
                    )
                await asyncio.sleep(30)
    
    def _handle_resource_alert(self, alert: str, usage: ResourceUsage):
        """Handle resource usage alerts."""
        if self.logging_monitor:
            self.logging_monitor.log_system_event(
                f"Resource alert: {alert}",
                LogLevel.WARNING,
                cpu_percent=usage.cpu_percent,
                memory_percent=usage.memory_percent,
                disk_usage_percent=usage.disk_usage_percent
            )
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        # Resource stats
        resource_stats = self.resource_monitor.get_usage_stats()
        
        # Concurrency metrics
        concurrency_metrics = self.optimizer.get_concurrency_metrics()
        
        # Operation performance
        operation_stats = {}
        for op_name, durations in self.operation_metrics.items():
            if durations:
                sorted_durations = sorted(durations)
                count = len(sorted_durations)
                operation_stats[op_name] = {
                    "count": count,
                    "avg_ms": sum(sorted_durations) / count,
                    "min_ms": sorted_durations[0],
                    "max_ms": sorted_durations[-1],
                    "p50_ms": sorted_durations[count // 2],
                    "p95_ms": sorted_durations[int(count * 0.95)] if count > 20 else sorted_durations[-1]
                }
        
        uptime_seconds = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "uptime_seconds": uptime_seconds,
            "resource_usage": resource_stats,
            "concurrency": {
                "active_executions": concurrency_metrics.active_executions,
                "max_concurrent": concurrency_metrics.max_concurrent_executions,
                "total_completed": concurrency_metrics.total_executions_completed,
                "average_queue_time_ms": concurrency_metrics.average_queue_time_ms,
                "thread_pool_size": concurrency_metrics.thread_pool_size
            },
            "operations": operation_stats,
            "prometheus_enabled": self.enable_prometheus,
            "prometheus_port": self.prometheus_port if self.enable_prometheus else None
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status."""
        current_usage = self.resource_monitor.get_current_usage()
        concurrency_metrics = self.optimizer.get_concurrency_metrics()
        
        # Determine health status
        health_issues = []
        
        if current_usage.cpu_percent > 90:
            health_issues.append("High CPU usage")
        
        if current_usage.memory_percent > 90:
            health_issues.append("High memory usage")
        
        if concurrency_metrics.active_executions >= self.max_concurrent_executions:
            health_issues.append("At maximum concurrency limit")
        
        if concurrency_metrics.average_queue_time_ms > 5000:  # 5 seconds
            health_issues.append("High queue times")
        
        status = "healthy" if not health_issues else "degraded" if len(health_issues) < 3 else "unhealthy"
        
        return {
            "status": status,
            "issues": health_issues,
            "cpu_percent": current_usage.cpu_percent,
            "memory_percent": current_usage.memory_percent,
            "active_executions": concurrency_metrics.active_executions,
            "queue_time_ms": concurrency_metrics.average_queue_time_ms,
            "timestamp": datetime.now().isoformat()
        }


# Global performance monitor instance
_global_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> Optional[PerformanceMonitor]:
    """Get the global performance monitor instance."""
    return _global_performance_monitor


def initialize_performance_monitor(
    max_concurrent_executions: int = 10,
    enable_prometheus: bool = True,
    prometheus_port: int = 8001,
    monitoring_interval: float = 5.0,
    logging_monitor: Optional[LoggingMonitor] = None
) -> PerformanceMonitor:
    """Initialize the global performance monitor."""
    global _global_performance_monitor
    _global_performance_monitor = PerformanceMonitor(
        max_concurrent_executions=max_concurrent_executions,
        enable_prometheus=enable_prometheus,
        prometheus_port=prometheus_port,
        monitoring_interval=monitoring_interval,
        logging_monitor=logging_monitor
    )
    return _global_performance_monitor


# Convenience functions
def monitor_execution(execution_id: str, team_id: str = "unknown"):
    """Context manager for monitoring execution performance."""
    monitor = get_performance_monitor()
    if monitor:
        return monitor.monitor_execution(execution_id, team_id)
    else:
        # Return a no-op context manager if no monitor is available
        from contextlib import nullcontext
        return nullcontext()


def record_api_metrics(method: str, endpoint: str, status_code: int, duration_seconds: float):
    """Record API request metrics."""
    monitor = get_performance_monitor()
    if monitor and monitor.prometheus_exporter:
        monitor.prometheus_exporter.record_api_request(method, endpoint, status_code, duration_seconds)


def record_agent_metrics(agent_id: str, status: str, duration_seconds: float):
    """Record agent execution metrics."""
    monitor = get_performance_monitor()
    if monitor and monitor.prometheus_exporter:
        monitor.prometheus_exporter.record_agent_invocation(agent_id, status, duration_seconds)