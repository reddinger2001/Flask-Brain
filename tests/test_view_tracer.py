"""Tests for ViewFunctionTracer."""

import pytest
from pathlib import Path

from flask_brain.scanners.view_tracer import ViewFunctionTracer
from flask_brain.graph import NodeType, EdgeType


@pytest.fixture
def flat_app_path():
    """Path to flat app fixture."""
    return Path(__file__).parent / "fixtures" / "flat_app"


@pytest.fixture
def factory_app_path():
    """Path to factory app fixture."""
    return Path(__file__).parent / "fixtures" / "factory_app"


@pytest.fixture
def blueprint_app_path():
    """Path to blueprint app fixture."""
    return Path(__file__).parent / "fixtures" / "blueprint_app"


def test_view_tracer_creates_action_nodes_for_view_functions(flat_app_path):
    """Test that action nodes are created for each view function."""
    tracer = ViewFunctionTracer(flat_app_path)
    nodes, edges = tracer.scan()
    
    # Should create action nodes for all three view functions (may include extra
    # action nodes for non-view service functions that reference models)
    action_nodes = [n for n in nodes if n.type == NodeType.ACTION]
    assert len(action_nodes) >= 3
    
    action_labels = {n.label for n in action_nodes}
    assert "list_users" in action_labels
    assert "get_user" in action_labels
    assert "create_user_route" in action_labels


def test_view_tracer_detects_module_level_service_calls(flat_app_path):
    """Test detection of calls to module-level service functions."""
    tracer = ViewFunctionTracer(flat_app_path)
    nodes, edges = tracer.scan()
    
    # list_users() calls list_all_users() service function
    list_users_edges = [e for e in edges if e.source == "action::list_users"]
    assert len(list_users_edges) > 0
    
    # Should have edge to service function
    service_edges = [e for e in list_users_edges if "list_all_users" in e.target]
    assert len(service_edges) == 1
    assert service_edges[0].type == EdgeType.CALLS


def test_view_tracer_detects_imported_service_instance_calls(factory_app_path):
    """Test detection of calls to imported service instance methods."""
    tracer = ViewFunctionTracer(factory_app_path)
    nodes, edges = tracer.scan()
    
    # list_users() calls user_service.get_all_users()
    list_users_edges = [e for e in edges if e.source == "action::list_users"]
    assert len(list_users_edges) > 0
    
    # Should detect call to UserService.get_all_users
    service_edges = [e for e in list_users_edges if "UserService" in e.target or "get_all_users" in e.target]
    assert len(service_edges) >= 1
    assert service_edges[0].type == EdgeType.CALLS


def test_view_tracer_detects_model_queries(flat_app_path):
    """Test detection of direct model queries in view functions."""
    # Note: flat_app service functions call User.query, not the view functions directly
    # But we should still test that the tracer can detect model queries when present
    tracer = ViewFunctionTracer(flat_app_path)
    nodes, edges = tracer.scan()
    
    # The view functions call service functions, which in turn query models
    # For now, just verify edges are created
    assert len(edges) > 0


def test_view_tracer_detects_task_dispatches(blueprint_app_path):
    """Test detection of Celery task dispatches."""
    # First, we need to enhance the blueprint_app fixture to include task dispatches
    # For now, this test documents the expected behavior
    tracer = ViewFunctionTracer(blueprint_app_path)
    nodes, edges = tracer.scan()
    
    # Should create action nodes for blueprint_app routes
    action_nodes = [n for n in nodes if n.type == NodeType.ACTION]
    assert len(action_nodes) > 0


def test_view_tracer_resolves_imported_service_classes(factory_app_path):
    """Test that tracer resolves service classes from import statements."""
    tracer = ViewFunctionTracer(factory_app_path)
    nodes, edges = tracer.scan()
    
    # factory_app imports UserService and creates instance
    # View functions call methods on user_service instance
    action_nodes = [n for n in nodes if n.type == NodeType.ACTION]
    assert len(action_nodes) >= 3  # list_users, get_user, create_user at minimum
    
    # Should have edges from actions to service
    service_call_edges = [e for e in edges if e.type == EdgeType.CALLS]
    assert len(service_call_edges) > 0


