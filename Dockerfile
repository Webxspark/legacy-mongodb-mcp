FROM python:3.11-slim

LABEL org.opencontainers.image.title="Legacy MongoDB MCP Server"
LABEL org.opencontainers.image.description="Read-only MCP server for legacy MongoDB instances (<4.0)"
LABEL org.opencontainers.image.source="https://github.com/Webxspark/legacy-mongodb-mcp"

# Set working directory
WORKDIR /app

# Install dependencies first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Set environment defaults
ENV MDB_MCP_READ_ONLY=true
ENV MDB_MCP_INDEX_CHECK=false
ENV MDB_MCP_MAX_DOCUMENTS_PER_QUERY=100
ENV MDB_MCP_MAX_BYTES_PER_QUERY=16777216
ENV MDB_MCP_LOG_LEVEL=INFO

# Run the MCP server
ENTRYPOINT ["python", "src/server.py"]
