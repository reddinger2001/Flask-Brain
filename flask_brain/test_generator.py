"""Test scaffolding generator for Flask Brain.

Reads the scanned graph and generates pytest test scaffolding for a target
blueprint, service, or route. The generated tests are fully functional for
routes and scaffolded with TODOs for services.

The generator never writes files — it returns the test code as a string that
agents or users write to disk themselves.
"""

from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask_brain.graph import Graph, Node

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_tests(
    graph: "Graph",
    target_id: str,
    conftest_path: str | None = None,
    output_path: str | None = None,
    project_root: "Path | str | None" = None,
) -> dict:
    """Generate pytest test scaffolding for a target node.
    
    Parameters
    ----------
    graph:
        The full project graph (loaded from ``graph-all.json``).
    target_id:
        ID of the target node (blueprint, service, or route).
    conftest_path:
        Optional path to existing conftest.py (for fixture discovery).
    output_path:
        Optional desired output file path (returned in response).
    project_root:
        Absolute path to the project root.  When provided, the generator reads
        service source files to infer model names from import statements — filling
        the gap when graph edges are incomplete.  Falls back to
        ``graph.project_path`` if set, then skips source inference if neither
        is available.
    
    Returns
    -------
    dict with keys:
        target_id: str
        target_label: str
        target_type: str
        output_path: str
        tiers: dict with "routes" and "services" keys (generated code)
        combined: str (full combined test file)
        stats: dict with counts
        warnings: list of str
    
    Raises
    ------
    ValueError:
        If target_id not found or unsupported node type.
    """
    node = graph.get_node(target_id)
    if not node:
        raise ValueError(f"Node '{target_id}' not found")

    # Resolve project root for source-based model inference
    if project_root is not None:
        project_root = Path(project_root)
    else:
        project_root = getattr(graph, "project_path", None)

    target_type = node.type.value
    
    # Resolve scope based on target type
    if target_type == "blueprint":
        scope = graph.blueprint_subgraph(target_id)
        routes = [graph.get_node(r["id"]) for r in scope["routes"]]
        services = [graph.get_node(s["id"]) for s in scope["services"]]
        models = [graph.get_node(m["id"]) for m in scope["models"]]
    elif target_type == "service":
        scope = graph.trace_node(target_id)
        routes = []
        services = [node]
        models = [graph.get_node(m["id"]) for m in scope["models_used"]]
    elif target_type == "route":
        scope = graph.trace_route(target_id)
        routes = [node]
        services = [graph.get_node(s["id"]) for s in scope["services"]]
        models = [graph.get_node(m["id"]) for m in scope["models"]]
    else:
        raise ValueError(f"Unsupported target type: {target_type} (must be blueprint, service, or route)")
    
    # Filter out None values
    routes = [r for r in routes if r]
    services = [s for s in services if s]
    models = [m for m in models if m]
    
    # Generate tiers
    routes_code = _generate_routes_tier(routes, graph)
    services_code = _generate_services_tier(services, models, graph, project_root)
    
    # Collect warnings
    warnings = []
    dead_weight = {n.id for n in graph.dead_weight()}
    for s in services:
        if s.id in dead_weight:
            warnings.append(f"{s.label} has no callers (dead-weight) — pragma: no cover candidate")
        complexity = s.metadata.get("complexity", 0)
        if complexity > 20:
            warnings.append(f"{s.label} has high complexity ({complexity}) — prioritise branch coverage")

    for r in routes:
        if "auth_required" not in r.metadata and "decorators" not in r.metadata:
            warnings.append(
                f"{r.label}: graph metadata is stale — re-run `flask-brain scan` to detect "
                f"auth decorators and async view functions. Auth tests may be missing."
            )
    
    for m in models:
        if not m.metadata.get("columns"):
            warnings.append(f"{m.label} has no column data — factory args may be incomplete")
    
    # Assemble combined file
    combined = _assemble_combined_file(
        target_id=target_id,
        target_label=node.label,
        routes_code=routes_code,
        services_code=services_code,
        routes=routes,
        services=services,
    )
    
    # Stats
    test_count = len(routes) * 2 + len(services) * 3  # rough estimate
    
    # Default output path
    if not output_path:
        safe_label = node.label.replace("/", "_").replace(" ", "_").replace("::", "_").lower()
        output_path = f"tests/test_{safe_label}.py"
    
    return {
        "target_id": target_id,
        "target_label": node.label,
        "target_type": target_type,
        "output_path": output_path,
        "tiers": {
            "routes": routes_code,
            "services": services_code,
        },
        "combined": combined,
        "stats": {
            "route_count": len(routes),
            "service_count": len(services),
            "model_count": len(models),
            "test_count": test_count,
        },
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Routes tier generator
# ---------------------------------------------------------------------------

def _generate_routes_tier(routes: list["Node"], graph: "Graph") -> str:
    """Generate route test classes — one per route, unique class names guaranteed."""
    if not routes:
        return ""

    seen_class_names: set = set()
    classes = []
    for route in routes:
        classes.append(_generate_route_class(route, graph, seen_class_names))

    return "\n\n".join(classes)


def _generate_route_class(route: "Node", graph: "Graph", seen_class_names: set) -> str:
    """Generate a test class for a single route.

    Parameters
    ----------
    seen_class_names:
        Mutable set of class names already emitted in this generation pass.
        Updated in-place; used to de-duplicate classes that share a sanitized
        path (e.g. GET and POST on the same URL).
    """
    meta = route.metadata
    methods = meta.get("methods", ["GET"])
    raw_url = meta.get("url", route.label.split()[-1] if " " in route.label else "/unknown")
    auth_required = (
        meta.get("auth_required", False)
        or "login_required" in str(meta.get("decorators", []))
    )
    # Warn in generated output if metadata looks stale (no decorator data at all).
    # This happens when the graph was scanned before decorator detection was added.
    # Resolution: re-run `flask-brain scan` to rebuild graph-all.json.
    stale_metadata = "auth_required" not in meta and "decorators" not in meta
    is_api = "/api/" in raw_url

    # Substitute param tokens with concrete placeholder values for client calls
    url, param_comments = _substitute_url_params(raw_url)

    # Build a unique class name: include the HTTP method to avoid collisions when
    # the same URL path handles multiple methods (e.g. GET and POST).
    primary_method = methods[0].upper()
    label_parts = route.label.split()
    raw_path = label_parts[-1] if len(label_parts) > 1 else route.label
    path_part = _sanitize_url_for_class_name(raw_path)
    base_name = f"Test{primary_method.capitalize()}{_to_pascal_case(path_part)}Route"

    # Guarantee uniqueness within this generation pass
    class_name = base_name
    suffix = 2
    while class_name in seen_class_names:
        class_name = f"{base_name}{suffix}"
        suffix += 1
    seen_class_names.add(class_name)

    pm = primary_method.lower()   # for use in generated method calls

    has_params = bool(param_comments)

    lines = [
        f'class {class_name}:',
        f'    """Tests for {route.label} ({route.id})',
        f'',
        f'    Fixtures expected in conftest.py:',
        f'        app    — configured Flask application instance',
        f'        client — unauthenticated Flask test client',
    ]
    if stale_metadata:
        lines.append(
            f'        # WARNING: graph metadata is stale — re-run `flask-brain scan` to detect'
            f' auth decorators and async view functions correctly.'
        )
    if auth_required:
        lines.append(
            f'        # TODO: add an `auth_client` fixture that logs in before yielding'
        )
    if has_params:
        lines.append(
            f'        # TODO: add fixtures that create the DB rows for the IDs used below'
        )
    lines.extend([f'    """', ''])

    # Emit param substitution notes once at class level
    if param_comments:
        for comment in param_comments:
            lines.append(f'    {comment}')
        lines.append('')

    # ── Unauthenticated test ──────────────────────────────────────────────────
    # Always runnable — no fixtures, no DB rows required.
    # Protected routes:  assert redirect/rejection (302 or 401) — this PASSES immediately.
    # Open routes:       assert 200 — this PASSES on a clean app with no setup,
    #                    UNLESS the URL contains placeholder IDs that may 404.
    if auth_required:
        lines.extend([
            f'    def test_unauthenticated_returns_302(self, client):',
            f'        """Unauthenticated request must be redirected to login."""',
            f'        resp = client.{pm}("{url}")',
            f'        assert resp.status_code in (302, 401)',
            '',
        ])
    elif has_params:
        # Open route but URL has placeholder IDs — skip until real fixtures exist.
        lines.extend([
            f'    @pytest.mark.skip(reason="URL contains placeholder IDs — wire fixture IDs before running")',
            f'    def test_{pm}_returns_200(self, client):',
            f'        """Open route: {pm.upper()} must return 200 with valid IDs."""',
            f'        resp = client.{pm}("{url}")',
            f'        assert resp.status_code == 200',
            '',
        ])
    else:
        lines.extend([
            f'    def test_{pm}_returns_200(self, client):',
            f'        """Open route: {pm.upper()} request must return 200."""',
            f'        resp = client.{pm}("{url}")',
            f'        assert resp.status_code == 200',
            '',
        ])

    # ── Authenticated success test ────────────────────────────────────────────
    # Only emit this stub when it adds value:
    #   - auth_required=True  → developer must wire an auth fixture to get 200
    #   - has_params=True     → developer must replace placeholder IDs with real fixtures
    # Open routes with no params already have a runnable 200 test above; a
    # second skipped stub would just be noise.
    if auth_required or has_params:
        skip_reasons = []
        if auth_required:
            skip_reasons.append("replace `client` with an `auth_client` fixture that logs in")
        if has_params:
            skip_reasons.append("replace placeholder IDs with real fixture IDs")
        skip_reason = "; ".join(skip_reasons)

        lines.extend([
            f'    @pytest.mark.skip(reason="{skip_reason}")',
            f'    def test_{pm}_authenticated_returns_200(self, client):',
            f'        """Authenticated request must return 200.',
            f'',
            f'        Steps to enable:',
        ])
        if auth_required:
            lines.extend([
                f'          1. Add an `auth_client` fixture to conftest.py that logs in.',
                f'          2. Replace `client` with `auth_client` in the method signature and call.',
            ])
        if has_params:
            step = 3 if auth_required else 1
            lines.extend([
                f'          {step}. Replace placeholder IDs in the URL with IDs from real fixtures.',
                f'             e.g. create the required DB rows in a fixture and pass their IDs here.',
            ])
        lines.extend([
            f'        """',
            f'        resp = client.{pm}("{url}")',
            f'        assert resp.status_code == 200',
            '',
        ])

    # ── POST/PUT/PATCH: missing-fields validation ─────────────────────────────
    # Skipped when URL has placeholder IDs (would 404 before reaching validation).
    if any(m in ["POST", "PUT", "PATCH"] for m in methods):
        if has_params:
            lines.extend([
                f'    @pytest.mark.skip(reason="replace placeholder IDs with real fixture IDs before running")',
                f'    def test_missing_fields_returns_400(self, client):',
                f'        """Submitting an empty body must be rejected."""',
                f'        resp = client.post("{url}", json={{}})',
                f'        assert resp.status_code in (400, 422)  # TODO: verify expected status',
                '',
            ])
        else:
            lines.extend([
                f'    def test_missing_fields_returns_400(self, client):',
                f'        """Submitting an empty body must be rejected."""',
                f'        resp = client.post("{url}", json={{}})',
                f'        assert resp.status_code in (400, 422)  # TODO: verify expected status',
                '',
            ])

    # ── API routes: Content-Type assertion ────────────────────────────────────
    if is_api:
        if has_params:
            lines.extend([
                f'    @pytest.mark.skip(reason="replace placeholder IDs with real fixture IDs before running")',
                f'    def test_returns_json(self, client):',
                f'        """API route must respond with JSON Content-Type."""',
                f'        resp = client.{pm}("{url}")',
                f'        assert "json" in resp.content_type',
                '',
            ])
        else:
            lines.extend([
                f'    def test_returns_json(self, client):',
                f'        """API route must respond with JSON Content-Type."""',
                f'        resp = client.{pm}("{url}")',
                f'        assert "json" in resp.content_type',
                '',
            ])

    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# Services tier generator
# ---------------------------------------------------------------------------

def _infer_models_from_source(service: "Node", project_root: Path) -> list[tuple[str, str]]:
    """Extract model names and their import paths from a service's source file.

    Reads the service file via AST and returns every name that looks like a
    SQLAlchemy model — identified by being imported from a module path containing
    ``models`` and being a CamelCase class name.  Falls back to an empty list
    if the file cannot be read or parsed.

    Returns
    -------
    list of (class_name, dotted_import_path) tuples, e.g.
        [("Invoice", "app.billing.models.invoice"),
         ("LineItem", "app.billing.models.line_item")]
    """
    if not service.file_path or not project_root:
        return []

    source_path = project_root / service.file_path
    if not source_path.exists():
        return []

    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []

    results: list[tuple[str, str]] = []
    seen: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        # Only consider imports from model modules
        if "model" not in module.lower():
            continue
        for alias in node.names:
            # Use the local alias if present, otherwise the original name
            local_name = alias.asname if alias.asname else alias.name
            # Only include CamelCase names (likely class names, not functions/constants)
            if local_name and local_name[0].isupper() and local_name not in seen:
                seen.add(local_name)
                results.append((local_name, module))

    return results


def _generate_services_tier(services: list["Node"], models: list["Node"], graph: "Graph", project_root: "Path | None" = None) -> str:
    """Generate scaffolded service tests with real factory inference."""
    if not services:
        return ""

    classes = []
    for service in services:
        classes.append(_generate_service_class(service, models, graph, project_root))
    
    return "\n\n".join(classes)


def _generate_service_class(service: "Node", models: list["Node"], graph: "Graph", project_root: "Path | None" = None) -> str:
    """Generate a test class for a single service."""
    class_name = f"Test{_to_pascal_case(service.label.split('.')[-1])}"

    # Infer model names from source imports — graph edges may be incomplete for
    # services that import models cross-file.  Source is the ground truth.
    inferred_models = _infer_models_from_source(service, project_root) if project_root else []
    # Merge with graph-resolved models (graph models take precedence as they are confirmed)
    graph_model_names = {m.label for m in models}
    all_model_names = list(graph_model_names)
    for name, module in inferred_models:
        if name not in graph_model_names:
            all_model_names.append(name)

    lines = [
        f'class {class_name}:',
        f'    """Tests for {service.id}',
        f'',
        f'    Coverage targets:',
    ]

    # Add coverage target hints
    complexity = service.metadata.get("complexity", 0)
    db_ops = service.metadata.get("db_operations", [])
    has_write_ops = any(
        op.get("type") in ["INSERT", "UPDATE", "DELETE", "WRITE"]
        if isinstance(op, dict) else "add" in str(op).lower() or "commit" in str(op).lower()
        for op in (db_ops if isinstance(db_ops, list) else [])
    )

    lines.append(f'      - happy path → returns expected result')
    lines.append(f'      - not found → raises exception  # TODO: verify exception type')
    if has_write_ops:
        lines.append(f'      - write operation → persists to DB')
    if complexity > 5:
        lines.append(f'      # TODO: add branch coverage tests (complexity={complexity})')
    lines.extend([
        f'    """',
        '',
    ])

    # Happy path test
    lines.extend([
        f'    def test_happy_path(self, app, db):',
        f'        """Service returns expected result for valid inputs."""',
        f'        with app.app_context():',
        f'            # TODO: build required fixtures',
    ])
    if all_model_names:
        lines.append(f'            # Models used: {", ".join(sorted(all_model_names))}')
    if inferred_models:
        # Emit concrete import hints so the dev can copy-paste
        for name, module in inferred_models:
            lines.append(f'            # from {module} import {name}')
    lines.extend([
        f'            # TODO: instantiate service and call method',
        f'            result = None  # TODO: call service method',
        f'        assert result is not None',
        '',
    ])

    # Not-found test — use 999999 so the intent is unambiguous
    lines.extend([
        f'    def test_not_found_raises(self, app):',
        f'        """Service raises an exception for a nonexistent ID."""',
        f'        with app.app_context():',
        f'            with pytest.raises((ValueError, Exception)):  # TODO: narrow exception type',
        f'                pass  # TODO: call service method with id=999999',
        '',
    ])

    # DB persistence test if write ops detected
    if has_write_ops:
        # Use first write-touching model as the example in the assertion hint
        example_model = all_model_names[0] if all_model_names else "MyModel"
        lines.extend([
            f'    def test_persists_to_db(self, app, db):',
            f'        """Write operation must persist to the database."""',
            f'        with app.app_context():',
            f'            # TODO: call service method that writes to DB',
            f'            db.session.commit()',
            f'        # TODO: assert DB state changed',
            f'        # Example: assert {example_model}.query.count() == 1',
            '',
        ])

    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# Combined file assembly
# ---------------------------------------------------------------------------

def _assemble_combined_file(
    target_id: str,
    target_label: str,
    routes_code: str,
    services_code: str,
    routes: list["Node"],
    services: list["Node"],
) -> str:
    """Assemble the full test file with imports and sections."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Count TODOs
    todo_count = routes_code.count("TODO") + services_code.count("TODO")
    
    # Build coverage targets summary
    coverage_targets = []
    for r in routes:
        coverage_targets.append(f"  - {r.label} (route)")
    for s in services:
        coverage_targets.append(f"  - {s.label} (service)")
    
    coverage_summary = "\n".join(coverage_targets) if coverage_targets else "  (none)"
    
    lines = [
        f'"""',
        f'Auto-generated by Flask Brain test generator.',
        f'Target: {target_label} ({target_id})',
        f'Generated: {timestamp}',
        f'',
        f'Coverage targets:',
        coverage_summary,
        f'',
        f'TODO items remaining: {todo_count}',
        f'"""',
        '',
        'import pytest',
        'from datetime import date, datetime',
        '',
        '# ── Imports (adjust paths to match your project) ──────────────────────────────',
        '# TODO: Add service and model imports',
        '# Example:',
        '# from app.services.auth_service import AuthService',
        '# from app.models import User, Contract',
        '',
    ]
    
    # Routes section
    if routes_code:
        lines.extend([
            '# ── Routes ────────────────────────────────────────────────────────────────────',
            routes_code,
            '',
        ])
    
    # Services section
    if services_code:
        lines.extend([
            '# ── Services ──────────────────────────────────────────────────────────────────',
            services_code,
            '',
        ])
    
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_pascal_case(s: str) -> str:
    """Convert snake_case or kebab-case to PascalCase."""
    parts = s.replace("-", "_").split("_")
    return "".join(p.capitalize() for p in parts if p)