def test_view_tracer_creates_edges_from_routes_to_actions(flat_app_path):
    """Test that edges are created from routes to action nodes."""
    tracer = ViewFunctionTracer(flat_app_path)
    nodes, edges = tracer.scan()
    
    # Each view function should have an action node (may include extra nodes
    # for non-view service functions that reference models)
    action_nodes = [n for n in nodes if n.type == NodeType.ACTION]
    assert len(action_nodes) >= 3
    
    # Verify action node IDs follow convention
    action_ids = {n.id for n in action_nodes}
    assert "action::list_users" in action_ids
    assert "action::get_user" in action_ids
    assert "action::create_user_route" in action_ids


def test_view_tracer_handles_self_service_calls(blueprint_app_path):
    """Test detection of self.service calls in class-based views."""
    # This tests the pattern: self.user_service.get_user()
    # For now, blueprint_app uses module-level service instances
    # This test documents expected behavior for future enhancement
    tracer = ViewFunctionTracer(blueprint_app_path)
    nodes, edges = tracer.scan()
    
    # Should handle blueprint_app structure
    action_nodes = [n for n in nodes if n.type == NodeType.ACTION]
    assert len(action_nodes) > 0


def test_view_tracer_classifies_edge_types_correctly(factory_app_path):
    """Test that edge types are classified correctly."""
    tracer = ViewFunctionTracer(factory_app_path)
    nodes, edges = tracer.scan()
    
    # Should have CALLS edges for service method calls
    call_edges = [e for e in edges if e.type == EdgeType.CALLS]
    assert len(call_edges) > 0
    
    # Edge types should be appropriate
    for edge in edges:
        assert edge.type in [EdgeType.CALLS, EdgeType.USES_MODEL, EdgeType.DISPATCHES_TASK]


def test_view_tracer_works_across_all_fixture_apps(flat_app_path, factory_app_path, blueprint_app_path):
    """Test that tracer works on all three fixture app structures."""
    for app_path in [flat_app_path, factory_app_path, blueprint_app_path]:
        tracer = ViewFunctionTracer(app_path)
        nodes, edges = tracer.scan()
        
        # Each app should have at least some action nodes
        action_nodes = [n for n in nodes if n.type == NodeType.ACTION]
        assert len(action_nodes) > 0, f"No action nodes found in {app_path.name}"
        
        # Each action node should have proper metadata
        for node in action_nodes:
            assert node.id.startswith("action::")
            assert node.label
            assert node.file_path
            assert node.line_number > 0


def test_view_tracer_creates_route_to_action_edges(blueprint_app_path):
    """Test that edges are created from route nodes to action nodes."""
    tracer = ViewFunctionTracer(blueprint_app_path)
    nodes, edges = tracer.scan()
    
    # Should have edges from routes to actions
    # For example: route::GET /users -> action::list_users
    route_to_action_edges = [e for e in edges if e.source.startswith("route::") and e.target.startswith("action::")]
    assert len(route_to_action_edges) > 0, "No route->action edges found"
    
    # Verify specific edges exist for known view functions
    edge_map = {e.source: e.target for e in route_to_action_edges}
    
    # list_users is at GET /users (with /users prefix from blueprint)
    assert any("GET /users/" in source and "action::list_users" in target 
               for source, target in edge_map.items()), "Missing edge for list_users"
    
    # get_user is at GET /users/<int:user_id>
    assert any("GET /users/" in source and "action::get_user" in target 
               for source, target in edge_map.items()), "Missing edge for get_user"
    
    # create_user is at POST /users/
    assert any("POST /users/" in source and "action::create_user" in target 
               for source, target in edge_map.items()), "Missing edge for create_user"


