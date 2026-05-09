"""Tests for ModelScanner."""

import pytest
from pathlib import Path
from flask_brain.scanners.model_scanner import ModelScanner
from flask_brain.graph import NodeType, EdgeType


@pytest.fixture
def flat_app_path():
    """Path to flat_app fixture."""
    return Path(__file__).parent / "fixtures" / "flat_app"


@pytest.fixture
def factory_app_path():
    """Path to factory_app fixture."""
    return Path(__file__).parent / "fixtures" / "factory_app"


@pytest.fixture
def blueprint_app_path():
    """Path to blueprint_app fixture."""
    return Path(__file__).parent / "fixtures" / "blueprint_app"


def test_model_scanner_flat_app(flat_app_path):
    """Test ModelScanner on flat app."""
    scanner = ModelScanner(flat_app_path)
    nodes, edges = scanner.scan()
    
    # Should find User model
    model_nodes = [n for n in nodes if n.type == NodeType.MODEL]
    assert len(model_nodes) == 1
    assert model_nodes[0].id == "model::User"
    assert model_nodes[0].label == "User"
    
    # Check columns
    user_model = model_nodes[0]
    assert "columns" in user_model.metadata
    columns = user_model.metadata["columns"]
    assert "id" in columns
    assert "name" in columns
    assert "email" in columns


def test_model_scanner_factory_app(factory_app_path):
    """Test ModelScanner on factory app."""
    scanner = ModelScanner(factory_app_path)
    nodes, edges = scanner.scan()
    
    # Should find User model
    model_nodes = [n for n in nodes if n.type == NodeType.MODEL]
    assert len(model_nodes) == 1
    assert model_nodes[0].id == "model::User"


def test_model_scanner_blueprint_app(blueprint_app_path):
    """Test ModelScanner on blueprint app with relationships."""
    scanner = ModelScanner(blueprint_app_path)
    nodes, edges = scanner.scan()
    
    # Should find User and Order models
    model_nodes = [n for n in nodes if n.type == NodeType.MODEL]
    assert len(model_nodes) == 2
    
    model_ids = {n.id for n in model_nodes}
    assert "model::User" in model_ids
    assert "model::Order" in model_ids
    
    # Should find relationship edges
    relationship_edges = [e for e in edges if e.type == EdgeType.HAS_RELATIONSHIP]
    assert len(relationship_edges) >= 1
    
    # Check User -> Order relationship
    user_order_edges = [e for e in relationship_edges if e.source == "model::User" and e.target == "model::Order"]
    assert len(user_order_edges) >= 1


def test_model_scanner_extracts_columns(flat_app_path):
    """Test that scanner extracts column information."""
    scanner = ModelScanner(flat_app_path)
    nodes, edges = scanner.scan()
    
    user_model = next(n for n in nodes if n.id == "model::User")
    columns = user_model.metadata["columns"]
    
    # Should have column details
    assert isinstance(columns, dict)
    assert len(columns) >= 3


# ── Annotated assignment (AnnAssign) tests ────────────────────────────────────

@pytest.fixture
def annotated_app_path():
    """Path to annotated_app fixture (PEP-526 style columns)."""
    return Path(__file__).parent / "fixtures" / "annotated_app"


def test_model_scanner_annotated_columns(annotated_app_path):
    """Scanner must detect columns declared with type annotations (AnnAssign)."""
    scanner = ModelScanner(annotated_app_path)
    nodes, edges = scanner.scan()

    model_nodes = [n for n in nodes if n.type == NodeType.MODEL]
    assert len(model_nodes) == 1, "Should find exactly 1 model"

    model = model_nodes[0]
    assert model.id == "model::AnnotatedModel"

    columns = model.metadata["columns"]
    # All five annotated Column() attrs must be detected
    assert "id" in columns, "id column missing"
    assert "name" in columns, "name column missing"
    assert "email" in columns, "email column missing"
    assert "is_active" in columns, "is_active column missing"
    assert "created_at" in columns, "created_at column missing"

    # __abstract_flag__ is a plain bool annotation — must NOT be a column
    assert "__abstract_flag__" not in columns


