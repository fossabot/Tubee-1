"""API for Tasks"""
from flask import Blueprint, jsonify
from flask_login import login_required

from ..helper import admin_required
from ..tasks import channels_renew, list_all_tasks, remove_all_tasks

api_task_blueprint = Blueprint("api_task", __name__)
api_task_blueprint.before_request(admin_required)


@api_task_blueprint.route("/list-all")
@login_required
def list_all():
    tasks = list_all_tasks()
    return jsonify(tasks)


@api_task_blueprint.route("/remove-all")
@login_required
def remove_all():
    results = remove_all_tasks()
    return jsonify(results)


@api_task_blueprint.route("/<task_id>/status")
@login_required
def status(task_id):
    task = channels_renew.AsyncResult(task_id)
    response = {
        "id": task.id,
        "status": task.status.title(),
        "current": task.result.get("current", 1),
        "total": task.result.get("total", 1),
        "channel_id": task.result.get("channel_id", None),
        "result": task.result,
        "traceback": task.traceback,
    }
    return jsonify(response)
