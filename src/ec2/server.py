"""
Standalone HTTP Server - 独立的 HTTP 服务器应用

支持在 EC2 实例上独立运行的 HTTP 服务器
提供完整的 API 接口，包括模型管理、层级团队管理、运行管理
"""

import os
from flask import Flask, jsonify
from flask_cors import CORS
from flasgger import Swagger


def convert_paths_to_openapi3(swagger_paths: dict) -> dict:
    """
    将 Swagger 2.0 的 paths 转换为 OpenAPI 3.0 格式

    主要转换:
    - parameters[in=body] -> requestBody
    - responses 内容格式调整
    """
    openapi_paths = {}

    for path, methods in swagger_paths.items():
        openapi_paths[path] = {}

        for method, operation in methods.items():
            if method == 'parameters':
                continue

            new_operation = {
                'tags': operation.get('tags', []),
                'summary': operation.get('summary', ''),
                'description': operation.get('description', ''),
                'operationId': operation.get('operationId', ''),
                'security': operation.get('security', [{'Bearer Authentication': []}]),
                'responses': {}
            }

            # 转换 parameters
            params = operation.get('parameters', [])
            path_params = []
            query_params = []
            request_body = None

            for param in params:
                if param.get('in') == 'body':
                    # 转换为 requestBody
                    request_body = {
                        'required': param.get('required', True),
                        'content': {
                            'application/json': {
                                'schema': param.get('schema', {'type': 'object'})
                            }
                        }
                    }
                elif param.get('in') == 'path':
                    path_params.append({
                        'name': param.get('name'),
                        'in': 'path',
                        'required': True,
                        'schema': {'type': param.get('type', 'string')}
                    })
                elif param.get('in') == 'query':
                    query_params.append({
                        'name': param.get('name'),
                        'in': 'query',
                        'required': param.get('required', False),
                        'schema': {'type': param.get('type', 'string')}
                    })

            # 处理已经是 OpenAPI 3.0 格式的 requestBody
            if 'requestBody' in operation:
                request_body = operation['requestBody']

            if request_body:
                new_operation['requestBody'] = request_body

            if path_params or query_params:
                new_operation['parameters'] = path_params + query_params

            # 转换 responses
            for status_code, response in operation.get('responses', {}).items():
                status_str = str(status_code)
                if isinstance(response, dict):
                    new_response = {'description': response.get('description', '')}
                    if 'schema' in response:
                        new_response['content'] = {
                            'application/json': {
                                'schema': response['schema']
                            }
                        }
                    elif 'content' in response:
                        new_response['content'] = response['content']
                    new_operation['responses'][status_str] = new_response
                else:
                    new_operation['responses'][status_str] = {'description': str(response)}

            # 确保至少有一个响应
            if not new_operation['responses']:
                new_operation['responses']['200'] = {'description': '成功'}

            openapi_paths[path][method] = new_operation

    return openapi_paths

# 导入配置管理
from ..core.config import setup_config

# 导入数据库
from ..db.database import init_db

# 导入路由蓝图
from ..api.routes import models_bp, hierarchies_bp, runs_bp, health_bp


