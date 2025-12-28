<!--
Sync Impact Report
==================
Version change: 1.2.0 → 1.3.0
Modified principles:
  - Added VII. Database Table Naming Convention (NON-NEGOTIABLE)
Added sections: Database Table Naming Convention
Removed sections: None
Templates requiring updates:
  - .specify/templates/plan-template.md: ✅ compatible
  - .specify/templates/spec-template.md: ✅ compatible
  - .specify/templates/tasks-template.md: ✅ compatible
Follow-up TODOs: None
-->

# Op-Stack Executor Constitution

## Core Principles

### I. URL Namespace Convention (NON-NEGOTIABLE)

All business-related HTTP API endpoints MUST follow this URL pattern:

```
/api/executor/v{version}/{resource}/{action}
```

**Rules:**
- Business APIs MUST use prefix `/api/executor/` followed by version number (e.g., `/api/executor/v1/`)
- System endpoints (health check, swagger, metrics) are EXCLUDED from this rule
- Legacy compatibility endpoints (e.g., `/execute`) may remain but MUST NOT be the primary interface
- Version numbers follow semantic versioning: `v1`, `v2`, etc.

**Rationale:** Consistent URL namespacing enables clear service identification in microservice architectures, simplifies API gateway routing, and prevents endpoint collisions across the op-stack ecosystem.

**Examples:**
- `POST /api/executor/v1/models/list` - List AI models
- `POST /api/executor/v1/hierarchies/create` - Create hierarchy team
- `POST /api/executor/v1/runs/start` - Start execution run
- `GET /health` - Health check (system endpoint, exempt)
- `GET /swagger` - API documentation (system endpoint, exempt)

### II. RESTful API Design

All API endpoints MUST follow RESTful conventions with POST-based operations for complex queries.

**Rules:**
- Resource-oriented endpoint design: `/{resource}/{action}`
- Use POST for all business operations (supports complex request bodies)
- Request/Response MUST use JSON format with `Content-Type: application/json`
- Response MUST include `success` boolean field and structured `data` or `error` fields

**Standard Response Format:**
```json
{
  "success": true,
  "message": "Operation description",
  "data": { ... }
}
```

**Error Response Format:**
```json
{
  "success": false,
  "error": "Error description",
  "code": 400001
}
```

**Pagination Request Format (NON-NEGOTIABLE):**
```json
{
  "page": 1,
  "size": 20,
  "tenantId": null,
  "traceId": null,
  "userId": null
}
```
- `page`: 页码（从 1 开始），默认 1，最小 1
- `size`: 每页大小，默认 20，范围 1-100
- `tenantId`, `traceId`, `userId`: 网关注入字段（hidden）

**Pagination Response Format (NON-NEGOTIABLE):**
```json
{
  "code": 0,
  "message": "success",
  "success": true,
  "data": {
    "content": [],
    "page": 1,
    "size": 10,
    "totalElements": 100,
    "totalPages": 10,
    "first": true,
    "last": false
  }
}
```
- `content`: 数据列表
- `page`: 当前页码（从 1 开始）
- `size`: 每页大小
- `totalElements`: 总记录数
- `totalPages`: 总页数
- `first`: 是否为第一页
- `last`: 是否为最后一页

### III. Hierarchical Agent Architecture

The system MUST maintain strict hierarchical delegation:

**Rules:**
- Global Supervisor → Team Supervisor → Worker Agent hierarchy MUST be preserved
- Supervisors MUST delegate tasks; they MUST NOT directly answer user queries
- Each agent level MUST have clearly defined responsibilities
- Output MUST be clearly labeled with agent identity (e.g., `[Global Supervisor]`, `[Team: X | Worker: Y]`)

**Rationale:** Clear hierarchy ensures predictable task flow, enables proper context sharing, and maintains system observability.

### IV. Streaming & Real-time Events

All long-running operations MUST support Server-Sent Events (SSE) for real-time updates.

**Rules:**
- Execution runs MUST emit events via SSE stream
- Events MUST include `event_type` and `data` fields
- Event types MUST be documented and consistent
- Clients MUST be able to poll for status as fallback

