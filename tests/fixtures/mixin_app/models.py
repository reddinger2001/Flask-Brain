"""Fixture: models that inherit columns from mixins."""
from __future__ import annotations
from .mixins import TimestampMixin, TenantMixin


class Post(TimestampMixin, db.Model):
    """Model that inherits timestamp columns from a mixin."""
    __tablename__ = "posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    # Should also show: created_at, updated_at from TimestampMixin


class Article(TenantMixin, TimestampMixin, db.Model):
    """Model that inherits from two mixins."""
    __tablename__ = "articles"
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    # Should also show: tenant_id, created_at, updated_at
