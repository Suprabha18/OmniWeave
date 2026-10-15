
from flask import Blueprint, jsonify, request, current_app

from api.schemas import validate_approval_payload
from storage.task_repository import TaskRepository


approvals_bp = Blueprint(
    "approvals_api", __name__, url_prefix="/api/approvals"
)

repository = TaskRepository()


@approvals_bp.get("/<task_id>")
def get_approval(task_id):
    if repository.get_task(task_id) is None:
        return jsonify({
            "success": False,
            "message": "Task not found."
        }), 404

    approval = repository.get_approval(task_id)

    return jsonify({
        "success": True,
        "approval": approval
    })


@approvals_bp.post("/<task_id>")
def submit_approval(task_id):
    payload = request.get_json(silent=True) or {}
    data, error = validate_approval_payload(payload)

    if error:
        return jsonify({
            "success": False,
            "message": error
        }), 400

    try:
        approval = repository.set_approval(
            task_id,
            "approved" if data["action"] == "approve" else "rejected",
            data["reason"]
        )

        if approval is None:
            return jsonify({
                "success": False,
                "message": "Task not found."
            }), 404

        return jsonify({
            "success": True,
            "approval": approval
        })

    except Exception:
        current_app.logger.exception("Approval update failed")
        return jsonify({
            "success": False,
            "message": "Could not update approval."
        }), 500
