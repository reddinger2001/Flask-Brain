# FLASK-BRAIN-01: Design

## Architecture Overview

```
flask-brain scan /path/to/project
        │
        ├─ ProjectDiscovery     → locate app factory / create_app / blueprints
        ├─ RouteScanner         → AST-parse routes/**/*.py, find @bp.route / @app.route
        ├─ BlueprintScanner     → map Blueprint() declarations and registrations
        ├─ ViewFunctionTracer   → trace view function → service calls → model access
        ├─ ServiceScanner       → detect service classes/modules (heuristic + naming)
        ├─ ModelScanner         → detect SQLAlchemy Model subclasses, columns, relationships
        ├─ CeleryTaskScanner    → detect @celery.task / @shared_task decorated functions
        ├─ ComplexityAnalyzer   → cyclomatic complexity + line count per function/class
        ├─ QueryTracer          → surface db.session.* / Model.query.* calls per function
        └─ GraphBuilder         → assemble nodes + edges, write JSON cache
                │
                └─ Writes JSON → .flask-brain/ (in project root or --output dir)

flask-brain serve (or auto-launched after scan)
        │
        └─ Built-in HTTP server → serves React SPA + graph JSON at http://localhost:7891
```

---

## Component Design

### 1. CLI Entry Point (`flask_brain/cli.py`)

```
flask-brain scan <path> [--output <dir>] [--watch] [--port <n>] [--no-serve]
flask-brain serve <path> [--port <n>]
flask-brain export-context <path> [--route <route>] [--node <id>] [--format json|md]
```

Built with **Typer** (cleaner API than Click, auto-generates help docs).

### 2. Scanner Layer (`flask_brain/scanners/`)

Each scanner is independent, receives the project root path, and returns a list of graph nodes and edges. Scanners are AST-only — they never import or execute project code.

```
scanners/
  route_scanner.py        → RouteNode, BlueprintNode
  view_tracer.py          → ActionNode, edges: route→action, action→service, action→model
  service_scanner.py      → ServiceNode
  model_scanner.py        → ModelNode, RelationshipEdge
  celery_scanner.py       → TaskNode
  complexity_analyzer.py  → attaches complexity metadata to existing nodes
  query_tracer.py         → attaches db_operations list to ActionNode/ServiceNode
```

**Route detection strategies (handles mixed project structures):**
- `@app.route(...)` on view functions in flat apps
- `@bp.route(...)` on Blueprint instances (any variable name)
- `add_url_rule(...)` calls in app factory functions
- Blueprint registration: `app.register_blueprint(bp, url_prefix=...)`

**Model detection:**
- Classes inheriting from `db.Model`, `Base`, or `DeclarativeBase`
- Column definitions (`db.Column(...)`, `mapped_column(...)`)
- Relationships (`db.relationship(...)`, `relationship(...)`)
- Foreign keys

**Call chain tracing (AST-based):**
- Within a view function body, detect:
  - Method calls on injected/imported service instances
  - Direct function calls to imported service functions
  - Model queries: `Model.query.*`, `db.session.*`, `select(Model)`
  - Task dispatches: `.delay()`, `.apply_async()`, `celery.send_task()`
- Resolve call targets by matching import statements to file paths

### 3. Graph Builder (`flask_brain/graph.py`)

Assembles all scanner outputs into a unified graph model:

```python
@dataclass
class Node:
    id: str                  # e.g. "route::GET /users"
    type: NodeType           # ROUTE, BLUEPRINT, ACTION, SERVICE, MODEL, TASK, RELATIONSHIP
    label: str
    file_path: str
    line_number: int
    metadata: dict           # type-specific (complexity, db_ops, columns, etc.)

@dataclass
class Edge:
    source: str              # node id
    target: str              # node id
    type: EdgeType           # CALLS, USES_MODEL, HAS_RELATIONSHIP, DISPATCHES_TASK
```

Output files written to `.flask-brain/` in the project root:
```
.flask-brain/
  manifest.json        → project metadata, scan timestamp, node/edge counts
  graph-all.json       → full graph (all nodes + edges)
  graph-routes.json    → route-level subgraph
  graph-<route-id>.json → per-route subgraph (one per route)
```

