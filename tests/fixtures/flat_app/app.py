"""Flat Flask app - single file with routes, models, and services."""

from flask import Flask, jsonify, request

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'

# Mock db object for testing
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


# Model
class User(db.Model):
    """User model."""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))


# Service module functions
def get_user_by_id(user_id):
    """Get user by ID."""
    return User.query.get(user_id)


def create_user(name, email):
    """Create a new user."""
    user = User(name=name, email=email)
    db.session.add(user)
    db.session.commit()
    return user


def list_all_users():
    """List all users."""
    return User.query.all()


# Routes
@app.route('/users', methods=['GET'])
def list_users():
    """List all users."""
    users = list_all_users()
    return jsonify([{'id': u.id, 'name': u.name} for u in users])


@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get a specific user."""
    user = get_user_by_id(user_id)
    if user:
        return jsonify({'id': user.id, 'name': user.name, 'email': user.email})
    return jsonify({'error': 'User not found'}), 404


@app.route('/users', methods=['POST'])
def create_user_route():
    """Create a new user."""
    data = request.get_json()
    user = create_user(data['name'], data['email'])
    return jsonify({'id': user.id, 'name': user.name}), 201


if __name__ == '__main__':
    app.run(debug=True)
