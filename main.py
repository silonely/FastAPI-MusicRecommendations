from typing import Union
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

import google.oauth2.credentials
import google_auth_oauthlib.flow

from dotenv import load_dotenv, set_key

import requests
from requests.auth import HTTPBasicAuth

import os
import json
import urllib.parse as urlparse
from urllib.parse import urlencode


load_dotenv()

GRANT_TYPE = os.getenv('GRANT_TYPE')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
SCOPE = ["user-top-read", "user-read-email", "user-read-private"]
GOOGLE_SCOPE=["https://www.googleapis.com/auth/youtube.readonly"]

app = FastAPI()

def urlParamCombiner(url:str = None, params:dict = None) -> str:
    urlParts = list(urlparse.urlparse(url)) # parse endpoint url
    urlParts[4] = urlencode(params)         # update endpoint query parameters
    return urlparse.urlunparse(urlParts)

def getHTMLResponse(items:dict):
    htmlResponse = ""
    for recommend in items["items"]:
        htmlResponse+= \
        """
            <a href='{url}' style=" 
                display: inline-flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                row-gap: 8px;">
                <img src={imageURL}>
                <span>{title}</span>
            </a>
        """.format(url=recommend["url"], 
                   imageURL=recommend["imageURL"],
                   title=recommend["title"])
    return htmlResponse

# https://developer.spotify.com/documentation/web-api/concepts/access-token
def getAccessTokenWithoutScope():
    endpoint = "https://accounts.spotify.com/api/token"
    header = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": GRANT_TYPE, 
        "client_id": CLIENT_ID, 
        "client_secret": CLIENT_SECRET
    }
    response = requests.post(endpoint, headers=header, data=data)
    if response.status_code==200:
        tokenDict = json.loads(response.content)
        return {"Authorization": "Bearer " + tokenDict['access_token']}
    else:
        return {
            "status": response.status_code,
            "content": response.content.decode('utf-8')
        }

# https://developer.spotify.com/documentation/web-api/tutorials/code-flow
@app.get("/")
async def getAuthorizationCode(code:str = None):
    """
    User Authorization Query Params
    ---
    'response_type': 'Required'
    'client_id': 'Required'
    'redirect_uri': 'Required'
    'state': 'Optional'
    'scope': 'Optional'
    'show_dialog': 'Optional'
    """

    if code is not None: 
        set_key('./.env', "AUTHORIZATION_CODE", code)
        
        return RedirectResponse("http://localhost:8000/google.auth")
    
    if code is None:
        
        endpoint = "https://accounts.spotify.com/authorize"
        params = {
            "response_type": "code", 
            "client_id": CLIENT_ID, 
            "redirect_uri": REDIRECT_URI, 
            "scope": (" ".join(SCOPE)).lstrip()
        }

        auth_url = urlParamCombiner(endpoint, params)
        return RedirectResponse(auth_url)

@app.get("/index")
async def index():
    await getAccessTokenWithScope()
    spotifyRecommends = await getSpotifyRecommendations()
    youtubeRecommends = await getYoutubeRecommends()
    htmlResponse = "<div>"
    htmlResponse += getHTMLResponse(spotifyRecommends)
    htmlResponse += getHTMLResponse(youtubeRecommends)
    return HTMLResponse(htmlResponse+"</div>")


async def getAccessTokenWithScope():
    
    endpoint = 'https://accounts.spotify.com/api/token'
    data = {
        "grant_type": "authorization_code", 
        "code": os.getenv("AUTHORIZATION_CODE"), 
        "redirect_uri": REDIRECT_URI
    }

    response = requests.post(endpoint, auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET), data=data)

    if response.status_code==200:
        # ---ensure server has got response.content--- 
        content = response.content
        content = json.loads(content)
        # --- End ---

        set_key("./.env", "ACCESS_TOKEN", content["access_token"])
    else:
        
        return RedirectResponse("http://localhost:8000")
    return 