def _sanitize_url_for_class_name(url: str) -> str:
    """Strip Flask URL parameter tokens from a URL path for use in a class name.

    Examples
    --------
    "/contractors/<int:contractor_id>/questionnaires"
      → "contractors_questionnaires"
    "/api/v1/users/<uuid:user_id>"
      → "api_v1_users"
    "/<string:slug>/edit"
      → "slug_edit"  (keep bare param names when they add context)
    """
    import re
    # Remove converter prefix (int:, string:, uuid:, float:, path:) and angle brackets,
    # leaving just the param name so the class name stays readable when it adds context.
    # e.g. <int:contractor_id> → contractor_id
    url = re.sub(r"<(?:[a-z_]+:)?([^>]+)>", r"\1", url)
    # Now strip leading/trailing slashes and replace remaining / and - with _
    url = url.strip("/").replace("/", "_").replace("-", "_")
    # Collapse runs of underscores (can appear when adjacent params are stripped)
    url = re.sub(r"_+", "_", url).strip("_")
    return url


def _substitute_url_params(url: str) -> tuple[str, list[str]]:
    """Replace Flask URL parameter tokens with concrete placeholder values.

    Returns
    -------
    (substituted_url, param_comments)
        substituted_url   — URL safe to pass to the test client (no angle brackets)
        param_comments    — list of '# TODO:' comment strings, one per param,
                           explaining what real value should be substituted
    Examples
    --------
    "/contractors/<int:contractor_id>/questionnaires"
      → "/contractors/1/questionnaires",
        ["# TODO: replace contractor_id=1 with a real fixture ID"]
    "/items/<uuid:item_id>"
      → "/items/00000000-0000-0000-0000-000000000001",
        ["# TODO: replace item_id=00000000-... with a real fixture ID"]
    """
    import re

    _TYPE_DEFAULTS = {
        "int":    "1",
        "float":  "1.0",
        "path":   "some/path",
        "uuid":   "00000000-0000-0000-0000-000000000001",
        "string": "test",
        "":       "1",       # bare <param> with no converter
    }

    param_comments: list[str] = []

    def _replace(match: re.Match) -> str:
        raw = match.group(1)          # e.g. "int:contractor_id" or "contractor_id"
        if ":" in raw:
            converter, name = raw.split(":", 1)
        else:
            converter, name = "", raw
        placeholder = _TYPE_DEFAULTS.get(converter, "1")
        param_comments.append(
            f"# TODO: replace {name}={placeholder} with a real fixture ID"
        )
        return placeholder

    substituted = re.sub(r"<([^>]+)>", _replace, url)
    return substituted, param_comments
