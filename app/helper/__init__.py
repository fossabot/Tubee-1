"""Helper Functions for Tubee"""

import codecs
import os
import requests
import google.oauth2.credentials
import googleapiclient.discovery
from flask import current_app
from Tubee import app, db, pusher
from ..models import User, Notification

def generate_random_id():
    """Generate a 16-chars long id"""
    return codecs.encode(os.urandom(16), "hex").decode()

def send_notification(initiator, user, *args, **kwargs):
    """
    str:initiator   Function or Part which fired the notification
    str:message     Main Body of Message

    str:title       Title of Message
    str:image       URL of Image
    str:url         URL contained with Message
    str:url_title   Title for the URL contained
    int:priority    Priority of Message
                    retry & expire is required with priority 2
                    Range       -2 ~ 2
                    Default     0
    int:retry       Seconds between retries
                    Range       30 ~ 10800
    int:expire      Seconds before retries stop
                    Range       30 ~ 10800
    """
    backup_kwargs = kwargs.copy()
    if "image" in kwargs and kwargs["image"]:
        img_url = kwargs["image"]
        kwargs["image"] = requests.get(img_url, stream=True).content
    response = pusher.send_message(user.pushover_key, *args, **kwargs)
    backup_kwargs["message"] = args[0]
    new = Notification(initiator, args[0][:2000], backup_kwargs, response)
    db.session.add(new)
    db.session.commit()
    return response

def build_youtube_service(credentials):
    """Build Corresponding YouTube Service from User's Credentials"""
    credentials = google.oauth2.credentials.Credentials(**credentials)
    return googleapiclient.discovery.build(
        current_app.config["YOUTUBE_API_SERVICE_NAME"],
        current_app.config["YOUTUBE_API_VERSION"],
        cache_discovery=False,
        credentials=credentials)
