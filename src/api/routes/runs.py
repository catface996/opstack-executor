"""
Runs Routes - 运行管理路由
"""

from flask import Blueprint, request, jsonify
from flasgger import swag_from
from pydantic import ValidationError

from ..schemas.run_schemas import (
    RunStartRequest, RunListRequest, RunStreamRequest, RunCancelRequest
)
from ..schemas.common import IdRequest, build_page_response
from ...db.database import get_db_session, db
from ...db.repositories import RunRepository
from ...runner.run_manager import RunManager
from ...streaming.sse_manager import SSERegistry

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
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'required': True,
        'schema': {
            'type': 'object',
            'properties': {
                'page': {'type': 'integer', 'default': 1},
                'size': {'type': 'integer', 'default': 20},
                'hierarchy_id': {'type': 'string'},
                'status': {'type': 'string', 'enum': ['pending', 'running', 'completed', 'failed', 'cancelled']}
            }
        }
    }],
    'responses': {
        200: {'description': '运行列表'}
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
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'required': True,
        'schema': {
            'type': 'object',
            'required': ['id'],
            'properties': {
                'id': {'type': 'string'}
            }
        }
    }],
    'responses': {
        200: {'description': '运行详情'},
        404: {'description': '运行不存在'}
    }
})
def get_run():
    """获取运行详情"""
    try:
        data = request.get_json() or {}
        req = IdRequest(**data)

        repo = get_repo()
        run = repo.get_by_id(req.id, include_events=True)

        if not run:
            return jsonify({'success': False, 'error': '运行记录不存在'}), 404

        return jsonify({
            'success': True,
            'data': run.to_dict(include_events=True)
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
                'id': {'type': 'string', 'description': '运行 ID'}
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

        # 返回 SSE 响应
        return sse_manager.create_response()

    except ValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@runs_bp.route('/cancel', methods=['POST'])
@swag_from({
    'tags': ['Runs'],
    'summary': '取消运行',
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'required': True,
        'schema': {
            'type': 'object',
            'required': ['id'],
            'properties': {
                'id': {'type': 'string'}
            }
        }
    }],
    'responses': {
        200: {'description': '取消成功'},
        400: {'description': '运行无法取消'},
        404: {'description': '运行不存在'}
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
    'description': '''获取运行的所有事件记录（非流式）。

返回的事件结构与 SSE 流式事件一致，包含完整的事件历史。

## 事件结构

每个事件包含以下字段:
- `id`: 事件唯一标识
- `run_id`: 所属运行 ID
- `timestamp`: 事件时间戳 (ISO 8601)
- `sequence`: 序列号 (用于排序)
- `source`: 来源信息 (agent_id, agent_type, agent_name, team_name)
- `event`: 事件类型 (category, action)
- `data`: 事件数据
''',
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'required': True,
        'schema': {
            'type': 'object',
            'required': ['id'],
            'properties': {
                'id': {'type': 'string', 'description': '运行 ID'}
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
                            'run_id': {'type': 'string'},
                            'status': {'type': 'string', 'enum': ['pending', 'running', 'completed', 'failed', 'cancelled']},
                            'events': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'id': {'type': 'string'},
                                        'run_id': {'type': 'string'},
                                        'timestamp': {'type': 'string', 'format': 'date-time'},
                                        'sequence': {'type': 'integer'},
                                        'source': {
                                            'type': 'object',
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
                            }
                        }
                    }
                }
            }
        },
        404: {'description': '运行不存在'}
    }
})
def get_run_events():
    """获取运行事件列表"""
    try:
        data = request.get_json() or {}
        req = IdRequest(**data)

        repo = get_repo()
        run = repo.get_by_id(req.id)

        if not run:
            return jsonify({'success': False, 'error': '运行记录不存在'}), 404

        events = repo.get_events(req.id)

        return jsonify({
            'success': True,
            'data': {
                'run_id': req.id,
                'status': run.status,
                'events': [e.to_dict() for e in events]
            }
        })
    except ValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
