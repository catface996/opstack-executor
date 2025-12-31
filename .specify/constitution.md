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
