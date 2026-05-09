# Flask Brain

Interactive architecture visualizer for Flask/Python projects.

## Overview

Flask Brain is a standalone Python CLI tool that scans any Flask project using **pure AST analysis** — it never imports or executes your project code. It produces an interactive browser-based graph with multiple diagram types, AI context export, snapshot diffing, and a live watch mode.

Tested against real-world projects with 1,400+ nodes and 1,200+ edges.

---

## Features

| Feature | Details |
|---|---|
| **AST-only scanning** | Analyzes Python code without executing it — safe for any codebase |
| **7 specialized scanners** | Routes, models, services, tasks, complexity, query tracing, call chains |
| **Interactive browser UI** | Served locally at `http://localhost:7891` via a pre-built React SPA |
| **Multiple diagram types** | Graph, Route Map, ERD, Complexity Heatmap, Dead Weight, Blind Spots, Search, Risk, Diff |
| **Git churn + risk scoring** | Enriches nodes with commit frequency and composite risk scores |
| **Watch mode** | Auto-rescans on `.py` file changes and pushes live updates via SSE |
| **AI context export** | Generates structured Markdown context for any node — ready for LLMs |
| **Snapshot & diff** | Capture named snapshots and compare architecture across time |

---

## Installation

```bash
# Clone the repository
git clone http://192.168.1.127:3000/Chris/flask-brain.git
cd flask-brain

# Install (Python 3.10+)
pip install -e .

# Or with dev dependencies
pip install -e ".[dev]"
```

---

## Quick Start

```bash
# Scan a project and open the UI
flask-brain scan ~/projects/my-flask-app

# Scan, watch for changes, and auto-refresh
flask-brain scan ~/projects/my-flask-app --watch
```

---

## CLI Reference

### `flask-brain scan`

Scan a project, write graph data to `.flask-brain/`, and start the server.

```bash
flask-brain scan <path> [options]

Options:
  --output, -o   Custom output directory (default: <path>/.flask-brain/)
  --port, -p     HTTP server port (default: 7891)
  --watch, -w    Watch for .py changes and auto-rescan
  --no-serve     Write graph data only — don't start the server
```

**Examples:**

```bash
# Basic scan
flask-brain scan ~/projects/my-flask-app

# Custom port
flask-brain scan ~/projects/my-flask-app --port 8080

# Scan + watch mode (auto-rescan on file changes)
flask-brain scan ~/projects/my-flask-app --watch

# Scan only — no browser
flask-brain scan ~/projects/my-flask-app --no-serve

# Custom output directory
flask-brain scan ~/projects/my-flask-app --output /tmp/brain-output
```

---

### `flask-brain serve`

Start the server for a previously scanned project (reads from `.flask-brain/`).

```bash
flask-brain serve <path> [options]

Options:
  --port, -p     HTTP server port (default: 7891)
  --watch, -w    Watch for .py changes and auto-rescan
```

**Example:**

```bash
flask-brain serve ~/projects/my-flask-app
flask-brain serve ~/projects/my-flask-app --watch --port 9000
```

---

### `flask-brain export-context`

Export AI-ready Markdown context for a specific node or route. Useful for pasting into LLM prompts.

```bash
flask-brain export-context <path> [options]

Options:
  --node         Node ID to export context for
  --route        Route node ID (alias for --node)
  --format       Output format: md (default) or json
  --budget       Approximate token budget (default: 4000)
  --depth        BFS depth from focal node (default: 3)
  --output, -o   Write to file instead of stdout
```

**Examples:**

```bash
# Export context for a route
flask-brain export-context ~/projects/my-app --route "route::GET /api/users"

# Export as JSON, write to file, custom depth
flask-brain export-context ~/projects/my-app \
  --node "service::UserService.create_user" \
  --format json \
  --depth 4 \
  --output context.json
```

---

### `flask-brain snapshot`

Capture a named snapshot of the current graph state.

```bash
flask-brain snapshot <path> [options]

Options:
  --label, -l    Human-readable label for this snapshot
```

**Examples:**

```bash
flask-brain snapshot ~/projects/my-app --label "before-refactor"
flask-brain snapshot ~/projects/my-app --label "v2.0-release"
```

Snapshots are stored in `.flask-brain/snapshots/` as `snapshot-<YYYYMMDD-HHMMSS>.json`.

---

### `flask-brain snapshots`

List all snapshots for a project, or delete one by ID.

```bash
flask-brain snapshots <path> [options]

Options:
  --delete       Delete a snapshot by ID
```

**Examples:**

```bash
# List all snapshots
flask-brain snapshots ~/projects/my-app

# Delete a specific snapshot
flask-brain snapshots ~/projects/my-app --delete 20250501-143022
```

---

### `flask-brain diff`

Compare the current graph (or any snapshot) against a baseline snapshot.

```bash
flask-brain diff <path> [options]

Options:
  --baseline, -b   Baseline snapshot ID (required)
  --current, -c    Current snapshot ID or 'current' (default: current scan)
  --output         Output format: summary (default) or json
```

**Examples:**

```bash
# Compare current scan to a baseline
flask-brain diff ~/projects/my-app --baseline 20250501-143022

# Compare two snapshots
flask-brain diff ~/projects/my-app \
  --baseline 20250501-143022 \
  --current 20250509-091500

# Output raw JSON diff
flask-brain diff ~/projects/my-app --baseline 20250501-143022 --output json
```

---

## Browser UI Tabs

Once the server is running at `http://localhost:7891`:

