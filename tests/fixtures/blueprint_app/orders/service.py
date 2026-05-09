"""Order service."""

from models import Order, db
from tasks import process_order_task


class OrderRepository:
    """Repository for order data access."""
    
    def get_order(self, order_id):
        """Get order by ID."""
        return Order.query.get(order_id)
    
    def get_orders_by_user(self, user_id):
        """Get all orders for a user."""
        return Order.query.filter_by(user_id=user_id).all()
    
    def create_order(self, user_id, product_name, quantity):
        """Create a new order."""
        order = Order(user_id=user_id, product_name=product_name, quantity=quantity)
        db.session.add(order)
        db.session.commit()
        
        # Dispatch async task
        process_order_task.delay(order.id)
        
        return order
