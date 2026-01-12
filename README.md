# Legacy MongoDB MCP Server

A Model Context Protocol (MCP) server specifically designed for legacy MongoDB instances (versions < 4.0).

## Overview

Modern MongoDB tools often drop support for older versions of the database. This project aims to bridge that gap by providing an MCP interface for legacy MongoDB deployments, allowing AI models to interact with historical data stored in older systems.

## Current Status

**Focus:** Read-only operations.

This project is currently in early development and focuses exclusively on **read-only** capabilities to ensure data safety while inspecting legacy systems.

### Features
- Connect to MongoDB versions < 4.0
- List databases and collections
- Query documents (find)
- Read-only access enforcement

## Roadmap

Future development will expand functionality based on user needs:
- [ ] Write operations (safeguarded)
- [ ] Aggregation pipeline support
- [ ] Index management
- [ ] User/Role management

## Installation

(Coming soon)

## Usage

(Coming soon)