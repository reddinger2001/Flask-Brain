"""Order routes."""

from flask import Blueprint, jsonify, request
from orders.service import OrderRepository

orders_bp = Blueprint('orders', __name__)
order_repo = OrderRepository()


@orders_bp.route('/', methods=['GET'])
def list_orders():
    """List all orders."""
    user_id = request.args.get('user_id', type=int)
    if user_id:
        orders = order_repo.get_orders_by_user(user_id)
    else:
        orders = []
    return jsonify([{'id': o.id, 'product': o.product_name} for o in orders])


@orders_bp.route('/<int:order_id>', methods=['GET'])
def get_order(order_id):
    """Get a specific order."""
    order = order_repo.get_order(order_id)
    if order:
        return jsonify({
            'id': order.id,
            'user_id': order.user_id,
            'product_name': order.product_name,
            'quantity': order.quantity
        })
    return jsonify({'error': 'Order not found'}), 404


@orders_bp.route('/', methods=['POST'])
def create_order():
    """Create a new order."""
    data = request.get_json()
    order = order_repo.create_order(
        data['user_id'],
        data['product_name'],
        data['quantity']
    )
    return jsonify({'id': order.id, 'product_name': order.product_name}), 201
