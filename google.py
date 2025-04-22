import os
import requests
import urllib.parse
from datetime import datetime
from datetime import timedelta
import xml.etree.ElementTree as ET

class GoogleBroker:
    def __init__(self):

        self.clientid = os.environ.get('GOOGLE_CLIENT_ID')
        self.secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        self.redirect = "https://api.arfevrier.fr/v2/google/redirect"

        self.auth_uri = 'https://accounts.google.com/o/oauth2/auth'
        self.token_uri = 'https://oauth2.googleapis.com/token'
        self.info_uri = 'https://www.googleapis.com/oauth2/v2/userinfo'

    def getRedirectUrl(self, redirect="https://api.arfevrier.fr/v2/google/redirect", scope="https://www.googleapis.com/auth/userinfo.email"):
        return f"{self.auth_uri}?client_id={self.clientid}&redirect_uri={urllib.parse.quote(redirect)}&response_type=code&scope={urllib.parse.quote(scope)}"

    def getEmail(self, code):
        try:
            payload = {"code": code, "client_id": self.clientid, "client_secret": self.secret,
                       "redirect_uri": self.redirect, "grant_type": 'authorization_code'}
            r = requests.post(self.token_uri, data=payload)
            access_token = r.json()['access_token']

            headers = {'Authorization': f'Bearer {access_token}'}
            r = requests.get(self.info_uri, headers=headers)
            return r.json()['email']
        except:
            return False
    
    def getToken(self, code, redirect="https://api.arfevrier.fr/v2/google/redirect"):
        try:
            payload = {"code": code, "client_id": self.clientid, "client_secret": self.secret,
                       "redirect_uri": redirect, "grant_type": 'authorization_code'}
            r = requests.post(self.token_uri, data=payload)
            return r.json()['access_token']
        except:
            return None

class YoutubeBroker:
    def __init__(self):
        self.subsUrl = "https://youtube.googleapis.com/youtube/v3/subscriptions"
        self.channelUrl = "https://www.googleapis.com/youtube/v3/channels"
        self.playlistItemUrl = "https://www.googleapis.com/youtube/v3/playlistItems"
        self.videosFeed = "https://www.youtube.com/feeds/videos.xml"

    def getSubscribers(self, pageToken=None):
        headers = {'Authorization': f'Bearer {self.token}'}
        params = {'part':'snippet','mine':'true','maxResults':'50', 'pageToken':pageToken}
        r = requests.get(self.subsUrl, params=params, headers=headers).json()
        subs = r['items']

        for sub in subs:
            yield sub['snippet']['resourceId']['channelId']
        if 'nextPageToken' in r:
            for channelid in self.getSubscribers(r['nextPageToken']):
                yield channelid

    def getVideos(self, xmlvideo):
        YTXML_entry = "{http://www.w3.org/2005/Atom}entry"
        YTXML_videoid = "{http://www.youtube.com/xml/schemas/2015}videoId"
        YTXML_title = "{http://www.w3.org/2005/Atom}title"
        YTXML_published = "{http://www.w3.org/2005/Atom}published"
        YTXML_author = "{http://www.w3.org/2005/Atom}author"
        YTXML_name = "{http://www.w3.org/2005/Atom}name"
        for video in xmlvideo.findall(YTXML_entry):
            videoInfo = {}
            videoInfo['resourceId'] = {'videoId': video.find(YTXML_videoid).text}
            videoInfo['title'] = video.find(YTXML_title).text
            videoInfo['publishedAt'] = video.find(YTXML_published).text
            videoInfo['channelTitle'] = video.find(f"{YTXML_author}/{YTXML_name}").text
            yield videoInfo

    def getLastVideos(self, channelId):
        r = requests.get(f"{self.videosFeed}?channel_id={channelId}").text
        root = ET.fromstring(r)
        return self.getVideos(root)

class StringCache:
    def __init__(self):
        self.data = {}

    def inCache(self, id):
        if id in self.data:
            print(f"[StringCache] <{id}> in cache since: ", datetime.utcnow()-self.data[id]["time"])
            if datetime.utcnow()-self.data[id]["time"] < timedelta(hours=2):
                return True
            else:
                del self.data[id]
                return False
        else:
            return False

    def add(self, id, element):
        assert not self.inCache(id)
        self.data[id] = {}
        self.data[id]["time"] = datetime.utcnow()
        self.data[id]["element"] = element

    def get(self, id):
        assert self.inCache(id)
        return self.data[id]["element"]