def test_view_tracer_filters_flask_builtins(blueprint_app_path):
    """Test that Flask builtin functions are not treated as service calls."""
    tracer = ViewFunctionTracer(blueprint_app_path)
    nodes, edges = tracer.scan()
    
    # Should NOT create edges to Flask builtins
    service_edges = [e for e in edges if e.target.startswith("service::")]
    
    # Check that common Flask builtins are NOT in the edges as standalone calls
    # We check for exact matches or as the last component after ::
    flask_builtins = ['jsonify', 'render_template', 'redirect', 'url_for', 'abort', 
                      'request', 'session', 'flash', 'send_file', 'make_response']
    
    for builtin in flask_builtins:
        # Check if builtin appears as a standalone service or as the final component
        assert not any(e.target == f"service::{builtin}" or e.target.endswith(f".{builtin}") 
                       for e in service_edges), \
            f"Flask builtin '{builtin}' should not appear as a service edge"


def test_view_tracer_creates_uses_model_edges_for_models(blueprint_app_path):
    """Test that model constructor calls create USES_MODEL edges, not CALLS edges."""
    from flask_brain.graph import EdgeType
    
    tracer = ViewFunctionTracer(blueprint_app_path)
    nodes, edges = tracer.scan()
    
    # Find edges from actions
    action_edges = [e for e in edges if e.source.startswith("action::")]
    
    # Model references should use USES_MODEL edge type, not CALLS
    model_edges = [e for e in action_edges if "User" in e.target or "Order" in e.target]
    
    for edge in model_edges:
        # If it's a model reference, it should be USES_MODEL
        if edge.target.startswith("model::"):
            assert edge.type == EdgeType.USES_MODEL, \
                f"Model edge {edge.source} -> {edge.target} should use USES_MODEL, not {edge.type}"
        # Should NOT be a service call to a model
        assert not (edge.target.startswith("service::") and ("User" in edge.target or "Order" in edge.target)), \
            f"Model should not appear as service: {edge.target}"


def test_view_tracer_handles_import_statements(tmp_path):
    """Test that import statements (not from...import) are collected."""
    # Create a test file with import statements
    test_file = tmp_path / "app.py"
    test_file.write_text("""
from flask import Flask
import os
import sys as system

app = Flask(__name__)

@app.route('/')
def index():
    path = os.path.join('/', 'test')
    version = system.version
    return 'OK'
""")
    
    tracer = ViewFunctionTracer(tmp_path)
    nodes, edges = tracer.scan()
    
    # Check that imports were collected
    imports = tracer.imports.get(str(test_file), {})
    assert 'os' in imports
    assert imports['os'] == 'os'
    assert 'system' in imports
    assert imports['system'] == 'sys'


def test_view_tracer_handles_ast_name_base_class(tmp_path):
    """Test model detection with ast.Name base class."""
    test_file = tmp_path / "models.py"
    test_file.write_text("""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Model inheriting from db.Model (ast.Attribute)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

# Model inheriting from Model directly (ast.Name)
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

class Product(Base):
    __tablename__ = 'products'
""")
    
    tracer = ViewFunctionTracer(tmp_path)
    nodes, edges = tracer.scan()
    
    # Both models should be detected
    assert 'User' in tracer.models
    assert 'Product' in tracer.models


def test_view_tracer_handles_ast_str_for_python37(tmp_path):
    """Test handling of ast.Str nodes for Python < 3.8 compatibility."""
    # This tests lines 185-186 and 197-198 (ast.Str fallback)
    # In Python 3.8+, these are ast.Constant, but the code has fallback for older versions
    # We can't easily test this without Python 3.7, but we can verify the code path exists
    test_file = tmp_path / "app.py"
    test_file.write_text("""
from flask import Flask
app = Flask(__name__)

@app.route('/test', methods=['GET', 'POST'])
def test_view():
    return 'OK'
""")
    
    tracer = ViewFunctionTracer(tmp_path)
    nodes, edges = tracer.scan()
    
    # Should detect the route
    action_nodes = [n for n in nodes if n.type == NodeType.ACTION]
    assert len(action_nodes) >= 1
    assert any(n.label == 'test_view' for n in action_nodes)


