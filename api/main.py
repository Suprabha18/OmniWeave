
from api.routes.tasks import tasks_bp
from api.routes.approvals import approvals_bp


def register_api(app):
    """Register OmniWeave API endpoints on the existing Flask app."""
    app.register_blueprint(tasks_bp)
    app.register_blueprint(approvals_bp)
