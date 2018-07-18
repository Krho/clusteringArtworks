# -*- coding: utf-8 -*-
from flask import (abort, Flask, render_template, request, Markup)
from flask_mwoauth import MWOAuth
import os
import json
import requests
import mwclient
import configparser
import ast

app = Flask(__name__)
app.secret_key = os.urandom(24)

BASEDIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILENAME = 'keys.cfg'
CONFIG_FILE = os.path.realpath(CONFIG_FILENAME)

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

consumer_key = config.get('keys', 'consumer_key')
consumer_secret = config.get('keys', 'consumer_secret')

mwoauth = MWOAuth(consumer_key=consumer_key, consumer_secret=consumer_secret)
app.register_blueprint(mwoauth.bp)

commons = mwclient.Site('commons.wikimedia.org')

IMAGE_WIDTH = 300
IMAGE_HEIGHT = 200

COMMONS_QI_CATEGORY = 'Category:Quality images'
COMMONS_FP_CATEGORY = 'Category:Featured pictures on Wikimedia Commons'
COMMONS_VI_CATEGORY = 'Category:Valued images sorted by promotion date'
SUPPORTED_CATEGORIES = [
    u'Category:Supported by Wikimedia AU‎',
    u'Category:Supported by Wikimedia CH‎',
    u'Category:Supported by Wikimedia Deutschland‎',
    u'Category:Supported by Wikimedia France',
    u'Category:Supported by Wikimedia Italia‎',
    u'Category:Supported by Wikimedia UK',
    u'Category:Supported by Wikimedia Österreich‎ ',
    u'Category:Media supported by Wikimedia France',
    u'Images uploaded by Fæ'
]

GLOBALUSAGE_URL = u"https://commons.wikimedia.org/w/api.php?action=query&prop=globalusage&format=json&titles="

IMAGES = json.loads(open("images.json").read())

g = {}
CURRENT_GALLERY = ""
CURRENT_CATEGORY = ""
TEST_NAME = "User:Léna/Visual"

def number_of_usages(image):
    r = requests.get(GLOBALUSAGE_URL + image.title()).json()
    if ("query" in r and "pages" in r["query"]):
        dict = r["query"]["pages"]
        keys = [k for k in dict]
        if "globalusage" in dict[keys[0]]:
            return len(dict[keys[0]]["globalusage"])
        else:
            return 0
    else:
        return 0

def compute_criteria(image, with_usage):
    # Init
    img = image.title()
    if img not in IMAGES:
        IMAGES[img] = {}
    # Google
    if "Google" not in IMAGES[img]:
        IMAGES[img]["Google"] = "Google" in img
    # Usage
    if with_usage and "Usage" not in IMAGES[img]:
        IMAGES[img]["Usage"] = number_of_usages(image)
    # QI/VI/FP and partnership
    if "Featured" not in IMAGES[img]:
        IMAGES[img]["Featured"] = False
        IMAGES[img]["Valued"] = False
        IMAGES[img]["Quality"] = False
        IMAGES[img]["Partnership"] = False
        for category in image.categories():
            IMAGES[img]["Featured"] = IMAGES[img]["Featured"] or category.title() == COMMONS_FP_CATEGORY
            IMAGES[img]["Valued"] = IMAGES[img]["Valued"] or category.title() == COMMONS_VI_CATEGORY
            IMAGES[img]["Quality"] = IMAGES[img]["Quality"] or category.title() == COMMONS_QI_CATEGORY
            IMAGES[img]["Partnership"] = IMAGES[img]["Partnership"] or category.title() in SUPPORTED_CATEGORIES
    return IMAGES[img]


def images_of(category_name):
    category = commons.Categories(category_name)
    return [img for img in category if img.namespace == 6]


def xor(b1, b2):
    return (b1 and not b2) or (b2 and not b1)


def with_label(c):
    return c["Featured"] or c["Valued"] or c["Quality"]


def compare_criteria(c1, c2, with_usage):
    if xor(c1["Google"], c2["Google"]):
        return c2["Google"]
    if xor(with_label(c1), with_label(c2)):
        return with_label(c2)
    if xor(c1["Partnership"], c2["Partnership"]):
        return c2["Partnership"]
    if with_usage:
        return c1["Usage"] < c2["Usage"]
    return False


def best_image(category, with_usage):
    images = images_of(category)
    if len(images) == 0:
        return None
    # Initiatization
    best_image = images[0]
    best_criteria = compute_criteria(images[0], with_usage)
    # Finding the best
    for image in images:
        current_criteria = compute_criteria(image, with_usage)
        if compare_criteria(best_criteria, current_criteria, with_usage):
            best_criteria = current_criteria
            best_image = image
    return best_image


