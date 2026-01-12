#!/usr/bin/env python3
"""
Legacy MongoDB Read-Only MCP Server

A Model Context Protocol (MCP) server specifically designed for legacy MongoDB 
instances (versions < 4.0). This server provides STRICTLY read-only access to 
MongoDB databases through a set of tools that can be used by AI models.

Configuration:
    Environment Variables:
        MDB_MCP_CONNECTION_STRING: MongoDB connection string (REQUIRED)
        MDB_MCP_READ_ONLY: When "true", enforces read-only mode (default: true)
        MDB_MCP_INDEX_CHECK: When "true", rejects queries without index usage
        MDB_MCP_MAX_DOCUMENTS_PER_QUERY: Max documents per query (default: 100)
        MDB_MCP_MAX_BYTES_PER_QUERY: Max response bytes (default: 16MB)
        MDB_MCP_LOG_LEVEL: Logging level (default: INFO)

Compatible with stdio transport for IDEs like VS Code, Cursor, etc.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from bson import json_util
from bson.json_util import JSONOptions, JSONMode


# ============================================================================
# Configuration
# ============================================================================

class Config:
    """Server configuration loaded from environment variables and CLI args."""
    
    def __init__(self):
        self.connection_string: Optional[str] = os.environ.get("MDB_MCP_CONNECTION_STRING")
        self.read_only: bool = os.environ.get("MDB_MCP_READ_ONLY", "true").lower() == "true"
        self.index_check: bool = os.environ.get("MDB_MCP_INDEX_CHECK", "false").lower() == "true"
        self.max_documents_per_query: int = int(os.environ.get("MDB_MCP_MAX_DOCUMENTS_PER_QUERY", "100"))
        self.max_bytes_per_query: int = int(os.environ.get("MDB_MCP_MAX_BYTES_PER_QUERY", str(16 * 1024 * 1024)))
        self.log_level: str = os.environ.get("MDB_MCP_LOG_LEVEL", "INFO").upper()
        self.default_sample_size: int = 50
        self.default_limit: int = 10
    
    def validate(self) -> None:
        """Validate configuration. Raises SystemExit if invalid."""
        if not self.connection_string:
            print(
                "ERROR: MDB_MCP_CONNECTION_STRING environment variable is required.\n"
                "\n"
                "Usage:\n"
                "  export MDB_MCP_CONNECTION_STRING='mongodb://user:pass@host:port/db'\n"
                "  python src/server.py\n"
                "\n"
                "Or in VS Code mcp.json:\n"
                '  {\n'
                '    "servers": {\n'
                '      "legacy-mongodb": {\n'
                '        "command": "python",\n'
                '        "args": ["src/server.py"],\n'
                '        "env": {\n'
                '          "MDB_MCP_CONNECTION_STRING": "mongodb://..."\n'
                '        }\n'
                '      }\n'
                '    }\n'
                '  }',
                file=sys.stderr
            )
            sys.exit(1)
    
    def to_dict(self) -> dict:
        """Return config as dict with sensitive data redacted."""
        return {
            "connection_string": self._redact_connection_string(),
            "read_only": self.read_only,
            "index_check": self.index_check,
            "max_documents_per_query": self.max_documents_per_query,
            "max_bytes_per_query": self.max_bytes_per_query,
            "log_level": self.log_level
        }
    
    def _redact_connection_string(self) -> str:
        """Redact password from connection string for safe logging."""
        if not self.connection_string:
            return "<not set>"
        # Simple redaction - replace password in mongodb:// or mongodb+srv:// URLs
        import re
        return re.sub(r'(mongodb(?:\+srv)?://[^:]+:)[^@]+(@)', r'\1****\2', self.connection_string)


# Global config instance
config = Config()


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging(level: str) -> logging.Logger:
    """Configure logging with the specified level."""
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format='%(name)s - %(levelname)s - %(message)s',
        stream=sys.stderr
    )
    return logging.getLogger("LegacyMongoDBMCP")


logger = setup_logging(config.log_level)


# ============================================================================
# MongoDB Connection Manager
# ============================================================================

class MongoDBConnection:
    """Manages the MongoDB connection lifecycle."""
    
    def __init__(self):
        self._client: Optional[MongoClient] = None
        self._server_version: Optional[str] = None
    
    def connect(self, connection_string: str) -> None:
        """
        Establish connection to MongoDB.
        Raises ConnectionFailure if unable to connect.
        """
        if self._client is not None:
            self._client.close()
        
        self._client = MongoClient(
            connection_string,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=30000
        )
        
        # Test the connection
        self._client.admin.command('ping')
        
        # Get and store server version
        server_info = self._client.server_info()
        self._server_version = server_info.get('version', 'unknown')
        
        logger.info(f"Connected to MongoDB {self._server_version}")
        
        # Warn if not a legacy version
        if not self._server_version.startswith(('2.', '3.')):
            logger.warning(
                f"MongoDB {self._server_version} detected. "
                "This server is optimized for legacy versions (<4.0)."
            )
    
    @property
    def client(self) -> MongoClient:
        """Get the MongoDB client. Raises error if not connected."""
        if self._client is None:
            raise ConnectionError("Not connected to MongoDB")
        return self._client
    
    @property
    def server_version(self) -> Optional[str]:
        """Get the connected server version."""
        return self._server_version
    
    def close(self) -> None:
        """Close the MongoDB connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
            self._server_version = None


