"""Blueprint app - domain-organized with multiple blueprints."""

from flask import Flask


def create_app():
    """Application factory."""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blueprint.db'
    
    # Register blueprints
    from users.routes import users_bp
    from orders.routes import orders_bp
    
    app.register_blueprint(users_bp, url_prefix='/users')
    app.register_blueprint(orders_bp, url_prefix='/orders')
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
