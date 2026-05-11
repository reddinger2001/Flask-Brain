# Flask Brain

Interactive architecture visualizer for Flask/Python projects.

## Overview

Flask Brain is a standalone Python CLI tool that scans any Flask project using **pure AST analysis** — it never imports or executes your project code. It produces an interactive browser-based graph with multiple diagram types, AI context export, snapshot diffing, a live watch mode, and a pytest scaffolding API.

Tested against real-world projects with 3,400+ nodes and 4,000+ edges.

---

## Features

| Feature | Details |
|---|---|
| **AST-only scanning** | Analyzes Python code without executing it — safe for any codebase |
| **8 specialized scanners** | Routes, models, services, tasks, properties, complexity, query tracing, git churn |
| **`async def` support** | All scanners handle both `def` and `async def` view functions correctly |
| **Interactive browser UI** | Served locally at `http://localhost:7891` via a pre-built React SPA |
| **Multiple diagram types** | Graph, Route Map, ERD, Complexity Heatmap, Dead Weight, Blind Spots, Search, Risk, Properties, Diff |
| **Auth-aware route display** | Route Map and Sidebar show auth badges and decorator chips per route |
| **Test generator API** | `POST /api/generate/tests` scaffolds a pytest suite from the live graph — one stub per service method, auth-aware, zero file writes |
| **Background daemon mode** | `--background` flag starts the server as a detached process — safe for agent and CI workflows |
| **Git churn + risk scoring** | Enriches nodes with commit frequency and composite risk scores |
| **Watch mode** | Auto-rescans on `.py` file changes and pushes live updates via SSE |
| **AI context export** | Generates structured Markdown context for any node — ready for LLMs |
| **Snapshot & diff** | Capture named snapshots and compare architecture across time |

---

## Installation

```bash
# Clone the repository
git clone https://github.com/reddinger2001/Flask-Brain.git
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

# Scan in the background — returns immediately, server keeps running
flask-brain scan ~/projects/my-flask-app --background

# Scan, watch for changes, and auto-refresh
flask-brain scan ~/projects/my-flask-app --watch
```

---

## CLI Reference

### `flask-brain scan`

Scan a project, write graph data to `.flask-brain/`, and start the server.

```
flask-brain scan <path> [options]

Options:
  --output, -o     Custom output directory (default: <path>/.flask-brain/)
  --port, -p       HTTP server port (default: 7891)
  --watch, -w      Watch for .py changes and auto-rescan
  --no-serve       Write graph data only — don't start the server
  --background, -b Start server in background (daemon mode) — returns immediately
```

**Examples:**

```bash
# Basic scan
flask-brain scan ~/projects/my-flask-app

# Scan and keep running in the background
flask-brain scan ~/projects/my-flask-app --background

# Custom port
flask-brain scan ~/projects/my-flask-app --port 8080

# Scan + watch mode (auto-rescan on file changes)
flask-brain scan ~/projects/my-flask-app --watch

# Scan only — no browser, no server
flask-brain scan ~/projects/my-flask-app --no-serve

# Custom output directory
flask-brain scan ~/projects/my-flask-app --output /data/brain-output
```

---

### `flask-brain serve`

Start the server for a previously scanned project (reads from `.flask-brain/`).

```
flask-brain serve <path> [options]

Options:
  --port, -p       HTTP server port (default: 7891)
  --watch, -w      Watch for .py changes and auto-rescan
  --background, -b Start server in background (daemon mode) — returns immediately
```

**Examples:**

```bash
flask-brain serve ~/projects/my-flask-app
flask-brain serve ~/projects/my-flask-app --watch --port 9000

# Background mode — useful for agents and scripts
flask-brain serve ~/projects/my-flask-app --background
```

**Background mode** forks the server into a detached process. The PID is written to `.flask-brain/server.pid` and output is logged to `.flask-brain/server.log`. Use `flask-brain stop` to shut it down.

---

### `flask-brain stop`

Stop a background Flask Brain server.

