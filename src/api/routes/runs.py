"""
Runs Routes - 运行管理路由
"""

from flask import Blueprint, request, jsonify
from flasgger import swag_from
from pydantic import ValidationError

from ..schemas.run_schemas import (
    RunStartRequest, RunListRequest, RunStreamRequest, RunCancelRequest,
    EventQueryRequest
)
from ..schemas.common import IdRequest, RunIdRequest, build_page_response
from ...db.database import get_db_session, db
from ...db.repositories import RunRepository
from ...runner.run_manager import RunManager
from ...streaming.sse_manager import SSERegistry
from ...streaming.event_store import get_event_store

runs_bp = Blueprint('runs', __name__)


def get_repo():
    """获取运行记录仓库"""
    # 确保使用新的会话，能看到其他线程提交的数据
    if db:
        db.remove()  # 清理当前线程的会话
    session = get_db_session()
    return RunRepository(session)


def get_run_manager():
    """获取运行管理器"""
    return RunManager.get_instance()


@runs_bp.route('/start', methods=['POST'])
@swag_from({
    'tags': ['Runs'],
    'summary': '启动运行',
    'description': '启动新的层级团队执行任务，返回运行 ID 和流式 URL',
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'required': True,
        'schema': {
            'type': 'object',
            'required': ['hierarchy_id', 'task'],
            'properties': {
                'hierarchy_id': {'type': 'string', 'description': '层级团队 ID'},
                'task': {'type': 'string', 'description': '任务描述'}
            }
        }
    }],
    'responses': {
        200: {
            'description': '启动成功',
            'schema': {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'string'},
                            'hierarchy_id': {'type': 'string'},
                            'task': {'type': 'string'},
                            'status': {'type': 'string'},
                            'stream_url': {'type': 'string'}
                        }
                    }
                }
            }
        },
        400: {'description': '请求无效'},
        404: {'description': '层级团队不存在'}
    }
})
def start_run():
    """启动运行"""
    try:
        data = request.get_json() or {}
        req = RunStartRequest(**data)

        manager = get_run_manager()
        run = manager.start_run(req.hierarchy_id, req.task)

        return jsonify({
            'success': True,
            'message': '运行已启动',
            'data': {
                'id': run.id,
                'hierarchy_id': run.hierarchy_id,
                'task': run.task,
                'status': run.status,
                'stream_url': f'/api/executor/v1/runs/stream',
                'created_at': run.created_at.isoformat() if run.created_at else None
            }
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except ValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runs_bp.route('/list', methods=['POST'])
@swag_from({
    'tags': ['Runs'],
    'summary': '获取运行列表',
    'description': '分页获取任务运行记录列表，支持按层级团队和状态筛选',
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'required': True,
        'schema': {
            'type': 'object',
            'properties': {
                'page': {'type': 'integer', 'default': 1, 'description': '页码，从 1 开始'},
                'size': {'type': 'integer', 'default': 20, 'description': '每页数量，范围 1-100'},
                'hierarchy_id': {'type': 'string', 'description': '按层级团队 ID 筛选'},
                'status': {'type': 'string', 'enum': ['pending', 'running', 'completed', 'failed', 'cancelled'], 'description': '按运行状态筛选'}
            }
        }
    }],
    'responses': {
        200: {
            'description': '运行列表',
            'schema': {
                'type': 'object',
                'properties': {
                    'code': {'type': 'integer', 'example': 0},
                    'success': {'type': 'boolean'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'content': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'id': {'type': 'string', 'description': '运行唯一标识'},
                                        'hierarchy_id': {'type': 'string', 'description': '关联的层级团队 ID'},
                                        'task': {'type': 'string', 'description': '任务描述'},
                                        'status': {'type': 'string', 'enum': ['pending', 'running', 'completed', 'failed', 'cancelled']},
                                        'result': {'type': 'string', 'description': '执行结果（完成时）'},
                                        'error': {'type': 'string', 'description': '错误信息（失败时）'},
                                        'started_at': {'type': 'string', 'format': 'date-time'},
                                        'completed_at': {'type': 'string', 'format': 'date-time'},
                                        'created_at': {'type': 'string', 'format': 'date-time'}
                                    }
                                }
                            },
                            'page': {'type': 'integer'},
                            'size': {'type': 'integer'},
                            'totalElements': {'type': 'integer'},
                            'totalPages': {'type': 'integer'}
                        }
                    }
                }
            }
        }
    }
})
def list_runs():
    """获取运行列表"""
    try:
        data = request.get_json() or {}
        req = RunListRequest(**data)

        repo = get_repo()
        runs, total = repo.list(
            page=req.page,
            size=req.size,
            hierarchy_id=req.hierarchy_id,
            status=req.status
        )

        return jsonify(build_page_response(
            content=[r.to_dict() for r in runs],
            page=req.page,
            size=req.size,
            total=total
        ))
    except ValidationError as e:
        return jsonify({'code': 400, 'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'code': 500, 'success': False, 'error': str(e)}), 500


@runs_bp.route('/get', methods=['POST'])
@swag_from({
    'tags': ['Runs'],
    'summary': '获取运行详情',
    'description': '根据运行 ID 获取运行的详细信息，包括任务描述、状态、结果和执行统计',
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'required': True,
        'schema': {
            'type': 'object',
            'required': ['id'],
            'properties': {
                'id': {'type': 'integer', 'description': '运行唯一标识'}
            }
        }
    }],
    'responses': {
        200: {
            'description': '运行详情',
            'schema': {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'string'},
                            'hierarchy_id': {'type': 'string'},
                            'task': {'type': 'string'},
                            'status': {'type': 'string', 'enum': ['pending', 'running', 'completed', 'failed', 'cancelled']},
                            'result': {'type': 'string', 'description': '执行结果文本'},
                            'error': {'type': 'string', 'description': '错误信息'},
                            'statistics': {'type': 'object', 'description': '执行统计信息'},
                            'topology_snapshot': {'type': 'object', 'description': '执行时的拓扑快照'},
                            'started_at': {'type': 'string', 'format': 'date-time'},
                            'completed_at': {'type': 'string', 'format': 'date-time'},
                            'created_at': {'type': 'string', 'format': 'date-time'}
                        }
                    }
                }
            }
        },
        404: {'description': '运行不存在'}
    }
})
def get_run():
    """获取运行详情"""
    try:
        data = request.get_json() or {}
        req = RunIdRequest(**data)

        repo = get_repo()
        run = repo.get_by_id(req.id)

        if not run:
            return jsonify({'success': False, 'error': '运行记录不存在'}), 404

        return jsonify({
            'success': True,
            'data': run.to_dict()
        })
    except ValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runs_bp.route('/stream', methods=['POST'])
