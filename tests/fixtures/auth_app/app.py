"""Auth fixture app — routes with various auth decorator patterns.

Used to verify that RouteScanner correctly detects @login_required and
similar decorators and sets auth_required=True in route metadata.
"""

from flask import Flask, jsonify

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Stub decorators — simulate Flask-Login / custom auth without the dependency
# ---------------------------------------------------------------------------

def login_required(f):
    return f


def admin_required(f):
    return f


def roles_required(*roles):
    def decorator(f):
        return f
    return decorator


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/public')
def public_view():
    """Open route — no auth decorator."""
    return jsonify({"status": "ok"})


@app.route('/dashboard')
@login_required
def dashboard():
    """Protected by @login_required."""
    return jsonify({"page": "dashboard"})


@app.route('/admin')
@admin_required
def admin_panel():
    """Protected by @admin_required."""
    return jsonify({"page": "admin"})


@app.route('/reports')
@roles_required("manager", "admin")
def reports():
    """Protected by @roles_required(...)."""
    return jsonify({"page": "reports"})


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Protected POST+GET route."""
    return jsonify({"page": "profile"})
