from datetime import datetime, timedelta
from random import randrange
from uuid import uuid4

from flask import Blueprint, jsonify, request, url_for
from flask_login import current_user, login_required

from ..helper import admin_required_decorator as admin_required
from ..helper.youtube import build_youtube_api
from ..models import Callback, Channel
from ..tasks import channels_renew

api_channel_blueprint = Blueprint("api_channel", __name__)


@api_channel_blueprint.route("/search")
@login_required
def search():
    query = request.args.get("query")
    response = (
        build_youtube_api()
        .search()
        .list(part="snippet", maxResults=30, q=query, type="channel")
        .execute()
    )
    results = response
    results = [
        {
            "title": item["snippet"]["title"],
            "id": item["snippet"]["channelId"],
            "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
        }
        for item in response["items"]
    ]
    return jsonify(results)


@api_channel_blueprint.route("/renew-all")
@login_required
def renew_all():
    """Renew Subscription Info, Both Hub and Info"""
    execution = int(request.args.to_dict().get("execution", 0))
    interval = 60 * 60 * 24 * 4
    if execution == 0:
        task = channels_renew.apply_async(
            args=[[channel.id for channel in Channel.query.all()]]
        )
        response = {
            "id": task.id,
            "status": url_for("api_task.status", task_id=task.id),
        }
    else:
        response = {}
        for channel in Channel.query.all():
            expiration = channel.expiration
            if expiration is None:
                # Expiration is not available yet (Channel just init)
                # Set ETA to four days later
                countdown = 60 * 60 * 24 * 4
            elif expiration > datetime.now() + timedelta(days=1):
                # Expiration is more than one day
                # Set ETA to one day before expiration
                countdown = expiration - timedelta(days=1) - datetime.now()
                countdown = countdown.total_seconds()
            else:
                # Expiration is less than one day
                # Set ETA to now
                countdown = 0
            if execution == -2 and countdown > 0:
                countdown = randrange(int(countdown))
            task = channels_renew.apply_async(
                args=[[channel.id], interval],
                countdown=countdown,
                task_id=f"renew_{channel.id}_{str(uuid4())[:8]}",
            )
            response[channel.id] = task.id
    return jsonify(response)


@api_channel_blueprint.route("/callbacks")
@login_required
@admin_required
def callbacks_all():
    days = int(request.args.to_dict().get("days", 3))
    days_ago = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    callbacks = Callback.query.filter(Callback.timestamp >= days_ago).order_by(
        Callback.timestamp.desc()
    )
    response = list(map(dict, callbacks))
    return jsonify(response)


@api_channel_blueprint.route("/<channel_id>/status")
@login_required
def status(channel_id):
    """From Hub fetch Status"""
    channel = Channel.query.get_or_404(channel_id)
    response = channel.refresh()
    return jsonify(response)


@api_channel_blueprint.route("/<channel_id>/subscribe")
@login_required
def subscribe(channel_id):
    """Subscribe to a Channel"""
    return jsonify(current_user.subscribe_to(channel_id))


@api_channel_blueprint.route("/<channel_id>/unsubscribe")
@login_required
def unsubscribe(channel_id):
    """Unsubscribe to a Channel"""
    return jsonify(current_user.unbsubscribe(channel_id))


@api_channel_blueprint.route("/<channel_id>/fetch-videos")
@login_required
@admin_required
def fetch_videos(channel_id):
    # TODO: deprecate this
    channel = Channel.query.get_or_404(channel_id)
    response = channel.fetch_videos()
    return jsonify(response)


@api_channel_blueprint.route("/<channel_id>/callbacks")
@login_required
@admin_required
def callbacks(channel_id):
    channel = Channel.query.get_or_404(channel_id)
    callbacks = channel.callbacks.limit(50)
    response = list(map(dict, callbacks))
    return jsonify(response)
