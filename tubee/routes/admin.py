"""Routes for Admin Access"""
import os
import platform
import sys
import flask
import werkzeug
from flask import (Blueprint, current_app, flash, render_template, redirect,
                   request, url_for)
from flask_login import current_user, login_required
from ..helper import admin_required
from ..models import Callback, Channel, Notification, Service
admin_blueprint = Blueprint("admin", __name__)


@admin_blueprint.route("/dashboard")
@login_required
@admin_required
def admin_dashboard():
    infos = {
        "os_version": platform.platform(),
        "python_version": sys.version,
        "flask_version": flask.__version__,
        "werkzeug_version": werkzeug.__version__,
        "app_config": current_app.config,
        "os_env": os.environ,
    }
    callbacks = Callback.query.order_by(Callback.timestamp.desc()).all()
    notifications = Notification.query.order_by(
        Notification.sent_timestamp.desc()).paginate()
    return render_template("admin_dashboard.html",
                           infos=infos,
                           callbacks=callbacks,
                           notifications=notifications)


@admin_blueprint.route("/raise-exception")
@login_required
@admin_required
def raise_exception():
    raise Exception


@admin_blueprint.route("/test-logging")
@login_required
@admin_required
def test_logging():
    current_app.logger.debug("debug Log")
    current_app.logger.info("info Log")
    current_app.logger.warning("warning Log")
    current_app.logger.error("error Log")
    current_app.logger.critical("critical Log")
    flash("Logged Success", "success")
    return redirect(url_for("admin.admin_dashboard"))


@admin_blueprint.route("/notification/push", methods=["POST"])
@login_required
@admin_required
def notification_push():
    """Send Test Notification to User"""
    if request.method == "POST":
        response = current_user.send_notification(
            "Test",
            Service(request.form.get("service", "Pushover")),
            message=request.form["message"])
        flash(response, "success")
        return redirect(url_for("admin.admin_dashboard"))


@admin_blueprint.route("/<channel_id>/fetch-channel-videos")
@login_required
@admin_required
def fetch_channel_videos(channel_id):
    channel_item = Channel.query.filter_by(id=channel_id).first_or_404()
    channel_item.fetch_videos()
    return redirect(url_for("admin.admin_dashboard"))
