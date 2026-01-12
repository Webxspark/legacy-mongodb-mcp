# Legacy MongoDB MCP Server

A Model Context Protocol (MCP) server specifically designed for legacy MongoDB instances (versions < 4.0).

## Overview

Modern MongoDB tools often drop support for older versions of the database. This project aims to bridge that gap by providing an MCP interface for legacy MongoDB deployments, allowing AI models to interact with historical data stored in older systems.

## Current Status

**Focus:** Strictly read-only operations.

This project enforces **read-only** access to ensure data safety when inspecting legacy production systems.

### 🔒 Read-Only Enforcement

- **No `connect` tool exposed** - Connection is established at startup via environment variable
- **No write operations** - All tools are read-only by design
- **Aggregation restrictions** - `$out` and `$merge` stages are blocked
- **Index check mode** - Optional enforcement to reject queries without index usage
- **Response limits** - Configurable limits on documents and bytes per query

### Available Tools

| Tool | Description |
|------|-------------|
| `list_databases` | List all databases in the MongoDB instance |
| `list_collections` | List all collections in a database |
| `find` | Run a find query against a collection |
| `count` | Count documents in a collection with optional filter |
| `aggregate` | Run an aggregation pipeline (read-only stages only) |
| `collection_indexes` | Describe indexes for a collection |
| `collection_schema` | Infer schema from sampled documents |
| `collection_storage_size` | Get storage size statistics for a collection |
| `db_stats` | Get database statistics |
| `explain` | Get query execution plan for find/aggregate/count |
| `export_data` | Export query/aggregation results to EJSON file |
| `mongodb_logs` | Retrieve recent mongod log entries |
| `get_server_config` | Get current server configuration (redacted) |

### Tool Usage Examples

#### explain
Returns query execution plan statistics:

```python
# Format: ["method_name", {"arguments"}]
explain(
    database="testdb",
    collection="products",
    method=["find", {"filter": {"status": "active"}, "limit": 10}],
    verbosity="executionStats"
)
```

#### export_data
Exports query results to a JSON file:

```python
# Format: ["target_name", {"arguments"}]
export_data(
    database="testdb",
    collection="products",
    exportTitle="active_products",
    exportTarget=["find", {"filter": {"status": "active"}, "limit": 100}],
    jsonExportFormat="relaxed"  # or "canonical"
)
```

## Configuration

The server is configured via environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MDB_MCP_CONNECTION_STRING` | Yes | - | MongoDB connection string (mongodb:// or mongodb+srv://) |
| `MDB_MCP_READ_ONLY` | No | `true` | Enable read-only mode (always true for this server) |
| `MDB_MCP_INDEX_CHECK` | No | `false` | Reject queries that don't use an index |
| `MDB_MCP_MAX_DOCUMENTS_PER_QUERY` | No | `100` | Maximum documents per query |
| `MDB_MCP_MAX_BYTES_PER_QUERY` | No | `16777216` | Maximum response bytes (16MB) |
| `MDB_MCP_LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

> 🔒 **Security Recommendation**: Always use environment variables for the connection string. Never pass credentials as command-line arguments.

## Installation

### Prerequisites

- Python 3.10+ (for local installation)
- Docker (for containerized usage)
- Access to a MongoDB instance (version 2.6 - 3.6 recommended)

### Option 1: Docker (Recommended)

Pull and run the pre-built Docker image:

```bash
docker run --rm -i \
  --network=host \
  -e MDB_MCP_CONNECTION_STRING="mongodb://user:password@localhost:27017/mydb?authSource=admin" \
  -e MDB_MCP_READ_ONLY=true \
  ghcr.io/webxspark/legacy-mongodb-mcp:latest
```

Or build locally:

```bash
# Clone the repository
git clone https://github.com/Webxspark/legacy-mongodb-mcp.git
cd legacy-mongodb-mcp

# Build the image
docker build -t legacy-mongodb-mcp .

# Run the container
docker run --rm -i \
  --network=host \
  -e MDB_MCP_CONNECTION_STRING="mongodb://user:password@localhost:27017" \
  legacy-mongodb-mcp
```

### Option 2: Local Installation

```bash
# Clone the repository
git clone https://github.com/Webxspark/legacy-mongodb-mcp.git
cd legacy-mongodb-mcp

# Install dependencies
pip install -r requirements.txt
```

## Usage

### With VS Code / Cursor (Docker)

Add to your `.vscode/mcp.json`:

```json
{
    "servers": {
        "legacy-mongodb": {
            "command": "docker",
            "args": [
                "run", "--rm", "-i",
                "--network=host",
                "-e", "MDB_MCP_CONNECTION_STRING",
                "-e", "MDB_MCP_READ_ONLY",
                "ghcr.io/webxspark/legacy-mongodb-mcp:latest"
            ],
            "env": {
                "MDB_MCP_CONNECTION_STRING": "mongodb://user:password@localhost:27017/mydb?authSource=admin",
                "MDB_MCP_READ_ONLY": "true"
            }
        }
    }
}
```

### With VS Code / Cursor (Local Python)

Add to your `.vscode/mcp.json`:

```json
{
    "servers": {
        "legacy-mongodb": {
            "command": "python",
            "args": ["src/server.py"],
            "env": {
                "MDB_MCP_CONNECTION_STRING": "mongodb://user:password@localhost:27017",
                "MDB_MCP_READ_ONLY": "true",
                "MDB_MCP_INDEX_CHECK": "false"
            }
        }
    }
}
```

Or with `uv`:

```json
{
    "servers": {
        "legacy-mongodb": {
            "command": "uv",
            "args": ["run", "--with", "mcp", "--with", "pymongo", "python", "src/server.py"],
            "env": {
                "MDB_MCP_CONNECTION_STRING": "mongodb://user:password@localhost:27017"
            }
        }
    }
}
```

### Dry Run Mode

Test your configuration without starting the server:

```bash
# Local
export MDB_MCP_CONNECTION_STRING="mongodb://localhost:27017"
python src/server.py --dry-run

# Docker
docker run --rm -i \
  -e MDB_MCP_CONNECTION_STRING="mongodb://localhost:27017" \
  ghcr.io/webxspark/legacy-mongodb-mcp:latest --dry-run
```

### Testing with Docker Compose

A Docker Compose configuration is provided for testing with MongoDB 3.6:

A Docker Compose configuration is provided for testing with MongoDB 3.6:

```bash
# Start the test MongoDB instance
docker compose up -d

# The connection string will be:
# mongodb://admin:secret_password@localhost:27017
```

## Roadmap

Future development will expand functionality based on user needs:
- [ ] Write operations (safeguarded, opt-in)
- [ ] User/Role management
- [ ] Backup utilities

## License

[MIT](LICENSE)