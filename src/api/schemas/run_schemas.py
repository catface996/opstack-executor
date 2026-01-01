"""
Run Schemas - 运行记录请求/响应模型
"""

from typing import Optional, List, Any
from pydantic import BaseModel, Field

from .common import PaginationRequest


class RunStartRequest(BaseModel):
    """启动运行请求"""
    hierarchy_id: str = Field(..., description="层级团队 ID")
    task: str = Field(..., min_length=1, description="任务描述")


class RunListRequest(PaginationRequest):
    """运行记录列表请求"""
    hierarchy_id: Optional[str] = Field(default=None, description="过滤层级团队")
    status: Optional[str] = Field(default=None, description="过滤状态")


class RunStreamRequest(BaseModel):
    """流式获取运行事件请求"""
    id: int = Field(..., description="运行 ID")


class RunCancelRequest(BaseModel):
    """取消运行请求"""
    id: int = Field(..., description="运行 ID")


class EventResponse(BaseModel):
    """事件响应"""
    id: int
    event_type: str
    timestamp: Optional[str]
    data: Optional[Any]
    team_name: Optional[str]
    worker_name: Optional[str]

    class Config:
        from_attributes = True


class RunResponse(BaseModel):
    """运行记录响应"""
    id: int
    hierarchy_id: str
    task: str
    status: str
    result: Optional[str]
    error: Optional[str]
    statistics: Optional[Any]
    started_at: Optional[str]
    completed_at: Optional[str]
    created_at: Optional[str]

    class Config:
        from_attributes = True


class RunDetailResponse(RunResponse):
    """运行详情响应（含事件）"""
    events: List[EventResponse] = []
    topology_snapshot: Optional[Any] = None


class RunStartResponse(BaseModel):
    """启动运行响应"""
    id: int
    hierarchy_id: str
    task: str
    status: str
    stream_url: str
    created_at: Optional[str]


class EventQueryRequest(BaseModel):
    """历史事件查询请求"""
    id: int = Field(..., description="运行 ID")
    start_id: Optional[str] = Field(default='-', description="起始 ID，'-' 表示最早")
    end_id: Optional[str] = Field(default='+', description="结束 ID，'+' 表示最新")
    limit: Optional[int] = Field(default=1000, ge=1, le=10000, description="最大返回数量")


class StreamEventItem(BaseModel):
    """流事件项"""
    id: str = Field(..., description="Redis Stream 消息 ID")
    run_id: int = Field(..., description="运行 ID")
    timestamp: str = Field(..., description="ISO 8601 时间戳")
    sequence: int = Field(..., description="序列号")
    source: Optional[dict] = Field(default=None, description="事件来源")
    event: dict = Field(..., description="事件类型 {category, action}")
    data: dict = Field(default_factory=dict, description="事件数据")


class EventListResponse(BaseModel):
    """历史事件列表响应"""
    run_id: int = Field(..., description="运行 ID")
    events: List[StreamEventItem] = Field(default_factory=list, description="事件列表")
    count: int = Field(..., description="返回的事件数量")
    has_more: bool = Field(default=False, description="是否还有更多事件")
    next_id: Optional[str] = Field(default=None, description="下一页起始 ID")
