from itertools import zip_longest
import os, io, json, glob
import typing_extensions
import streamlit as st
from datetime import datetime
import pytz
import shutil
from zipfile import ZipFile
import boto3
from trp import Document
import tempfile
import boto3.session
import os
from dotenv import load_dotenv
load_dotenv()
from PIL import Image, ImageDraw

# Sanitize working directory
for f in glob.glob("*"): # millenium bug
    if f != 'app.py' and f != 'Untitled.ipynb':
        try:
            os.remove(f)
        except:
            shutil.rmtree(f) 

def image_or_json(s):
    ext = s.split('/')[-1].split('.')[-1]
    if ext in {'jpg', 'jpeg', 'png', 'bmp'}:
        return 'image'
    elif ext in {'json'}:
        return 'json'

# boto3 client
session = boto3.session.Session(
    region_name='eu-west-3', 
    aws_access_key_id=os.getenv('aws_access_key_id'),
    aws_secret_access_key=os.getenv('aws_secret_access_key')
)

title = '<p style="font-family:Courier; color:Black; font-size: 60px; font-weight:bold;">Handwritten Text Extractor</p>'
st.markdown(title, unsafe_allow_html=True)
st.text('Powered by Google Cloud, Microsoft Azure and AWS Textract')

st.subheader('Step 1: Upload files')
data = st.file_uploader("Upload a video", type=None, accept_multiple_files=True)
out_folders = []
if len(data) >= 1 :
    for file in data:
        folder_name = file.name.split('.')[0]
        os.mkdir(f'{folder_name}')
        out_folders.append(folder_name)
        img = Image.open(file)
        width, height = img.size
        textract = session.client('textract')
        response = textract.analyze_document(
            Document={
            'Bytes': file.getvalue()
            },
            FeatureTypes=["FORMS", "TABLES"])
        FormdocumentName = file.name
        doc = Document(response)
        for page in doc.pages:
            page_path = f'page_{doc.pages.index(page) + 1}'    
            os.mkdir(f'{folder_name}/{page_path}')
            form_dict={}
            for field in page.form.fields:
                if field.key and field.value:
                    form_dict[field.key.text]= field.value.text
                    x1 = field.value.geometry.boundingBox.left*width
                    y1 = field.value.geometry.boundingBox.top*height-2
                    x2 = x1 + (field.value.geometry.boundingBox.width*width)+5
                    y2 = y1 + (field.value.geometry.boundingBox.height*height)+2
                    draw = ImageDraw.Draw(img)
                    draw.rectangle([x1, y1, x2, y2], fill=None, outline ="Black", width=10)
            with open(f'{folder_name}/{page_path}/{page_path}.json', 'w') as json_f:
                json.dump(form_dict, json_f)
            img.save(f'{folder_name}/{page_path}/{page_path}.png')
            timezone = pytz.timezone('Europe/Brussels')
            dateTimeObj = datetime.now(timezone)
            dest_path = dateTimeObj.strftime("%Y%m%d_%H%M%S")
    paths_list_img = []
    paths_list_json = []
    with ZipFile(f'{dest_path}.zip','w') as zip:
    # writing each file one by one
        for folder in out_folders:
            for dirpath,dirs,files in os.walk(folder):
                for f in files:
                    fn = os.path.join(dirpath, f)
                    if image_or_json(fn) == 'image':
                        paths_list_img.append(fn)
                    if image_or_json(fn) == 'json':
                        paths_list_json.append(fn)
                    zip.write(fn)
                    s3 = session.resource('s3')
                    bucket = "kpmg-bucket-test"
                    s3.Bucket(bucket).upload_file(fn , f'{dest_path}_{fn}')

    with st.container():
        col1,col2 = st.columns(2)
        with col1:
            index = 0
            if st.button('Previous'):
                if index >= 1 and index in range(len(paths_list_img)):
                    index -= 1
        with col2:
            if st.button('Next'):
                if index >= 0 and index in range(len(paths_list_img)):
                    index += 1
    with st.container():
        col1,col2 = st.columns(2)
        with col1:
            st.image(paths_list_img[index])
        with col2:
            with open(paths_list_json[index]) as json_file:
                data = json.load(json_file)
                st.json(data)
    with st.container():
        with open(f'{dest_path}.zip', 'rb') as zip:
            st.download_button(
                label="Download files as .zip",
                file_name=f'{dest_path}.zip',
                data=zip,
                args=(dest_path,),
                mime='application/zip')
        