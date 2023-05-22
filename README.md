# Personal Music Recommendations

This is a music recommendations based on FastAPI for my personal using.

It interacts with Spotify Web Api and Youtube Data Api v3 and implement oauth2.

## The flow of request Spotify Web Api

<https://developer.spotify.com/documentation/web-api/tutorials/code-flow>

1. Create an APP on Spotify Web for Development and write app information.
2. Request the AUTHORIZATION_CODE with response_type, redirect_uri, client_id and scope for Spotity access_token.
3. Request the access_token with grant_type, AUTHORIZATION_CODE and redirect_uri.
4. Redirect to url based on the redirect_uri.

With the access_token, I can start to request data through Spotify Web Api.

For this app, I request "Get Recommendations" on Spotify Web Api to get the music recommends.

The paramters seed_artists, seed_genres and seed_tracks are requested from "Get User's Top Items" on Spotify Web Api.

After parse the data from "Get User's Top Items", I can get the music recommendations from "Get Recommendations" finally.

## The flow of request Youtube Data Api v3

<https://developers.google.com/youtube/v3/guides/authentication?hl=en>

Because Youtube Data Api v3 doesn't have recommendations api, so I use my subscriptions on Youtube to fulfill the music recommendations, althrough this may not be as accurate as Spotify recommendations.

1. Enable Youtube Data Api v3 on Google Cloud Console, then request API_KEY and create Oauth2.
2. Using google_auth_oauthlib to fulfill the Oauth2 and redirect to REDIRECT_URI. This REDIRECT_URI may not as the same as the spotify's redirect_uri, depends on settings.
3. First, get my personal subscriptions on Youtube through "Subscriptions: list". Then, parse these subscriptions data to get every channel's channel id. But, in this app, I need to ensure the channel is publishing music videos, so I need to analyze the channels.
4. Second, using these channel ids to search channel's videos through "Search: list". Then will get video ids which are publised by those channels.
5. Third, using these video ids to check the video category. If the video category id is 10, it represents "music" category. And just I said before, I just want the channel is publishing videos related music, Therefore, if the video category id is not 10, I won't use these channel's videos as the seed_video.
6. Finally, using "Search: list" again and set parameter "relatedToVideoId"=seed_vide to get the related videos. Then parse the data and render on browser, the music recommendations is done!
  
Youtube Data Api v3 docs:

<https://developers.google.com/youtube/v3/docs/subscriptions/list?hl=en>

<https://developers.google.com/youtube/v3/docs/search/list?hl=en>

<https://developers.google.com/youtube/v3/docs/videos/list?hl=en>
