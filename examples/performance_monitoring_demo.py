#!/usr/bin/env python3
"""
Performance Monitoring Demo

This script demonstrates the performance monitoring and optimization features
of the hierarchical multi-agent system, including:
- Performance metrics collection
- Resource usage monitoring
- Concurrent execution optimization
- Prometheus metrics export
"""

import asyncio
import time
from datetime import datetime

from hierarchical_agents.performance_monitor import (
    initialize_performance_monitor,
    get_performance_monitor,
    monitor_execution,
    record_api_metrics,
    record_agent_metrics
)


async def simulate_agent_execution(agent_id: str, duration: float = 1.0):
    """Simulate an agent execution with performance monitoring."""
    execution_id = f"exec_{agent_id}_{int(time.time())}"
    
    print(f"Starting execution {execution_id} for agent {agent_id}")
    
    # Monitor the execution
    async with monitor_execution(execution_id, f"team_{agent_id}"):
        # Simulate some work
        await asyncio.sleep(duration)
        
        # Record agent metrics
        record_agent_metrics(agent_id, "success", duration)
        
        print(f"Completed execution {execution_id}")
        return f"Result from {agent_id}"


async def simulate_api_requests():
    """Simulate API requests with performance monitoring."""
    endpoints = [
        ("GET", "/api/v1/teams", 200),
        ("POST", "/api/v1/teams", 201),
        ("GET", "/api/v1/executions/123", 200),
        ("POST", "/api/v1/executions/123/execute", 202),
    ]
    
    for method, endpoint, status_code in endpoints:
        start_time = time.time()
        
        # Simulate API processing time
        await asyncio.sleep(0.1 + (hash(endpoint) % 100) / 1000)  # 0.1-0.2 seconds
        
        duration = time.time() - start_time
        record_api_metrics(method, endpoint, status_code, duration)
        
        print(f"{method} {endpoint} -> {status_code} ({duration:.3f}s)")


async def demonstrate_concurrent_execution():
    """Demonstrate concurrent execution with performance monitoring."""
    print("\n=== Concurrent Execution Demo ===")
    
    # Create multiple concurrent agent executions
    agents = [f"agent_{i:03d}" for i in range(8)]
    durations = [0.5, 1.0, 1.5, 0.8, 1.2, 0.7, 1.1, 0.9]
    
    print(f"Starting {len(agents)} concurrent executions...")
    start_time = time.time()
    
    # Execute agents concurrently
    tasks = [
        simulate_agent_execution(agent_id, duration)
        for agent_id, duration in zip(agents, durations)
    ]
    
    results = await asyncio.gather(*tasks)
    
    total_time = time.time() - start_time
    print(f"All executions completed in {total_time:.2f} seconds")
    print(f"Results: {len(results)} successful executions")


