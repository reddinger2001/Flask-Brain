"""View function tracer - traces call chains from view functions."""

import ast
from pathlib import Path
from typing import Any

from flask_brain.scanners.base import BaseScanner
from flask_brain.graph import Node, Edge, NodeType, EdgeType


# Flask builtins that should never be treated as service targets
FLASK_BUILTINS = {
    'jsonify', 'render_template', 'redirect', 'url_for', 'abort',
    'request', 'session', 'g', 'flash', 'send_file', 'make_response',
    'current_app', 'Response', 'get_json', 'get_flashed_messages',
    'send_from_directory', 'safe_join', 'escape', 'Markup'
}


class ViewFunctionTracer(BaseScanner):
    """Tracer for view function call chains."""
    
    def __init__(self, project_path: Path):
        super().__init__(project_path)
        self.view_functions: dict[str, dict[str, Any]] = {}
        self.imports: dict[str, dict[str, str]] = {}  # file_path -> {name: module}
        self.blueprints: dict[str, dict[str, Any]] = {}  # blueprint_name -> {var_name, url_prefix, file_path}
        self.models: set[str] = set()  # Set of known model class names
    
    def scan(self) -> tuple[list[Node], list[Edge]]:
        """Scan project for view functions and their call chains."""
        nodes = []
        edges = []
        
        # First pass: identify models, blueprints and collect imports
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                self._collect_imports(tree, py_file)
                self._identify_models(tree, py_file)
                self._identify_blueprint_declarations(tree, py_file)
        
        # Second pass: find blueprint registrations (now that all blueprints are known)
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                self._identify_blueprint_registrations(tree, py_file)
        
        # Third pass: identify view functions
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                self._identify_view_functions(tree, py_file)
        
        # Fourth pass: trace calls from view functions
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                file_nodes, file_edges = self._trace_view_calls(tree, py_file)
                nodes.extend(file_nodes)
                edges.extend(file_edges)

        # Fifth pass: trace model usage inside service/helper functions so that
        # action::fn → model::M edges are emitted even when the function is not
        # itself a view function (e.g. a service method called from a view).
        for py_file in self._get_python_files():
            tree = self._parse_file(py_file)
            if tree:
                file_nodes, file_edges = self._trace_service_model_calls(tree, py_file)
                nodes.extend(file_nodes)
                edges.extend(file_edges)

        return nodes, edges
    
    def _collect_imports(self, tree: ast.Module, file_path: Path) -> None:
        """Collect import statements from a file."""
        if str(file_path) not in self.imports:
            self.imports[str(file_path)] = {}
        
        for node in ast.walk(tree):
            # from module import Name
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    self.imports[str(file_path)][name] = f"{module}.{alias.name}" if module else alias.name
            
            # import module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    self.imports[str(file_path)][name] = alias.name
    
    def _identify_models(self, tree: ast.Module, file_path: Path) -> None:
        """Identify SQLAlchemy model classes."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if class inherits from Model, Base, or DeclarativeBase
                for base in node.bases:
                    base_name = None
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr
                    
                    if base_name in ('Model', 'Base', 'DeclarativeBase'):
                        self.models.add(node.name)
                        break

    def _get_local_models(self, file_path: Path) -> set[str]:
        """Return the set of model names visible in a given file.

        Includes both globally identified model classes and any names imported
        into this file whose resolved class name is a known model.  This allows
        service files that import ``EvidenceFile`` from a models module to have
        that name recognised as a model during call tracing.
        """
        local = set(self.models)
        file_imports = self.imports.get(str(file_path), {})
        for local_name, dotted_path in file_imports.items():
            # dotted_path is "some.module.ClassName" — the last segment is the
            # class name as it was defined in the source file.
            class_name = dotted_path.split(".")[-1]
            if class_name in self.models:
                local.add(local_name)
        return local
    
    def _identify_blueprint_declarations(self, tree: ast.Module, file_path: Path) -> None:
        """Identify Blueprint() declarations."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if isinstance(node.value, ast.Call):
                    # Check if it's Blueprint(...)
                    if isinstance(node.value.func, ast.Name) and node.value.func.id == "Blueprint":
                        # Get blueprint name from first argument
                        bp_name = None
                        if node.value.args and isinstance(node.value.args[0], ast.Constant):
                            bp_name = node.value.args[0].value
                        
                        # Get variable name
                        if node.targets and isinstance(node.targets[0], ast.Name):
                            var_name = node.targets[0].id
                            if bp_name:
                                self.blueprints[bp_name] = {
                                    "var_name": var_name,
                                    "url_prefix": "",
                                    "file_path": file_path
                                }
    
    def _identify_blueprint_registrations(self, tree: ast.Module, file_path: Path) -> None:
        """Identify register_blueprint() calls to extract URL prefixes."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == "register_blueprint":
                    # Get blueprint variable from first argument
                    if node.args and isinstance(node.args[0], ast.Name):
                        bp_var = node.args[0].id
                        
                        # Extract url_prefix from keyword args
                        url_prefix = ""
                        for keyword in node.keywords:
                            if keyword.arg == "url_prefix":
                                if isinstance(keyword.value, ast.Constant):
                                    url_prefix = keyword.value.value
                        
                        # Find the blueprint by var_name and update its url_prefix
                        for bp_name, bp_info in self.blueprints.items():
                            if bp_info.get("var_name") == bp_var:
                                bp_info["url_prefix"] = url_prefix
                                break
    
    def _identify_view_functions(self, tree: ast.Module, file_path: Path) -> None:
        """Identify view functions by their route decorators."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check if function has route decorator
                for decorator in node.decorator_list:
                    route_info = self._extract_route_info(decorator)
                    if route_info:
                        self.view_functions[node.name] = {
                            "file_path": file_path,
                            "line_number": node.lineno,
                            "node": node,
                            "route_path": route_info["path"],
                            "route_methods": route_info["methods"]
                        }
                        break
    
    def _has_route_decorator(self, decorator: ast.expr) -> bool:
        """Check if decorator is a route decorator."""
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                if decorator.func.attr == "route":
                    return True
        return False
    
    def _extract_route_info(self, decorator: ast.expr) -> dict[str, Any] | None:
        """Extract route path and methods from decorator."""
        if not isinstance(decorator, ast.Call):
            return None
        
        if not isinstance(decorator.func, ast.Attribute):
            return None
        
        if decorator.func.attr != "route":
            return None
        
        # Extract path from first argument
        path = "/"
        if decorator.args:
            if isinstance(decorator.args[0], ast.Constant):
                path = decorator.args[0].value
            elif isinstance(decorator.args[0], ast.Str):  # Python < 3.8
                path = decorator.args[0].s
        
        # Extract methods from keyword arguments
        methods = ["GET"]  # Default
        for keyword in decorator.keywords:
            if keyword.arg == "methods":
                if isinstance(keyword.value, ast.List):
                    methods = []
                    for elt in keyword.value.elts:
                        if isinstance(elt, ast.Constant):
                            methods.append(elt.value)
                        elif isinstance(elt, ast.Str):  # Python < 3.8
                            methods.append(elt.s)
        
        return {
            "path": path,
            "methods": methods
        }
    
    def _trace_view_calls(self, tree: ast.Module, file_path: Path) -> tuple[list[Node], list[Edge]]:
        """Trace calls from view functions."""
        nodes = []
        edges = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in self.view_functions:
                    view_info = self.view_functions[node.name]
                    
                    # Only process if this is the file where the view function is defined
                    if view_info["file_path"] != file_path:
                        continue
                    
                    # Create action node for this view function
                    action_node = Node(
                        id=f"action::{node.name}",
                        type=NodeType.ACTION,
                        label=node.name,
                        file_path=self._get_relative_path(file_path),
                        line_number=node.lineno,
                        metadata={}
                    )
                    nodes.append(action_node)
                    
                    # Create edges from route(s) to this action
                    route_edges = self._create_route_to_action_edges(node.name, view_info, file_path)
                    edges.extend(route_edges)
                    
                    # Trace calls within the function
                    for call_node in ast.walk(node):
                        if isinstance(call_node, ast.Call):
                            targets = self._identify_call_targets(call_node, file_path)
                            for target, edge_type in targets:
                                edge = Edge(
                                    source=f"action::{node.name}",
                                    target=target,
                                    type=edge_type
                                )
                                edges.append(edge)
        
        return nodes, edges

    def _trace_service_model_calls(self, tree: ast.Module, file_path: Path) -> list[Edge]:
        """Emit action→model USES_MODEL edges for non-view functions that use models.

        The main ``_trace_view_calls`` pass only walks functions that are
        registered as Flask route handlers.  Service and helper functions that
        directly query or construct models are therefore invisible to model-edge
        detection.  This pass fills that gap: for every function whose name is
        *not* a view function we walk its body and emit a USES_MODEL edge
        whenever a model is referenced.  This means service methods that import
        and use ``EvidenceFile`` will produce ``action::upload → model::EvidenceFile``
        edges in the graph.

        An ``action`` node is created for the service function so that
        ``Graph.add_edge`` (which silently drops dangling edges) does not discard
        the edges.
        """
        nodes = []
        edges = []
        local_models = self._get_local_models(file_path)
        if not local_models:
            return nodes, edges

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # Skip view functions — already handled by _trace_view_calls
            if node.name in self.view_functions:
                continue

            seen_targets: set[str] = set()
            model_edges = []
            for call_node in ast.walk(node):
                if not isinstance(call_node, ast.Call):
                    continue
                targets = self._identify_call_targets(call_node, file_path)
                for target, edge_type in targets:
                    if edge_type == EdgeType.USES_MODEL and target not in seen_targets:
                        seen_targets.add(target)
                        model_edges.append(Edge(
                            source=f"action::{node.name}",
                            target=target,
                            type=EdgeType.USES_MODEL,
                        ))

            if model_edges:
                # Create the action node so add_edge doesn't drop the edges
                action_node = Node(
                    id=f"action::{node.name}",
                    type=NodeType.ACTION,
                    label=node.name,
                    file_path=self._get_relative_path(file_path),
                    line_number=node.lineno,
                    metadata={},
                )
                nodes.append(action_node)
                edges.extend(model_edges)

        return nodes, edges

    def _create_route_to_action_edges(self, func_name: str, view_info: dict[str, Any], file_path: Path) -> list[Edge]:
        """Create edges from route nodes to action nodes."""
        edges = []
        
        route_path = view_info.get("route_path", "/")
        route_methods = view_info.get("route_methods", ["GET"])
        
        # Try to find the blueprint this route belongs to by matching file path
        blueprint_prefix = ""
        for bp_name, bp_info in self.blueprints.items():
            if bp_info.get("file_path") == file_path:
                blueprint_prefix = bp_info.get("url_prefix", "")
                break
        
        # Construct full route path
        full_path = blueprint_prefix + route_path
        
        # Create an edge for each HTTP method
        for method in route_methods:
            route_id = f"route::{method} {full_path}"
            edge = Edge(
                source=route_id,
                target=f"action::{func_name}",
                type=EdgeType.CALLS
            )
            edges.append(edge)
        
        return edges
    
    def _identify_call_targets(self, call_node: ast.Call, file_path: Path) -> list[tuple[str, EdgeType]]:
        """Identify the targets of a function call."""
        targets = []
        local_models = self._get_local_models(file_path)

        # Method call: obj.method()
        if isinstance(call_node.func, ast.Attribute):
            attr_name = call_node.func.attr
            
            # Skip Flask builtins
            if attr_name in FLASK_BUILTINS:
                return targets
            
            # Check if it's a method call on an object
            if isinstance(call_node.func.value, ast.Name):
                obj_name = call_node.func.value.id
                
                # Skip Flask builtins used as objects
                if obj_name in FLASK_BUILTINS:
                    return targets
                
                # Check if obj_name is a known model - create USES_MODEL edge
                if obj_name in local_models:
                    targets.append((f"model::{obj_name}", EdgeType.USES_MODEL))
                    return targets
                
                # Check if object is an imported service
                file_imports = self.imports.get(str(file_path), {})
                if obj_name in file_imports:
                    imported_module = file_imports[obj_name]
                    
                    # Check if imported module is a model
                    imported_name = imported_module.split('.')[-1]
                    if imported_name in local_models:
                        targets.append((f"model::{imported_name}", EdgeType.USES_MODEL))
                        return targets
                    
                    # If imported from a service module, create service edge
                    if "service" in imported_module.lower() or "Service" in imported_module:
                        targets.append((f"service::{imported_module}.{attr_name}", EdgeType.CALLS))
                    else:
                        # Generic call
                        targets.append((f"service::{imported_module}.{attr_name}", EdgeType.CALLS))
                
                # Check if it's a service instance (by naming convention)
                elif "service" in obj_name.lower() or "repo" in obj_name.lower():
                    targets.append((f"service::{obj_name}.{attr_name}", EdgeType.CALLS))
                
                # Check if it's a model query
                elif attr_name in ("query", "filter", "filter_by", "all", "get", "first", "one"):
                    targets.append((f"model::{obj_name}", EdgeType.USES_MODEL))
                
                # Check if it's a task dispatch
                elif attr_name in ("delay", "apply_async"):
                    targets.append((f"task::{obj_name}", EdgeType.DISPATCHES_TASK))
            
            # Check for db.session.* calls or flask.request.* calls
            elif isinstance(call_node.func.value, ast.Attribute):
                if isinstance(call_node.func.value.value, ast.Name):
                    obj_name = call_node.func.value.value.id
                    middle_attr = call_node.func.value.attr
                    
                    # Skip flask.* calls
                    if obj_name == "flask" or obj_name in FLASK_BUILTINS:
                        return targets
                    
                    # db.session.add(), db.session.query(), etc.
                    if obj_name == "db" and middle_attr == "session":
                        if attr_name in ("query", "execute"):
                            # Try to extract model from arguments
                            if call_node.args and isinstance(call_node.args[0], ast.Name):
                                model_name = call_node.args[0].id
                                if model_name in local_models:
                                    targets.append((f"model::{model_name}", EdgeType.USES_MODEL))
        
        # Direct function call
        elif isinstance(call_node.func, ast.Name):
            func_name = call_node.func.id
            
            # Skip Flask builtins
            if func_name in FLASK_BUILTINS:
                return targets
            
            # Check if it's a model constructor call
            if func_name in local_models:
                targets.append((f"model::{func_name}", EdgeType.USES_MODEL))
                return targets
            
            # Check if it's an imported function
            file_imports = self.imports.get(str(file_path), {})
            if func_name in file_imports:
                imported_module = file_imports[func_name]
                
                # Check if it's a Flask builtin
                if func_name in FLASK_BUILTINS or 'flask' in imported_module.lower():
                    return targets
                
                targets.append((f"service::{func_name}", EdgeType.CALLS))
            
            # Check if it's a service function by naming convention
            elif any(keyword in func_name.lower() for keyword in ["get_", "create_", "update_", "delete_", "list_", "find_"]):
                targets.append((f"service::{func_name}", EdgeType.CALLS))
        
        return targets
    
    def _classify_edge_type(self, target: str) -> EdgeType:
        """Classify edge type based on target."""
        if target.startswith("service::"):
            return EdgeType.CALLS
        elif target.startswith("model::"):
            return EdgeType.USES_MODEL
        elif target.startswith("task::"):
            return EdgeType.DISPATCHES_TASK
        return EdgeType.CALLS
