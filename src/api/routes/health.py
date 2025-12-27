"""
Health Routes - 健康检查路由
"""

from flask import Blueprint, jsonify
from flasgger import swag_from

health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
@swag_from({
    'tags': ['Health'],
    'summary': '健康检查',
    'description': '检查服务是否正常运行',
    'responses': {
        200: {
            'description': '服务正常',
            'schema': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'example': 'healthy'},
                    'service': {'type': 'string', 'example': 'hierarchical-agents-api'},
                    'version': {'type': 'string', 'example': '2.0.0'}
                }
            }
        }
    }
})
def health_check():
    """健康检查"""
    return jsonify({
        'status': 'healthy',
        'service': 'hierarchical-agents-api',
        'version': '2.0.0'
    })


@health_bp.route('/', methods=['GET'])
@swag_from({
    'tags': ['Health'],
    'summary': 'API 信息',
    'description': '获取 API 基本信息',
    'responses': {
        200: {
            'description': 'API 信息'
        }
    }
})
def api_info():
    """API 信息"""
    return jsonify({
        'name': 'Hierarchical Agents API',
        'version': '2.0.0',
        'description': '层级多智能体系统 API',
        'endpoints': {
            'health': '/health',
            'swagger': '/swagger',
            'models': '/api/executor/v1/models/*',
            'hierarchies': '/api/executor/v1/hierarchies/*',
            'runs': '/api/executor/v1/runs/*'
        }
    })