def create_app(config_name: str = None) -> Flask:
    """
    应用工厂函数

    Args:
        config_name: 配置名称（可选）

    Returns:
        Flask 应用实例
    """
    app = Flask(__name__)

    # 加载配置
    app.config['DATABASE_URL'] = os.environ.get('DATABASE_URL')
    app.config['DEBUG'] = os.environ.get('DEBUG', 'false').lower() == 'true'

    # 配置 CORS
    CORS(
        app,
        origins='*',
        methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
        allow_headers=['Content-Type', 'Authorization']
    )

    # 配置 Swagger - 内部使用，仅用于收集路由文档
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": 'apispec_internal',
                "route": '/swagger-internal.json',
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/swagger-ui.html"
    }

    # OpenAPI 3.0 模板
    openapi_info = {
        "title": "Op-Stack Executor API",
        "description": """层级多智能体系统执行器 API 文档 - Hierarchical Multi-Agent System Executor

## 功能模块

### AI 模型管理
- **模型配置**: 模型 CRUD、参数配置、状态管理

### 层级团队管理
- **层级团队**: 团队 CRUD、Worker 配置、执行模式设置
- **层级结构**: Global Supervisor → Team Supervisor → Worker Agent

### 运行管理
- **运行执行**: 启动运行、流式事件、状态查询、取消运行
- **事件流**: SSE 实时事件推送

## 认证方式

需要在请求头中携带 Bearer Token：
```
Authorization: Bearer <token>
```
""",
        "version": "1.0.0",
        "contact": {
            "name": "Op-Stack Team",
            "email": "opstack@example.com",
            "url": "https://github.com/catface996/opstack-executor"
        },
        "license": {
            "name": "Apache 2.0",
            "url": "https://www.apache.org/licenses/LICENSE-2.0"
        }
    }

    swagger_template = {
        "swagger": "2.0",
        "info": openapi_info,
        "tags": [
            {"name": "Health", "description": "健康检查接口"},
            {"name": "Models", "description": "AI 模型管理接口：创建、查询、更新、删除（POST-Only API）"},
            {"name": "Hierarchies", "description": "层级团队管理接口：创建、查询、更新、删除（POST-Only API）"},
            {"name": "Runs", "description": "运行管理接口：启动、查询、流式事件、取消（POST-Only API）"}
        ],
        "securityDefinitions": {
            "Bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "JWT 认证，格式: Bearer <token>"
            }
        },
        "security": [{"Bearer": []}]
    }

    swagger = Swagger(app, config=swagger_config, template=swagger_template)

    # 添加纯 OpenAPI 3.0 端点
    @app.route('/v3/api-docs', methods=['GET'])
    def openapi_docs():
        """返回纯 OpenAPI 3.0 格式的 API 文档"""
        import requests
        from ..core.config import Config

        # 从内部 Swagger 端点获取生成的 spec
        try:
            # 直接从内部端点获取 spec（使用配置中的固定端口）
            internal_url = f"http://127.0.0.1:{Config.SERVER_PORT}/swagger-internal.json"
            resp = requests.get(internal_url, timeout=5)
            spec = resp.json()
        except Exception:
            # 如果获取失败，使用空 paths
            spec = {"paths": {}, "tags": swagger_template.get("tags", [])}

        # 转换为 OpenAPI 3.0 格式
        openapi_spec = {
            "openapi": "3.0.3",
            "info": openapi_info,
            "servers": [
                {"url": "http://localhost:7070", "description": "本地开发环境"},
                {"url": "http://localhost:8080", "description": "本地 Docker 环境"},
                {"url": "https://api.executor.example.com", "description": "生产环境"}
            ],
            "tags": spec.get("tags", []),
            "paths": convert_paths_to_openapi3(spec.get("paths", {})),
            "components": {
                "securitySchemes": {
                    "Bearer Authentication": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT",
                        "description": "JWT 认证，请填入有效的 Token"
                    }
                },
                "schemas": {
                    "SuccessResponse": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "message": {"type": "string", "example": "操作成功"},
                            "data": {"type": "object"}
                        }
                    },
                    "ErrorResponse": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": False},
                            "error": {"type": "string", "example": "错误描述"},
                            "code": {"type": "integer", "example": 400001}
                        }
                    },
                    "PageResult": {
                        "type": "object",
                        "properties": {
                            "items": {"type": "array", "items": {"type": "object"}},
                            "total": {"type": "integer", "example": 100},
                            "page": {"type": "integer", "example": 1},
                            "size": {"type": "integer", "example": 20},
                            "pages": {"type": "integer", "example": 5}
                        }
                    }
                }
            },
            "security": [{"Bearer Authentication": []}]
        }

        return jsonify(openapi_spec)

    # 初始化数据库
    db = init_db(app)

    # 注册请求结束时的会话清理
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """每个请求结束后清理数据库会话"""
        if db:
            db.remove()

    # 初始化配置（AWS 认证等）
    try:
        setup_config()
    except Exception as e:
        print(f"Warning: Configuration error: {e}")

    # 注册蓝图
    app.register_blueprint(health_bp)  # /health, /
    app.register_blueprint(models_bp, url_prefix='/api/executor/v1/models')
    app.register_blueprint(hierarchies_bp, url_prefix='/api/executor/v1/hierarchies')
    app.register_blueprint(runs_bp, url_prefix='/api/executor/v1/runs')

    # 保留旧的 /execute 端点（向后兼容）
    register_legacy_routes(app)

    # 错误处理
    register_error_handlers(app)

    return app


