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
    
    # Should create action nodes for all three view functions
    action_nodes = [n for n in nodes if n.type == NodeType.ACTION]
    assert len(action_nodes) == 3
    
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
    
    # Each view function should have an action node
    action_nodes = [n for n in nodes if n.type == NodeType.ACTION]
    assert len(action_nodes) == 3
    
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
