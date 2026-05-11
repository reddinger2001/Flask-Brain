"""Route scanner - detects Flask routes and blueprints."""

import ast
from pathlib import Path
from typing import Any

from flask_brain.scanners.base import BaseScanner
from flask_brain.graph import Node, Edge, NodeType, EdgeType


class RouteScanner(BaseScanner):
    """Scanner for Flask routes and blueprints."""
    
    # Decorator names (or name fragments) that indicate a route requires
    # authentication.  Checked case-insensitively against the full decorator
    # name so that project-specific wrappers like `require_auth` or
    # `admin_required` are caught alongside the Flask-Login standard.
    _AUTH_DECORATOR_HINTS = frozenset([
        "login_required",
        "auth_required",
        "require_login",
        "require_auth",
        "admin_required",
        "roles_required",
        "permission_required",
        "fresh_login_required",   # Flask-Login
        "jwt_required",           # Flask-JWT-Extended
        "token_required",
    ])

    def __init__(self, project_path: Path):
        super().__init__(project_path)
        self.blueprints: dict[str, dict[str, Any]] = {}  # name -> {url_prefix, file_path}
        self.routes: list[dict[str, Any]] = []
        self.imports: dict[str, str] = {}  # imported_name -> original_name mapping
    
    def scan(self) -> tuple[list[Node], list[Edge]]:
        """Scan project for routes and blueprints."""
        nodes = []
        edges = []
        
        # First pass: find all blueprints
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                self._extract_imports(tree, py_file)
                self._extract_blueprints(tree, py_file)
        
        # Second pass: find blueprint registrations (after all blueprints are found)
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                self._extract_blueprint_registrations(tree, py_file)
        
        # Third pass: find all routes
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                self._extract_routes(tree, py_file)
        
        # Create blueprint nodes
        for bp_name, bp_info in self.blueprints.items():
            node = Node(
                id=f"blueprint::{bp_name}",
                type=NodeType.BLUEPRINT,
                label=bp_name,
                file_path=self._get_relative_path(bp_info["file_path"]),
                line_number=bp_info.get("line_number", 0),
                metadata={
                    "url_prefix": bp_info.get("url_prefix", ""),
                }
            )
            nodes.append(node)
        
        # Create route nodes
        for route_info in self.routes:
            # Build full path with blueprint prefix
            full_path = route_info["path"]
            blueprint_name = route_info.get("blueprint")
            
            if blueprint_name and blueprint_name in self.blueprints:
                prefix = self.blueprints[blueprint_name].get("url_prefix", "")
                if prefix:
                    full_path = prefix + full_path
            
            # Create a node for each method
            for method in route_info["methods"]:
                route_id = f"route::{method} {full_path}"
                node = Node(
                    id=route_id,
                    type=NodeType.ROUTE,
                    label=f"{method} {full_path}",
                    file_path=self._get_relative_path(route_info["file_path"]),
                    line_number=route_info["line_number"],
                    metadata={
                        "methods": [method],
                        "view_function": route_info["view_function"],
                        "blueprint": blueprint_name,
                        "decorators": route_info.get("decorators", []),
                        "auth_required": route_info.get("auth_required", False),
                    }
                )
                nodes.append(node)
                
                # Create edge from blueprint to route
                if blueprint_name:
                    edge = Edge(
                        source=f"blueprint::{blueprint_name}",
                        target=route_id,
                        type=EdgeType.REGISTERS_BLUEPRINT
                    )
                    edges.append(edge)
        
        return nodes, edges
    
    def _extract_imports(self, tree: ast.Module, file_path: Path) -> None:
        """Extract import statements to track blueprint variable names."""
        for node in ast.walk(tree):
            # from routes.users import users_bp
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_name = alias.asname if alias.asname else alias.name
                    self.imports[imported_name] = alias.name
    
    def _extract_blueprints(self, tree: ast.Module, file_path: Path) -> None:
        """Extract Blueprint declarations."""
        for node in ast.walk(tree):
            # Look for: bp = Blueprint('name', __name__)
            if isinstance(node, ast.Assign):
                if isinstance(node.value, ast.Call):
                    if self._is_blueprint_call(node.value):
                        # Get blueprint name from first argument
                        if node.value.args:
                            bp_name = self._get_string_value(node.value.args[0])
                            if bp_name:
                                # Get variable name
                                var_name = None
                                if node.targets:
                                    target = node.targets[0]
                                    if isinstance(target, ast.Name):
                                        var_name = target.id
                                
                                if var_name:
                                    self.blueprints[bp_name] = {
                                        "file_path": file_path,
                                        "line_number": node.lineno,
                                        "var_name": var_name,
                                        "url_prefix": "",
                                    }
    
    def _extract_blueprint_registrations(self, tree: ast.Module, file_path: Path) -> None:
        """Extract blueprint registrations to get URL prefixes."""
        for node in ast.walk(tree):
            # Look for: app.register_blueprint(bp, url_prefix='/api')
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "register_blueprint":
                        # Get blueprint variable name from first argument
                        if node.args:
                            bp_var = self._get_name_value(node.args[0])
                            if bp_var:
                                # Resolve through imports if needed
                                original_name = self.imports.get(bp_var, bp_var)
                                
                                # Find matching blueprint by var_name or original import name
                                for bp_name, bp_info in self.blueprints.items():
                                    if bp_info.get("var_name") == bp_var or bp_info.get("var_name") == original_name:
                                        # Extract url_prefix from keyword args
                                        for keyword in node.keywords:
                                            if keyword.arg == "url_prefix":
                                                prefix = self._get_string_value(keyword.value)
                                                if prefix:
                                                    bp_info["url_prefix"] = prefix
    
    def _extract_routes(self, tree: ast.Module, file_path: Path) -> None:
        """Extract route decorators from both sync and async view functions."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    route_info = self._parse_route_decorator(decorator, node, file_path)
                    if route_info:
                        self.routes.append(route_info)
    
    def _parse_route_decorator(
        self,
        decorator: ast.expr,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: Path
    ) -> dict[str, Any] | None:
        """Parse a route decorator and extract route information."""
        if not isinstance(decorator, ast.Call):
            return None
        
        # Check if it's a .route() call
        if not isinstance(decorator.func, ast.Attribute):
            return None
        
        if decorator.func.attr != "route":
            return None
        
        # Get the object being called (app, bp, etc.)
        obj_name = None
        if isinstance(decorator.func.value, ast.Name):
            obj_name = decorator.func.value.id
        
        # Determine if this is a blueprint route
        blueprint_name = None
        if obj_name and obj_name != "app":
            # Try to find matching blueprint by var_name
            for bp_name, bp_info in self.blueprints.items():
                if bp_info.get("var_name") == obj_name:
                    blueprint_name = bp_name
                    break
        
        # Extract path from first argument
        path = "/"
        if decorator.args:
            path = self._get_string_value(decorator.args[0]) or "/"
        
        # Extract methods from keyword arguments
        methods = ["GET"]  # Default
        for keyword in decorator.keywords:
            if keyword.arg == "methods":
                methods = self._get_list_values(keyword.value)
        
        # Collect all non-route decorators on this function so callers can
        # inspect them (e.g. to detect @login_required).
        other_decorators = []
        for dec in func_node.decorator_list:
            if dec is decorator:
                continue   # skip the @bp.route() we're currently parsing
            name = self._extract_decorator_name(dec)
            if name:
                other_decorators.append(name)

        # Detect auth requirement from sibling decorators
        auth_required = any(
            any(hint in name.lower() for hint in self._AUTH_DECORATOR_HINTS)
            for name in other_decorators
        )

        return {
            "path": path,
            "methods": methods,
            "view_function": func_node.name,
            "file_path": file_path,
            "line_number": func_node.lineno,
            "blueprint": blueprint_name,
            "decorators": other_decorators,
            "auth_required": auth_required,
        }
    
    def _extract_decorator_name(self, node: ast.expr) -> str | None:
        """Return a human-readable name for a decorator node.

        Handles the three common forms:
          @login_required          → "login_required"
          @roles_required("admin") → "roles_required"
          @auth.login_required     → "auth.login_required"
        """
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            # e.g. auth.login_required
            parts = []
            cur: ast.expr = node
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            return ".".join(reversed(parts))
        if isinstance(node, ast.Call):
            # e.g. roles_required("admin") — return the function name only
            return self._extract_decorator_name(node.func)
        return None

    def _is_blueprint_call(self, node: ast.Call) -> bool:
        """Check if a call is Blueprint(...)."""
        if isinstance(node.func, ast.Name):
            return node.func.id == "Blueprint"
        return False
    
    def _get_string_value(self, node: ast.expr) -> str | None:
        """Extract string value from AST node."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        # Handle old-style Str nodes (Python < 3.8)
        if isinstance(node, ast.Str):
            return node.s
        return None
    
    def _get_name_value(self, node: ast.expr) -> str | None:
        """Extract name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        return None
    
    def _get_list_values(self, node: ast.expr) -> list[str]:
        """Extract list of strings from AST node."""
        if isinstance(node, ast.List):
            values = []
            for elt in node.elts:
                val = self._get_string_value(elt)
                if val:
                    values.append(val)
            return values
        return []
