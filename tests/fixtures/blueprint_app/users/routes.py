"""User routes."""

from flask import Blueprint, jsonify, request
from users.service import UserService

users_bp = Blueprint('users', __name__)
user_service = UserService()


@users_bp.route('/', methods=['GET'])
def list_users():
    """List all users."""
    users = user_service.get_all_users()
    return jsonify([{'id': u.id, 'username': u.username} for u in users])


@users_bp.route('/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get a specific user."""
    user = user_service.get_user(user_id)
    if user:
        return jsonify({'id': user.id, 'username': user.username, 'email': user.email})
    return jsonify({'error': 'User not found'}), 404


@users_bp.route('/', methods=['POST'])
def create_user():
    """Create a new user."""
    data = request.get_json()
    user = user_service.create_user(data['username'], data['email'])
    return jsonify({'id': user.id, 'username': user.username}), 201