# Global connection instance
mongo_conn = MongoDBConnection()


# ============================================================================
# Utility Functions
# ============================================================================

def serialize_doc(doc: Any, json_mode: str = "relaxed") -> str:
    """Serialize a MongoDB document to JSON string."""
    if json_mode == "canonical":
        options = JSONOptions(json_mode=JSONMode.CANONICAL)
    else:
        options = JSONOptions(json_mode=JSONMode.RELAXED)
    return json_util.dumps(doc, json_options=options)


def truncate_response(data: str, limit: Optional[int] = None) -> str:
    """Truncate response to fit within byte limit."""
    if limit is None:
        limit = config.max_bytes_per_query
    
    encoded = data.encode('utf-8')
    if len(encoded) <= limit:
        return data
    
    truncated = encoded[:limit].decode('utf-8', errors='ignore')
    return truncated + "\n... [Response truncated due to size limit]"


def infer_field_type(value: Any) -> str:
    """Infer the BSON/Python type of a value."""
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "bool"
    elif isinstance(value, int):
        return "int"
    elif isinstance(value, float):
        return "double"
    elif isinstance(value, str):
        return "string"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "object"
    elif isinstance(value, datetime):
        return "date"
    else:
        return type(value).__name__


def infer_schema_from_docs(docs: list) -> dict:
    """Infer schema from a list of documents."""
    schema = {}
    
    for doc in docs:
        for key, value in doc.items():
            if key not in schema:
                schema[key] = {
                    "types": set(),
                    "count": 0,
                    "sample_values": []
                }
            
            field_type = infer_field_type(value)
            schema[key]["types"].add(field_type)
            schema[key]["count"] += 1
            
            # Store up to 3 sample values
            if len(schema[key]["sample_values"]) < 3 and value is not None:
                try:
                    sample = str(value)[:100]
                    if sample not in schema[key]["sample_values"]:
                        schema[key]["sample_values"].append(sample)
                except:
                    pass
    
    # Convert sets to lists for JSON serialization
    result = {}
    for key, info in schema.items():
        result[key] = {
            "types": list(info["types"]),
            "occurrence_count": info["count"],
            "occurrence_percentage": round(info["count"] / len(docs) * 100, 2) if docs else 0,
            "sample_values": info["sample_values"]
        }
    
    return result