async def demonstrate_performance_monitoring():
    """Main demonstration of performance monitoring features."""
    print("=== Performance Monitoring Demo ===")
    print(f"Demo started at: {datetime.now()}")
    
    # Initialize performance monitor
    print("\n1. Initializing Performance Monitor...")
    monitor = initialize_performance_monitor(
        max_concurrent_executions=5,
        enable_prometheus=True,
        prometheus_port=8001,
        monitoring_interval=2.0
    )
    
    await monitor.initialize()
    print("Performance monitor initialized successfully")
    print(f"Prometheus metrics available at: http://localhost:8001/metrics")
    
    # Demonstrate API monitoring
    print("\n2. Simulating API Requests...")
    await simulate_api_requests()
    
    # Demonstrate concurrent execution
    await demonstrate_concurrent_execution()
    
    # Wait a bit for metrics to be collected
    print("\n3. Collecting Performance Data...")
    await asyncio.sleep(3)
    
    # Show performance summary
    print("\n4. Performance Summary:")
    summary = monitor.get_performance_summary()
    
    print(f"Uptime: {summary['uptime_seconds']:.1f} seconds")
    print(f"Prometheus enabled: {summary['prometheus_enabled']}")
    
    if 'concurrency' in summary:
        concurrency = summary['concurrency']
        print(f"Max concurrent executions: {concurrency['max_concurrent']}")
        print(f"Total completed executions: {concurrency['total_completed']}")
        print(f"Thread pool size: {concurrency['thread_pool_size']}")
        if concurrency['average_queue_time_ms'] > 0:
            print(f"Average queue time: {concurrency['average_queue_time_ms']:.1f}ms")
    
    if 'operations' in summary and summary['operations']:
        print("\nOperation Performance:")
        for op_name, stats in summary['operations'].items():
            print(f"  {op_name}: {stats['count']} calls, avg {stats['avg_ms']:.1f}ms")
    
    if 'resource_usage' in summary and summary['resource_usage']:
        resource = summary['resource_usage']
        if 'cpu' in resource:
            print(f"\nResource Usage:")
            print(f"  CPU: {resource['cpu']['current']:.1f}% (avg: {resource['cpu']['average']:.1f}%)")
        if 'memory' in resource:
            print(f"  Memory: {resource['memory']['current']:.1f}% (avg: {resource['memory']['average']:.1f}%)")
    
    # Show health status
    print("\n5. System Health Status:")
    health = monitor.get_health_status()
    print(f"Status: {health['status']}")
    print(f"CPU: {health['cpu_percent']:.1f}%")
    print(f"Memory: {health['memory_percent']:.1f}%")
    print(f"Active executions: {health['active_executions']}")
    
    if health['issues']:
        print("Issues:")
        for issue in health['issues']:
            print(f"  - {issue}")
    else:
        print("No issues detected")
    
    # Show Prometheus metrics sample
    if monitor.prometheus_exporter:
        print("\n6. Sample Prometheus Metrics:")
        metrics = monitor.prometheus_exporter.get_metrics()
        
        # Show first few lines of metrics
        lines = metrics.split('\n')[:20]
        for line in lines:
            if line.strip() and not line.startswith('#'):
                print(f"  {line}")
        
        print(f"  ... (total {len(metrics.split())} metrics)")
    
    # Cleanup
    print("\n7. Shutting down...")
    await monitor.shutdown()
    print("Performance monitor shut down successfully")


async def demonstrate_resource_monitoring():
    """Demonstrate resource monitoring features."""
    print("\n=== Resource Monitoring Demo ===")
    
    monitor = get_performance_monitor()
    if not monitor:
        print("No performance monitor available")
        return
    
    resource_monitor = monitor.resource_monitor
    
    # Show current resource usage
    current_usage = resource_monitor.get_current_usage()
    print(f"Current Resource Usage:")
    print(f"  CPU: {current_usage.cpu_percent:.1f}%")
    print(f"  Memory: {current_usage.memory_percent:.1f}% ({current_usage.memory_used_mb:.1f}MB used)")
    print(f"  Disk: {current_usage.disk_usage_percent:.1f}%")
    print(f"  Threads: {current_usage.thread_count}")
    print(f"  Open FDs: {current_usage.open_file_descriptors}")
    
    # Simulate some resource-intensive work
    print("\nSimulating resource-intensive work...")
    
    # CPU intensive task
    def cpu_intensive_work():
        """Simulate CPU intensive work."""
        result = 0
        for i in range(1000000):
            result += i ** 0.5
        return result
    
    # Memory intensive task
    def memory_intensive_work():
        """Simulate memory intensive work."""
        data = []
        for i in range(100000):
            data.append(f"data_item_{i}" * 10)
        return len(data)
    
    # Run intensive tasks
    start_time = time.time()
    cpu_result = cpu_intensive_work()
    memory_result = memory_intensive_work()
    work_duration = time.time() - start_time
    
    print(f"Intensive work completed in {work_duration:.2f} seconds")
    
    # Show resource usage after intensive work
    after_usage = resource_monitor.get_current_usage()
    print(f"\nResource Usage After Intensive Work:")
    print(f"  CPU: {after_usage.cpu_percent:.1f}%")
    print(f"  Memory: {after_usage.memory_percent:.1f}% ({after_usage.memory_used_mb:.1f}MB used)")
    
    # Clean up memory
    del cpu_result, memory_result
    import gc
    gc.collect()


if __name__ == "__main__":
    async def main():
        """Main demo function."""
        try:
            await demonstrate_performance_monitoring()
            await demonstrate_resource_monitoring()
            
        except KeyboardInterrupt:
            print("\nDemo interrupted by user")
        except Exception as e:
            print(f"Demo error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Ensure cleanup
            monitor = get_performance_monitor()
            if monitor:
                await monitor.shutdown()
    
    # Run the demo
    print("Starting Performance Monitoring Demo...")
    print("Press Ctrl+C to stop")
    
    asyncio.run(main())