### 4. Viewer (`flask_brain/viewer/`)

React SPA bundled with the Python package (pre-built, no Node.js needed at runtime).

**Tech stack:**
- React 18 + TypeScript
- Cytoscape.js — battle-tested graph rendering, same library as Laravel Brain
- `cytoscape-dagre` — hierarchical layout (best for call chains)
- `cytoscape-cose-bilkent` — force-directed layout (best for ERD)
- Tailwind CSS — styling
- Mermaid.js — sequence diagram rendering

**Graph panels (left sidebar tabs):**
1. **Route Map** — all routes grouped by blueprint, colored by HTTP method
2. **Call Chain** — per-route drill-down: route → view → services → models
3. **Data Model / ERD** — all SQLAlchemy models, columns, and relationships
4. **Sequence Diagram** — Mermaid sequence diagram for selected route (HTTP in → response out)
5. **Complexity Heatmap** — all functions/methods colored by complexity tier

**Node color scheme:**

| Node Type | Color |
|---|---|
| Route | Green `#4CAF50` |
| Blueprint | Teal `#009688` |
| View Function | Blue `#2196F3` |
| Service | Purple `#9C27B0` |
| Model | Red `#F44336` |
| Celery Task | Orange `#FF9800` |
| Relationship | Grey `#9E9E9E` |

**Complexity tier colors (heatmap):**

| Tier | Cyclomatic Complexity | Color |
|---|---|---|
| Low | 1–5 | Green |
| Moderate | 6–10 | Yellow |
| High | 11–20 | Orange |
| Critical | 21+ | Red |

### 5. HTTP Server (`flask_brain/server.py`)

Simple built-in server (Python `http.server` or `waitress`) that:
- Serves the bundled React SPA at `/`
- Serves graph JSON from `.flask-brain/` at `/api/graph/*`
- Serves source file content at `/api/source?path=<file>&line=<n>`
- Serves AI context export at `/api/context?nodeId=<id>`
- Accepts scan trigger at `POST /api/scan` (for watch mode / browser refresh button)

Default port: **7891** (avoids conflicts with common dev ports 3000, 5000, 8000, 8080).

### 6. Watch Mode (`flask_brain/watcher.py`)

Uses `watchdog` library to monitor the project directory for `.py` file changes:
- Debounce 2 seconds (avoid thrashing during saves)
- Re-runs all scanners on change
- Notifies browser via Server-Sent Events (SSE) at `/api/events`
- Browser SPA listens on SSE and auto-reloads graph data without full page refresh

### 7. AI Context Export (`flask_brain/context_export.py`)

For any selected node, generates a structured Markdown block containing:
- Node identity (type, name, file path, line number)
- Call chain (BFS up to depth 3 from selected node)
- Complexity metrics for all nodes in the chain
- DB operations surfaced in the chain
- Source snippet for the focal node (truncated to token budget, default 4000 tokens)
- Project package list from `requirements.txt` / `pyproject.toml`

Output is deterministic: same scan data + same node = identical output every time.

---

## Project Structure

