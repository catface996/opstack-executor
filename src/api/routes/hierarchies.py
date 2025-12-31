"""
Hierarchies Routes - 层级团队管理路由
"""

from flask import Blueprint, request, jsonify
from flasgger import swag_from
from pydantic import ValidationError

from ..schemas.hierarchy_schemas import (
    HierarchyCreateRequest, HierarchyUpdateRequest, HierarchyListRequest
)
from ..schemas.common import IdRequest, build_page_response
from ...db.database import get_db_session
from ...db.repositories import HierarchyRepository
from ...db.repositories.hierarchy_repo import check_agent_ids_unique_in_hierarchy


hierarchies_bp = Blueprint('hierarchies', __name__)


def get_repo():
    """获取层级团队仓库"""
    return HierarchyRepository(get_db_session())


@hierarchies_bp.route('/list', methods=['POST'])
@swag_from({
    'tags': ['Hierarchies'],
    'summary': '获取层级团队列表',
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'required': True,
        'schema': {
            'type': 'object',
            'properties': {
                'page': {'type': 'integer', 'default': 1},
                'size': {'type': 'integer', 'default': 20},
                'is_active': {'type': 'boolean'}
            }
        }
    }],
    'responses': {
        200: {'description': '层级团队列表'}
    }
})
def list_hierarchies():
    """获取层级团队列表"""
    try:
        data = request.get_json() or {}
        req = HierarchyListRequest(**data)

        repo = get_repo()
        hierarchies, total = repo.list(
            page=req.page,
            size=req.size,
            is_active=req.is_active
        )

        # 返回简化的列表项
        content = []
        for h in hierarchies:
            config = h.config or {}
            item = {
                'id': h.id,
                'name': h.name,
                'description': h.description,
                'execution_mode': config.get('execution_mode', 'sequential'),
                'team_count': len(config.get('teams', [])),
                'is_active': h.is_active,
                'version': h.version,
                'created_at': h.created_at.isoformat() if h.created_at else None,
                'updated_at': h.updated_at.isoformat() if h.updated_at else None,
            }
            content.append(item)

        return jsonify(build_page_response(
            content=content,
            page=req.page,
            size=req.size,
            total=total
        ))
    except ValidationError as e:
        return jsonify({'code': 400, 'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'code': 500, 'success': False, 'error': str(e)}), 500


@hierarchies_bp.route('/get', methods=['POST'])
@swag_from({
    'tags': ['Hierarchies'],
    'summary': '获取层级团队详情',
    'description': '获取完整的层级团队配置',
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
        200: {'description': '层级团队详情'},
        404: {'description': '层级团队不存在'}
    }
})
def get_hierarchy():
    """获取层级团队详情"""
    try:
        data = request.get_json() or {}
        req = IdRequest(**data)

        repo = get_repo()
        hierarchy = repo.get_by_id(req.id)

        if not hierarchy:
            return jsonify({'success': False, 'error': '层级团队不存在'}), 404

        return jsonify({
            'success': True,
            'data': hierarchy.to_dict()
        })
    except ValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@hierarchies_bp.route('/create', methods=['POST'])
@swag_from({
    'tags': ['Hierarchies'],
    'summary': '创建层级团队',
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'required': True,
        'schema': {
            'type': 'object',
            'required': ['name', 'global_supervisor_agent', 'teams'],
            'properties': {
                'name': {'type': 'string'},
                'description': {'type': 'string'},
                'execution_mode': {'type': 'string', 'enum': ['sequential', 'parallel']},
                'enable_context_sharing': {'type': 'boolean'},
                'global_supervisor_agent': {
                    'type': 'object',
                    'required': ['system_prompt'],
                    'properties': {
                        'agent_id': {'type': 'string'},
                        'system_prompt': {'type': 'string'},
                        'user_message': {'type': 'string'},
                        'llm_config': {'type': 'object'}
                    }
                },
                'teams': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'required': ['name', 'team_supervisor_agent', 'workers'],
                        'properties': {
                            'name': {'type': 'string'},
                            'team_supervisor_agent': {
                                'type': 'object',
                                'required': ['system_prompt'],
                                'properties': {
                                    'agent_id': {'type': 'string'},
                                    'system_prompt': {'type': 'string'},
                                    'user_message': {'type': 'string'},
                                    'llm_config': {'type': 'object'}
                                }
                            },
                            'prevent_duplicate': {'type': 'boolean'},
                            'share_context': {'type': 'boolean'},
                            'workers': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'required': ['name', 'role', 'system_prompt'],
                                    'properties': {
                                        'agent_id': {'type': 'string'},
                                        'name': {'type': 'string'},
                                        'role': {'type': 'string'},
                                        'system_prompt': {'type': 'string'},
                                        'user_message': {'type': 'string'},
                                        'tools': {'type': 'array'},
                                        'llm_config': {'type': 'object'}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }],
    'responses': {
        200: {'description': '创建成功'},
        400: {'description': '请求无效'}
    }
})
def create_hierarchy():
    """创建层级团队"""
    try:
        data = request.get_json() or {}
        req = HierarchyCreateRequest(**data)

        repo = get_repo()

        # 检查名称是否重复
        if repo.get_by_name(req.name):
            return jsonify({'success': False, 'error': f'层级团队名称 "{req.name}" 已存在'}), 400

        # 构建 config JSON
        config = {
            'execution_mode': req.execution_mode,
            'enable_context_sharing': req.enable_context_sharing,
            'global_supervisor_agent': req.global_supervisor_agent.model_dump(),
            'teams': [team.model_dump() for team in req.teams]
        }

        # 验证 agent_id 唯一性
        is_unique, duplicate_id = check_agent_ids_unique_in_hierarchy(config)
        if not is_unique:
            return jsonify({
                'success': False,
                'error': f"agent_id '{duplicate_id}' is duplicated within this hierarchy",
                'code': 400001
            }), 400

        # 创建 Hierarchy
        hierarchy = repo.create(
            name=req.name,
            description=req.description,
            config=config
        )

        return jsonify({
            'success': True,
            'message': '层级团队创建成功',
            'data': hierarchy.to_dict()
        })
    except ValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@hierarchies_bp.route('/update', methods=['POST'])
@swag_from({
    'tags': ['Hierarchies'],
    'summary': '更新层级团队',
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'required': True,
        'schema': {
            'type': 'object',
            'required': ['id'],
            'properties': {
                'id': {'type': 'string'},
                'name': {'type': 'string'},
                'description': {'type': 'string'},
                'execution_mode': {'type': 'string'},
                'enable_context_sharing': {'type': 'boolean'},
                'global_supervisor_agent': {'type': 'object'},
                'teams': {'type': 'array'},
                'is_active': {'type': 'boolean'}
            }
        }
    }],
    'responses': {
        200: {'description': '更新成功'},
        404: {'description': '层级团队不存在'}
    }
})
def update_hierarchy():
    """更新层级团队"""
    try:
        data = request.get_json() or {}
        req = HierarchyUpdateRequest(**data)

        repo = get_repo()

        # 检查名称是否与其他层级重复
        if req.name:
            existing = repo.get_by_name(req.name)
            if existing and existing.id != req.id:
                return jsonify({'success': False, 'error': f'层级团队名称 "{req.name}" 已存在'}), 400

        # 构建更新数据
        update_data = {}
        if req.name:
            update_data['name'] = req.name
        if req.description is not None:
            update_data['description'] = req.description
        if req.is_active is not None:
            update_data['is_active'] = req.is_active

        # 如果有配置更新，构建新的 config
        if req.global_supervisor_agent or req.teams or req.execution_mode or req.enable_context_sharing is not None:
            # 获取现有配置
            hierarchy = repo.get_by_id(req.id)
            if not hierarchy:
                return jsonify({'success': False, 'error': '层级团队不存在'}), 404

            config = hierarchy.config.copy() if hierarchy.config else {}

            if req.execution_mode:
                config['execution_mode'] = req.execution_mode
            if req.enable_context_sharing is not None:
                config['enable_context_sharing'] = req.enable_context_sharing
            if req.global_supervisor_agent:
                config['global_supervisor_agent'] = req.global_supervisor_agent.model_dump()
            if req.teams:
                config['teams'] = [team.model_dump() for team in req.teams]

            # 验证 agent_id 唯一性
            is_unique, duplicate_id = check_agent_ids_unique_in_hierarchy(config)
            if not is_unique:
                return jsonify({
                    'success': False,
                    'error': f"agent_id '{duplicate_id}' is duplicated within this hierarchy",
                    'code': 400001
                }), 400

            update_data['config'] = config

        hierarchy = repo.update(req.id, update_data)

        if not hierarchy:
            return jsonify({'success': False, 'error': '层级团队不存在'}), 404

        return jsonify({
            'success': True,
            'message': '层级团队更新成功',
            'data': hierarchy.to_dict()
        })
    except ValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@hierarchies_bp.route('/delete', methods=['POST'])
@swag_from({
    'tags': ['Hierarchies'],
    'summary': '删除层级团队',
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
        200: {'description': '删除成功'},
        404: {'description': '层级团队不存在'}
    }
})
def delete_hierarchy():
    """删除层级团队"""
    try:
        data = request.get_json() or {}
        req = IdRequest(**data)

        repo = get_repo()
        success = repo.delete(req.id)

        if not success:
            return jsonify({'success': False, 'error': '层级团队不存在'}), 404

        return jsonify({
            'success': True,
            'message': '层级团队删除成功'
        })
    except ValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