def register_legacy_routes(app: Flask):
    """注册向后兼容的旧路由"""
    import traceback
    from flask import request
    from ..core.api_models import ErrorResponse
    # 注意: execute_hierarchy 延迟导入到 execute() 函数中以避免 strands 依赖检查

    def _validate_request(body):
        # Support both old format (global_prompt) and new format (global_supervisor_agent)
        has_global_prompt = 'global_prompt' in body
        has_global_agent = 'global_supervisor_agent' in body and isinstance(body.get('global_supervisor_agent'), dict)
        if not has_global_prompt and not has_global_agent:
            return "Missing required field: 'global_prompt' or 'global_supervisor_agent.system_prompt'"
        if has_global_agent and 'system_prompt' not in body['global_supervisor_agent']:
            return "Missing required field: 'global_supervisor_agent.system_prompt'"

        if 'teams' not in body:
            return "Missing required field: 'teams'"
        if 'task' not in body:
            return "Missing required field: 'task'"
        if not isinstance(body['teams'], list):
            return "Field 'teams' must be a list"
        if len(body['teams']) == 0:
            return "At least one team is required"

        for i, team in enumerate(body['teams']):
            if 'name' not in team:
                return f"Team {i}: Missing required field 'name'"
            if 'workers' not in team:
                return f"Team {i}: Missing required field 'workers'"

            # Support both old format (supervisor_prompt) and new format (team_supervisor_agent)
            has_supervisor_prompt = 'supervisor_prompt' in team
            has_team_agent = 'team_supervisor_agent' in team and isinstance(team.get('team_supervisor_agent'), dict)
            if not has_supervisor_prompt and not has_team_agent:
                return f"Team {i}: Missing required field 'supervisor_prompt' or 'team_supervisor_agent.system_prompt'"
            if has_team_agent and 'system_prompt' not in team['team_supervisor_agent']:
                return f"Team {i}: Missing required field 'team_supervisor_agent.system_prompt'"

            if not isinstance(team['workers'], list):
                return f"Team {i}: Field 'workers' must be a list"
            if len(team['workers']) == 0:
                return f"Team {i}: At least one worker is required"
            for j, worker in enumerate(team['workers']):
                worker_required = ['name', 'role', 'system_prompt']
                for field in worker_required:
                    if field not in worker:
                        return f"Team {i}, Worker {j}: Missing required field '{field}'"
        return None

    @app.route('/execute', methods=['POST'])
    def execute():
        """旧版执行端点（向后兼容）"""
        # 延迟导入 - 需要 strands 依赖
        from ..core.hierarchy_executor import execute_hierarchy

        try:
            if not request.is_json:
                return jsonify({'error': 'Content-Type must be application/json'}), 400

            body = request.get_json()
            validation_error = _validate_request(body)
            if validation_error:
                return jsonify({'error': validation_error}), 400

            response = execute_hierarchy(body)
            return jsonify(response.to_dict()), 200

        except Exception as e:
            error_msg = str(e)
            error_details = traceback.format_exc()
            print(f"Error: {error_msg}")
            print(f"Details: {error_details}")

            error_response = ErrorResponse(
                error=error_msg,
                details=error_details if os.environ.get('DEBUG') == 'true' else None
            )
            return jsonify(error_response.to_dict()), 500


def register_error_handlers(app: Flask):
    """注册错误处理器"""

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'error': 'Endpoint not found',
            'available_endpoints': {
                'swagger_ui': '/swagger-ui.html',
                'openapi_json': '/v3/api-docs',
                'health': '/health',
                'models': '/api/executor/v1/models/*',
                'hierarchies': '/api/executor/v1/hierarchies/*',
                'runs': '/api/executor/v1/runs/*',
                'legacy_execute': '/execute'
            }
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            'success': False,
            'error': 'Method not allowed',
            'hint': 'All API endpoints use POST method'
        }), 405

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(error) if os.environ.get('DEBUG') == 'true' else None
        }), 500


# 创建默认应用实例
app = create_app()


def initialize_server():
    """初始化服务器配置"""
    print("=" * 80)
    print("Op-Stack Executor HTTP Server v1.0.0")
    print("=" * 80)
    print("\nAPI Endpoints:")
    print("  Swagger UI:    GET  /swagger-ui.html")
    print("  OpenAPI JSON:  GET  /v3/api-docs")
    print("  Health:        GET  /health")
    print("  Models:        POST /api/executor/v1/models/{list,get,create,update,delete}")
    print("  Hierarchies:   POST /api/executor/v1/hierarchies/{list,get,create,update,delete}")
    print("  Runs:          POST /api/executor/v1/runs/{start,list,get,stream,cancel,events}")
    print("  Legacy:        POST /execute (backward compatible)")
    print("=" * 80)


def main():
    """主函数 - 启动 HTTP 服务器"""
    from ..core.config import Config

    initialize_server()

    # 使用配置类中的固定值（NON-NEGOTIABLE，禁止通过环境变量修改）
    port = Config.SERVER_PORT
    host = Config.SERVER_HOST
    debug = Config.DEBUG_MODE

    print(f"\nStarting server on {host}:{port}")
    print(f"Debug mode: {debug}")
    print(f"Swagger UI: http://{host}:{port}/swagger-ui.html")
    print(f"OpenAPI JSON: http://{host}:{port}/v3/api-docs")
    print(f"\nPress Ctrl+C to stop the server\n")

    app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True
    )


if __name__ == '__main__':
    main()