```
flask-brain/                        ← repo root
├── flask_brain/                    ← Python package
│   ├── __init__.py
│   ├── cli.py                      ← Typer CLI entry point
│   ├── graph.py                    ← Node/Edge dataclasses + GraphBuilder
│   ├── server.py                   ← Built-in HTTP server
│   ├── watcher.py                  ← File watcher (watchdog)
│   ├── context_export.py           ← AI context export
│   ├── scanners/
│   │   ├── __init__.py
│   │   ├── base.py                 ← BaseScanner abstract class
│   │   ├── route_scanner.py
│   │   ├── view_tracer.py
│   │   ├── service_scanner.py
│   │   ├── model_scanner.py
│   │   ├── celery_scanner.py
│   │   ├── complexity_analyzer.py
│   │   └── query_tracer.py
│   └── viewer/                     ← Pre-built React SPA (committed as dist/)
│       └── dist/
│           ├── index.html
│           └── assets/
├── frontend/                       ← React source (built separately)
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── Graph.tsx           ← Cytoscape.js wrapper
│   │   │   ├── Sidebar.tsx         ← Node inspector panel
│   │   │   ├── RouteMap.tsx
│   │   │   ├── ERDView.tsx
│   │   │   ├── SequenceDiagram.tsx
│   │   │   └── HeatmapView.tsx
│   │   └── types/
│   │       └── graph.ts
│   ├── package.json
│   └── vite.config.ts
├── tests/
│   ├── fixtures/                   ← Sample Flask apps for scanner testing
│   │   ├── flat_app/
│   │   ├── factory_app/
│   │   └── blueprint_app/
│   ├── test_route_scanner.py
│   ├── test_model_scanner.py
│   ├── test_view_tracer.py
│   ├── test_graph_builder.py
│   └── test_complexity_analyzer.py
├── pyproject.toml
├── README.md
└── .opencode/
    └── config.json
```

---

## Data Flow

```
User runs: flask-brain scan /path/to/myapp
    │
    ▼
ProjectDiscovery identifies structure (flat / factory / blueprints)
    │
    ▼
All scanners run in sequence against project ASTs
    │
    ├─ RouteScanner         → [RouteNode, BlueprintNode, ...]
    ├─ ViewFunctionTracer   → [ActionNode, ...] + edges
    ├─ ServiceScanner       → [ServiceNode, ...]
    ├─ ModelScanner         → [ModelNode, RelationshipEdge, ...]
    ├─ CeleryTaskScanner    → [TaskNode, ...]
    ├─ ComplexityAnalyzer   → enriches existing nodes with complexity
    └─ QueryTracer          → enriches ActionNode/ServiceNode with db_ops
    │
    ▼
GraphBuilder assembles unified graph → writes .flask-brain/*.json
    │
    ▼
HTTP server starts at http://localhost:7891
    │
    ▼
Browser opens → React SPA loads graph JSON → Cytoscape renders
    │
    ▼
User clicks nodes → Sidebar shows details, source, sequence diagram
```

---

## Scanner Implementation: Key Patterns

### Route detection (handles all Flask conventions)

```python
# Pattern 1: @app.route decorator
@app.route('/users', methods=['GET', 'POST'])
def list_users(): ...

# Pattern 2: Blueprint decorator (any variable name)
@bp.route('/users')
@users_bp.route('/users')
@api.route('/users')

# Pattern 3: add_url_rule in factory
app.add_url_rule('/users', 'list_users', view_func=list_users)

# Pattern 4: Class-based views
app.add_url_rule('/users', view_func=UserView.as_view('users'))
```

AST detection uses `ast.walk()` to find `ast.FunctionDef` nodes with `ast.Call` decorators where the attribute is `route`.

### Model detection

```python
# Pattern 1: Flask-SQLAlchemy
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    orders = db.relationship('Order', back_populates='user')

# Pattern 2: SQLAlchemy 2.x declarative
class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    orders: Mapped[List['Order']] = relationship(back_populates='user')
```

Detection: walk AST for `ast.ClassDef` nodes; check bases for `Model`, `Base`, or `DeclarativeBase`.

---

## Build & Release

- **Python package:** `pyproject.toml` with `[project.scripts] flask-brain = "flask_brain.cli:app"`
- **Frontend build:** `npm run build` in `frontend/` outputs to `flask_brain/viewer/dist/` — committed to repo so users don't need Node.js
- **Distribution:** PyPI (`pip install flask-brain`) + Forgejo releases
- **CI:** Forgejo Actions — run pytest on push, build frontend, publish to PyPI on tag

---

## Dependencies

**Runtime:**
- `typer` — CLI framework
- `rich` — terminal output formatting
- `watchdog` — file system watcher
- `waitress` — production-grade WSGI server for the viewer

**Dev only:**
- `pytest` — test runner
- `pytest-cov` — coverage
- Node.js + Vite + React (frontend build only)

**No runtime dependencies on Flask or SQLAlchemy** — the tool analyzes projects that use these frameworks but does not require them itself.
