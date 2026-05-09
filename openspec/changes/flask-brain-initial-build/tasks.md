# FLASK-BRAIN-01: Tasks

## Build Discipline (read before starting)

This is a greenfield project. There is no existing code to break.

Before writing any scanner:
1. Create the fixture Flask app that the scanner will be tested against
2. Write the test first (red)
3. Implement the scanner until the test passes (green)
4. Move to the next scanner

Frontend is built separately from the Python backend. Do not mix concerns.

---

## Prerequisites

- Python 3.11+ available
- Node.js 20+ available (for frontend build only)
- Forgejo repo created at `http://192.168.1.127:3000`
- Git remotes configured: `forgejo` (push target) + `origin` (GitHub mirror, CI only)

---

## Phase 1: Project Scaffold

### Task 1.1: Create repo and project structure

- [ ] Create Forgejo repo `flask-brain` at `http://192.168.1.127:3000`
- [ ] Initialize git repo at `/Volumes/DevEnvironment/projects/FlaskBrain`
- [ ] Add `forgejo` remote
- [ ] Create `pyproject.toml` with:
  - Package name: `flask-brain`
  - Entry point: `flask-brain = "flask_brain.cli:app"`
  - Runtime deps: `typer`, `rich`, `watchdog`, `waitress`
  - Dev deps: `pytest`, `pytest-cov`, `ruff`
- [ ] Create directory structure per design.md
- [ ] Create `.opencode/config.json` for the project
- [ ] Create `README.md` with basic usage
- [ ] Initial commit and push to forgejo

### Task 1.2: CLI scaffold

- [ ] Implement `flask_brain/cli.py` with Typer:
  - `flask-brain scan <path>` — stub that prints "Scanning..."
  - `flask-brain serve <path>` — stub that prints "Serving..."
  - `flask-brain export-context <path>` — stub
- [ ] Verify `pip install -e .` works and `flask-brain --help` shows commands

### Task 1.3: Graph data model

- [ ] Implement `flask_brain/graph.py`:
  - `NodeType` enum: ROUTE, BLUEPRINT, ACTION, SERVICE, MODEL, TASK, RELATIONSHIP
  - `EdgeType` enum: CALLS, USES_MODEL, HAS_RELATIONSHIP, DISPATCHES_TASK
  - `Node` dataclass with: id, type, label, file_path, line_number, metadata
  - `Edge` dataclass with: source, target, type
  - `Graph` class: add_node(), add_edge(), to_dict(), from_dict()
  - `GraphBuilder` class: takes list of scanner outputs, assembles unified Graph
- [ ] Write `tests/test_graph.py` — unit tests for Node, Edge, Graph, GraphBuilder

---

## Phase 2: Scanner Fixtures

### Task 2.1: Create test fixture apps

Create three minimal Flask apps in `tests/fixtures/` that cover the common patterns:

- [ ] `tests/fixtures/flat_app/` — single `app.py` with `@app.route` decorators, one SQLAlchemy model, one service module
- [ ] `tests/fixtures/factory_app/` — `create_app()` factory, `models.py`, `services/user_service.py`, `routes/users.py` with blueprint
- [ ] `tests/fixtures/blueprint_app/` — multiple blueprints registered in factory, domain-organized (`users/`, `orders/`), Celery task in `tasks.py`

Each fixture must be realistic enough to exercise all scanner patterns.

---

## Phase 3: Scanners

### Task 3.1: RouteScanner

- [ ] Write `tests/test_route_scanner.py` — assert routes discovered from all three fixture apps
- [ ] Implement `flask_brain/scanners/route_scanner.py`:
  - AST walk for `@*.route(...)` decorators on function defs
  - AST walk for `add_url_rule(...)` calls
  - Detect Blueprint declarations: `bp = Blueprint('name', __name__)`
  - Detect `app.register_blueprint(bp, url_prefix='...')`
  - Build full URL by combining prefix + route path
  - Return list of RouteNode and BlueprintNode
- [ ] All tests green

### Task 3.2: ModelScanner