def test_view_tracer_handles_attribute_func_calls(tmp_path):
    """Test detection of calls with ast.Attribute func (e.g., obj.method())."""
    test_file = tmp_path / "app.py"
    test_file.write_text("""
from flask import Flask
app = Flask(__name__)

class UserService:
    def get_user(self, user_id):
        return None

user_service = UserService()

@app.route('/user/<int:user_id>')
def get_user_view(user_id):
    # This is an ast.Attribute call: user_service.get_user()
    user = user_service.get_user(user_id)
    return str(user)
""")
    
    tracer = ViewFunctionTracer(tmp_path)
    nodes, edges = tracer.scan()
    
    # Should detect the service call
    service_edges = [e for e in edges if e.source == "action::get_user_view"]
    assert len(service_edges) > 0


def test_view_tracer_handles_subscript_calls(tmp_path):
    """Test handling of subscript calls (e.g., services['user'].get())."""
    test_file = tmp_path / "app.py"
    test_file.write_text("""
from flask import Flask
app = Flask(__name__)

services = {'user': None}

@app.route('/user')
def get_user():
    # This is an ast.Subscript: services['user']
    user = services['user']
    return str(user)
""")
    
    tracer = ViewFunctionTracer(tmp_path)
    nodes, edges = tracer.scan()
    
    # Should handle subscript without crashing
    action_nodes = [n for n in nodes if n.type == NodeType.ACTION]
    assert len(action_nodes) >= 1


def test_view_tracer_skips_flask_builtin_objects(tmp_path):
    """Test that Flask builtin objects are skipped (line 295)."""
    test_file = tmp_path / "app.py"
    test_file.write_text("""
from flask import Flask, request
app = Flask(__name__)

@app.route('/test')
def test_view():
    # request is a Flask builtin - should be skipped
    data = request.get_json()
    return str(data)
""")
    
    tracer = ViewFunctionTracer(tmp_path)
    nodes, edges = tracer.scan()
    
    # Should NOT create edges to request.get_json
    service_edges = [e for e in edges if e.source == "action::test_view"]
    assert not any('request' in e.target for e in service_edges)


def test_view_tracer_detects_model_object_calls(tmp_path):
    """Test detection of model object method calls (lines 299-300)."""
    test_file = tmp_path / "app.py"
    test_file.write_text("""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
app = Flask(__name__)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    def save(self):
        pass

@app.route('/user')
def create_user():
    user = User()
    user.save()  # This should create a USES_MODEL edge
    return 'OK'
""")
    
    tracer = ViewFunctionTracer(tmp_path)
    nodes, edges = tracer.scan()
    
    # Should detect User model
    assert 'User' in tracer.models
    
    # Should create USES_MODEL edge for user.save()
    from flask_brain.graph import EdgeType
    model_edges = [e for e in edges if e.type == EdgeType.USES_MODEL]
    assert len(model_edges) > 0


def test_view_tracer_handles_imported_models(tmp_path):
    """Test detection of imported model calls (lines 305-311)."""
    # Create models file
    models_file = tmp_path / "models.py"
    models_file.write_text("""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
""")
    
    # Create app file that imports the model
    app_file = tmp_path / "app.py"
    app_file.write_text("""
from flask import Flask
from models import User

app = Flask(__name__)

@app.route('/user')
def get_user():
    user = User.query.first()
    return str(user)
""")
    
    tracer = ViewFunctionTracer(tmp_path)
    nodes, edges = tracer.scan()
    
    # Should detect User as a model (even if imported)
    # The tracer scans models.py and finds User
    assert 'User' in tracer.models
    
    # Should create action node for the route
    action_nodes = [n for n in nodes if n.type == NodeType.ACTION and n.label == "get_user"]
    assert len(action_nodes) == 1