# Perhaps need to apply random generate seed artist/genres/track
async def getTopItems(time_range: str="medium_term", limit: int=10, offset: int=0):
    """
    params = {
        "type": ['artists', 'tracks'],
        "time_range": ["long_term", "medium_term", "short_term"],     # [several years, last 6 months, last 4 weeks]
        "limit": "50",
        "offset": "0"
    }
    """

    params = {
        "time_range": time_range,
        "limit": limit,
        "offset": offset,
    }

    getArtistEndpoint = "https://api.spotify.com/v1/me/top/{type}".format(type="artists")
    getTracksEndpoint = "https://api.spotify.com/v1/me/top/{type}".format(type="tracks")

    getArtistEndpoint = urlParamCombiner(getArtistEndpoint, params)
    getTracksEndpoint = urlParamCombiner(getTracksEndpoint, params)

    header = {
        "Authorization": "Bearer " + os.getenv("ACCESS_TOKEN")
    }
    # get data
    artistsResponse = requests.get(getArtistEndpoint, headers=header)
    tracksResponse = requests.get(getTracksEndpoint, headers=header)

    if artistsResponse.status_code==200 and tracksResponse.status_code==200:
        # parse artistsResponse
        artistsContent = artistsResponse.content
        tracksContent = tracksResponse.content
        artistsContent = json.loads(artistsContent)
        tracksContent = json.loads(tracksContent)
        genres = []
        seedArtist = artistsContent["items"][0]["id"]

        for item in artistsContent["items"]:
            for category in item["genres"]:
                if len(genres)<3 and category not in genres: genres.append(category)
                else: break
        
        # get seed track id
        seedTrack = tracksContent["items"][0]["id"]
        return {
            "seed_artists": seedArtist,
            "seed_genres": (" ".join(genres)).lstrip(),
            "seed_tracks": seedTrack
        }
    return "Fail To Get Spotify Top Info."

async def getSpotifyRecommendations(limit:int = 10, market:str = "JP"):
    """
    params = {
        "limit": limit,
        "market": market,
        "seed_artists": seed_artists,
        "seed_genres": seed_genres,
        "seed_tracks": seed_tracks,
    }
    """
    endpoint = "https://api.spotify.com/v1/recommendations"
    header = {
        "Authorization": "Bearer " + os.getenv("ACCESS_TOKEN")
    }
    seed = await getTopItems()
    if seed:
        seed_artists, seed_genres, seed_tracks = seed['seed_artists'], seed['seed_genres'], seed['seed_tracks']
        params = {
            "limit": limit,
            "market": market,
            "seed_artists": seed_artists,
            "seed_genres": seed_genres,
            "seed_tracks": seed_tracks,
        }

        getRecommUrl = urlParamCombiner(endpoint, params)

        response = requests.get(getRecommUrl, headers=header)
        content = response.content
        content = json.loads(content)
        result = {"items": []}
        for track in content["tracks"]:
            if "album" in track:
                trackInfo = {}
                trackInfo["title"] = track["name"]
                trackInfo["url"] = track["album"]["external_urls"]["spotify"]
                trackInfo["imageURL"] = track["album"]["images"][1]["url"]
                result["items"].append(trackInfo)
        return result

@app.get("/google.auth")
def googleOauth2():
    # Use the client_secret.json file to identify the application requesting
    # authorization. The client ID (from that file) and access scopes are required.
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        'client_secret.json',
        scopes=GOOGLE_SCOPE)

    # Indicate where the API server will redirect the user after the user completes
    # the authorization flow. The redirect URI is required. The value must exactly
    # match one of the authorized redirect URIs for the OAuth 2.0 client, which you
    # configured in the API Console. If this value doesn't match an authorized URI,
    # you will get a 'redirect_uri_mismatch' error.
    flow.redirect_uri = GOOGLE_REDIRECT_URI

    # Generate URL for request to Google's OAuth 2.0 server.
    # Use kwargs to set optional request parameters.
    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type='offline',
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes='true')
    return RedirectResponse(authorization_url)

@app.get("/oauth2callback")
def oauthCallback(code:str = None):
    
    if code is None:
        auth_url = ('https://accounts.google.com/o/oauth2/v2/auth?response_type=code'
                '&client_id={}&redirect_uri={}&scope={}').format(GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI, GOOGLE_SCOPE)
        return RedirectResponse(auth_url)
    else:
        endpoint = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        response = requests.post(endpoint, data=data)
        content = response.content
        content = json.loads(content)
        set_key("./.env", "GOOGLE_ACCESS_TOKEN", content["access_token"])
        set_key("./.env", "GOOGLE_REFRESH_TOKEN", content["refresh_token"])
        return RedirectResponse("http://localhost:8000/index")