def check_query_uses_index(explain_result: dict) -> tuple[bool, str]:
    """
    Check if a query uses an index based on explain output.
    Returns (uses_index, stage_info).
    """
    # For legacy MongoDB (2.x/3.x), check queryPlanner output
    query_planner = explain_result.get("queryPlanner", {})
    winning_plan = query_planner.get("winningPlan", {})
    
    # Check for COLLSCAN which indicates no index usage
    def find_stage(plan: dict, stage_name: str) -> bool:
        if plan.get("stage") == stage_name:
            return True
        # Check input stage (for 3.x format)
        if "inputStage" in plan:
            if find_stage(plan["inputStage"], stage_name):
                return True
        # Check input stages (array format)
        if "inputStages" in plan:
            for stage in plan["inputStages"]:
                if find_stage(stage, stage_name):
                    return True
        return False
    
    uses_collscan = find_stage(winning_plan, "COLLSCAN")
    stage = winning_plan.get("stage", "unknown")
    
    return (not uses_collscan, stage)


def enforce_index_check(database: str, collection: str, query_filter: dict) -> None:
    """
    If index check is enabled, verify the query uses an index.
    Raises ValueError if query would result in a collection scan.
    """
    if not config.index_check:
        return
    
    if not query_filter:
        # Empty filter = full collection scan
        raise ValueError(
            "Query rejected: Empty filter would result in a collection scan. "
            "Index check mode is enabled. Please provide a filter that uses an indexed field."
        )
    
    # Run explain to check if index is used
    client = mongo_conn.client
    db = client[database]
    coll = db[collection]
    
    cursor = coll.find(query_filter)
    explain_result = cursor.explain()
    
    uses_index, stage = check_query_uses_index(explain_result)
    
    if not uses_index:
        raise ValueError(
            f"Query rejected: Would perform a collection scan (stage: {stage}). "
            "Index check mode is enabled. Please ensure your query uses an indexed field. "
            f"Use the 'collection_indexes' tool to see available indexes for {database}.{collection}."
        )


# ============================================================================
# Initialize MCP Server
# ============================================================================

mcp = FastMCP("LegacyMongoDBReadOnlyMCP")


# ============================================================================
# MCP Tools - Read Only
# ============================================================================

