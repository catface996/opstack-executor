"""
Main FastAPI application for hierarchical multi-agent system.

This module creates and configures the FastAPI application with all
necessary middleware, routers, and error handlers.
"""

import logging
import signal
import sys
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from .api.teams import router as teams_router
from .api.executions import router as executions_router
from .hierarchical_manager import HierarchicalManager
from .env_key_manager import EnvironmentKeyManager
from .performance_monitor import initialize_performance_monitor, get_performance_monitor
from .logging_monitor import get_logging_monitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Global manager instance
hierarchical_manager: HierarchicalManager = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    
    Handles startup and shutdown of the hierarchical manager and other resources.
    """
    global hierarchical_manager
    
    # Startup
    logger.info("Starting hierarchical multi-agent system...")
    try:
        # Initialize logging monitor
        logging_monitor = get_logging_monitor()
        
        # Initialize performance monitor
        performance_monitor = initialize_performance_monitor(
            max_concurrent_executions=10,
            enable_prometheus=True,
            prometheus_port=8001,
            monitoring_interval=5.0,
            logging_monitor=logging_monitor
        )
        await performance_monitor.initialize()
        
        # Initialize key manager
        key_manager = EnvironmentKeyManager()
        
        # Initialize hierarchical manager with graceful fallback
        hierarchical_manager = HierarchicalManager(key_manager=key_manager)
        
        try:
            await hierarchical_manager.initialize()
            logger.info("Hierarchical multi-agent system started successfully")
        except Exception as init_error:
            logger.warning(f"Failed to fully initialize hierarchical manager: {init_error}")
            logger.info("Starting in limited mode - some features may not be available")
            # Continue startup even if some components fail
            # This allows the API to start for development/testing
        
    except Exception as e:
        logger.error(f"Failed to start hierarchical multi-agent system: {e}")
        # For development, we'll continue even if initialization fails
        logger.warning("Starting in minimal mode - API endpoints will be available but functionality may be limited")
        hierarchical_manager = None
    
    yield
    
    # Shutdown
    logger.info("Shutting down hierarchical multi-agent system...")
    try:
        if hierarchical_manager:
            await hierarchical_manager.shutdown()
        
        # Shutdown performance monitor
        performance_monitor = get_performance_monitor()
        if performance_monitor:
            await performance_monitor.shutdown()
        
        logger.info("Hierarchical multi-agent system shut down successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title="Hierarchical Multi-Agent System API",
    description="API for creating and managing hierarchical teams of AI agents",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)


# Graceful shutdown handlers
def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging and performance monitoring middleware
@app.middleware("http")
async def log_and_monitor_requests(request: Request, call_next):
    """Log all HTTP requests and collect performance metrics."""
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url}")
    
    # Process request
    response = await call_next(request)
    
    # Calculate metrics
    process_time = time.time() - start_time
    
    # Log response
    logger.info(
        f"Response: {response.status_code} for {request.method} {request.url} "
        f"in {process_time:.3f}s"
    )
    
    # Record performance metrics
    from .performance_monitor import record_api_metrics
    endpoint = str(request.url.path)
    record_api_metrics(request.method, endpoint, response.status_code, process_time)
    
    return response


# Custom exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    logger.warning(f"Validation error for {request.url}: {exc}")
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "code": "VALIDATION_ERROR",
            "message": "请求数据验证失败",
            "detail": exc.errors()
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    logger.warning(f"HTTP exception for {request.url}: {exc.detail}")
    
    # If detail is already a dict (from our API), return it as-is
    if isinstance(exc.detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    
    # Otherwise, wrap in standard format
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "code": "HTTP_ERROR",
            "message": str(exc.detail),
            "detail": None
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unexpected error for {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "code": "INTERNAL_ERROR",
            "message": "服务器内部错误",
            "detail": "An unexpected error occurred"
        }
    )


# Include routers
app.include_router(teams_router)
app.include_router(executions_router)


# Root endpoint
@app.get("/", summary="API Root", description="Root endpoint with API information")
async def root():
    """Root endpoint providing API information."""
    return {
        "success": True,
        "code": "API_INFO",
        "message": "Hierarchical Multi-Agent System API",
        "data": {
            "name": "Hierarchical Multi-Agent System API",
            "version": "1.0.0",
            "description": "API for creating and managing hierarchical teams of AI agents",
            "docs_url": "/docs",
            "redoc_url": "/redoc",
            "openapi_url": "/openapi.json",
            "endpoints": {
                "teams": "/api/v1/hierarchical-teams",
                "executions": "/api/v1/executions",
                "health": "/api/v1/teams/health"
            }
        }
    }


# Health check endpoint
@app.get("/health", summary="API Health Check", description="Check API health status")
async def health_check():
    """General API health check."""
    global hierarchical_manager
    
    manager_status = "not_initialized"
    manager_details = {}
    
    if hierarchical_manager:
        try:
            stats = await hierarchical_manager.get_manager_stats()
            manager_status = "healthy" if stats.get("initialized") else "unhealthy"
            manager_details = stats
        except Exception as e:
            manager_status = "unhealthy"
            manager_details = {"error": str(e)}
    
    # Check performance monitor status
    performance_monitor = get_performance_monitor()
    performance_status = "not_initialized"
    performance_details = {}
    
    if performance_monitor:
        try:
            health_status = performance_monitor.get_health_status()
            performance_status = health_status["status"]
            performance_details = health_status
        except Exception as e:
            performance_status = "unhealthy"
            performance_details = {"error": str(e)}
    
    api_status = "healthy"
    overall_status = "healthy"
    
    # Determine overall status
    if manager_status == "unhealthy" or performance_status == "unhealthy":
        overall_status = "unhealthy"
    elif manager_status == "degraded" or performance_status == "degraded":
        overall_status = "degraded"
    
    return {
        "success": True,
        "code": "HEALTHY" if overall_status == "healthy" else "DEGRADED" if overall_status == "degraded" else "UNHEALTHY",
        "message": f"API is {overall_status}",
        "data": {
            "status": overall_status,
            "components": {
                "api": api_status,
                "hierarchical_manager": {
                    "status": manager_status,
                    "details": manager_details
                },
                "performance_monitor": {
                    "status": performance_status,
                    "details": performance_details
                }
            },
            "version": "1.0.0",
            "timestamp": time.time()
        }
    }


# Performance metrics endpoint
@app.get("/metrics", summary="Performance Metrics", description="Get performance metrics in Prometheus format")
async def get_metrics():
    """Get performance metrics in Prometheus format."""
    performance_monitor = get_performance_monitor()
    
    if not performance_monitor or not performance_monitor.prometheus_exporter:
        raise HTTPException(
            status_code=503,
            detail={
                "success": False,
                "code": "METRICS_UNAVAILABLE",
                "message": "Performance monitoring or Prometheus export is not available",
                "detail": "Install prometheus-client package to enable metrics export"
            }
        )
    
    try:
        metrics_data = performance_monitor.prometheus_exporter.get_metrics()
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            content=metrics_data,
            media_type="text/plain; version=0.0.4; charset=utf-8"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "code": "METRICS_ERROR",
                "message": "Failed to generate metrics",
                "detail": str(e)
            }
        )


# Performance summary endpoint
@app.get("/api/v1/performance", summary="Performance Summary", description="Get comprehensive performance summary")
async def get_performance_summary():
    """Get comprehensive performance summary."""
    performance_monitor = get_performance_monitor()
    
    if not performance_monitor:
        raise HTTPException(
            status_code=503,
            detail={
                "success": False,
                "code": "PERFORMANCE_MONITOR_UNAVAILABLE",
                "message": "Performance monitoring is not available",
                "detail": None
            }
        )
    
    try:
        summary = performance_monitor.get_performance_summary()
        return {
            "success": True,
            "code": "PERFORMANCE_SUMMARY",
            "message": "Performance summary retrieved successfully",
            "data": summary
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "code": "PERFORMANCE_ERROR",
                "message": "Failed to get performance summary",
                "detail": str(e)
            }
        )


if __name__ == "__main__":
    import uvicorn
    
    # This allows running the app directly with: python -m hierarchical_agents.main
    uvicorn.run(
        "hierarchical_agents.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

# DEPLOYMENT INSTRUCTIONS:
#
# From project root directory:
# 
# Production deployment:
#   uvicorn hierarchical_agents.main:app --host 0.0.0.0 --port 8000 --app-dir src
#
# Development with auto-reload:
#   uvicorn hierarchical_agents.main:app --host 0.0.0.0 --port 8000 --app-dir src --reload
#
# Direct Python execution:
#   python -m hierarchical_agents.main  (from project root with src in PYTHONPATH)
#   python src/hierarchical_agents/main.py  (direct execution)