async def getYTSubscriptions():
    params = {
        "key": GOOGLE_API_KEY,
        "part": "snippet",
        "mine": True,
        "maxResults": 20,
    }
    headers = {
        "Authorization": "Bearer " + os.getenv("GOOGLE_ACCESS_TOKEN")
    }
    endpoint = urlParamCombiner("https://www.googleapis.com/youtube/v3/subscriptions",
                      params)

    response = requests.get(endpoint, headers=headers)
    CHANNEL_ID_LIST = []

    if response.status_code==200:
        content = response.content
        content = json.loads(content)
        for subInfo in content["items"]:
            channelID = subInfo["snippet"]["resourceId"]["channelId"]
            CHANNEL_ID_LIST.append(channelID)
        return CHANNEL_ID_LIST
    else:
        return "Error at get subscriptions"
    
async def searchChannel(channelId:str = None):
    if channelId is None: return "Error at channel ID"
    params = {
        "parts": "snippet",
        "channelId": channelId,
        "type": "video",
        "videoCategoryId": 10
    }
    headers = {
        "Authorization": "Bearer " + os.getenv("GOOGLE_ACCESS_TOKEN")
    }

    endpoint = urlParamCombiner("https://youtube.googleapis.com/youtube/v3/search", 
                                params)
    response = requests.get(endpoint, headers=headers)

    if response.status_code==200:
        content = response.content
        content = json.loads(content)
        result = content["items"]
        videoIDs = []
        for i in range(min(3, len(result))):
            videoID = result[i]["id"]["videoId"]
            if await checkVideoCategory(videoID):
                videoIDs.append(videoID)
            else: return None
        return videoIDs
    else:
        return "Error at search channel"

async def checkVideoCategory(videoID:str = None):
    if videoID is None: return "videoID is empty."
    params = {
        "part": "snippet",
        "id": videoID,
    }
    endpoint = urlParamCombiner("https://youtube.googleapis.com/youtube/v3/videos",
                     params)
    headers = {
        "Authorization": "Bearer " + os.getenv("GOOGLE_ACCESS_TOKEN")
    }
    response = requests.get(endpoint, headers=headers)
    if response.status_code==200:
        content = response.content
        content = json.loads(content)
        if content["items"]["snippet"]["categoryId"]==10:
            return True
    return False

async def searchRelatedVideo(videoID:str = None):
    if videoID is None: return "videoID is empty."
    params = {
        "part": "snippet",
        "relatedToVideoId": videoID,
        "type": "video",
        "maxResults": 10,
    }
    headers = {
        "Authorization": "Bearer " + os.getenv("GOOGLE_ACCESS_TOKEN")
    }
    endpoint = urlParamCombiner("https://youtube.googleapis.com/youtube/v3/search", 
                                params)
    response = requests.get(endpoint, headers=headers)

    if response.status_code==200:
        content = response.content
        content = json.loads(content)
        searchResult = content["items"]
        recommends = {"videos": []}
        youtube = "https://www.youtube.com/watch?v="
        for i in range(min(2, len(searchResult))):
            recommend = dict()
            info = searchResult[i]
            
            recommend["title"]=info["snippet"]["title"]
            recommend["url"]=youtube+info["id"]["videoId"]
            recommend["imageURL"]=info["snippet"]["thumbnails"]["medium"]["url"]

            recommends["items"].append(recommend)
        return recommends
    else:
        return "Error at search related videos"

async def getYoutubeRecommends():
    recommends = {"items": []}
    channelIDs = await getYTSubscriptions()
    for channelID in channelIDs:
        videoIDs= await searchChannel(channelID)
        if len(recommends["items"])<5 and videoIDs is not None:
            for videoID in videoIDs:
                recommendVideos = await searchRelatedVideo(videoID)
                for item in recommendVideos["items"]:
                    recommends["items"].append(item)
        else: break
    return recommends