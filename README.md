# Flask Brain

Interactive architecture visualizer for Flask/Python projects.

## Overview

Flask Brain is a standalone Python CLI tool that scans any Flask project using AST analysis and renders an interactive browser-based architecture graph. It helps developers understand project structure, trace call chains, visualize data models, and export AI-ready context.

## Features

- **AST-based scanning** — analyzes Python code without executing it
- **Multiple diagram types** — route maps, call chains, ERDs, sequence diagrams, complexity heatmaps
- **Interactive browser UI** — served locally at http://localhost:7891
- **Watch mode** — auto-refresh on file changes
- **AI context export** — generate structured context for any node

## Installation

```bash
pip install -e .
```

## Usage

### Scan a project

```bash
flask-brain scan /path/to/your/flask/project
```

This will:
1. Scan the project and extract architecture information
2. Write graph JSON to `.flask-brain/` in the project root
3. Start an HTTP server at http://localhost:7891
4. Open your browser to view the interactive graph

### Watch mode

```bash
flask-brain scan /path/to/project --watch
```

### Serve a previously scanned project

```bash
flask-brain serve /path/to/project
```

### Export AI context

```bash
flask-brain export-context /path/to/project --node "route::GET /users"
```

## Development

### Install dev dependencies

```bash
pip install -e ".[dev]"
```

### Run tests

```bash
pytest tests/ -v
```

### Run linter

```bash
ruff check .
```

## Architecture

Flask Brain uses multiple specialized scanners to extract different aspects of a Flask project:

- **RouteScanner** — detects routes, blueprints, and URL rules
- **ModelScanner** — detects SQLAlchemy models, columns, and relationships
- **ViewFunctionTracer** — traces call chains from views to services and models
- **ServiceScanner** — detects service classes and modules
- **CeleryTaskScanner** — detects Celery tasks
- **ComplexityAnalyzer** — computes cyclomatic complexity
- **QueryTracer** — detects database operations

All scanner outputs are assembled into a unified graph by the GraphBuilder.

## License

MIT