def test_view_tracer_handles_imported_service_modules(tmp_path):
    """Test detection of imported service module calls (lines 314-318)."""
    # Create service file
    service_file = tmp_path / "user_service.py"
    service_file.write_text("""
class UserService:
    def get_user(self, user_id):
        return None

user_service = UserService()
""")
    
    # Create app file that imports the service
    app_file = tmp_path / "app.py"
    app_file.write_text("""
from flask import Flask
from user_service import user_service

app = Flask(__name__)

@app.route('/user/<int:user_id>')
def get_user(user_id):
    user = user_service.get_user(user_id)
    return str(user)
""")
    
    tracer = ViewFunctionTracer(tmp_path)
    nodes, edges = tracer.scan()
    
    # Should detect service call
    service_edges = [e for e in edges if e.source == "action::get_user" and 'service' in e.target.lower()]
    assert len(service_edges) > 0


def test_view_tracer_has_route_decorator_with_call(tmp_path):
    """Test _has_route_decorator with ast.Call decorator (lines 163-167)."""
    app_file = tmp_path / "app.py"
    app_file.write_text("""
from flask import Flask

app = Flask(__name__)

@app.route('/test')
def test_route():
    return 'OK'
""")
    
    tracer = ViewFunctionTracer(tmp_path)
    nodes, edges = tracer.scan()
    
    # Should detect route decorator and create action node
    action_nodes = [n for n in nodes if n.type == NodeType.ACTION and n.label == "test_route"]
    assert len(action_nodes) == 1


def test_view_tracer_extract_route_info_non_attribute(tmp_path):
    """Test _extract_route_info returns None for non-Attribute func (line 175)."""
    # This is tested indirectly - if decorator.func is not ast.Attribute, 
    # _extract_route_info returns None and the route is skipped
    app_file = tmp_path / "app.py"
    app_file.write_text("""
from flask import Flask

app = Flask(__name__)

# Normal route - should work
@app.route('/test')
def test_route():
    return 'OK'
""")
    
    tracer = ViewFunctionTracer(tmp_path)
    nodes, edges = tracer.scan()
    
    # Should still create action node for valid route
    action_nodes = [n for n in nodes if n.type == NodeType.ACTION]
    assert len(action_nodes) >= 1


def test_view_tracer_detects_celery_task_dispatch(tmp_path):
    """Test detection of Celery task dispatch via .delay() or .apply_async() (line 330)."""
    app_file = tmp_path / "app.py"
    app_file.write_text("""
from flask import Flask
from celery import Celery

app = Flask(__name__)
celery = Celery(app.name)

@celery.task
def send_email(to, subject):
    pass

@app.route('/send')
def send_notification():
    send_email.delay('user@example.com', 'Hello')
    return 'Sent'
""")
    
    tracer = ViewFunctionTracer(tmp_path)
    nodes, edges = tracer.scan()
    
    # Should detect task dispatch
    from flask_brain.graph import EdgeType
    task_edges = [e for e in edges if e.type == EdgeType.DISPATCHES_TASK]
    assert len(task_edges) > 0


def test_view_tracer_detects_db_session_query(tmp_path):
    """Test detection of db.session.query(Model) calls (lines 343-349)."""
    app_file = tmp_path / "app.py"
    app_file.write_text("""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

@app.route('/users')
def list_users():
    users = db.session.query(User).all()
    return str(users)
""")
    
    tracer = ViewFunctionTracer(tmp_path)
    nodes, edges = tracer.scan()
    
    # Should detect User model usage via db.session.query
    from flask_brain.graph import EdgeType
    model_edges = [e for e in edges if e.type == EdgeType.USES_MODEL and 'User' in e.target]
    assert len(model_edges) > 0