- [ ] Write `tests/test_model_scanner.py` — assert models, columns, and relationships discovered
- [ ] Implement `flask_brain/scanners/model_scanner.py`:
  - Detect classes inheriting from `db.Model`, `Base`, `DeclarativeBase`
  - Extract `db.Column(...)` and `mapped_column(...)` with type info
  - Extract `db.relationship(...)` and `relationship(...)` — get target model name
  - Extract `db.ForeignKey(...)` references
  - Handle both Flask-SQLAlchemy 2.x and SQLAlchemy 2.x ORM styles
  - Return list of ModelNode and RelationshipEdge
- [ ] All tests green

### Task 3.3: ViewFunctionTracer

- [ ] Write `tests/test_view_tracer.py` — assert call edges traced correctly
- [ ] Implement `flask_brain/scanners/view_tracer.py`:
  - For each discovered route's view function, walk the function AST body
  - Detect service calls: `self.service.method()`, `service_module.function()`, imported class method calls
  - Detect model queries: `Model.query.*`, `db.session.*`, `select(Model)`
  - Detect task dispatches: `.delay()`, `.apply_async()`
  - Resolve call targets by cross-referencing import statements with file paths
  - Return list of ActionNode and edges (route→action, action→service, action→model, action→task)
- [ ] All tests green

### Task 3.4: ServiceScanner

- [ ] Write `tests/test_service_scanner.py`
- [ ] Implement `flask_brain/scanners/service_scanner.py`:
  - Detect service classes: classes whose name ends in `Service` or `Repository`
  - Detect service modules: files named `*_service.py`, `*_repository.py`, `services/*.py`
  - Extract public methods with their signatures
  - Return list of ServiceNode
- [ ] All tests green

### Task 3.5: CeleryTaskScanner

- [ ] Write `tests/test_celery_scanner.py`
- [ ] Implement `flask_brain/scanners/celery_scanner.py`:
  - Detect `@celery.task`, `@shared_task`, `@app.task` decorated functions
  - Extract task name, file path, queue (if specified in decorator args)
  - Return list of TaskNode
- [ ] All tests green

### Task 3.6: ComplexityAnalyzer

- [ ] Write `tests/test_complexity_analyzer.py`
- [ ] Implement `flask_brain/scanners/complexity_analyzer.py`:
  - For each function/method in the project, compute cyclomatic complexity:
    - Start at 1, add 1 for each: `if`, `elif`, `for`, `while`, `except`, `with`, `and`, `or`, ternary
  - Count lines of code per function and per class
  - Flag "fat classes": >10 methods or >300 lines
  - Enrich existing nodes with complexity metadata; return no new nodes
- [ ] All tests green

### Task 3.7: QueryTracer

- [ ] Write `tests/test_query_tracer.py`
- [ ] Implement `flask_brain/scanners/query_tracer.py`:
  - Within each view function and service method body, detect DB operation patterns:
    - `db.session.add()`, `db.session.delete()`, `db.session.commit()`
    - `Model.query.filter()`, `Model.query.all()`, `Model.query.get()`
    - `db.session.execute(select(...))`
  - Classify as READ, WRITE, or DELETE
  - Enrich ActionNode and ServiceNode with `db_operations` list
- [ ] All tests green

---

## Phase 4: Graph Builder Integration

### Task 4.1: Wire all scanners into GraphBuilder

- [ ] Write `tests/test_graph_builder.py` — full integration test against all three fixture apps
- [ ] Implement `GraphBuilder.build(project_path)`:
  - Run all scanners
  - Deduplicate nodes (same file + line → merge)
  - Resolve cross-scanner edges (e.g., ViewTracer references a ServiceNode by name)
  - Return complete `Graph`
- [ ] Implement `Graph.write(output_dir)`:
  - Write `manifest.json`, `graph-all.json`, `graph-routes.json`, per-route `graph-<id>.json`
- [ ] All tests green

---

## Phase 5: HTTP Server + Viewer

### Task 5.1: Build React frontend

