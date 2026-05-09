# FLASK-BRAIN-01: Flask Brain — Interactive Architecture Visualizer for Python/Flask Projects

**Status:** Proposed  
**Created:** 2026-05-09  
**Priority:** High  
**Estimated Effort:** 5–7 days

---

## Problem Statement

Developers working on Python/Flask applications have no fast, visual way to understand a project's architecture from its source code. The only options are:

1. **Read the code** — slow, error-prone, and requires deep familiarity with each project
2. **Build UML diagrams by hand** — time-consuming, immediately stale, and doesn't scale
3. **Use generic tools** (pyreverse, dependency-cruiser) — produce raw output with no Flask awareness; no route → service → model tracing; no interactive drill-down

The result is that developers — particularly those maintaining multiple Flask projects — carry the architecture map in their heads. New developers, returning developers, and AI coding tools all suffer from the same problem: no single source of truth for how the pieces connect.

Laravel Brain (PHP ecosystem) solved this problem elegantly: scan the codebase with static analysis, render an interactive node graph in the browser, and let developers drill through routes → controllers → services → models. Python/Flask has no equivalent.

---

## Proposed Solution

Build **Flask Brain** — a standalone Python CLI tool that:

1. **Scans any Flask project** using Python AST analysis (no code execution, no imports required)
2. **Extracts the full architecture** — routes, blueprints, view functions, services, SQLAlchemy models, Celery tasks, relationships, and complexity metrics
3. **Renders an interactive browser-based graph** — served locally via a built-in HTTP server, navigable by node type, with per-route drill-down
4. **Generates multiple diagram types** from the same scan data — call chain graphs, ERDs, sequence diagrams, complexity heatmaps

### Key Design Decisions

- **AST-based scanning** — reads Python syntax trees without executing code; works on any project regardless of whether dependencies are installed in the analysis environment
- **Standalone CLI** — installed once via pip (`pip install flask-brain`), pointed at any project (`flask-brain scan /path/to/project`); no per-project installation required
- **Self-contained viewer** — serves a React SPA at `http://localhost:7891`; all graph data is written to a local JSON cache; no network access needed
- **Structure-agnostic** — handles flat apps, app-factory pattern, blueprint-based projects, and domain-organized codebases without configuration

---

## Goals

- Provide a visual map of any Flask project's architecture within seconds of running a single command
- Support the five diagram types developers need most: route map, call chain graph, data model/ERD, sequence diagrams, and complexity heatmap
- Work against real-world projects (mixed structure, varying conventions) without requiring project-specific configuration
- Be fast enough to re-run after code changes (watch mode)
- Export AI-ready context snapshots for any node (compatible with Claude, Cursor, Copilot, etc.)

## Non-Goals

- Not a runtime profiler or debugger — analysis is static only
- Not a full Python dependency analyzer — focused on Flask architecture, not generic Python packages
- Not a production monitoring tool — dev-only, not deployed alongside the application
- Not a code formatter or linter — reads code, never modifies it

---

## Alternatives Considered

| Option | Why Rejected |
|---|---|
| pyreverse / pylint | Generic Python, not Flask-aware; no route tracing; output is Graphviz, not interactive |
| dependency-cruiser | JavaScript tool; doesn't understand Python or Flask conventions |
| Per-project install (like Laravel Brain) | Requires modification of every project; standalone CLI is lower friction and works on legacy projects |
| Jupyter notebook analysis | One-off, not reusable; requires manual setup per project |

---

## Success Criteria

- `flask-brain scan /path/to/project` completes in under 30 seconds for a medium-sized project (~50 routes, ~20 models)
- All five diagram types render correctly for at least three structurally different Flask projects (flat, app-factory, domain-organized)
- Interactive graph supports click-to-inspect for all node types
- AI context export produces a structured Markdown block usable as LLM context
- Watch mode re-scans and refreshes the browser on file changes
