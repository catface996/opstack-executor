"""
Execution control API endpoints for hierarchical multi-agent system.

This module provides HTTP endpoints for controlling and monitoring hierarchical team executions.
"""

import logging
import uuid
import json
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status, Path, Body
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.responses import Response

from ..hierarchical_manager import HierarchicalManager, HierarchicalManagerError
from ..execution_engine import ExecutionEngine
from ..state_manager import StateManager
from ..event_manager import EventManager
from ..output_formatter import OutputFormatter, OutputFormatterError
from ..data_models import (
    ExecutionConfig,
    ExecutionStartResponse,
    APIResponse,
    ExecutionStatus,
    StandardizedOutput,
    ExecutionEvent,
    ExecutionResultsResponse,
    FormatRequest,
    OutputTemplate,
    ExtractionRules
)

logger = logging.getLogger(__name__)

# Create router for execution endpoints
router = APIRouter(prefix="/api/v1", tags=["executions"])

# Global instances (will be properly initialized in main app)
hierarchical_manager = HierarchicalManager()
state_manager = StateManager()
event_manager = EventManager()
output_formatter = OutputFormatter()


# Health check endpoint for the executions API (must be before parameterized routes)
@router.get(
    "/executions/health",
    response_model=Dict[str, Any],
    summary="Executions API Health Check",
    description="Check the health status of the executions API",
    responses={
        200: {
            "description": "API is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "code": "HEALTHY",
                        "message": "Executions API is healthy",
                        "data": {
                            "status": "healthy",
                            "timestamp": "2024-01-15T10:30:00Z",
                            "version": "1.0.0"
                        }
                    }
                }
            }
        }
    }
)
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for the executions API.
    
    Returns:
        Dict containing health status information
    """
    return {
        "success": True,
        "code": "HEALTHY",
        "message": "Executions API is healthy",
        "data": {
            "status": "healthy",
            "timestamp": datetime.now().isoformat() + "Z",
            "version": "1.0.0",
            "components": {
                "hierarchical_manager": "initialized",
                "state_manager": "initialized"
            }
        }
    }


@router.post(
    "/hierarchical-teams/{team_id}/execute",
    response_model=ExecutionStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Execute Hierarchical Team",
    description="Trigger execution of a hierarchical team",
    responses={
        202: {
            "description": "Execution started successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "code": "EXECUTION_STARTED",
                        "message": "团队执行已启动",
                        "data": {
                            "execution_id": "exec_987654321",
                            "team_id": "ht_123456789",
                            "status": "started",
                            "started_at": "2024-01-15T10:35:00Z",
                            "stream_url": "/api/v1/executions/exec_987654321/stream",
                            "estimated_duration": 1800
                        }
                    }
                }
            }
        },
        400: {
            "description": "Invalid request or team configuration",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "code": "INVALID_REQUEST",
                        "message": "请求无效",
                        "detail": "Invalid execution configuration"
                    }
                }
            }
        },
        404: {
            "description": "Team not found",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "code": "TEAM_NOT_FOUND",
                        "message": "团队未找到",
                        "detail": "Team with ID 'ht_123456789' not found"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "code": "EXECUTION_ERROR",
                        "message": "执行启动失败",
                        "detail": "Failed to start execution"
                    }
                }
            }
        }
    }
)
async def execute_hierarchical_team(
    team_id: str = Path(..., description="Team ID to execute"),
    execution_request: Dict[str, Any] = Body(
        default={"execution_config": {}},
        description="Execution configuration",
        example={
            "execution_config": {
                "stream_events": True,
                "save_intermediate_results": True,
                "max_parallel_teams": 2
            }
        }
    )
) -> ExecutionStartResponse:
    """
    Execute a hierarchical team.
    
    This endpoint triggers the execution of a hierarchical team and returns
    immediately with execution details. The actual execution runs asynchronously.
    
    Args:
        team_id: The unique team identifier
        execution_request: Request body containing execution configuration
        
    Returns:
        ExecutionStartResponse: Response containing execution start details
        
    Raises:
        HTTPException: If team is not found or execution fails to start
    """
    try:
        logger.info(f"Received execution request for team: {team_id}")
        
        # Validate team_id format
        if not team_id.startswith("ht_") or len(team_id) != 12:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "code": "TEAM_NOT_FOUND",
                    "message": "团队未找到",
                    "detail": f"Invalid team ID format: {team_id}"
                }
            )
        
        # Extract execution configuration
        execution_config_data = execution_request.get("execution_config", {})
        
        # Validate and create execution config
        try:
            execution_config = ExecutionConfig(**execution_config_data)
        except Exception as e:
            logger.warning(f"Invalid execution configuration: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "code": "INVALID_REQUEST",
                    "message": "请求无效",
                    "detail": f"Invalid execution configuration: {str(e)}"
                }
            )
        
        # For now, create a mock team configuration since we don't have persistent storage
        # In a real implementation, this would fetch the team configuration from storage
        mock_team_config = _create_mock_team_config(team_id)
        
        # Build the hierarchical team
        try:
            built_team = hierarchical_manager.build_hierarchy(mock_team_config)
        except HierarchicalManagerError as e:
            logger.error(f"Failed to build team {team_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "code": "TEAM_BUILD_ERROR",
                    "message": "团队构建失败",
                    "detail": str(e)
                }
            )
        
        # Generate unique execution ID
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        
        # Start execution asynchronously (fire and forget)
        try:
            # Initialize hierarchical manager if not already done
            if not hierarchical_manager._initialized:
                await hierarchical_manager.initialize()
            
            # Start execution in background
            import asyncio
            asyncio.create_task(_execute_team_async(
                hierarchical_manager, 
                built_team, 
                execution_id, 
                execution_config
            ))
            
        except Exception as e:
            logger.error(f"Failed to start execution for team {team_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "success": False,
                    "code": "EXECUTION_ERROR",
                    "message": "执行启动失败",
                    "detail": "Failed to start execution"
                }
            )
        
        # Create response data
        response_data = {
            "execution_id": execution_id,
            "team_id": team_id,
            "status": "started",
            "started_at": datetime.now().isoformat() + "Z",
            "stream_url": f"/api/v1/executions/{execution_id}/stream",
            "estimated_duration": 1800  # 30 minutes estimate
        }
        
        logger.info(f"Successfully started execution {execution_id} for team {team_id}")
        
        return ExecutionStartResponse(
            success=True,
            code="EXECUTION_STARTED",
            message="团队执行已启动",
            data=response_data
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Handle any unexpected errors
        logger.error(f"Unexpected error in execute_hierarchical_team: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误",
                "detail": "An unexpected error occurred"
            }
        )


@router.get(
    "/executions/{execution_id}",
    response_model=Dict[str, Any],
    summary="Get Execution Status",
    description="Retrieve the current status and details of an execution",
    responses={
        200: {
            "description": "Execution status retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "code": "EXECUTION_FOUND",
                        "message": "执行状态获取成功",
                        "data": {
                            "execution_id": "exec_987654321",
                            "team_id": "ht_123456789",
                            "status": "running",
                            "started_at": "2024-01-15T10:35:00Z",
                            "progress": 45,
                            "current_team": "team_a7b9c2d4e5f6",
                            "teams_completed": 1,
                            "total_teams": 2,
                            "estimated_completion": "2024-01-15T11:05:00Z"
                        }
                    }
                }
            }
        },
        404: {
            "description": "Execution not found",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "code": "EXECUTION_NOT_FOUND",
                        "message": "执行未找到",
                        "detail": "Execution with ID 'exec_987654321' not found"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "code": "INTERNAL_ERROR",
                        "message": "服务器内部错误",
                        "detail": "Failed to retrieve execution status"
                    }
                }
            }
        }
    }
)
async def get_execution_status(
    execution_id: str = Path(..., description="Execution ID to query")
) -> Dict[str, Any]:
    """
    Get the current status and details of an execution.
    
    Args:
        execution_id: The unique execution identifier
        
    Returns:
        Dict containing execution status and details
        
    Raises:
        HTTPException: If execution is not found
    """
    try:
        logger.info(f"Retrieving execution status for ID: {execution_id}")
        
        # Validate execution_id format
        if not execution_id.startswith("exec_") or len(execution_id) != 17:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "code": "EXECUTION_NOT_FOUND",
                    "message": "执行未找到",
                    "detail": f"Invalid execution ID format: {execution_id}"
                }
            )
        
        # Initialize state manager if needed
        if not hasattr(state_manager, '_redis') or state_manager._redis is None:
            await state_manager.initialize()
        
        # Get execution state from state manager
        try:
            execution_state = await state_manager.get_execution_state(execution_id)
            
            if not execution_state:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "success": False,
                        "code": "EXECUTION_NOT_FOUND",
                        "message": "执行未找到",
                        "detail": f"Execution with ID '{execution_id}' not found"
                    }
                )
            
            # Calculate progress
            total_teams = len(execution_state.team_states) if execution_state.team_states else 1
            completed_teams = sum(
                1 for state in execution_state.team_states.values()
                if state.execution_status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]
            ) if execution_state.team_states else 0
            
            progress = int((completed_teams / total_teams) * 100) if total_teams > 0 else 0
            
            # Find current team
            current_team = None
            for team_id, team_state in (execution_state.team_states or {}).items():
                if team_state.execution_status == ExecutionStatus.RUNNING:
                    current_team = team_id
                    break
            
            # Estimate completion time (simple heuristic)
            estimated_completion = None
            if execution_state.status == ExecutionStatus.RUNNING and progress > 0:
                elapsed_time = (datetime.now() - execution_state.created_at).total_seconds()
                estimated_total_time = elapsed_time * (100 / progress)
                estimated_completion = (
                    execution_state.created_at.timestamp() + estimated_total_time
                )
                estimated_completion = datetime.fromtimestamp(estimated_completion).isoformat() + "Z"
            
            # Create response data
            response_data = {
                "execution_id": execution_id,
                "team_id": execution_state.team_id,
                "status": execution_state.status.value,
                "started_at": execution_state.created_at.isoformat() + "Z",
                "progress": progress,
                "current_team": current_team,
                "teams_completed": completed_teams,
                "total_teams": total_teams,
                "estimated_completion": estimated_completion
            }
            
            # Add completion time if finished
            if execution_state.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]:
                response_data["completed_at"] = execution_state.updated_at.isoformat() + "Z"
                response_data["duration"] = int(
                    (execution_state.updated_at - execution_state.created_at).total_seconds()
                )
            
            return {
                "success": True,
                "code": "EXECUTION_FOUND",
                "message": "执行状态获取成功",
                "data": response_data
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve execution state: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "success": False,
                    "code": "INTERNAL_ERROR",
                    "message": "服务器内部错误",
                    "detail": "Failed to retrieve execution status"
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_execution_status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误",
                "detail": "An unexpected error occurred"
            }
        )


@router.delete(
    "/executions/{execution_id}",
    response_model=APIResponse,
    summary="Stop Execution",
    description="Stop a running execution",
    responses={
        200: {
            "description": "Execution stopped successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "code": "EXECUTION_STOPPED",
                        "message": "执行已停止"
                    }
                }
            }
        },
        404: {
            "description": "Execution not found",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "code": "EXECUTION_NOT_FOUND",
                        "message": "执行未找到"
                    }
                }
            }
        }
    }
)
async def stop_execution(
    execution_id: str = Path(..., description="Execution ID to stop"),
    graceful: bool = True
) -> APIResponse:
    """
    Stop a running execution.
    
    Args:
        execution_id: The unique execution identifier
        graceful: Whether to stop gracefully (default: True)
        
    Returns:
        APIResponse: Confirmation of execution stop
        
    Raises:
        HTTPException: If execution is not found
    """
    try:
        logger.info(f"Stopping execution: {execution_id}")
        
        # Validate execution_id format
        if not execution_id.startswith("exec_") or len(execution_id) != 17:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "code": "EXECUTION_NOT_FOUND",
                    "message": "执行未找到",
                    "detail": f"Invalid execution ID format: {execution_id}"
                }
            )
        
        # Initialize hierarchical manager if needed
        if not hierarchical_manager._initialized:
            await hierarchical_manager.initialize()
        
        # Stop the execution
        stopped = await hierarchical_manager.stop_execution(execution_id, graceful)
        
        if not stopped:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "code": "EXECUTION_NOT_FOUND",
                    "message": "执行未找到",
                    "detail": f"Execution with ID '{execution_id}' not found or already stopped"
                }
            )
        
        logger.info(f"Successfully stopped execution: {execution_id}")
        
        return APIResponse(
            success=True,
            code="EXECUTION_STOPPED",
            message="执行已停止"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in stop_execution: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误",
                "detail": "Failed to stop execution"
            }
        )


@router.get(
    "/executions",
    response_model=Dict[str, Any],
    summary="List Executions",
    description="List all executions with optional filtering",
    responses={
        200: {
            "description": "Executions listed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "code": "EXECUTIONS_LISTED",
                        "message": "执行列表获取成功",
                        "data": {
                            "executions": [
                                {
                                    "execution_id": "exec_987654321",
                                    "team_id": "ht_123456789",
                                    "status": "completed",
                                    "started_at": "2024-01-15T10:35:00Z",
                                    "completed_at": "2024-01-15T11:05:00Z",
                                    "duration": 1800
                                }
                            ],
                            "total_count": 1,
                            "page": 1,
                            "page_size": 10
                        }
                    }
                }
            }
        }
    }
)
async def list_executions(
    team_id: Optional[str] = None,
    execution_status: Optional[str] = None,
    page: int = 1,
    page_size: int = 10
) -> Dict[str, Any]:
    """
    List all executions with optional filtering.
    
    Args:
        team_id: Filter by team ID (optional)
        status: Filter by execution status (optional)
        page: Page number (default: 1)
        page_size: Number of executions per page (default: 10)
        
    Returns:
        Dict containing list of executions and pagination info
    """
    try:
        logger.info(f"Listing executions - team_id: {team_id}, status: {execution_status}, page: {page}")
        
        # Validate pagination parameters
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 10
        
        # Validate status parameter
        if execution_status and execution_status not in [s.value for s in ExecutionStatus]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "code": "INVALID_PARAMETER",
                    "message": "参数无效",
                    "detail": f"Invalid status: {execution_status}"
                }
            )
        
        # Initialize state manager if needed
        if not hasattr(state_manager, '_redis') or state_manager._redis is None:
            await state_manager.initialize()
        
        # Get executions from state manager
        try:
            status_filter = ExecutionStatus(execution_status) if execution_status else None
            execution_ids = await state_manager.list_executions(
                team_id=team_id,
                status=status_filter,
                limit=page_size * 10  # Get more to handle pagination
            )
            
            # Apply pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_ids = execution_ids[start_idx:end_idx]
            
            # Get detailed information for each execution
            executions = []
            for exec_id in paginated_ids:
                exec_state = await state_manager.get_execution_state(exec_id)
                if exec_state:
                    execution_info = {
                        "execution_id": exec_id,
                        "team_id": exec_state.team_id,
                        "status": exec_state.status.value,
                        "started_at": exec_state.created_at.isoformat() + "Z"
                    }
                    
                    if exec_state.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]:
                        execution_info["completed_at"] = exec_state.updated_at.isoformat() + "Z"
                        execution_info["duration"] = int(
                            (exec_state.updated_at - exec_state.created_at).total_seconds()
                        )
                    
                    executions.append(execution_info)
            
            response_data = {
                "executions": executions,
                "total_count": len(execution_ids),
                "page": page,
                "page_size": page_size
            }
            
            return {
                "success": True,
                "code": "EXECUTIONS_LISTED",
                "message": "执行列表获取成功",
                "data": response_data
            }
            
        except Exception as e:
            logger.error(f"Failed to list executions: {e}")
            # Return empty list on error rather than failing
            response_data = {
                "executions": [],
                "total_count": 0,
                "page": page,
                "page_size": page_size
            }
            
            return {
                "success": True,
                "code": "EXECUTIONS_LISTED",
                "message": "执行列表获取成功",
                "data": response_data
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in list_executions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误",
                "detail": "Failed to list executions"
            }
        )


@router.get(
    "/executions/{execution_id}/stream",
    summary="Stream Execution Events",
    description="Get real-time execution events via Server-Sent Events (SSE)",
    responses={
        200: {
            "description": "Event stream established",
            "content": {
                "text/event-stream": {
                    "example": """event: execution_started