@swag_from({
    'tags': ['Runs'],
    'summary': '流式获取运行事件',
    'description': '''通过 SSE (Server-Sent Events) 流式获取运行执行过程中的事件。

## 事件格式

每个事件遵循以下结构:
```
event: {category}.{action}
data: {"run_id": "...", "timestamp": "...", "sequence": 123, "source": {...}, "event": {...}, "data": {...}}
```

## 事件类别 (category)

| category | 说明 |
|----------|------|
| lifecycle | 生命周期事件 |
| llm | LLM 相关事件 |
| dispatch | 调度事件 |
| system | 系统事件 |

## 事件动作 (action)

| category | action | 说明 |
|----------|--------|------|
| lifecycle | started | 运行开始 |
| lifecycle | completed | 运行完成 |
| lifecycle | failed | 运行失败 |
| lifecycle | cancelled | 运行取消 |
| llm | stream | LLM 输出流 |
| llm | reasoning | LLM 推理过程 |
| llm | tool_call | LLM 工具调用 |
| llm | tool_result | 工具调用结果 |
| dispatch | team | 调度团队 |
| dispatch | worker | 调度 Worker |
| system | topology | 拓扑结构 |
| system | warning | 警告信息 |
| system | error | 错误信息 |

## 来源标识 (source)

| 字段 | 说明 |
|------|------|
| agent_id | Agent 唯一标识 |
| agent_type | Agent 类型: global_supervisor, team_supervisor, worker |
| agent_name | Agent 名称 |
| team_name | 所属团队名称 (可选) |

## 示例事件

```json
{
  "run_id": "abc-123",
  "timestamp": "2025-01-01T12:00:00.123Z",
  "sequence": 1,
  "source": {
    "agent_id": "gs-001",
    "agent_type": "global_supervisor",
    "agent_name": "Global Supervisor",
    "team_name": null
  },
  "event": {
    "category": "llm",
    "action": "stream"
  },
  "data": {
    "content": "开始分析任务..."
  }
}
```
''',
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'required': True,
        'schema': {
            'type': 'object',
            'required': ['id'],
            'properties': {
                'id': {'type': 'integer', 'description': '运行 ID'}
            }
        }
    }],
    'responses': {
        200: {
            'description': 'SSE 事件流 (text/event-stream)',
            'content': {
                'text/event-stream': {
                    'schema': {
                        'type': 'string',
                        'example': 'event: lifecycle.started\\ndata: {"run_id":"abc","timestamp":"2025-01-01T12:00:00.123Z","sequence":1,"source":null,"event":{"category":"lifecycle","action":"started"},"data":{"task":"请解释AI"}}\\n\\n'
                    }
                }
            }
        },
        404: {'description': '运行不存在或已结束'}
    }
})
def stream_run():
    """流式获取运行事件"""
    try:
        data = request.get_json() or {}
        req = RunStreamRequest(**data)

        registry = SSERegistry.get_instance()
        sse_manager = registry.get(req.id)

        # 获取 Last-Event-ID 头（用于断线重连）
        last_event_id = request.headers.get('Last-Event-ID')

        # 调试日志
        print(f"[stream] 请求 run_id: {req.id}", flush=True)
        print(f"[stream] Last-Event-ID: {last_event_id}", flush=True)
        print(f"[stream] SSE Registry ID: {id(registry)}", flush=True)
        print(f"[stream] 已注册的 run_ids: {registry.get_all_run_ids()}", flush=True)
        print(f"[stream] SSE Manager 存在: {sse_manager is not None}", flush=True)

        if not sse_manager:
            # 检查运行是否存在
            repo = get_repo()
            run = repo.get_by_id(req.id)

            if not run:
                return jsonify({'success': False, 'error': '运行记录不存在'}), 404

            if run.status in ('completed', 'failed', 'cancelled'):
                return jsonify({
                    'success': False,
                    'error': f'运行已结束，状态: {run.status}'
                }), 400

            return jsonify({
                'success': False,
                'error': '运行流不可用，可能尚未开始或已结束'
            }), 404

        # 如果有 Last-Event-ID，从 Redis 恢复历史事件
        initial_events = None
        if last_event_id:
            event_store = get_event_store()
            initial_events = event_store.get_events_after(req.id, last_event_id)
            print(f"[stream] 恢复历史事件数量: {len(initial_events)}", flush=True)

        # 返回 SSE 响应（带历史事件恢复）
        return sse_manager.create_response(initial_events=initial_events)

    except ValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runs_bp.route('/cancel', methods=['POST'])
