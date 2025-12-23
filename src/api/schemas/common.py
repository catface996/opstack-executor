"""
Common Schemas - 通用请求/响应模型
"""

from typing import Optional, List, Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar('T')


class LLMConfig(BaseModel):
    """LLM 配置 - 统一的模型参数对象，适用于 Global Supervisor、Team Supervisor 和 Worker"""
    model_id: Optional[str] = Field(default=None, description="关联的 AI 模型 ID")
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(default=2048, ge=1, le=100000, description="最大 token 数")
    top_p: float = Field(default=0.9, ge=0, le=1, description="Top-P 参数")


class PaginationRequest(BaseModel):
    """分页请求"""
    page: int = Field(default=1, ge=1, description="页码")
    size: int = Field(default=20, ge=1, le=100, description="每页数量")


class IdRequest(BaseModel):
    """ID 请求"""
    id: str = Field(..., description="资源 ID")


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    items: List[T]
    total: int
    page: int
    size: int
    pages: int


class SuccessResponse(BaseModel):
    """成功响应"""
    success: bool = True
    message: str = "操作成功"
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error: str
    details: Optional[str] = None
