"""
Models Routes - AI 模型管理路由
"""

from flask import Blueprint, request, jsonify
from flasgger import swag_from
from pydantic import ValidationError

from ..schemas.model_schemas import (
    ModelCreateRequest, ModelUpdateRequest, ModelListRequest
)
from ..schemas.common import IdRequest, build_page_response
from ...db.database import get_db_session
from ...db.repositories import ModelRepository

models_bp = Blueprint('models', __name__)


def get_repo():
    """获取模型仓库"""
    return ModelRepository(get_db_session())


@models_bp.route('/list', methods=['POST'])
@swag_from({
    'tags': ['Models'],
    'summary': '获取模型列表',
    'description': '分页获取 AI 模型配置列表，支持按状态筛选',
    'security': [{'Bearer Authentication': []}],
    'requestBody': {
        'required': True,
        'content': {
            'application/json': {
                'schema': {
                    'type': 'object',
                    'properties': {
                        'page': {'type': 'integer', 'default': 1, 'description': '页码'},
                        'size': {'type': 'integer', 'default': 20, 'description': '每页数量'},
                        'is_active': {'type': 'boolean', 'description': '是否激活'}
                    }
                }
            }
        }
    },
    'responses': {
        '200': {
            'description': '查询成功',
            'content': {
                'application/json': {
                    'schema': {'$ref': '#/components/schemas/PageResult'}
                }
            }
        },
        '401': {'description': '未认证'},
        '500': {'description': '服务器错误'}
    }
})
def list_models():
    """获取模型列表"""
    try:
        data = request.get_json() or {}
        req = ModelListRequest(**data)

        repo = get_repo()
        models, total = repo.list(
            page=req.page,
            size=req.size,
            is_active=req.is_active
        )

        return jsonify(build_page_response(
            content=[m.to_dict() for m in models],
            page=req.page,
            size=req.size,
            total=total
        ))
    except ValidationError as e:
        return jsonify({'code': 400, 'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'code': 500, 'success': False, 'error': str(e)}), 500


@models_bp.route('/get', methods=['POST'])
@swag_from({
    'tags': ['Models'],
    'summary': '获取模型详情',
    'description': '根据ID获取模型详细信息',
    'security': [{'Bearer Authentication': []}],
    'requestBody': {
        'required': True,
        'content': {
            'application/json': {
                'schema': {
                    'type': 'object',
                    'required': ['id'],
                    'properties': {
                        'id': {'type': 'string', 'description': '模型ID'}
                    }
                }
            }
        }
    },
    'responses': {
        '200': {'description': '查询成功'},
        '401': {'description': '未认证'},
        '404': {'description': '模型不存在'}
    }
})
def get_model():
    """获取模型详情"""
    try:
        data = request.get_json() or {}
        req = IdRequest(**data)

        repo = get_repo()
        model = repo.get_by_id(req.id)

        if not model:
            return jsonify({'success': False, 'error': '模型不存在'}), 404

        return jsonify({
            'success': True,
            'data': model.to_dict()
        })
    except ValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@models_bp.route('/create', methods=['POST'])
@swag_from({
    'tags': ['Models'],
    'summary': '创建模型',
    'description': '创建新的 AI 模型配置',
    'security': [{'Bearer Authentication': []}],
    'requestBody': {
        'required': True,
        'content': {
            'application/json': {
                'schema': {
                    'type': 'object',
                    'required': ['name', 'model_id'],
                    'properties': {
                        'name': {'type': 'string', 'description': '模型名称'},
                        'model_id': {'type': 'string', 'description': 'AWS Bedrock 模型ID'},
                        'region': {'type': 'string', 'default': 'us-east-1', 'description': 'AWS 区域'},
                        'temperature': {'type': 'number', 'default': 0.7, 'description': '温度参数'},
                        'max_tokens': {'type': 'integer', 'default': 2048, 'description': '最大Token数'},
                        'top_p': {'type': 'number', 'default': 0.9, 'description': 'Top-P 参数'},
                        'description': {'type': 'string', 'description': '模型描述'},
                        'is_active': {'type': 'boolean', 'default': True, 'description': '是否激活'}
                    }
                }
            }
        }
    },
    'responses': {
        '201': {'description': '创建成功'},
        '400': {'description': '参数无效'},
        '401': {'description': '未认证'},
        '409': {'description': '模型名称已存在'}
    }
})
def create_model():
    """创建模型"""
    try:
        data = request.get_json() or {}
        req = ModelCreateRequest(**data)

        repo = get_repo()

        # 检查名称是否重复
        if repo.get_by_name(req.name):
            return jsonify({'success': False, 'error': f'模型名称 "{req.name}" 已存在'}), 400

        model = repo.create(req.model_dump())

        return jsonify({
            'success': True,
            'message': '模型创建成功',
            'data': model.to_dict()
        })
    except ValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@models_bp.route('/update', methods=['POST'])
@swag_from({
    'tags': ['Models'],
    'summary': '更新模型',
    'description': '更新模型配置信息',
    'security': [{'Bearer Authentication': []}],
    'requestBody': {
        'required': True,
        'content': {
            'application/json': {
                'schema': {
                    'type': 'object',
                    'required': ['id'],
                    'properties': {
                        'id': {'type': 'string', 'description': '模型ID'},
                        'name': {'type': 'string', 'description': '模型名称'},
                        'model_id': {'type': 'string', 'description': 'AWS Bedrock 模型ID'},
                        'region': {'type': 'string', 'description': 'AWS 区域'},
                        'temperature': {'type': 'number', 'description': '温度参数'},
                        'max_tokens': {'type': 'integer', 'description': '最大Token数'},
                        'top_p': {'type': 'number', 'description': 'Top-P 参数'},
                        'description': {'type': 'string', 'description': '模型描述'},
                        'is_active': {'type': 'boolean', 'description': '是否激活'}
                    }
                }
            }
        }
    },
    'responses': {
        '200': {'description': '更新成功'},
        '400': {'description': '参数无效'},
        '401': {'description': '未认证'},
        '404': {'description': '模型不存在'},
        '409': {'description': '模型名称已存在'}
    }
})
def update_model():
    """更新模型"""
    try:
        data = request.get_json() or {}
        req = ModelUpdateRequest(**data)

        repo = get_repo()

        # 过滤掉 None 值
        update_data = {k: v for k, v in req.model_dump().items() if v is not None and k != 'id'}

        # 检查名称是否与其他模型重复
        if 'name' in update_data:
            existing = repo.get_by_name(update_data['name'])
            if existing and existing.id != req.id:
                return jsonify({'success': False, 'error': f'模型名称 "{update_data["name"]}" 已存在'}), 400

        model = repo.update(req.id, update_data)

        if not model:
            return jsonify({'success': False, 'error': '模型不存在'}), 404

        return jsonify({
            'success': True,
            'message': '模型更新成功',
            'data': model.to_dict()
        })
    except ValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@models_bp.route('/delete', methods=['POST'])
@swag_from({
    'tags': ['Models'],
    'summary': '删除模型',
    'description': '删除指定的模型配置',
    'security': [{'Bearer Authentication': []}],
    'requestBody': {
        'required': True,
        'content': {
            'application/json': {
                'schema': {
                    'type': 'object',
                    'required': ['id'],
                    'properties': {
                        'id': {'type': 'string', 'description': '模型ID'}
                    }
                }
            }
        }
    },
    'responses': {
        '200': {'description': '删除成功'},
        '401': {'description': '未认证'},
        '404': {'description': '模型不存在'}
    }
})
def delete_model():
    """删除模型"""
    try:
        data = request.get_json() or {}
        req = IdRequest(**data)

        repo = get_repo()
        success = repo.delete(req.id)

        if not success:
            return jsonify({'success': False, 'error': '模型不存在'}), 404

        return jsonify({
            'success': True,
            'message': '模型删除成功'
        })
    except ValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
