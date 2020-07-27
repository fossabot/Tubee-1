"""Channel Model"""
import logging
from datetime import datetime

from .. import db
from ..helper import build_callback_url, build_topic_url, try_parse_datetime
from ..helper.hub import details, subscribe, unsubscribe
from ..helper.youtube import build_youtube_api
from ..exceptions import InvalidAction, APIError

from googleapiclient.errors import Error as YouTubeAPIError
from flask import current_app


class Channel(db.Model):
    __tablename__ = "channel"
    id = db.Column(db.String(32), primary_key=True)
    name = db.Column(db.String(128))
    active = db.Column(db.Boolean, default=False)
    infos = db.Column(db.JSON)
    hub_infos = db.Column(db.JSON)
    subscribe_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    unsubscribe_timestamp = db.Column(db.DateTime)
    videos = db.relationship("Video", backref="channel", lazy="dynamic")
    callbacks = db.relationship("Callback", backref="channel", lazy="dynamic")
    subscribers = db.relationship(
        "Subscription",
        backref=db.backref("channel", lazy="joined"),
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __init__(self, channel_id):
        from ..tasks import (
            # schedule_channels_update_hub_infos,
            # schedule_channels_fetch_videos,
            channels_update_hub_infos,
            channels_fetch_videos,
        )

        self.id = channel_id
        db.session.add(self)
        db.session.commit()
        try:
            self.update_youtube_infos()
        except (APIError, InvalidAction) as error:
            db.session.delete(self)
            db.session.commit()
            raise error

        # schedule_channels_update_hub_infos([channel_id], countdown=60)
        # schedule_channels_fetch_videos([channel_id])

        channels_update_hub_infos.apply_async(
            args=[
                [
                    (
                        channel_id,
                        build_callback_url(channel_id),
                        build_topic_url(channel_id),
                    )
                ]
            ],
            countdown=60,
        )
        channels_fetch_videos.apply_async(args=[[channel_id]])
        self.activate()

    def __repr__(self):
        return "<Channel {} (#{})>".format(self.name, self.id)

    @property
    def expiration(self):
        try:
            return try_parse_datetime(self.hub_infos["expiration"])
        except TypeError:
            return None

    @expiration.setter
    def expiration(self, expiration):
        raise ValueError("expiration can not be set")

    @expiration.deleter
    def expiration(self, exception):
        raise ValueError("expiration can not be delete")

    def activate(self):
        """Submitting hub Subscription, called when first user subscribe"""
        if self.active:
            raise AttributeError("Channel is already active")
        results = self.subscribe()
        if results:
            self.active = True
            self.subscribe_timestamp = datetime.utcnow()
            db.session.commit()
        return results

    def deactivate(self, callback_url=None, topic_url=None):
        """Submitting hub unsubscription, called when last user unsubscribe"""
        if not self.active:
            raise AttributeError("Channel is already deactivate")
        if not callback_url:
            callback_url = build_callback_url(self.id)
        if not topic_url:
            topic_url = build_topic_url(self.id)
        response = unsubscribe(
            current_app.config["HUB_GOOGLE_HUB"], callback_url, topic_url
        )
        if response.success:
            self.active = False
            self.unsubscribe_timestamp = datetime.utcnow()
            db.session.commit()
        return response

    def update_hub_infos(self, callback_url=None, topic_url=None):
        """Update hub subscription details, called by task or app"""
        if not callback_url:
            callback_url = build_callback_url(self.id)
        if not topic_url:
            topic_url = build_topic_url(self.id)
        results = details(current_app.config["HUB_GOOGLE_HUB"], callback_url, topic_url)
        results.pop("requests_url")
        results.pop("response_object")
        response = results.copy()
        for key, val in results.items():
            if not val:
                continue
            if isinstance(val, datetime):
                results[key] = str(val)
            elif isinstance(val[0], datetime):
                results[key] = (str(val[0]), val[1])
        self.hub_infos = results
        db.session.commit()
        return response

    def update_youtube_infos(self):
        """Update YouTube metadata, called by task"""
        try:
            api_result = (
                build_youtube_api()
                .channels()
                .list(part="snippet", id=self.id)
                .execute()
            )
            if api_result["pageInfo"]["totalResults"] == 0:
                if self.name is None:
                    raise InvalidAction(f"Channel {self.id} doesn't exists")
                raise APIError(
                    service="YouTube",
                    message=f"Unable to update channel <{self.id}> info",
                )
            self.infos = api_result["items"][0]
            self.name = self.infos["snippet"]["title"]
            db.session.commit()
            return self.infos
        except (YouTubeAPIError, KeyError) as error:
            # TODO: Parse API Error
            raise APIError(
                service="YouTube",
                message=str(error.args),
                error_type=error.__class__.__name__,
            )

    def fetch_videos(self):
        """Update videos, Called by task"""
        from .video import Video

        # Querying from a special playlist created by YouTube
        # Playlist ID is replacing prefix of Channel ID from UC to UU
        playlist_items = build_youtube_api().playlistItems()
        request = playlist_items.list(
            part="snippet", maxResults=50, playlistId=f"UU{self.id[2:]}",
        )

        results = {"new_item_appended": 0, "video_ids": []}
        while request is not None:
            api_results = request.execute()
            for video in api_results["items"]:
                video_id = video["snippet"]["resourceId"]["videoId"]
                if not Video.query.get(video_id):
                    Video(video_id, self, fetch_infos=False)
                    results["new_item_appended"] += 1
                    results["video_ids"].append(video_id)
            request = playlist_items.list_next(request, api_results)

        return results

    def subscribe(self, callback_url=None, topic_url=None):
        """Submitting hub Subscription, called by task or app"""
        if not callback_url:
            callback_url = build_callback_url(self.id)
        if not topic_url:
            topic_url = build_topic_url(self.id)
        response = subscribe(
            current_app.config["HUB_GOOGLE_HUB"], callback_url, topic_url
        )
        logging.info("Callback URL: {}".format(callback_url))
        logging.info("Topic URL   : {}".format(topic_url))
        logging.info("Channel ID  : {}".format(self.id))
        logging.info("Response    : {}".format(response.status_code))
        return response.success

    # TODO: DEPRECATE THIS
    def renew(self, stringify=False, callback_url=None, topic_url=None):
        """Trigger renew functions"""

        response = {
            "subscription_response": self.subscribe(callback_url, topic_url),
            "info_response": self.update_youtube_infos(),
            # "hub_response": self.update_hub_infos(stringify=stringify, callback_url, topic_url),
        }
        # update_channel_hub_infos.apply_async(self.id, callback_url, topic_url)
        logging.info("Channel Renewed: {}<{}>".format(self.name, self.id))
        return response
