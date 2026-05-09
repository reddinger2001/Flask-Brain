"""User service."""

from models import User, db
from tasks import send_welcome_email


class UserService:
    """Service for user operations."""
    
    def get_user(self, user_id):
        """Get user by ID."""
        return User.query.get(user_id)
    
    def get_all_users(self):
        """Get all users."""
        return User.query.all()
    
    def create_user(self, username, email):
        """Create a new user."""
        user = User(username=username, email=email)
        db.session.add(user)
        db.session.commit()
        
        # Dispatch task
        send_welcome_email.delay(user.id)
        
        return user
