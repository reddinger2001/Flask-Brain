"""Models for blueprint app."""

# Mock db object
class MockDB:
    class Column:
        def __init__(self, *args, **kwargs):
            pass
    
    class Integer:
        pass
    
    class String:
        def __init__(self, *args):
            pass
    
    class ForeignKey:
        def __init__(self, *args):
            pass
    
    class Model:
        pass
    
    class relationship:
        def __init__(self, *args, **kwargs):
            pass

db = MockDB()


class User(db.Model):
    """User model."""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    orders = db.relationship('Order', back_populates='user')


class Order(db.Model):
    """Order model."""
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    product_name = db.Column(db.String(200))
    quantity = db.Column(db.Integer)
    user = db.relationship('User', back_populates='orders')
