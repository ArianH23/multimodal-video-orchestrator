import requests
import google.generativeai as genai
import PIL.Image
import gen_image
import ftfy
import json
from source.image_gen import generate_image
from source.title_gen import generate_title_image
from source.gen_voice import generate_voices
from source.video_gen_zoom_out import generate_video
import shutil

file = open('prompt.txt', 'r')
prompt = file.read()

API_KEY = "key1"
API_KEY_BILLED = "key2"
genai.configure(api_key=API_KEY)
google1114 = "gemini-exp-1114"
google2 = "gemini-2.0-flash-exp"
google25 = "gemini-2.5-pro"

model = genai.GenerativeModel(google25)

response1 = model.generate_content([prompt],
                                   generation_config=genai.types.GenerationConfig(
                                    # Only one candidate for now.
                                    temperature=1.95
    ),)


# print(response2.text)
a = response1.text.replace('```json', '')
a = a.replace('```', '')
a = a.replace('python', '')

print(a)
# b = response2.text.replace('```json','')
# b = b.replace('```','')
# b = b.replace('FINISHED CREATING THE DICTIONARY','')
my_dict = eval(a)
# my_dict = other_dict
my_dict = {item["topic"]: item for item in my_dict}
# ------------------------------------------------------------------------------------------
chosen_topic = 'Strength'
music_prompt = my_dict[chosen_topic]['music_prompt']
prompt1 = my_dict[chosen_topic]['image_prompts'][0]
prompt2 = my_dict[chosen_topic]['image_prompts'][1]

split_quote1 = my_dict[chosen_topic]['split_quote'][0]
split_quote2 = my_dict[chosen_topic]['split_quote'][1]

font_rgb = my_dict[chosen_topic]['font_rgb']

file_desc = open('descr_font_color.txt', 'r')
desc_prompt = file_desc.read()


desc_prompt = desc_prompt.format(font_rgb=font_rgb, split_quote1=split_quote1, split_quote2=split_quote2, topic=chosen_topic)
print(desc_prompt)
print(music_prompt)


gen_image.gen_image(prompt1, 'image1')
gen_image.gen_image(prompt2, 'image2')

# ------------------------------------------------------------------------------------------
chosen_image = 'image2'

if chosen_image == 'image1':
    music_prompt = prompt1
else:
    music_prompt = prompt2

chosen_image_path = 'current_analysis/' + chosen_image + '.png'

image = PIL.Image.open(chosen_image_path)
contents = [image, desc_prompt]
response2 = model.generate_content(contents,
                                   generation_config=genai.types.GenerationConfig(
                                    # Only one candidate for now.
                                    temperature=1.95
    ),)

b = response2.text.replace('```json', '')
b = b.replace('```', '')
b = b.replace('python', '')

print(b)
# b = response2.text.replace('```json','')
# b = b.replace('```','')
# b = b.replace('FINISHED CREATING THE DICTIONARY','')
my_dict2 = eval(b)
# my_dict = other_dict
my_dict2.keys()

# ------------------------------------------------------------------------------------------

source = chosen_image_path
destination = "1.base_images/" + my_dict2['image_name'] + '.png' # or a folder path
shutil.copy(source, destination)

text_diff_mult = 3
generate_image(my_dict2['suggested_border_rgb'], chosen_topic, my_dict2['quotes'], my_dict2['image_name'] + '.png', text_diff_mult)

generate_title_image(chosen_topic, my_dict2['image_name'], tuple(my_dict2['suggested_border_rgb']))

generate_voices(my_dict2['image_name'], my_dict2['quotes'])

file_video_desc = open('videos_descr_esp.txt', 'r', encoding='utf-8')
video_desc = file_video_desc.read()
print(music_prompt)

epic_part = 15.5
download_path = "C:/Users/rodri/Downloads/"
song_name = "Cosmic Defiance"
song_path = download_path + song_name + '.mp3'

source = song_path
destination = "4.music/" + song_name + '.mp3' # or a folder path
shutil.move(source, destination)

print(ftfy.fix_text(my_dict2['tiktok_description'])+ '\n\n' + video_desc)

generate_video(my_dict2['image_name'], "BR", 3, epic_part, chosen_topic, 4, my_dict2['quotes'], text_diff_mult, my_dict2['suggested_border_rgb'], song_name)

print(ftfy.fix_text(my_dict2['tiktok_description'])+ '\n\n' + video_desc)

generate_video(my_dict2['image_name'], "BR", 3, epic_part, chosen_topic, 60, my_dict2['quotes'], text_diff_mult, my_dict2['suggested_border_rgb'], song_name)

# ------------------------------------------------------------------------------------------
