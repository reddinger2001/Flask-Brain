"""User routes blueprint."""

from flask import Blueprint, jsonify, request
from services.user_service import UserService

users_bp = Blueprint('users', __name__)
user_service = UserService()


@users_bp.route('/users', methods=['GET'])
def list_users():
    """List all users."""
    users = user_service.get_all_users()
    return jsonify([u.to_dict() for u in users])


@users_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get a specific user."""
    user = user_service.get_user(user_id)
    if user:
        return jsonify(user.to_dict())
    return jsonify({'error': 'User not found'}), 404


@users_bp.route('/users', methods=['POST'])
def create_user():
    """Create a new user."""
    data = request.get_json()
    user = user_service.create_user(data['username'], data['email'])
    return jsonify(user.to_dict()), 201


@users_bp.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Update a user."""
    data = request.get_json()
    user = user_service.update_user(
        user_id,
        username=data.get('username'),
        email=data.get('email')
    )
    if user:
        return jsonify(user.to_dict())
    return jsonify({'error': 'User not found'}), 404


@users_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Delete a user."""
    user = user_service.delete_user(user_id)
    if user:
        return jsonify({'message': 'User deleted'})
    return jsonify({'error': 'User not found'}), 404