@swag_from({
    'tags': ['Runs'],
    'summary': '取消运行',
    'description': '''取消正在执行的运行任务。

## 取消条件

只有状态为 `pending` 或 `running` 的运行可以被取消。

## 取消行为

- 向执行中的 Agent 发送取消信号
- 更新运行状态为 `cancelled`
- 记录 `lifecycle.cancelled` 事件
- 关闭相关的 SSE 流连接

## 注意事项

- 已完成 (`completed`)、已失败 (`failed`)、已取消 (`cancelled`) 的运行无法再次取消
- 取消操作是异步的，Agent 可能需要一定时间才能完全停止
''',
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'required': True,
        'schema': {
            'type': 'object',
            'required': ['id'],
            'properties': {
                'id': {'type': 'integer', 'description': '要取消的运行 ID'}
            }
        }
    }],
    'responses': {
        200: {
            'description': '取消成功',
            'schema': {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean', 'example': True},
                    'message': {'type': 'string', 'example': '运行已取消'}
                }
            }
        },
        400: {
            'description': '运行无法取消（状态不允许）',
            'schema': {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean', 'example': False},
                    'error': {'type': 'string', 'example': '运行状态为 completed，无法取消'}
                }
            }
        },
        404: {
            'description': '运行不存在',
            'schema': {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean', 'example': False},
                    'error': {'type': 'string', 'example': '运行记录不存在'}
                }
            }
        }
    }
})
def cancel_run():
    """取消运行"""
    try:
        data = request.get_json() or {}
        req = RunCancelRequest(**data)

        # 检查运行是否存在
        repo = get_repo()
        run = repo.get_by_id(req.id)

        if not run:
            return jsonify({'success': False, 'error': '运行记录不存在'}), 404

        if run.status not in ('pending', 'running'):
            return jsonify({
                'success': False,
                'error': f'运行状态为 {run.status}，无法取消'
            }), 400

        manager = get_run_manager()
        success = manager.cancel_run(req.id)

        if success:
            return jsonify({
                'success': True,
                'message': '运行已取消'
            })
        else:
            # 直接更新状态（可能运行管理器中没有此运行）
            repo.update_status(req.id, 'cancelled')
            return jsonify({
                'success': True,
                'message': '运行已取消'
            })

    except ValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runs_bp.route('/events', methods=['POST'])
