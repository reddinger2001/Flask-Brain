"""Factory app - app factory pattern with blueprints."""

from flask import Flask


def create_app():
    """Application factory."""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///factory.db'
    
    # Register blueprints
    from routes.users import users_bp
    app.register_blueprint(users_bp, url_prefix='/api')
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
