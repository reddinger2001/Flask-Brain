"""Celery tasks."""

# Mock celery
class MockCelery:
    def task(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator

celery = MockCelery()


@celery.task
def send_welcome_email(user_id):
    """Send welcome email to new user."""
    # Mock implementation
    print(f"Sending welcome email to user {user_id}")
    return True


@celery.task(name='process_order')
def process_order_task(order_id):
    """Process an order asynchronously."""
    # Mock implementation
    print(f"Processing order {order_id}")
    return True
