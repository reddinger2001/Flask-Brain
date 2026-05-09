"""User model."""

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
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email
        }