**Rationale:** Real-time feedback is essential for multi-agent systems where operations may take extended time.

### V. Database Agnosticism

The system MUST support multiple database backends without code changes.

**Rules:**
- Database configuration via environment variables: `DB_TYPE`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- Supported databases: PostgreSQL, MySQL
- ORM (SQLAlchemy) MUST be used for all database operations
- Direct SQL queries are PROHIBITED except for migrations

**Rationale:** Deployment flexibility across different infrastructure environments.

### VI. Server Configuration (NON-NEGOTIABLE)

Development environment server configuration MUST be fixed and controlled via configuration file, NOT environment variables.

**Rules:**
- Development server port MUST be `8082` - 禁止修改
- Server host MUST be `0.0.0.0`
- Debug mode MUST be `false` in production
- Port configuration MUST be defined in `src/core/config.py` as class constants
- Environment variables MUST NOT override server port configuration

**Configuration Location:**
```python
# src/core/config.py
class Config:
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8082  # 开发环境固定端口，禁止修改
    DEBUG_MODE: bool = False
```

**Rationale:** Fixed port configuration prevents port conflicts in development environments and ensures consistent service discovery across the team. Environment variable overrides are prohibited to maintain deployment consistency.

**Violations:**
- Using `os.environ.get('PORT')` for server port - PROHIBITED
- Hardcoding different port values - PROHIBITED
- Adding command-line arguments for port - PROHIBITED

### VII. Database Table Naming Convention (NON-NEGOTIABLE)

Database table names MUST use **singular form**, NOT plural.

**Rules:**
- Table names MUST be singular (e.g., `ai_model`, NOT `ai_models`)
- Use snake_case for table names
- Table name should match the entity it represents
- Exceptions require explicit justification in code comments

**Standard Table Names:**
| Entity | Table Name | ~~Prohibited~~ |
|--------|------------|----------------|
| AI Model | `ai_model` | ~~ai_models~~ |
| Hierarchy Team | `hierarchy_team` | ~~hierarchy_teams~~ |
| Team | `team` | ~~teams~~ |
| Worker | `worker` | ~~workers~~ |
| Execution Run | `execution_run` | ~~execution_runs~~ |
| Execution Event | `execution_event` | ~~execution_events~~ |

**Rationale:** Singular table names align with ORM entity class naming conventions, improve code readability, and maintain consistency with Spring/Java ecosystem conventions used in op-stack-service.

**Violations:**
- Using plural table names (e.g., `users`, `orders`) - PROHIBITED
- Inconsistent naming within the same project - PROHIBITED

## API Standards

### Endpoint Categories

| Category | URL Pattern | Method | Example |
|----------|-------------|--------|---------|
| Business API | `/api/executor/v1/{resource}/{action}` | POST | `/api/executor/v1/runs/start` |
| Health Check | `/health` | GET | System status |
| Documentation | `/swagger` | GET | Swagger UI |
| Legacy | `/execute` | POST | Backward compatibility only |

### Authentication

Support three authentication modes (priority order):
1. API Key: `AWS_BEDROCK_API_KEY`
2. AK/SK: `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`
3. IAM Role: `USE_IAM_ROLE=true`

## Development Workflow

### Code Changes

1. All API endpoint changes MUST update corresponding documentation (README.md, docs/)
2. URL pattern changes MUST update all test scripts (`test_stream.py`, `test_stream_raw.py`)
3. Breaking API changes MUST increment the API version number

### Testing Requirements

- API endpoint changes require manual testing with `curl` or test scripts
- Stream functionality MUST be tested with `test_stream.py`
- Database compatibility MUST be verified with both PostgreSQL and MySQL

## Governance

This constitution establishes the foundational rules for the op-stack-executor project. All development decisions MUST align with these principles.

**Amendment Process:**
1. Propose changes via pull request with justification
2. Document impact on existing endpoints/functionality
3. Update all affected documentation and test files
4. Version bump according to change severity

**Compliance:**
- All PRs MUST verify compliance with URL namespace convention
- Code review MUST check API response format consistency
- Violations require explicit justification in PR description

**Version**: 1.3.0 | **Ratified**: 2025-12-27 | **Last Amended**: 2025-12-28