data: {"timestamp": "2024-01-15T10:35:00Z", "execution_id": "exec_987654321", "status": "started", "source_type": "system"}

event: supervisor_routing
data: {"timestamp": "2024-01-15T10:35:05Z", "source_type": "supervisor", "supervisor_id": "supervisor_main", "supervisor_name": "顶级监督者", "team_id": "ht_123456789", "action": "routing", "content": "分析任务需求，选择研究团队开始执行", "selected_team": "team_a7b9c2d4e5f6"}

event: agent_started
data: {"timestamp": "2024-01-15T10:35:15Z", "source_type": "agent", "team_id": "team_a7b9c2d4e5f6", "agent_id": "agent_search_001", "agent_name": "医疗文献搜索专家", "action": "started", "content": "开始搜索AI医疗应用相关信息", "status": "running"}"""
                }
            }
        },
        404: {
            "description": "Execution not found",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "code": "EXECUTION_NOT_FOUND",
                        "message": "执行未找到",
                        "detail": "Execution with ID 'exec_987654321' not found"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "code": "INTERNAL_ERROR",
                        "message": "服务器内部错误",
                        "detail": "Failed to establish event stream"
                    }
                }
            }
        }
    }
)
async def stream_execution_events(
    execution_id: str = Path(..., description="Execution ID to stream events for")
) -> StreamingResponse:
    """
    Stream real-time execution events via Server-Sent Events (SSE).
    
    This endpoint establishes a persistent connection and streams execution events
    in real-time using the Server-Sent Events protocol. Events are formatted
    according to the SSE specification with event types and JSON data.
    
    Args:
        execution_id: The unique execution identifier
        
    Returns:
        StreamingResponse: SSE stream of execution events
        
    Raises:
        HTTPException: If execution is not found or streaming fails
    """
    try:
        logger.info(f"Starting event stream for execution: {execution_id}")
        
        # Validate execution_id format
        if not execution_id.startswith("exec_") or len(execution_id) != 17:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "code": "EXECUTION_NOT_FOUND",
                    "message": "执行未找到",
                    "detail": f"Invalid execution ID format: {execution_id}"
                }
            )
        
        # Initialize event manager if needed
        if not hasattr(event_manager, '_subscribers'):
            await event_manager.initialize()
        
        # Check if execution exists
        if not hasattr(state_manager, '_redis') or state_manager._redis is None:
            await state_manager.initialize()
        
        execution_state = await state_manager.get_execution_state(execution_id)
        if not execution_state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "code": "EXECUTION_NOT_FOUND",
                    "message": "执行未找到",
                    "detail": f"Execution with ID '{execution_id}' not found"
                }
            )
        
        # Create SSE event generator
        async def event_generator():
            """Generate SSE-formatted events."""
            try:
                # Send any buffered events first
                buffered_events = await event_manager.get_buffered_events(execution_id)
                for event in buffered_events:
                    sse_data = _format_sse_event(event)
                    yield sse_data
                
                # Stream real-time events
                async for event in event_manager.get_events_stream(execution_id):
                    sse_data = _format_sse_event(event)
                    yield sse_data
                    
            except Exception as e:
                logger.error(f"Error in event stream for {execution_id}: {e}")
                # Send error event and close stream
                error_event = {
                    "timestamp": datetime.now().isoformat() + "Z",
                    "event_type": "stream_error",
                    "source_type": "system",
                    "execution_id": execution_id,
                    "content": "Event stream encountered an error",
                    "status": "error"
                }
                yield f"event: stream_error\ndata: {json.dumps(error_event)}\n\n"
        
        logger.info(f"Successfully established event stream for execution: {execution_id}")
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Handle any unexpected errors
        logger.error(f"Unexpected error in stream_execution_events: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误",
                "detail": "Failed to establish event stream"
            }
        )


@router.get(
    "/executions/{execution_id}/results",
    response_model=ExecutionResultsResponse,
    summary="Get Execution Results",
    description="Retrieve the complete execution results for a finished execution",
    responses={
        200: {
            "description": "Execution results retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "code": "RESULTS_RETRIEVED",
                        "message": "执行结果获取成功",
                        "data": {
                            "execution_id": "exec_987654321",
                            "execution_summary": {
                                "status": "completed",
                                "started_at": "2024-01-15T10:35:00Z",
                                "completed_at": "2024-01-15T11:05:00Z",
                                "total_duration": 1800,
                                "teams_executed": 2,
                                "agents_involved": 3
                            },
                            "team_results": {
                                "team_a7b9c2d4e5f6": {
                                    "status": "completed",
                                    "duration": 900,
                                    "agents": {
                                        "agent_search_001": {
                                            "agent_name": "医疗文献搜索专家",
                                            "status": "completed",
                                            "output": "收集了15篇AI医疗应用研究论文"
                                        }
                                    },
                                    "output": "研究阶段完成，收集了相关资料"
                                }
                            },
                            "errors": [],
                            "metrics": {
                                "total_tokens_used": 2500,
                                "api_calls_made": 8,
                                "success_rate": 1.0,
                                "average_response_time": 45.2
                            }
                        }
                    }
                }
            }
        },
        404: {
            "description": "Execution not found",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "code": "EXECUTION_NOT_FOUND",
                        "message": "执行未找到",
                        "detail": "Execution with ID 'exec_987654321' not found"
                    }
                }
            }
        },
        400: {
            "description": "Execution not completed",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "code": "EXECUTION_NOT_COMPLETED",
                        "message": "执行未完成",
                        "detail": "Execution is still running. Results are only available for completed executions."
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "code": "INTERNAL_ERROR",
                        "message": "服务器内部错误",
                        "detail": "Failed to retrieve execution results"
                    }
                }
            }
        }
    }
)
async def get_execution_results(
    execution_id: str = Path(..., description="Execution ID to get results for"),
    format: str = "json"
) -> ExecutionResultsResponse:
    """
    Get the complete execution results for a finished execution.
    
    This endpoint returns the full standardized results including execution summary,
    team results, error information, and performance metrics. Results are only
    available for completed executions.
    
    Args:
        execution_id: The unique execution identifier
        format: Output format (json|xml|markdown) - currently only json is supported
        
    Returns:
        ExecutionResultsResponse: Complete execution results
        
    Raises:
        HTTPException: If execution is not found, not completed, or retrieval fails
    """
    try:
        logger.info(f"Retrieving execution results for ID: {execution_id}")
        
        # Validate execution_id format
        if not execution_id.startswith("exec_") or len(execution_id) != 17:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "code": "EXECUTION_NOT_FOUND",
                    "message": "执行未找到",
                    "detail": f"Invalid execution ID format: {execution_id}"
                }
            )
        
        # Validate format parameter
        if format not in ["json", "xml", "markdown"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "code": "INVALID_FORMAT",
                    "message": "格式无效",
                    "detail": f"Unsupported format: {format}. Supported formats: json, xml, markdown"
                }
            )
        
        # Initialize state manager and output formatter if needed
        if not hasattr(state_manager, '_redis') or state_manager._redis is None:
            await state_manager.initialize()
        
        # Set state manager in output formatter
        output_formatter.state_manager = state_manager
        
        # Get execution state from state manager
        try:
            execution_state = await state_manager.get_execution_state(execution_id)
            
            if not execution_state:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "success": False,
                        "code": "EXECUTION_NOT_FOUND",
                        "message": "执行未找到",
                        "detail": f"Execution with ID '{execution_id}' not found"
                    }
                )
            
            # Check if execution is completed
            if execution_state.status not in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "success": False,
                        "code": "EXECUTION_NOT_COMPLETED",
                        "message": "执行未完成",
                        "detail": f"Execution is in '{execution_state.status.value}' status. Results are only available for completed executions."
                    }
                )
            
            # Format execution results using OutputFormatter
            try:
                standardized_results = await output_formatter.format_execution_results(execution_id)
                
                logger.info(f"Successfully retrieved results for execution {execution_id}")
                
                return ExecutionResultsResponse(
                    success=True,
                    code="RESULTS_RETRIEVED",
                    message="执行结果获取成功",
                    data=standardized_results
                )
                
            except OutputFormatterError as e:
                logger.error(f"Failed to format execution results: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "success": False,
                        "code": "FORMATTING_ERROR",
                        "message": "结果格式化失败",
                        "detail": "Failed to format execution results"
                    }
                )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve execution results: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "success": False,
                    "code": "INTERNAL_ERROR",
                    "message": "服务器内部错误",
                    "detail": "Failed to retrieve execution results"
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_execution_results: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误",
                "detail": "An unexpected error occurred"
            }
        )


@router.post(
    "/executions/{execution_id}/results/format",
    response_model=Dict[str, Any],
    summary="Format Execution Results",
    description="Generate formatted output using user-defined JSON template and extraction rules",
    responses={
        200: {
            "description": "Formatted results generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "code": "FORMATTED_RESULTS_GENERATED",
                        "message": "格式化结果生成成功",
                        "data": {
                            "report_title": "AI医疗应用分析报告",
                            "executive_summary": "本报告全面分析了人工智能在医疗领域的当前应用状况...",
                            "research_findings": {
                                "key_technologies": [
                                    "深度学习医学影像诊断",
                                    "自然语言处理病历分析"
                                ],
                                "market_trends": [
                                    "AI医疗市场预计2030年达到1000亿美元"
                                ]
                            },
                            "recommendations": [
                                "建立统一的医疗AI数据标准",
                                "加强跨学科人才培养"
                            ]
                        }
                    }
                }
            }
        },
        400: {
            "description": "Invalid template or extraction rules",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "code": "INVALID_TEMPLATE",
                        "message": "模板无效",
                        "detail": "Template parsing failed: Template must be a dictionary"
                    }
                }
            }
        },
        404: {
            "description": "Execution not found",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "code": "EXECUTION_NOT_FOUND",
                        "message": "执行未找到",
                        "detail": "Execution with ID 'exec_987654321' not found"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "code": "INTERNAL_ERROR",
                        "message": "服务器内部错误",
                        "detail": "Failed to generate formatted results"
                    }
                }
            }
        }
    }
)
async def format_execution_results(
    execution_id: str = Path(..., description="Execution ID to format results for"),
    format_request: Dict[str, Any] = Body(
        ...,
        description="Format request with template and extraction rules",
        example={
            "output_template": {
                "report_title": "AI医疗应用分析报告",
                "executive_summary": "{从所有团队结果中提取执行摘要}",
                "research_findings": {
                    "key_technologies": "{从研究团队结果中提取关键技术}",
                    "market_trends": "{从分析结果中提取市场趋势}"
                },
                "recommendations": "{从写作团队结果中提取建议}"
            },
            "extraction_rules": {
                "executive_summary": "总结所有团队的核心发现，不超过200字",
                "key_technologies": "从搜索结果中提取3-5个关键技术",
                "market_trends": "从分析结果中提取市场趋势，以列表形式呈现",
                "recommendations": "基于分析结果提供3-5条具体建议"
            }
        }
    )
) -> Dict[str, Any]:
    """
    Generate formatted output using user-defined JSON template and extraction rules.
    
    This endpoint takes a user-defined template and extraction rules to generate
    customized reports from execution results. The template defines the output
    structure while extraction rules specify how to extract information from
    the raw execution results.
    
    Args:
        execution_id: The unique execution identifier
        format_request: Request body containing output template and extraction rules
        
    Returns:
        Dict: Formatted output according to user template
        
    Raises:
        HTTPException: If execution is not found, template is invalid, or formatting fails
    """
    try:
        logger.info(f"Formatting execution results for ID: {execution_id}")
        
        # Validate execution_id format
        if not execution_id.startswith("exec_") or len(execution_id) != 17:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "code": "EXECUTION_NOT_FOUND",
                    "message": "执行未找到",
                    "detail": f"Invalid execution ID format: {execution_id}"
                }
            )
        
        # Validate request structure
        if not isinstance(format_request, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "code": "INVALID_REQUEST",
                    "message": "请求无效",
                    "detail": "Request body must be a JSON object"
                }
            )
        
        # Extract template and rules from request
        output_template = format_request.get("output_template")
        extraction_rules = format_request.get("extraction_rules")
        
        if not output_template:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "code": "MISSING_TEMPLATE",
                    "message": "缺少模板",
                    "detail": "output_template is required"
                }
            )
        
        if not extraction_rules:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "code": "MISSING_RULES",
                    "message": "缺少提取规则",
                    "detail": "extraction_rules is required"
                }
            )
        
        # Initialize state manager and output formatter if needed
        if not hasattr(state_manager, '_redis') or state_manager._redis is None:
            await state_manager.initialize()
        
        # Set state manager in output formatter
        output_formatter.state_manager = state_manager
        
        # Check if execution exists and is completed
        try:
            execution_state = await state_manager.get_execution_state(execution_id)
            
            if not execution_state:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "success": False,
                        "code": "EXECUTION_NOT_FOUND",
                        "message": "执行未找到",
                        "detail": f"Execution with ID '{execution_id}' not found"
                    }
                )
            
            # Check if execution is completed
            if execution_state.status not in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "success": False,
                        "code": "EXECUTION_NOT_COMPLETED",
                        "message": "执行未完成",
                        "detail": f"Execution is in '{execution_state.status.value}' status. Formatting is only available for completed executions."
                    }
                )
            
            # Validate and process template formatting
            try:
                # Validate template structure
                validated_template = output_formatter.parse_template(output_template)
                
                # Validate extraction rules
                validated_rules = output_formatter.validate_extraction_rules(extraction_rules)
                
                # Format execution results with template
                formatted_output = await output_formatter.format_execution_with_template(
                    execution_id, validated_template, validated_rules
                )
                
                logger.info(f"Successfully formatted results for execution {execution_id}")
                
                return {
                    "success": True,
                    "code": "FORMATTED_RESULTS_GENERATED",
                    "message": "格式化结果生成成功",
                    "data": formatted_output
                }
                
            except OutputFormatterError as e:
                logger.error(f"Template formatting failed: {e}")
                
                # Determine specific error type
                error_msg = str(e).lower()
                if "template" in error_msg and ("parsing" in error_msg or "invalid" in error_msg):
                    error_code = "INVALID_TEMPLATE"
                    error_message = "模板无效"
                elif "rule" in error_msg and ("validation" in error_msg or "invalid" in error_msg):
                    error_code = "INVALID_RULES"
                    error_message = "提取规则无效"
                elif "extraction" in error_msg:
                    error_code = "EXTRACTION_ERROR"
                    error_message = "信息提取失败"
                else:
                    error_code = "FORMATTING_ERROR"
                    error_message = "格式化失败"
                
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "success": False,
                        "code": error_code,
                        "message": error_message,
                        "detail": str(e)
                    }
                )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to format execution results: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "success": False,
                    "code": "INTERNAL_ERROR",
                    "message": "服务器内部错误",
                    "detail": "Failed to format execution results"
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in format_execution_results: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误",
                "detail": "An unexpected error occurred"
            }
        )


# Helper functions

async def _execute_team_async(
    manager: HierarchicalManager,
    team,
    execution_id: str,
    config: ExecutionConfig
) -> None:
    """Execute team asynchronously in background."""
    try:
        logger.info(f"Starting background execution {execution_id}")
        
        # Create execution context
        from ..data_models import ExecutionContext
        context = ExecutionContext(
            execution_id=execution_id,
            team_id=team.team_name,
            config=config,
            started_at=datetime.now()
        )
        
        # Execute the team (this will stream events internally)
        async for event in manager.execute_team(team, context):
            # Events are handled by the event manager internally
            pass
        
        logger.info(f"Completed background execution {execution_id}")
        
    except Exception as e:
        logger.error(f"Background execution {execution_id} failed: {e}", exc_info=True)


def _format_sse_event(event: ExecutionEvent) -> str:
    """
    Format an ExecutionEvent as a Server-Sent Event.
    
    Args:
        event: The ExecutionEvent to format
        
    Returns:
        str: SSE-formatted event string
    """
    # Convert event to dictionary, excluding None values
    event_dict = event.model_dump(exclude_none=True)
    
    # Convert datetime to ISO string
    if 'timestamp' in event_dict:
        event_dict['timestamp'] = event.timestamp.isoformat() + "Z"
    
    # Format as SSE
    event_type = event.event_type
    data = json.dumps(event_dict, ensure_ascii=False)
    
    return f"event: {event_type}\ndata: {data}\n\n"


def _create_mock_team_config(team_id: str) -> Dict[str, Any]:
    """Create a mock team configuration for testing purposes."""
    return {
        "team_name": f"mock_team_{team_id}",
        "description": f"Mock team for {team_id}",
        "top_supervisor_config": {
            "llm_config": {
                "provider": "openai",
                "model": "gpt-4o",
                "temperature": 0.3,
                "max_tokens": 1000
            },
            "system_prompt": "You are a top-level supervisor coordinating hierarchical team execution.",
            "user_prompt": "Please coordinate the hierarchical team execution. Select the most appropriate sub-team to start execution based on dependencies.",
            "max_iterations": 10
        },
        "sub_teams": [
            {
                "id": "mock_team_001",
                "name": "Mock Research Team",
                "description": "Mock team for testing",
                "supervisor_config": {
                    "llm_config": {
                        "provider": "openai",
                        "model": "gpt-4o",
                        "temperature": 0.3
                    },
                    "system_prompt": "You are a team supervisor coordinating research work.",
                    "user_prompt": "Please coordinate the team to execute research tasks.",
                    "max_iterations": 8
                },
                "agent_configs": [
                    {
                        "agent_id": "mock_agent_001",
                        "agent_name": "Mock Research Agent",
                        "llm_config": {
                            "provider": "openai",
                            "model": "gpt-4o",
                            "temperature": 0.3,
                            "max_tokens": 2000
                        },
                        "system_prompt": "You are a research agent that performs mock research tasks.",
                        "user_prompt": "Please perform mock research and return sample results.",
                        "tools": ["mock_search"],
                        "max_iterations": 5
                    }
                ]
            }
        ],
        "dependencies": {},
        "global_config": {
            "max_execution_time": 3600,
            "enable_streaming": True,
            "output_format": "detailed"
        }
    }


