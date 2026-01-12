# Op-Stack Executor Project Constitution

## Database

### Database Type: MySQL

- **Must use MySQL** as the database engine
- **Do NOT use PostgreSQL** or SQLite in this project
- Local development uses Docker MySQL container

### Local Development Database Configuration

```bash
# Docker MySQL container
Host: localhost
Port: 3306
User: root
Password: root123
Database: aiops_local

# Connection URL format
DATABASE_URL="mysql+pymysql://root:root123@localhost:3306/aiops_local"
```

### Why MySQL

1. Production environment uses AWS RDS MySQL
2. Keep consistency between development and production
3. MySQL is the standard database for the op-stack ecosystem

---

## Redis (Event Streaming)

### Redis Type: Redis Stream

- **Must use Redis** for real-time event streaming and persistence
- Events are stored in Redis Stream with automatic TTL (24 hours)
- Local development uses Docker Redis container

### Local Development Redis Configuration

```bash
# Docker Redis container
Host: localhost
Port: 6379
Database: 0

# Connection URL format
REDIS_URL="redis://localhost:6379/0"
```

### Why Redis Stream

1. Low-latency real-time event delivery (< 100ms)
2. Built-in support for reconnection recovery via Last-Event-ID
3. Automatic event ordering with Redis message IDs
4. Memory-efficient with MAXLEN trimming (~10000 events per run)

### Graceful Degradation

- Redis failures should NOT block the main execution flow
- Events are dual-written: Redis Stream (persistence) + memory queue (low-latency SSE)
- If Redis is unavailable, SSE streaming continues via memory queue only

---

## Development Environment

### Running the Server Locally

```bash
# Set environment variables
export DATABASE_URL="mysql+pymysql://root:root123@localhost:3306/aiops_local"

# Run directly (NOT in Docker)
python -c "from src.ec2.server import main; main()"
```

### Do NOT

- Do not run the application server in Docker for local development
- Do not use SQLite for testing
- Do not use PostgreSQL

---

## Event Format

### V2 Event Structure

All stream events must follow the V2 format:

```json
{
  "run_id": "...",
  "timestamp": "...",
  "sequence": 123,
  "source": {
    "agent_id": "...",
    "agent_type": "global_supervisor | team_supervisor | worker",
    "agent_name": "...",
    "team_name": "..."
  },
  "event": {
    "category": "lifecycle | llm | dispatch | system",
    "action": "started | completed | stream | ..."
  },
  "data": { ... }
}
```
