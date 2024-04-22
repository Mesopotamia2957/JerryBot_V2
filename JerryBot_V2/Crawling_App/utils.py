import requests
from django.conf import settings

def post_message(token, channel, text):
    response = requests.post('https://slack.com/api/chat.postMessage', {
        'token': token,
        'channel': channel,
        'text': text
    }).json()
    return response
