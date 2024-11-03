import requests
import json
import os
config = json.load(open('config.json'))
CHUNK_SIZE = 1024
url = "https://api.elevenlabs.io/v1/text-to-speech/acCWxmzPBgXdHwA63uzP"
title = config['image_name'].split('.')[0]

newpath = f'7.voices/{title}'
if not os.path.exists(newpath):
    os.makedirs(newpath)

headers = {
  "Accept": "audio/mpeg",
  "Content-Type": "application/json",
  "xi-api-key": "sk_2ab609e720e0b6d45dc367fb27e427fe12de2c769f2c46ec"
}
data1 = {
  "text": config["text1"],
  "model_id": "eleven_multilingual_v2",
  "voice_settings": {
    "stability": 0.5,
    "similarity_boost": 1
  }
}

if data1['text'][-1] != '.':
    data1['text'] += '.'

voice1_path = f'7.voices/{title}/voice1.mp3'
if not os.path.exists(voice1_path):
    response = requests.post(url, json=data1, headers=headers)
    with open(voice1_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                f.write(chunk)

data2 = {
  "text": config["text2"],
  "model_id": "eleven_multilingual_v2",
  "voice_settings": {
    "stability": 0.5,
    "similarity_boost": 1
  }
}

if data2['text'][-1] != '.':
    data2['text'] += '.'

voice2_path = f'7.voices/{title}/voice2.mp3'
if not os.path.exists(voice2_path):
    response = requests.post(url, json=data2, headers=headers)
    with open(f'7.voices/{title}/voice2.mp3', 'wb') as f:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                f.write(chunk)