```
flask-brain stop <path>
```

**Example:**

```bash
flask-brain stop ~/projects/my-flask-app
```

Sends `SIGTERM` to the PID recorded in `.flask-brain/server.pid` and removes the PID file. Safe to run if the server is already gone — the stale PID file is cleaned up automatically.

---

### `flask-brain status`

Show whether the Flask Brain server is running for a project.

```
flask-brain status <path> [options]

Options:
  --port, -p   Port to probe (default: 7891)
```

**Example:**

```bash
flask-brain status ~/projects/my-flask-app
# ● Server is running (PID 12345)
# ✓ Port 7891 is responding
```

Reports both PID file state and whether the port is actually accepting connections.

---

### `flask-brain export-context`

Export AI-ready Markdown context for a specific node or route. Useful for pasting into LLM prompts.

```
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
  --node "service::UserService" \
  --format json \
  --depth 4 \
  --output context.json
```

---

### `flask-brain snapshot`

Capture a named snapshot of the current graph state.

```
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

```
flask-brain snapshots <path> [options]

Options:
  --delete   Delete a snapshot by ID
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

```
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

## Test Generator API

Flask Brain can scaffold a pytest test suite directly from the live graph via a REST API. It never writes files — pipe the output where you need it.

### `POST /api/generate/tests`

Generates pytest tests for a blueprint, service, or route node.

**Request body:**

```json
{
  "target": "<node_id>",
  "debug": false
}
```

- **`target`** *(required)* — Node ID to generate tests for. Use a blueprint (`blueprint::my_bp`), service (`service::UserService`), or route (`route::GET /api/users`). Use `GET /api/search?q=<keyword>` to discover valid IDs.
- **`debug`** *(optional, default `false`)* — Returns raw route metadata instead of generated code. Useful for diagnosing stale scans or unexpected auth values.

**Response:**

```json
{
  "target_id": "blueprint::my_bp",
  "target_label": "my_bp",
  "target_type": "blueprint",
  "output_path": "tests/test_my_bp.py",
  "tiers": {
    "routes": "...generated route test code...",
    "services": "...generated service scaffold..."
  },
  "combined": "...full file ready to write...",
  "stats": {
    "route_count": 8,
    "service_count": 3,
    "model_count": 4,
    "test_count": 27
  },
  "warnings": []
}
```

**Error response (node not found):**

```json
{
  "error": "Node 'blueprint::typo' not found in graph",
  "suggestions": ["blueprint::my_bp", "blueprint::other_bp"]
}
```

**Examples:**

```bash
# Generate tests for a blueprint and write to file
curl -s -X POST http://localhost:7891/api/generate/tests \
  -H "Content-Type: application/json" \
  -d '{"target": "blueprint::my_bp"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['combined'])" \
  > tests/test_my_bp.py

# Inspect raw route metadata before generating
curl -s -X POST http://localhost:7891/api/generate/tests \
  -H "Content-Type: application/json" \
  -d '{"target": "blueprint::my_bp", "debug": true}' | python3 -m json.tool

# Find the right node ID first
curl -s "http://localhost:7891/api/search?q=my_bp" | python3 -c \
  "import sys,json; [print(n['id'], n['type']) for n in json.load(sys.stdin)['nodes']]"
