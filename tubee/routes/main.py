"""The Main Routes"""
from flask import Blueprint, current_app, redirect, render_template, url_for
from flask_login import current_user, login_required
from ..helper import youtube_required
from ..models import Channel, Subscription
main_blueprint = Blueprint("main", __name__)


@main_blueprint.route("/")
@login_required
def dashboard():
    """Showing All Subscribed Channels"""
    subscriptions = current_user.subscriptions.join(
        Subscription.channel).order_by(Channel.channel_name.asc()).all()
    return render_template("dashboard.html",
                           subscriptions=subscriptions)


@main_blueprint.route("/youtube/subscription")
@login_required
@youtube_required
def youtube_subscription():
    """Showing User's YouTube Subsciptions"""
    response = current_user.youtube.subscriptions().list(
        part="snippet", maxResults=50, mine=True,
        order="alphabetical").execute()
    for channel in response["items"]:
        channel_id = channel["snippet"]["resourceId"]["channelId"]
        channel["snippet"]["subscribed"] = current_user.is_subscribing(
            channel_id)
        channel["snippet"]["subscribe_endpoint"] = url_for(
            "api.channel_subscribe", channel_id=channel_id)
    return render_template("youtube_subscription.html", response=response)