def generated_code(category_name, with_usage, width=True):
    image = best_image(category_name, with_usage)
    with open("images.json", "w") as file:
        data = json.dumps(IMAGES, indent=2)
        file.write(data)
    if image is None:
        return None
    elif width:
        return {
            "Title": image.title(),
            "Image": image.get_file_url(url_width=IMAGE_WIDTH),
            "URL": image.full_url(),
            "debug": IMAGES
        }
    else:
        return {
            "Title":  image.title(),
            "Image": image.get_file_url(url_height=IMAGE_HEIGHT),
            "URL": image.full_url()
        }


def subcategories(category_name, flattening=False):
    if flattening:
        result = []
        for category in commons.Categories[category_name]:
            if category.namespace == 12:
                subs = [cat for cat in category if cat.namespace == 12]
                if len(subs) == 0:
                    result.append(category)
                else:
                    for subcategory in subs:
                        result.append(subcategory)
        return result
    else:
        content = [p for p in commons.Categories[category_name]]
        print(content)
        return [p for p in content if p.namespace == 12]


def generate_gallery(category_name, with_usage=True, flattening=False):
    HTML_gallery = ""
    WIKI_gallery = "<gallery mode=\"packed\">"
    categories = subcategories(category_name, flattening)
    if len(categories) == 0:
        # Feedback when there are no sub categories
        HTML_gallery = '<p>No subcategory in {}</p>'.format(category_name)
    for category in categories:
        code = generated_code(category.title(), with_usage, False)
        if code:  # generated_code may return None value
            HTML_gallery = HTML_gallery + "<img src=\"" + code["Image"] + "\" height=\"" + str(IMAGE_HEIGHT) + "\">"
            WIKI_gallery = WIKI_gallery + "\n" + code["Title"] + "|[[:" + category.title() + "|" + category.title()[9:] + "]]"
    WIKI_gallery = WIKI_gallery + "\n</gallery>"
    CURRENT_GALLERY = WIKI_gallery
    CURRENT_CATEGORY = category_name
    return [Markup(HTML_gallery), WIKI_gallery]

def upload(g):
    print("upload")
    p = commons.Pages["User:Léna/mwclient"]
    text = g["WIKI"]+ p.edit()
    p.save(text, summary='Visual category')

# @app.route('/', methods=['GET', 'POST'])
# def index():
#    s = {}
#    s.username = repr(mwoauth.get_current_user(False))
#    return render_template('view_index.html', **s)

@app.route("/")
def index():
    username = repr(mwoauth.get_current_user(False))
    return "logged in as: " + username + "<br>" + \
"<a href=login>login</a> / <a href=logout>logout</a>"

@app.route("/test")
def insert():
    token_req = ast.literal_eval(mwoauth.request({'action': 'query',
                                 'titles': 'Project:Sandbox',
                                 'prop': 'info',
                                 'intoken': 'edit'
                                 }))
    print("\n")
    print(token_req['query']['pages'])
    print("\n")
    keys = [k for k in token_req['query']['pages']]
    pageid = keys[0]
    token = token_req['query']['pages'][pageid]['edittoken']
    test = mwoauth.request({'action': 'edit',
                            'title': 'Project:Sandbox',
                            'summary': 'test summary',
                            'text': 'article content',
                            'token': token})
    return "Done!"


@app.route('/gallery', methods=['GET', 'POST'])
def gallery():
    g = {'category_name': '', 'code_generated': '', 'with_usage': True}
    if request.method == 'POST':
        g['category_name'] = request.form['category']
        g['with_usage'] = "with_usage" in request.form
        g['flattening'] = "flattening" in request.form
        generated = generate_gallery(g['category_name'], g['with_usage'], g['flattening'])
        g['HTML'] = generated[0]
        g['WIKI'] = generated[1]
        if "upload" in request.form:
            upload(g)
    else:
        # GET
        pass
    return render_template('view_gallery.html', **g)


@app.route('/image', methods=['GET', 'POST'])
def image():
    gallery = {'category_name': '', 'code_generated': '', 'with_usage': True}
    if request.method == 'POST':
        gallery['category_name'] = request.form['category']
        gallery['with_usage'] = "with_usage" in request.form
        generated = generated_code(gallery['category_name'], gallery['with_usage'])
        gallery['image_name'] = generated['Title']
        gallery['image_url'] = generated['Image']
        gallery['file_url'] = generated['URL']
        gallery['debug'] = generated['debug']
    else:
        # GET
        pass
    print("render_template")
    return render_template('view_image.html', **gallery)


@app.route('/json', methods=['GET'])
def json_endpoint():
    """Serve the JSON file.

    If request is used with ?fmt=html, the response is returned to be pretty print in HTML
    Otherwise just sends the content of the JSON file.
    """
    response = ''
    if request.method == 'GET':
        with open('images.json', mode='r') as f:
            images = json.loads(f.read())
            json_content = json.dumps(images, indent=4)
            if request.args.get('fmt', '') == 'html':
                response = '<pre>{}</pre>'.format(json_content)
            else:
                response = json_content
    else:
        # Method not allowed
        abort(405)
    return response


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=4242)