- [ ] Scaffold React + TypeScript + Vite project in `frontend/`
- [ ] Add dependencies: `cytoscape`, `cytoscape-dagre`, `cytoscape-cose-bilkent`, `mermaid`, `tailwindcss`
- [ ] Implement `Graph.tsx` — Cytoscape.js wrapper that loads graph JSON and renders nodes/edges
- [ ] Implement node color scheme per design.md
- [ ] Implement `Sidebar.tsx` — shows node details on click (type, file, line, complexity, db_ops)
- [ ] Implement tab switcher: Route Map / Call Chain / Data Model / Sequence / Heatmap
- [ ] Implement `SequenceDiagram.tsx` — renders Mermaid sequence diagram for selected route
- [ ] Implement `HeatmapView.tsx` — renders all functions colored by complexity tier
- [ ] Implement SSE listener for watch mode auto-refresh
- [ ] Implement AI context copy button (🤖) — calls `/api/context?nodeId=<id>` and copies to clipboard
- [ ] `npm run build` outputs to `flask_brain/viewer/dist/`
- [ ] Verify build output is committed and served correctly

### Task 5.2: HTTP server

- [ ] Implement `flask_brain/server.py`:
  - Serve `flask_brain/viewer/dist/` as static files at `/`
  - `GET /api/graph/all` → serve `graph-all.json`
  - `GET /api/graph/<route-id>` → serve `graph-<id>.json`
  - `GET /api/source?path=<file>&line=<n>` → return source file content
  - `GET /api/context?nodeId=<id>` → return AI context export
  - `POST /api/scan` → re-run GraphBuilder, return updated manifest
  - `GET /api/events` → SSE endpoint for watch mode
- [ ] Verify server starts, SPA loads, and graph renders in browser

### Task 5.3: Wire CLI scan command

- [ ] Update `flask-brain scan <path>` to:
  1. Run GraphBuilder against the target path
  2. Write JSON to `.flask-brain/` in the target project root (or `--output` dir)
  3. Start HTTP server (unless `--no-serve`)
  4. Open browser at `http://localhost:7891`
  5. If `--watch`, start file watcher and SSE broadcaster

---

## Phase 6: AI Context Export

### Task 6.1: Implement context exporter

- [ ] Implement `flask_brain/context_export.py`:
  - `export_context(graph, node_id, budget=4000)` → returns Markdown string
  - BFS from focal node up to depth 3
  - Include: node identity, call chain, complexity table, db_operations, source snippet
  - Enforce token budget (count words × 1.3 as token estimate); truncate source last
  - Output is deterministic
- [ ] Write `tests/test_context_export.py`
- [ ] Wire to `GET /api/context` endpoint and `flask-brain export-context` CLI command

---

## Phase 7: Watch Mode

### Task 7.1: Implement file watcher

- [ ] Implement `flask_brain/watcher.py` using `watchdog`:
  - Watch project root for `*.py` file changes
  - Debounce 2 seconds
  - On change: re-run GraphBuilder, overwrite JSON cache, broadcast SSE event
- [ ] Verify watch mode works end-to-end: edit a file in a fixture app → browser auto-refreshes graph

---

## Phase 8: Polish & Release

### Task 8.1: Test against real projects

- [ ] Run `flask-brain scan` against VendorSync at `/Volumes/DevEnvironment/projects/VendorSync`
- [ ] Run against ComplyGrid at `/Volumes/DevEnvironment/projects/ComplyGrid`
- [ ] Fix any crashes or missed patterns discovered
- [ ] Verify all five diagram types render correctly on real-world data

### Task 8.2: README and docs

- [ ] Complete `README.md` with: installation, usage, diagram types, watch mode, AI export, project structure
- [ ] Add `CONTRIBUTING.md` with frontend build instructions

### Task 8.3: CI setup

- [ ] Add `.forgejo/workflows/ci.yml`:
  - On push: run `pytest tests/` with coverage
  - On tag: build frontend + publish to PyPI
- [ ] Verify CI passes on Forgejo runner

### Task 8.4: Initial release

- [ ] Tag `v0.1.0`
- [ ] Push to forgejo
- [ ] Verify CI publishes package