```

### What gets generated

**Route tests** (fully functional):
- One test class per route
- `test_unauthenticated_returns_302` for every `auth_required` route — verifies the login redirect without a session
- `test_authenticated_returns_200` stub pre-wired with the correct URL and HTTP method
- Class docstring includes URL, HTTP methods, and auth status

**Service tests** (scaffolded with TODOs):
- One test class per service
- **One `def test_<method>()` stub per public method** — includes the exact call hint and model import comments
- `test_not_found_raises` stub for exception path coverage
- `test_persists_to_db` stub (only emitted when write DB ops are detected)
- Model names and import paths inferred from service source file AST when graph edges are incomplete

**`test_count`** in the response stats reflects actual generated test methods — not a rough estimate.

**Auth detection** uses decorator name hints. Recognized decorators:
`login_required`, `auth_required`, `require_login`, `require_auth`, `admin_required`,
`roles_required`, `permission_required`, `fresh_login_required`, `jwt_required`, `token_required`

Unknown decorators are stored verbatim in `decorators[]` and shown in the UI but do not trigger auth stubs. Add them to `_AUTH_DECORATOR_HINTS` in `route_scanner.py` to enable detection.

**Stale metadata warning:** If a route node was scanned before auth-detection was added, it may lack `auth_required` and `decorators` keys. The generator emits a warning in the response and adds a comment in the generated class docstring. Re-run `flask-brain scan` to refresh.

---

## Agent / CI Workflow

Background mode makes Flask Brain safe for automated workflows where the calling process can't block:

```bash
# 1. Scan the project (no server)
flask-brain scan ~/projects/my-app --no-serve

# 2. Start the server in the background
flask-brain serve ~/projects/my-app --background

# 3. Use the API (the scan/serve commands returned immediately)
curl -s http://localhost:7891/api/manifest

# 4. Generate test scaffolding
curl -s -X POST http://localhost:7891/api/generate/tests \
  -H "Content-Type: application/json" \
  -d '{"target": "blueprint::auth"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['combined'])" \
  > tests/test_auth.py

# 5. Check status any time
flask-brain status ~/projects/my-app

# 6. Stop when done
flask-brain stop ~/projects/my-app
```

---

## Browser UI Tabs

Once the server is running at `http://localhost:7891`:

| Tab | What it shows |
|---|---|
| **Graph** | Full interactive node graph. Click blueprints to expand routes. Click nodes for details and sequence diagrams. |
| **Route Map** | Blueprint → route hierarchy. Expandable tree with HTTP method badges, auth badges, and decorator chips per route. |
| **ERD** | Entity-Relationship Diagram for all SQLAlchemy models. Shows columns, types, and relationships. |
| **Heatmap** | Complexity heatmap — color-coded by cyclomatic complexity and line count. |
| **Dead Weight** | Nodes with no incoming edges — likely unused code. |
| **Blind Spots** | Nodes with no outgoing edges — functions that call nothing. |
| **Search** | Free-text + predicate search across the full graph. Predicates: `type:`, `file:`, `label:`, `blueprint:`, `complexity=`. |
| **Risk 🔥** | Top 50 highest-risk nodes ranked by composite score (complexity × churn × DB ops). Sortable. |
| **Properties 🔍** | Search class properties and variables — type badges, getter/setter/deleter decorators, read-only warnings, source locations. |
| **Diff 📊** | Visual diff between two snapshots — added/removed/modified nodes and edges with filter chips. |

---

## What Gets Detected

Flask Brain uses 8 specialized scanners:

### RouteScanner
- `@app.route` and `@bp.route` decorators
- Blueprint declarations and `register_blueprint()` calls
- URL prefixes and HTTP methods
- Auth decorator detection (`login_required`, `auth_required`, and 8 other common patterns)
- Unknown decorators stored verbatim in `decorators[]`
- Full `async def` support

### ModelScanner
- SQLAlchemy Model classes (Flask-SQLAlchemy 2.x and SQLAlchemy 2.x)
- Column definitions with types
- `relationship()` and `ForeignKey` declarations
- Both `db.Model` and `DeclarativeBase` patterns

### ServiceScanner
- Service classes (`*Service`, `*Repository`, `*Manager`)
- Service modules (`*_service.py`, `*_repository.py`)
- Public methods (including `@staticmethod` and `@classmethod`)

### ViewFunctionTracer
- Call chains from view functions to services and models
- `service::ClassName → model::M` USES_MODEL edges for all service class methods, including `@staticmethod`
- Model usage inferred from import statements when cross-file
- Full `async def` support

### CeleryTaskScanner
- `@celery.task`, `@shared_task`, `@app.task` decorators