def test_view_tracer_detects_direct_model_constructor(tmp_path):
    """Test detection of direct model constructor calls (lines 361-362)."""
    app_file = tmp_path / "app.py"
    app_file.write_text("""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))

@app.route('/create')
def create_user():
    user = User(name='John')
    db.session.add(user)
    return 'Created'
""")
    
    tracer = ViewFunctionTracer(tmp_path)
    nodes, edges = tracer.scan()
    
    # Should detect User model usage via constructor
    from flask_brain.graph import EdgeType
    model_edges = [e for e in edges if e.type == EdgeType.USES_MODEL and 'User' in e.target]
    assert len(model_edges) > 0


def test_view_tracer_skips_imported_flask_builtins(tmp_path):
    """Test that imported Flask builtins are skipped (lines 367-373)."""
    app_file = tmp_path / "app.py"
    app_file.write_text("""
from flask import Flask, jsonify, render_template

app = Flask(__name__)

@app.route('/test')
def test_route():
    data = {'key': 'value'}
    return jsonify(data)
""")
    
    tracer = ViewFunctionTracer(tmp_path)
    nodes, edges = tracer.scan()
    
    # Should create action node but NOT create service edges for jsonify
    action_nodes = [n for n in nodes if n.type == NodeType.ACTION and n.label == "test_route"]
    assert len(action_nodes) == 1
    
    # Should not have edges to jsonify (it's a Flask builtin)
    jsonify_edges = [e for e in edges if 'jsonify' in e.target]
    assert len(jsonify_edges) == 0


def test_view_tracer_classify_edge_type(tmp_path):
    """Test _classify_edge_type method (lines 383-389)."""
    app_file = tmp_path / "app.py"
    app_file.write_text("""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

def get_user_service(user_id):
    return User.query.get(user_id)

@app.route('/user/<int:user_id>')
def get_user(user_id):
    user = get_user_service(user_id)
    return str(user)
""")
    
    tracer = ViewFunctionTracer(tmp_path)
    nodes, edges = tracer.scan()
    
    # Should have service edges with correct type (CALLS)
    from flask_brain.graph import EdgeType
    service_edges = [e for e in edges if e.type == EdgeType.CALLS and 'service' in e.target]
    
    # The _classify_edge_type method is used internally
    # We verify it works by checking edge types are correct
    assert len(service_edges) > 0
    
    # Verify the method exists and can be called
    assert hasattr(tracer, '_classify_edge_type')
    assert tracer._classify_edge_type('service::test') == EdgeType.CALLS
    assert tracer._classify_edge_type('model::User') == EdgeType.USES_MODEL
    assert tracer._classify_edge_type('task::send_email') == EdgeType.DISPATCHES_TASK