| Tab | What it shows |
|---|---|
| **Graph** | Full interactive node graph. Click blueprints to expand routes. Click nodes for details and sequence diagrams. |
| **Route Map** | Blueprint → route hierarchy. Expandable tree with HTTP method badges. |
| **ERD** | Entity-Relationship Diagram for all SQLAlchemy models. Shows columns, types, and relationships. |
| **Heatmap** | Complexity heatmap — color-coded by cyclomatic complexity and line count. |
| **Dead Weight** | Nodes with no incoming edges — likely unused code. |
| **Blind Spots** | Nodes with no outgoing edges — functions that call nothing. |
| **Search** | Free-text + predicate search across the full graph. Predicates: `type:`, `file:`, `label:`. AND logic. |
| **Risk 🔥** | Top 50 highest-risk nodes ranked by composite score (complexity × churn × DB ops). Sortable. |
| **Diff 📊** | Visual diff between two snapshots — added/removed/modified nodes and edges with filter chips. |

---

## What Gets Detected

Flask Brain uses 7 specialized scanners:

### RouteScanner
- `@app.route` and `@bp.route` decorators
- Blueprint declarations and `register_blueprint()` calls
- URL prefixes and HTTP methods
- View function names

### ModelScanner
- SQLAlchemy Model classes (Flask-SQLAlchemy 2.x and SQLAlchemy 2.x)
- Column definitions with types
- `relationship()` and `ForeignKey` declarations
- Both `db.Model` and `DeclarativeBase` patterns

### ViewFunctionTracer
- Call chains from view functions
- Service method calls, model queries, task dispatches

### ServiceScanner
- Service classes (`*Service`, `*Repository`, `*Manager`)
- Service modules (`*_service.py`, `*_repository.py`)
- Public methods

### CeleryTaskScanner
- `@celery.task`, `@shared_task`, `@app.task` decorators

### ComplexityAnalyzer
- Cyclomatic complexity per function
- Line counts and fat class detection (>10 methods or >300 lines)

### QueryTracer
- `db.session.*`, `Model.query.*`, `select(Model)` patterns
- Classifies each operation as `READ`, `WRITE`, or `DELETE`

---

## Git Churn & Risk Scoring

After scanning, Flask Brain runs `git log` on the project repo to enrich nodes with:

- **`churn_count`** — number of commits that touched the file
- **`risk_score`** — composite score: `complexity × churn × db_op_count` (normalized)

These scores power the **Risk 🔥** tab and are visible in node metadata panels.

If the project has no git history (or `git` is not available), churn enrichment is silently skipped.

---

## Output Files

Scan output is written to `.flask-brain/` in the project root:

```
.flask-brain/
├── manifest.json              # Project metadata, scan timestamp, node/edge counts
├── graph-all.json             # Full graph (all nodes + edges)
├── graph-routes.json          # Route-level subgraph
├── graph-route_*.json         # Per-route subgraphs (one per route)
└── snapshots/
    └── snapshot-YYYYMMDD-HHMMSS.json
```

---

## Watch Mode

```bash
flask-brain scan ~/projects/my-app --watch
# or
flask-brain serve ~/projects/my-app --watch
```

Flask Brain watches for `.py` file changes in the project directory, debounces rapid saves (1 second), re-runs the full scan pipeline, and pushes updated graph data to the browser via **Server-Sent Events (SSE)**. The UI auto-reloads without a manual refresh.

---

## Development

```bash
# Run tests
pytest tests/ -v

# Run linter
ruff check .

# Frontend dev server (proxies /api/* to port 7891)
cd frontend && npm install && npm run dev

# Build frontend
cd frontend && npm run build
```

### Test Fixtures

Three fixture Flask apps in `tests/fixtures/`:

| Fixture | Pattern |
|---|---|
| `flat_app` | Single `app.py` with routes, models, and service functions |
| `factory_app` | App factory pattern with blueprints and service classes |
| `blueprint_app` | Domain-organized with multiple blueprints and Celery tasks |

### Test Suite

190 tests, 1 skipped — covering all scanners, graph analysis methods, server endpoints, snapshot management, and diff engine.

---

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
    ├─ QueryTracer          → database operations
    └─ GitChurnAnalyzer     → commit frequency + risk scores
        │
        └─ GraphBuilder → unified graph
            │
            ├─ graph.write() → .flask-brain/*.json
            │
            └─ start_server() → http://localhost:7891
                ├─ React SPA (pre-built dist)
                ├─ SSE endpoint (/api/events)
                └─ ProjectWatcher (--watch mode)
```

---

## Project Structure

```
flask-brain/
├── flask_brain/
│   ├── cli.py                      # Typer CLI (scan, serve, export-context, snapshot, snapshots, diff)
│   ├── graph.py                    # Node, Edge, Graph, GraphBuilder
│   ├── server.py                   # Flask HTTP server + SSE
│   ├── context_export.py           # AI context generator (BFS-bounded)
│   ├── diff.py                     # SnapshotManager, DiffEngine, GraphDiff
│   ├── watcher.py                  # ProjectWatcher (debounced file watcher)
│   └── scanners/
│       ├── base.py
│       ├── route_scanner.py
│       ├── model_scanner.py
│       ├── view_tracer.py
│       ├── service_scanner.py
│       ├── celery_scanner.py
│       ├── complexity_analyzer.py
│       ├── query_tracer.py
│       └── git_churn_analyzer.py
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/             # GraphView, RouteMapView, ERDView, HeatmapView,
│   │   │                           # DeadWeightView, BlindSpotsView, SearchView,
│   │   │                           # RiskView, DiffView
│   │   └── types/graph.ts
│   └── dist/                       # Pre-built React SPA (committed)
├── tests/
│   ├── fixtures/
│   ├── test_graph.py
│   ├── test_route_scanner.py
│   ├── test_model_scanner.py
│   ├── test_server.py
│   ├── test_diff.py
│   └── ...
├── pyproject.toml
└── README.md
```

---

## Forgejo Repository

http://192.168.1.127:3000/Chris/flask-brain

---

## License

MIT