@swag_from({
    'tags': ['Runs'],
    'summary': '获取运行事件列表',
    'description': '''获取运行的历史事件记录（从 Redis Stream 读取）。

返回的事件结构与 SSE 流式事件一致，包含完整的事件历史。
支持分页查询，通过 start_id、end_id 和 limit 参数控制。

## 事件结构

每个事件包含以下字段:
- `id`: Redis Stream 消息 ID
- `run_id`: 所属运行 ID
- `timestamp`: 事件时间戳 (ISO 8601)
- `sequence`: 序列号 (用于排序)
- `source`: 来源信息 (agent_id, agent_type, agent_name, team_name)
- `event`: 事件类型 (category, action)
- `data`: 事件数据

## 分页

- 使用 `start_id` 和 `limit` 进行分页
- 响应中的 `has_more` 表示是否还有更多数据
- `next_id` 为下一页的起始 ID

## 注意

- 事件数据保留 24 小时
- 超过 24 小时的运行可能返回空事件列表
''',
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'required': True,
        'schema': {
            'type': 'object',
            'required': ['id'],
            'properties': {
                'id': {'type': 'integer', 'description': '运行 ID'},
                'start_id': {'type': 'string', 'default': '-', 'description': '起始 ID，"-" 表示最早'},
                'end_id': {'type': 'string', 'default': '+', 'description': '结束 ID，"+" 表示最新'},
                'limit': {'type': 'integer', 'default': 1000, 'description': '最大返回数量 (1-10000)'}
            }
        }
    }],
    'responses': {
        200: {
            'description': '事件列表',
            'schema': {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'run_id': {'type': 'integer'},
                            'events': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'id': {'type': 'string', 'description': 'Redis Stream 消息 ID'},
                                        'run_id': {'type': 'integer'},
                                        'timestamp': {'type': 'string', 'format': 'date-time'},
                                        'sequence': {'type': 'integer'},
                                        'source': {
                                            'type': 'object',
                                            'nullable': True,
                                            'properties': {
                                                'agent_id': {'type': 'string'},
                                                'agent_type': {'type': 'string', 'enum': ['global_supervisor', 'team_supervisor', 'worker']},
                                                'agent_name': {'type': 'string'},
                                                'team_name': {'type': 'string'}
                                            }
                                        },
                                        'event': {
                                            'type': 'object',
                                            'properties': {
                                                'category': {'type': 'string', 'enum': ['lifecycle', 'llm', 'dispatch', 'system']},
                                                'action': {'type': 'string'}
                                            }
                                        },
                                        'data': {'type': 'object'}
                                    }
                                }
                            },
                            'count': {'type': 'integer', 'description': '返回的事件数量'},
                            'has_more': {'type': 'boolean', 'description': '是否还有更多事件'},
                            'next_id': {'type': 'string', 'nullable': True, 'description': '下一页起始 ID'}
                        }
                    }
                }
            }
        },
        404: {'description': '运行不存在'},
        410: {'description': '运行事件已过期'}
    }
})
def get_run_events():
    """获取运行事件列表（从 Redis Stream）"""
    try:
        data = request.get_json() or {}
        req = EventQueryRequest(**data)

        # 检查运行是否存在
        repo = get_repo()
        run = repo.get_by_id(req.id)

        if not run:
            return jsonify({
                'success': False,
                'code': 'RUN_NOT_FOUND',
                'error': '运行记录不存在'
            }), 404

        # 从 Redis Stream 获取事件
        event_store = get_event_store()

        # 检查 Stream 是否存在
        if not event_store.exists(req.id):
            # Stream 不存在，可能已过期或从未产生事件
            if run.status in ('completed', 'failed', 'cancelled'):
                return jsonify({
                    'success': False,
                    'code': 'RUN_EXPIRED',
                    'error': '运行事件已过期或不存在'
                }), 410

            # 运行尚未产生事件
            return jsonify({
                'success': True,
                'data': {
                    'run_id': req.id,
                    'events': [],
                    'count': 0,
                    'has_more': False,
                    'next_id': None
                }
            })

        # 获取事件（多取一条用于判断 has_more）
        fetch_count = req.limit + 1 if req.limit else None
        events = event_store.get_events(
            run_id=req.id,
            start_id=req.start_id,
            end_id=req.end_id,
            count=fetch_count
        )

        # 判断是否有更多数据
        has_more = len(events) > req.limit if req.limit else False
        if has_more:
            events = events[:req.limit]

        # 获取下一页起始 ID
        next_id = events[-1].id if has_more and events else None

        # 转换为响应格式
        event_list = [
            {
                'id': e.id,
                'run_id': e.run_id,
                'timestamp': e.timestamp,
                'sequence': e.sequence,
                'source': e.source,
                'event': e.event,
                'data': e.data
            }
            for e in events
        ]

        return jsonify({
            'success': True,
            'data': {
                'run_id': req.id,
                'events': event_list,
                'count': len(event_list),
                'has_more': has_more,
                'next_id': next_id
            }
        })

    except ValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