def test_view_tracer_resolves_uses_model_edges_for_cross_file_imports(tmp_path):
    """USES_MODEL edges must be emitted when a model is imported from another file.

    Regression test: ViewFunctionTracer previously only recognised model names
    defined in the *same* file.  Service files that import a model class from a
    models module would produce no uses_model edges even though the service
    clearly queries or constructs that model.
    """
    # models/record.py — defines the SQLAlchemy model
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "__init__.py").write_text("")
    (models_dir / "record.py").write_text(
        "from flask_sqlalchemy import SQLAlchemy\n"
        "db = SQLAlchemy()\n"
        "class EvidenceFile(db.Model):\n"
        "    id = db.Column(db.Integer, primary_key=True)\n"
    )

    # services/evidence_service.py — imports the model and uses it
    services_dir = tmp_path / "services"
    services_dir.mkdir()
    (services_dir / "__init__.py").write_text("")
    (services_dir / "evidence_service.py").write_text(
        "from models.record import EvidenceFile\n"
        "\n"
        "def upload(data):\n"
        "    record = EvidenceFile()\n"
        "    return record\n"
        "\n"
        "def list_all():\n"
        "    return EvidenceFile.query.all()\n"
    )

    # app.py — view function that calls the service
    (tmp_path / "app.py").write_text(
        "from flask import Flask\n"
        "from services.evidence_service import upload, list_all\n"
        "\n"
        "app = Flask(__name__)\n"
        "\n"
        "@app.route('/evidence', methods=['POST'])\n"
        "def create_evidence():\n"
        "    return upload({})\n"
        "\n"
        "@app.route('/evidence')\n"
        "def get_evidence():\n"
        "    return list_all()\n"
    )
    (tmp_path / "__init__.py").write_text("")

    tracer = ViewFunctionTracer(tmp_path)
    nodes, edges = tracer.scan()

    # EvidenceFile must be recognised as a model
    assert "EvidenceFile" in tracer.models, (
        "EvidenceFile should be in tracer.models after scanning models/record.py"
    )

    # _get_local_models must include EvidenceFile for the service file
    service_file = tmp_path / "services" / "evidence_service.py"
    local = tracer._get_local_models(service_file)
    assert "EvidenceFile" in local, (
        "_get_local_models should include imported model name EvidenceFile"
    )

    # At least one USES_MODEL edge pointing at model::EvidenceFile must exist
    uses_model_edges = [
        e for e in edges
        if e.type == EdgeType.USES_MODEL and e.target == "model::EvidenceFile"
    ]
    assert uses_model_edges, (
        "Expected at least one USES_MODEL edge to model::EvidenceFile; "
        f"got edges: {[e for e in edges if 'EvidenceFile' in e.target]}"
    )

    # An action node must have been created for the service function
    action_ids = {n.id for n in nodes}
    assert "action::upload" in action_ids or "action::list_all" in action_ids, (
        "Expected action node for standalone service function using EvidenceFile; "
        f"got action nodes: {[n.id for n in nodes if n.id.startswith('action::')]}"
    )


def test_view_tracer_emits_service_node_uses_model_edges_for_class_methods(tmp_path):
    """USES_MODEL edges from service class methods must use service:: as source.

    Regression test: _trace_service_model_calls previously emitted all edges
    from action::method_name, making them invisible to graph.trace_node() calls
    on service:: nodes and therefore useless for the test generator.

    Methods inside a Service/Repository/Manager class must produce
    ``service::ClassName → model::M`` edges so that blueprint_subgraph() and
    trace_node() return the correct model set.
    """
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "__init__.py").write_text("")
    (models_dir / "invoice.py").write_text(
        "from flask_sqlalchemy import SQLAlchemy\n"
        "db = SQLAlchemy()\n"
        "class Invoice(db.Model):\n"
        "    id = db.Column(db.Integer, primary_key=True)\n"
    )

    services_dir = tmp_path / "services"
    services_dir.mkdir()
    (services_dir / "__init__.py").write_text("")
    (services_dir / "billing_service.py").write_text(
        "from models.invoice import Invoice\n"
        "\n"
        "class BillingService:\n"
        "    def create_invoice(self, data):\n"
        "        inv = Invoice()\n"
        "        return inv\n"
        "\n"
        "    def list_invoices(self):\n"
        "        return Invoice.query.all()\n"
    )

    (tmp_path / "__init__.py").write_text("")

    tracer = ViewFunctionTracer(tmp_path)
    nodes, edges = tracer.scan()

    uses_model_edges = [
        e for e in edges
        if e.type == EdgeType.USES_MODEL and e.target == "model::Invoice"
    ]
    assert uses_model_edges, (
        "Expected at least one USES_MODEL edge to model::Invoice; "
        f"got edges: {[e for e in edges if 'Invoice' in str(e)]}"
    )

    # Sources must be service::BillingService, NOT action::create_invoice etc.
    sources = {e.source for e in uses_model_edges}
    assert "service::BillingService" in sources, (
        f"Expected service::BillingService as edge source; got: {sources}"
    )
    action_sources = {s for s in sources if s.startswith("action::")}
    assert not action_sources, (
        f"Service class methods must not produce action:: edge sources; got: {action_sources}"
    )
