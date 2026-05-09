"""Fixture: models with String(n), Numeric, etc. — nested Call types."""
from __future__ import annotations
from typing import Optional


class Product(db.Model):
    """Model using parameterised column types like String(128), Numeric(10,2)."""
    __tablename__ = "products"

    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(128), nullable=False)
    slug: Optional[str] = db.Column(db.String(64), nullable=True)
    price = db.Column(db.Numeric(10, 2))
    description = db.Column(db.Text)
