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


def test_model_inherits_from_base(tmp_path):
    """Test detection of models inheriting from Base or DeclarativeBase (line 92)."""
    models_file = tmp_path / "models.py"
    models_file.write_text("""
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id = 1
""")
    
    scanner = ModelScanner(tmp_path)
    nodes, edges = scanner.scan()
    
    model_nodes = [n for n in nodes if n.type == NodeType.MODEL]
    # Should find User (inherits from Base which inherits from DeclarativeBase)
    assert len(model_nodes) >= 1


def test_relationship_self_loop_skipped(tmp_path):
    """Test that self-referential relationships are skipped (line 147)."""
    models_file = tmp_path / "models.py"
    models_file.write_text("""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    parent = db.relationship('Category')
""")
    
    scanner = ModelScanner(tmp_path)
    nodes, edges = scanner.scan()
    
    # Should create Category node but no self-loop edge
    model_nodes = [n for n in nodes if n.id == "model::Category"]
    assert len(model_nodes) == 1
    
    # Should not have self-loop edge
    self_loop_edges = [e for e in edges if e.source == "model::Category" and e.target == "model::Category"]
    assert len(self_loop_edges) == 0


def test_column_as_name_not_attribute(tmp_path):
    """Test Column() as ast.Name, not db.Column() (lines 233-235)."""
    models_file = tmp_path / "models.py"
    models_file.write_text("""
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
""")
    
    scanner = ModelScanner(tmp_path)
    nodes, edges = scanner.scan()
    
    model_nodes = [n for n in nodes if n.id == "model::User"]
    assert len(model_nodes) == 1
    
    columns = model_nodes[0].metadata["columns"]
    assert "id" in columns
    assert "name" in columns


def test_relationship_as_name_not_attribute(tmp_path):
    """Test relationship() as ast.Name, not db.relationship() (lines 243-245)."""
    models_file = tmp_path / "models.py"
    models_file.write_text("""
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship, DeclarativeBase

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User')
""")
    
    scanner = ModelScanner(tmp_path)
    nodes, edges = scanner.scan()
    
    # Should find relationship edge
    relationship_edges = [e for e in edges if e.type == EdgeType.HAS_RELATIONSHIP]
    assert len(relationship_edges) >= 1


def test_column_with_no_args_returns_unknown(tmp_path):
    """Test Column() with no args returns 'Unknown' type (line 259)."""
    models_file = tmp_path / "models.py"
    models_file.write_text("""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column()
""")
    
    scanner = ModelScanner(tmp_path)
    nodes, edges = scanner.scan()
    
    model_nodes = [n for n in nodes if n.id == "model::User"]
    assert len(model_nodes) == 1
    
    columns = model_nodes[0].metadata["columns"]
    assert "id" in columns
    assert columns["id"]["type"] == "Unknown"


def test_column_with_string_alias_no_type(tmp_path):
    """Test Column('alias') with no second arg returns 'Unknown' (lines 266-269)."""
    models_file = tmp_path / "models.py"
    models_file.write_text("""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column('user_id')
""")
    
    scanner = ModelScanner(tmp_path)
    nodes, edges = scanner.scan()
    
    model_nodes = [n for n in nodes if n.id == "model::User"]
    assert len(model_nodes) == 1
    
    columns = model_nodes[0].metadata["columns"]
    assert "id" in columns
    assert columns["id"]["type"] == "Unknown"


def test_column_type_as_name(tmp_path):
    """Test column type as ast.Name (Integer not db.Integer) (line 275)."""
    models_file = tmp_path / "models.py"
    models_file.write_text("""
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    age = Column(Integer)
""")
    
    scanner = ModelScanner(tmp_path)
    nodes, edges = scanner.scan()
    
    model_nodes = [n for n in nodes if n.id == "model::User"]
    assert len(model_nodes) == 1
    
    columns = model_nodes[0].metadata["columns"]
    assert columns["id"]["type"] == "Integer"
    assert columns["age"]["type"] == "Integer"


def test_column_type_nested_call_with_name(tmp_path):
    """Test nested Call with ast.Name func (String(100) not db.String(100)) (lines 282-285)."""
    models_file = tmp_path / "models.py"
    models_file.write_text("""
from sqlalchemy import Column, String
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    name = Column(String(100))
    email = Column(String(255))
""")
    
    scanner = ModelScanner(tmp_path)
    nodes, edges = scanner.scan()
    
    model_nodes = [n for n in nodes if n.id == "model::User"]
    assert len(model_nodes) == 1
    
    columns = model_nodes[0].metadata["columns"]
    assert columns["name"]["type"] == "String"
    assert columns["email"]["type"] == "String"


def test_relationship_target_ast_str_python37(tmp_path):
    """Test relationship target as ast.Str for Python < 3.8 compatibility (lines 293-295)."""
    # This is hard to test directly in Python 3.8+ since ast.Str is deprecated
    # But we can verify the code path exists and doesn't crash
    models_file = tmp_path / "models.py"
    models_file.write_text("""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('User')
""")
    
    scanner = ModelScanner(tmp_path)
    nodes, edges = scanner.scan()
    
    # Should handle relationship target extraction
    relationship_edges = [e for e in edges if e.type == EdgeType.HAS_RELATIONSHIP]
    assert len(relationship_edges) >= 1
