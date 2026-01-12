# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **Critical**: Fixed `explain` tool argument parsing - now correctly handles array format `["method_name", {"args"}]` instead of expecting object format
- **Critical**: Fixed `export_data` tool argument parsing - now correctly handles array format `["target_name", {"args"}]` instead of expecting object format
- Both tools were previously throwing runtime error: `'str' object has no attribute 'get'` when called with array arguments

### Added
- Input validation for `explain` verbosity parameter (must be one of: `queryPlanner`, `executionStats`, `allPlansExecution`)
- Input validation for `export_data` jsonExportFormat parameter (must be one of: `relaxed`, `canonical`)
- Unit tests for tool argument parsing to prevent regression
- Usage examples in README demonstrating correct array format for `explain` and `export_data`

### Changed
- Improved documentation for `explain` and `export_data` tools with explicit format specifications and concrete examples
- Enhanced error messages for invalid parameters

## [0.1.0] - 2026-01-12

### Added
- Initial release with read-only MongoDB MCP server
- Support for legacy MongoDB versions (2.6 - 3.6)
- 13 read-only tools for database inspection
- Docker support for containerized deployment
- Configuration via environment variables
- Index check mode for query optimization
- Response size limits for safety
