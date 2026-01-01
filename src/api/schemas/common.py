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
    """分页请求 - 符合宪法分页协议"""
    page: int = Field(default=1, ge=1, description="页码（从 1 开始）")
    size: int = Field(default=20, ge=1, le=100, description="每页大小，范围 1-100")
    tenantId: Optional[str] = Field(default=None, description="租户ID（网关注入）")
    traceId: Optional[str] = Field(default=None, description="追踪ID（网关注入）")
    userId: Optional[str] = Field(default=None, description="用户ID（网关注入）")


class IdRequest(BaseModel):
    """ID 请求 (字符串类型)"""
    id: str = Field(..., description="资源 ID")


class RunIdRequest(BaseModel):
    """Run ID 请求 (整数类型)"""
    id: int = Field(..., description="运行 ID")


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应 - 符合宪法分页协议"""
    content: List[T] = Field(description="数据列表")
    page: int = Field(description="当前页码（从 1 开始）")
    size: int = Field(description="每页大小")
    totalElements: int = Field(description="总记录数")
    totalPages: int = Field(description="总页数")
    first: bool = Field(description="是否为第一页")
    last: bool = Field(description="是否为最后一页")


def build_page_response(content: list, page: int, size: int, total: int) -> dict:
    """
    构建符合宪法分页协议的响应

    Args:
        content: 数据列表
        page: 当前页码（从 1 开始）
        size: 每页大小
        total: 总记录数

    Returns:
        符合宪法的分页响应字典
    """
    import math
    total_pages = math.ceil(total / size) if size > 0 else 0
    return {
        'code': 0,
        'message': 'success',
        'success': True,
        'data': {
            'content': content,
            'page': page,
            'size': size,
            'totalElements': total,
            'totalPages': total_pages,
            'first': page == 1,
            'last': page >= total_pages
        }
    }


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
