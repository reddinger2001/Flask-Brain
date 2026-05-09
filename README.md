# Flask Brain

Interactive architecture visualizer for Flask/Python projects.

## Overview

Flask Brain is a standalone Python CLI tool that scans any Flask project using AST analysis and renders an interactive browser-based architecture graph. It helps developers understand project structure, trace call chains, visualize data models, and export AI-ready context.

## Features

- **AST-based scanning** — analyzes Python code without executing it
- **7 specialized scanners** — routes, models, services, tasks, complexity, queries, call chains
- **Multiple diagram types** — route maps, call chains, ERDs, sequence diagrams, complexity heatmaps
- **Interactive browser UI** — served locally at http://localhost:7891
- **Watch mode** — auto-refresh on file changes (coming soon)
- **AI context export** — generate structured context for any node (coming soon)

## Installation

```bash
# Clone the repository
git clone http://192.168.1.127:3000/Chris/flask-brain.git
cd flask-brain

# Install in editable mode
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
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

**Example:**
```bash
flask-brain scan ~/projects/my-flask-app
```

### Custom output directory

```bash
flask-brain scan /path/to/project --output /path/to/output
```

### Scan without starting server

```bash
flask-brain scan /path/to/project --no-serve
```

### Custom port

```bash
flask-brain scan /path/to/project --port 8080
```

### Serve a previously scanned project

```bash
flask-brain serve /path/to/project
```

### Export AI context (coming soon)

```bash
flask-brain export-context /path/to/project --node "route::GET /users"
```

## What Gets Detected

Flask Brain uses 7 specialized scanners to extract architecture information:

### 1. RouteScanner
- `@app.route` and `@bp.route` decorators
- Blueprint declarations and registrations
- URL prefixes and HTTP methods
- View function names

### 2. ModelScanner
- SQLAlchemy Model classes (Flask-SQLAlchemy 2.x and SQLAlchemy 2.x)
- Column definitions with types
- Relationships and foreign keys
- Both `db.Model` and `DeclarativeBase` styles

### 3. ViewFunctionTracer
- Call chains from view functions
- Service method calls
- Model queries
- Task dispatches

### 4. ServiceScanner
- Service classes (`*Service`, `*Repository`, `*Manager`)
- Service modules (`*_service.py`, `*_repository.py`)
- Public methods

### 5. CeleryTaskScanner
- `@celery.task` decorators
- `@shared_task` decorators
- `@app.task` decorators

### 6. ComplexityAnalyzer
- Cyclomatic complexity per function
- Line counts
- Fat class detection (>10 methods or >300 lines)

### 7. QueryTracer
- `db.session.*` operations
- `Model.query.*` operations
- `select(Model)` patterns
- Classifies as READ, WRITE, or DELETE

## Output Files

After scanning, Flask Brain writes the following files to `.flask-brain/`:

```
.flask-brain/
├── manifest.json              # Project metadata, scan timestamp, node/edge counts
├── graph-all.json             # Full graph (all nodes + edges)
├── graph-routes.json          # Route-level subgraph
└── graph-route_*.json         # Per-route subgraphs (one per route)
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

### Test fixtures

The project includes three test fixture Flask apps in `tests/fixtures/`:

1. **flat_app** — single `app.py` with routes, models, and service functions
2. **factory_app** — app factory pattern with blueprints and service classes
3. **blueprint_app** — domain-organized with multiple blueprints and Celery tasks

These fixtures are used to test all scanners against realistic Flask project structures.

## Architecture

```
flask-brain scan /path/to/project
    │
    ├─ RouteScanner         → routes, blueprints
    ├─ ModelScanner         → models, columns, relationships
    ├─ ViewFunctionTracer   → call chains
    ├─ ServiceScanner       → service classes/modules
    ├─ CeleryTaskScanner    → async tasks
    ├─ ComplexityAnalyzer   → complexity metrics
    └─ QueryTracer          → database operations
        │
        └─ GraphBuilder → assembles unified graph
            │
            └─ Writes JSON → .flask-brain/
                │
                └─ HTTP Server → http://localhost:7891
```

## Project Structure

```
flask-brain/
├── flask_brain/              # Python package
│   ├── cli.py                # Typer CLI entry point
│   ├── graph.py              # Node/Edge/Graph/GraphBuilder
│   ├── server.py             # HTTP server
│   ├── scanners/
│   │   ├── base.py           # BaseScanner abstract class
│   │   ├── route_scanner.py
│   │   ├── model_scanner.py
│   │   ├── view_tracer.py
│   │   ├── service_scanner.py
│   │   ├── celery_scanner.py
│   │   ├── complexity_analyzer.py
│   │   └── query_tracer.py
│   └── viewer/               # React SPA (to be built separately)
├── tests/
│   ├── fixtures/             # Test Flask apps
│   ├── test_graph.py
│   ├── test_route_scanner.py
│   └── test_model_scanner.py
├── pyproject.toml
└── README.md
```

## Test Results

All 26 tests passing:
- 17 graph data model tests
- 5 RouteScanner tests
- 4 ModelScanner tests

## What's Next

The backend is complete and functional. Next steps:

1. **React Frontend** — build the interactive Cytoscape.js-based viewer (separate task)
2. **Watch Mode** — implement file watcher with auto-refresh
3. **AI Context Export** — implement context generation for LLMs
4. **Complexity Heatmap** — integrate ComplexityAnalyzer into graph enrichment
5. **Query Tracing** — integrate QueryTracer into graph enrichment

## Forgejo Repository

http://192.168.1.127:3000/Chris/flask-brain

## License

MIT