### ComplexityAnalyzer
- Cyclomatic complexity per function
- Line counts and fat class detection (>10 methods or >300 lines)

### QueryTracer
- `db.session.*`, `Model.query.*`, `select(Model)` patterns
- Classifies each operation as `READ`, `WRITE`, or `DELETE`

### PropertyScanner
- `@property`, `@x.setter`, `@x.deleter` decorators
- Class variables and instance variables (`self.x = ...`)
- Cross-class attribute reads and writes
- Flags orphaned getters (getter defined, no setter) and orphaned setters

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
├── server.pid                 # PID of background server (when --background is used)
├── server.log                 # Background server stdout/stderr
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

Flask Brain watches for `.py` file changes, debounces rapid saves (1 second), re-runs the full scan pipeline, and pushes updated graph data to the browser via **Server-Sent Events (SSE)**. The UI auto-reloads without a manual refresh.

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
| `property_app` | Class properties, instance variables, and `@property` decorators |

### Test Suite

365 tests, 3 skipped — covering all scanners, graph analysis methods, server endpoints, snapshot management, diff engine, test generator, and scanner ordering.

---

## Architecture

```
flask-brain scan /path/to/project
    │
    ├─ RouteScanner         → routes, blueprints, auth decorators
    ├─ ModelScanner         → models, columns, relationships
    ├─ ServiceScanner       → service classes/modules (runs before ViewFunctionTracer)
    ├─ ViewFunctionTracer   → call chains, service→model edges
    ├─ CeleryTaskScanner    → async tasks
    ├─ ComplexityAnalyzer   → complexity metrics
    ├─ QueryTracer          → database operations
    ├─ PropertyScanner      → class/instance vars, @property decorators
    └─ GitChurnAnalyzer     → commit frequency + risk scores
        │
        └─ GraphBuilder → unified graph
            │
            ├─ graph.write() → .flask-brain/*.json
            │
            └─ start_server() → http://localhost:7891
                ├─ React SPA (pre-built dist)
                ├─ SSE endpoint (/api/events)
                ├─ Test generator (/api/generate/tests)
                └─ ProjectWatcher (--watch mode)
```

**Scanner ordering matters:** `ServiceScanner` runs before `ViewFunctionTracer` so that `service::` nodes exist in the graph when the view tracer emits `service → model` edges. `Graph.add_edge()` silently drops edges whose source node doesn't exist yet.

---

## Project Structure

```
flask-brain/
├── flask_brain/
│   ├── cli.py                      # Typer CLI (scan, serve, stop, status, export-context, snapshot, snapshots, diff)
│   ├── _daemon.py                  # Background server subprocess entry point
│   ├── graph.py                    # Node, Edge, Graph, GraphBuilder
│   ├── server.py                   # HTTP server + SSE + test generator endpoint
│   ├── context_export.py           # AI context generator (BFS-bounded)
│   ├── test_generator.py           # Pytest test scaffolder (POST /api/generate/tests)
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
│       ├── property_scanner.py
│       └── git_churn_analyzer.py
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/             # GraphView, RouteMapView, ERDView, HeatmapView,
│   │   │                           # DeadWeightView, BlindSpotsView, SearchView,
│   │   │                           # RiskView, PropertyTraceView, DiffView
│   │   └── types/graph.ts
│   └── dist/                       # Pre-built React SPA (committed)
├── tests/
│   ├── fixtures/
│   ├── test_graph.py
│   ├── test_route_scanner.py
│   ├── test_model_scanner.py
│   ├── test_view_tracer.py
│   ├── test_service_scanner.py
│   ├── test_property_scanner.py
│   ├── test_server.py
│   ├── test_diff.py
│   ├── test_test_generator.py
│   └── ...
├── pyproject.toml
└── README.md
```

---

## Inspired By

Flask Brain was inspired by [Laravel Brain](https://github.com/nicahzif/laravel-brain) — an architecture visualizer for Laravel projects. The concept of AST-driven, zero-execution scanning adapted here for the Python/Flask ecosystem.

---

## License

MIT