def test_model_scanner_annotated_column_count(annotated_app_path):
    """Column count must be 5 for AnnotatedModel — not 0."""
    scanner = ModelScanner(annotated_app_path)
    nodes, _ = scanner.scan()
    model = next(n for n in nodes if n.id == "model::AnnotatedModel")
    assert len(model.metadata["columns"]) == 5


# ── Parameterised column type tests (String(n), Numeric, etc.) ───────────────

@pytest.fixture
def string_type_app_path():
    """Path to string_type_app fixture."""
    return Path(__file__).parent / "fixtures" / "string_type_app"


def test_string_column_type_resolved(string_type_app_path):
    """String(128) should resolve to 'String', not 'Unknown'."""
    scanner = ModelScanner(string_type_app_path)
    nodes, _ = scanner.scan()
    model = next(n for n in nodes if n.id == "model::Product")
    columns = model.metadata["columns"]
    assert columns["name"]["type"] == "String", f"Expected 'String', got {columns['name']['type']}"
    assert columns["slug"]["type"] == "String"


def test_numeric_column_type_resolved(string_type_app_path):
    """Numeric(10, 2) should resolve to 'Numeric', not 'Unknown'."""
    scanner = ModelScanner(string_type_app_path)
    nodes, _ = scanner.scan()
    model = next(n for n in nodes if n.id == "model::Product")
    columns = model.metadata["columns"]
    assert columns["price"]["type"] == "Numeric"


def test_no_unknown_column_types(string_type_app_path):
    """No column should have type 'Unknown' for well-known SQLAlchemy types."""
    scanner = ModelScanner(string_type_app_path)
    nodes, _ = scanner.scan()
    model = next(n for n in nodes if n.id == "model::Product")
    for col_name, col_info in model.metadata["columns"].items():
        assert col_info["type"] != "Unknown", f"Column '{col_name}' has Unknown type"


# ── Mixin inheritance tests ───────────────────────────────────────────────────

@pytest.fixture
def mixin_app_path():
    """Path to mixin_app fixture."""
    return Path(__file__).parent / "fixtures" / "mixin_app"


def test_mixin_columns_inherited_single(mixin_app_path):
    """Post inherits created_at and updated_at from TimestampMixin."""
    scanner = ModelScanner(mixin_app_path)
    nodes, _ = scanner.scan()
    post = next((n for n in nodes if n.id == "model::Post"), None)
    assert post is not None, "model::Post not found"
    columns = post.metadata["columns"]
    assert "id" in columns
    assert "title" in columns
    assert "created_at" in columns, "created_at inherited from TimestampMixin missing"
    assert "updated_at" in columns, "updated_at inherited from TimestampMixin missing"


def test_mixin_columns_inherited_multiple(mixin_app_path):
    """Article inherits from TenantMixin and TimestampMixin — all columns visible."""
    scanner = ModelScanner(mixin_app_path)
    nodes, _ = scanner.scan()
    article = next((n for n in nodes if n.id == "model::Article"), None)
    assert article is not None, "model::Article not found"
    columns = article.metadata["columns"]
    assert "id" in columns
    assert "body" in columns
    assert "tenant_id" in columns, "tenant_id inherited from TenantMixin missing"
    assert "created_at" in columns, "created_at inherited from TimestampMixin missing"
    assert "updated_at" in columns, "updated_at inherited from TimestampMixin missing"


def test_mixin_source_tagged(mixin_app_path):
    """Inherited columns should be tagged with their source mixin name."""
    scanner = ModelScanner(mixin_app_path)
    nodes, _ = scanner.scan()
    post = next(n for n in nodes if n.id == "model::Post")
    columns = post.metadata["columns"]
    assert columns["created_at"].get("from_mixin") == "TimestampMixin", (
        "created_at should be tagged with from_mixin='TimestampMixin'"
    )


def test_mixin_classes_not_emitted_as_model_nodes(mixin_app_path):
    """TimestampMixin and TenantMixin must NOT appear as model nodes."""
    scanner = ModelScanner(mixin_app_path)
    nodes, _ = scanner.scan()
    node_ids = {n.id for n in nodes}
    assert "model::TimestampMixin" not in node_ids
    assert "model::TenantMixin" not in node_ids
