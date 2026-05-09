"""
Fixture: models using PEP-526 annotated assignments (id: int = db.Column(...)).
This is the modern SQLAlchemy style and was previously NOT detected by the scanner.
"""
from __future__ import annotations
from typing import Optional
from datetime import datetime


class AnnotatedModel(db.Model):
    """Model using annotated assignment columns (AnnAssign AST nodes)."""
    __tablename__: str = 'annotated_models'

    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(256), nullable=False)
    email: Optional[str] = db.Column(db.String(128), nullable=True)
    is_active: bool = db.Column(db.Boolean, default=True)
    created_at: datetime = db.Column(db.DateTime, nullable=False)

    # Non-column annotated attrs should NOT be counted as columns
    __abstract_flag__: bool = False
