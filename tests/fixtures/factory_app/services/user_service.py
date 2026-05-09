"""User service."""

from models import User, db


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
        return user
    
    def update_user(self, user_id, username=None, email=None):
        """Update user."""
        user = self.get_user(user_id)
        if user:
            if username:
                user.username = username
            if email:
                user.email = email
            db.session.commit()
        return user
    
    def delete_user(self, user_id):
        """Delete user."""
        user = self.get_user(user_id)
        if user:
            db.session.delete(user)
            db.session.commit()
        return user