@mcp.tool()
def list_databases() -> str:
    """
    List all databases for a MongoDB connection.
    
    Returns:
        JSON object with array of database names, sizes, and total size
    """
    try:
        client = mongo_conn.client
        result = client.admin.command('listDatabases')
        
        databases = []
        for db in result.get('databases', []):
            databases.append({
                "name": db.get('name'),
                "sizeOnDisk": db.get('sizeOnDisk'),
                "empty": db.get('empty', False)
            })
        
        return json.dumps({
            "databases": databases,
            "totalSize": result.get('totalSize')
        })
    
    except Exception as e:
        logger.error(f"Error listing databases: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def list_collections(database: str) -> str:
    """
    List all collections for a given database.
    
    Args:
        database: Database name
    
    Returns:
        JSON object with array of collection names
    """
    try:
        client = mongo_conn.client
        db = client[database]
        
        # Use collection_names() for legacy compatibility (MongoDB 2.x/3.x)
        try:
            collections = db.collection_names()
        except AttributeError:
            collections = db.list_collection_names()
        
        return json.dumps({
            "database": database,
            "collections": collections
        })
    
    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def find(
    database: str,
    collection: str,
    filter: Optional[dict] = None,
    projection: Optional[dict] = None,
    limit: Optional[int] = None,
    sort: Optional[dict] = None,
    responseBytesLimit: Optional[int] = None
) -> str:
    """
    Run a find query against a MongoDB collection.
    
    Args:
        database: Database name
        collection: Collection name
        filter: The query filter, matching the syntax of db.collection.find()
        projection: The projection, matching the syntax of db.collection.find()
        limit: The maximum number of documents to return (default: 10, max: configured limit)
        sort: Sort order document. Keys are fields, values are 1 (asc) or -1 (desc)
        responseBytesLimit: Maximum bytes to return in response
    
    Returns:
        JSON object with matching documents
    """
    try:
        client = mongo_conn.client
        db = client[database]
        coll = db[collection]
        
        query_filter = filter or {}
        
        # Enforce index check if enabled
        enforce_index_check(database, collection, query_filter)
        
        # Apply limits
        effective_limit = min(
            limit or config.default_limit,
            config.max_documents_per_query
        )
        
        cursor = coll.find(query_filter, projection)
        
        if sort:
            sort_list = [(k, v) for k, v in sort.items()]
            cursor = cursor.sort(sort_list)
        
        cursor = cursor.limit(effective_limit)
        
        documents = list(cursor)
        
        result = serialize_doc({
            "database": database,
            "collection": collection,
            "documentsCount": len(documents),
            "documents": documents
        })
        
        return truncate_response(result, responseBytesLimit)
    
    except ValueError as e:
        # Index check failures
        return json.dumps({"error": str(e)})
    except Exception as e:
        logger.error(f"Error executing find: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def count(
    database: str,
    collection: str,
    query: Optional[dict] = None
) -> str:
    """
    Gets the number of documents in a MongoDB collection.
    
    Uses db.collection.count() with query as an optional filter parameter.
    
    Args:
        database: Database name
        collection: Collection name
        query: Optional filter to count matching documents
    
    Returns:
        JSON object with document count
    """
    try:
        client = mongo_conn.client
        db = client[database]
        coll = db[collection]
        
        query_filter = query or {}
        
        # Use count() for legacy compatibility (deprecated in 4.0+)
        try:
            doc_count = coll.count(query_filter)
        except (AttributeError, TypeError):
            doc_count = coll.count_documents(query_filter)
        
        return json.dumps({
            "database": database,
            "collection": collection,
            "count": doc_count
        })
    
    except Exception as e:
        logger.error(f"Error executing count: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def aggregate(
    database: str,
    collection: str,
    pipeline: list,
    responseBytesLimit: Optional[int] = None
) -> str:
    """
    Run an aggregation against a MongoDB collection.
    
    Note: $vectorSearch is NOT supported in legacy MongoDB (<4.0).
    
    Args:
        database: Database name
        collection: Collection name
        pipeline: An array of aggregation stages to execute
        responseBytesLimit: Maximum bytes to return in response
    
    Returns:
        JSON object with aggregation results
    """
    try:
        client = mongo_conn.client
        db = client[database]
        coll = db[collection]
        
        # Check for unsupported stages
        for stage in pipeline:
            if '$vectorSearch' in stage:
                return json.dumps({
                    "error": "$vectorSearch is not supported in MongoDB versions < 4.0. "
                             "This feature requires MongoDB Atlas with vector search capability."
                })
            # Check for write operations in aggregation (read-only enforcement)
            if '$out' in stage or '$merge' in stage:
                return json.dumps({
                    "error": f"Write operations ($out, $merge) are not allowed in read-only mode."
                })
        
        # Add $limit if not present to prevent unbounded results
        has_limit = any('$limit' in stage for stage in pipeline)
        if not has_limit:
            pipeline = pipeline + [{"$limit": config.max_documents_per_query}]
        
        cursor = coll.aggregate(pipeline)
        documents = list(cursor)
        
        result = serialize_doc({
            "database": database,
            "collection": collection,
            "documentsCount": len(documents),
            "documents": documents
        })
        
        return truncate_response(result, responseBytesLimit)
    
    except Exception as e:
        logger.error(f"Error executing aggregate: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def collection_indexes(database: str, collection: str) -> str:
    """
    Describe the indexes for a collection.
    
    Args:
        database: Database name
        collection: Collection name
    
    Returns:
        JSON object with array of index definitions
    """
    try:
        client = mongo_conn.client
        db = client[database]
        coll = db[collection]
        
        indexes = list(coll.list_indexes())
        
        result = serialize_doc({
            "database": database,
            "collection": collection,
            "indexes": indexes
        })
        
        return result
    
    except Exception as e:
        logger.error(f"Error getting collection indexes: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def collection_schema(
    database: str,
    collection: str,
    sampleSize: Optional[int] = None,
    responseBytesLimit: Optional[int] = None
) -> str:
    """
    Describe the schema for a collection by sampling documents.
    
    Args:
        database: Database name
        collection: Collection name
        sampleSize: Number of documents to sample for schema inference (default: 50)
        responseBytesLimit: Maximum bytes to return in response
    
    Returns:
        Inferred schema with field types and statistics
    """
    try:
        client = mongo_conn.client
        db = client[database]
        coll = db[collection]
        
        sample_size = sampleSize or config.default_sample_size
        
        # Sample documents using $sample if available (MongoDB 3.2+)
        try:
            docs = list(coll.aggregate([{"$sample": {"size": sample_size}}]))
        except OperationFailure:
            # Fallback for older MongoDB versions
            docs = list(coll.find().limit(sample_size))
        
        schema = infer_schema_from_docs(docs)
        
        result = json.dumps({
            "database": database,
            "collection": collection,
            "sampleSize": len(docs),
            "schema": schema
        })
        
        return truncate_response(result, responseBytesLimit)
    
    except Exception as e:
        logger.error(f"Error inferring collection schema: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def collection_storage_size(database: str, collection: str) -> str:
    """
    Gets the size of the collection.
    
    Args:
        database: Database name
        collection: Collection name
    
    Returns:
        Collection storage statistics
    """
    try:
        client = mongo_conn.client
        db = client[database]
        
        stats = db.command("collStats", collection)
        
        return json.dumps({
            "database": database,
            "collection": collection,
            "storageSize": stats.get("storageSize"),
            "size": stats.get("size"),
            "count": stats.get("count"),
            "avgObjSize": stats.get("avgObjSize"),
            "totalIndexSize": stats.get("totalIndexSize"),
            "indexSizes": stats.get("indexSizes", {})
        })
    
    except Exception as e:
        logger.error(f"Error getting collection storage size: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def db_stats(database: str) -> str:
    """
    Returns statistics that reflect the use state of a single database.
    
    Args:
        database: Database name
    
    Returns:
        Database statistics
    """
    try:
        client = mongo_conn.client
        db = client[database]
        
        stats = db.command("dbStats")
        
        return serialize_doc({
            "database": database,
            "collections": stats.get("collections"),
            "views": stats.get("views", 0),
            "objects": stats.get("objects"),
            "avgObjSize": stats.get("avgObjSize"),
            "dataSize": stats.get("dataSize"),
            "storageSize": stats.get("storageSize"),
            "numExtents": stats.get("numExtents"),
            "indexes": stats.get("indexes"),
            "indexSize": stats.get("indexSize"),
            "fileSize": stats.get("fileSize"),
            "nsSizeMB": stats.get("nsSizeMB")
        })
    
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def explain(
    database: str,
    collection: str,
    method: list,
    verbosity: str = "queryPlanner"
) -> str:
    """
    Returns statistics describing the execution of the winning plan chosen by the query optimizer.
    
    Args:
        database: Database name
        collection: Collection name
        method: The method and its arguments to run (find, aggregate, or count)
        verbosity: The verbosity of the explain plan (queryPlanner, executionStats, allPlansExecution)
    
    Returns:
        Explain plan output
    """
    try:
        client = mongo_conn.client
        db = client[database]
        coll = db[collection]
        
        if not method or len(method) == 0:
            return json.dumps({"error": "Method is required"})
        
        method_info = method[0]
        method_name = method_info.get("name")
        method_args = method_info.get("arguments", {})
        
        explain_result = None
        
        if method_name == "find":
            query_filter = method_args.get("filter", {})
            projection = method_args.get("projection")
            
            cursor = coll.find(query_filter, projection)
            
            if method_args.get("sort"):
                sort_list = [(k, v) for k, v in method_args["sort"].items()]
                cursor = cursor.sort(sort_list)
            
            if method_args.get("limit"):
                cursor = cursor.limit(method_args["limit"])
            
            explain_result = cursor.explain()
            
        elif method_name == "aggregate":
            pipeline = method_args.get("pipeline", [])
            
            explain_cmd = {
                "aggregate": collection,
                "pipeline": pipeline,
                "explain": True
            }
            explain_result = db.command(explain_cmd)
            
        elif method_name == "count":
            query_filter = method_args.get("query", {})
            
            explain_cmd = {
                "count": collection,
                "query": query_filter
            }
            try:
                explain_result = db.command("explain", explain_cmd, verbosity=verbosity)
            except OperationFailure:
                # Fallback for older MongoDB versions
                cursor = coll.find(query_filter)
                explain_result = cursor.explain()
            
        else:
            return json.dumps({"error": f"Unsupported method: {method_name}"})
        
        # Add index usage analysis
        uses_index, stage = check_query_uses_index(explain_result)
        
        result = serialize_doc({
            "database": database,
            "collection": collection,
            "method": method_name,
            "verbosity": verbosity,
            "indexUsed": uses_index,
            "stage": stage,
            "explainResult": explain_result
        })
        
        return result
    
    except Exception as e:
        logger.error(f"Error executing explain: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def export_data(
    database: str,
    collection: str,
    exportTitle: str,
    exportTarget: list,
    jsonExportFormat: str = "relaxed"
) -> str:
    """
    Export a query or aggregation results in the specified EJSON format.
    
    Args:
        database: Database name
        collection: Collection name
        exportTitle: A short description to uniquely identify the export
        exportTarget: The export target along with its arguments (find or aggregate)
        jsonExportFormat: The EJSON format (relaxed or canonical)
    
    Returns:
        Path to the exported file and document count
    """
    try:
        client = mongo_conn.client
        db = client[database]
        coll = db[collection]
        
        if not exportTarget or len(exportTarget) == 0:
            return json.dumps({"error": "Export target is required"})
        
        target_info = exportTarget[0]
        target_name = target_info.get("name")
        target_args = target_info.get("arguments", {})
        
        if target_name == "find":
            query_filter = target_args.get("filter", {})
            projection = target_args.get("projection")
            
            cursor = coll.find(query_filter, projection)
            
            if target_args.get("sort"):
                sort_list = [(k, v) for k, v in target_args["sort"].items()]
                cursor = cursor.sort(sort_list)
            
            if target_args.get("limit"):
                cursor = cursor.limit(target_args["limit"])
            
            documents = list(cursor)
            
        elif target_name == "aggregate":
            pipeline = target_args.get("pipeline", [])
            
            # Block write operations in aggregation
            for stage in pipeline:
                if '$out' in stage or '$merge' in stage:
                    return json.dumps({
                        "error": "Write operations ($out, $merge) are not allowed in read-only mode."
                    })
            
            cursor = coll.aggregate(pipeline)
            documents = list(cursor)
            
        else:
            return json.dumps({"error": f"Unsupported export target: {target_name}"})
        
        # Serialize documents
        if jsonExportFormat == "canonical":
            options = JSONOptions(json_mode=JSONMode.CANONICAL)
        else:
            options = JSONOptions(json_mode=JSONMode.RELAXED)
        
        # Create export file
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in exportTitle)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_title}_{timestamp}.json"
        
        # Create exports directory
        export_dir = os.path.join(os.getcwd(), "exports")
        os.makedirs(export_dir, exist_ok=True)
        
        filepath = os.path.join(export_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            for doc in documents:
                f.write(json_util.dumps(doc, json_options=options))
                f.write('\n')
        
        return json.dumps({
            "success": True,
            "exportTitle": exportTitle,
            "database": database,
            "collection": collection,
            "documentCount": len(documents),
            "format": jsonExportFormat,
            "filePath": filepath,
            "message": f"Exported {len(documents)} documents to {filepath}"
        })
    
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def mongodb_logs(
    type: str = "global",
    limit: int = 50
) -> str:
    """
    Returns the most recent logged mongod events.
    
    Args:
        type: The type of logs to return (global or startupWarnings)
        limit: The maximum number of log entries to return (default: 50, max: 1024)
    
    Returns:
        Array of log entries
    """
    try:
        client = mongo_conn.client
        
        limit = max(1, min(limit, 1024))
        
        log_type = "startupWarnings" if type == "startupWarnings" else "global"
        
        result = client.admin.command("getLog", log_type)
        
        log_entries = result.get("log", [])
        
        if len(log_entries) > limit:
            log_entries = log_entries[-limit:]
        
        return json.dumps({
            "type": log_type,
            "totalLinesWritten": result.get("totalLinesWritten"),
            "entriesReturned": len(log_entries),
            "logs": log_entries
        })
    
    except OperationFailure as e:
        logger.error(f"Error getting MongoDB logs: {e}")
        return json.dumps({
            "error": str(e),
            "hint": "The getLog command may require administrative privileges."
        })
    except Exception as e:
        logger.error(f"Error getting MongoDB logs: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_server_config() -> str:
    """
    Get the current server configuration (with sensitive data redacted).
    
    Returns:
        Server configuration and connection status
    """
    return json.dumps({
        "config": config.to_dict(),
        "connected": mongo_conn.client is not None,
        "serverVersion": mongo_conn.server_version,
        "readOnlyMode": config.read_only,
        "indexCheckMode": config.index_check
    })


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(
        description="Legacy MongoDB Read-Only MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  MDB_MCP_CONNECTION_STRING     MongoDB connection string (REQUIRED)
  MDB_MCP_READ_ONLY             Enable read-only mode (default: true)
  MDB_MCP_INDEX_CHECK           Reject queries without index (default: false)
  MDB_MCP_MAX_DOCUMENTS_PER_QUERY  Max documents per query (default: 100)
  MDB_MCP_MAX_BYTES_PER_QUERY   Max response bytes (default: 16MB)
  MDB_MCP_LOG_LEVEL             Logging level (default: INFO)

Example:
  export MDB_MCP_CONNECTION_STRING="mongodb://localhost:27017"
  python src/server.py
        """
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print configuration and exit without starting the server"
    )
    args = parser.parse_args()
    
    # Validate configuration
    config.validate()
    
    # Dry run mode
    if args.dry_run:
        print(json.dumps(config.to_dict(), indent=2))
        print("\nAvailable tools:")
        print("  - list_databases")
        print("  - list_collections")
        print("  - find")
        print("  - count")
        print("  - aggregate")
        print("  - collection_indexes")
        print("  - collection_schema")
        print("  - collection_storage_size")
        print("  - db_stats")
        print("  - explain")
        print("  - export_data")
        print("  - mongodb_logs")
        print("  - get_server_config")
        sys.exit(0)
    
    # Connect to MongoDB
    logger.info("Connecting to MongoDB...")
    try:
        mongo_conn.connect(config.connection_string)
    except ConnectionFailure as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        print(f"ERROR: Failed to connect to MongoDB: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error connecting to MongoDB: {e}")
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Log configuration
    logger.info(f"Configuration: {json.dumps(config.to_dict())}")
    logger.info(f"Read-only mode: {config.read_only}")
    logger.info(f"Index check mode: {config.index_check}")
    
    # Start the MCP server
    logger.info("Starting Legacy MongoDB Read-Only MCP Server with stdio transport...")
    try:
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
    finally:
        mongo_conn.close()
        logger.info("Connection closed")


if __name__ == "__main__":
    main()
