# -*- coding: utf-8 -*-
import io
import os
import re
import ast
import sys
import json
import uuid
import logging
import pywikibot
import mwclient
from pywikibot import page
from sklearn import metrics
from sklearn.cluster import AffinityPropagation
from sklearn.datasets import load_svmlight_file
from sklearn.metrics import pairwise
from flask import (abort, Flask, render_template, request, Markup)
from flask_mwoauth import MWOAuth

#Properties
catalog = "P528"
inventory = "P217"
commonsCat = "P373"
imageProperty = "P18"
depict = "P180"
creator = "P170"

app = Flask(__name__)
app.secret_key = os.urandom(24)

LOG =  logging.getLogger(name=__name__)
HANDLER = logging.StreamHandler(stream=sys.stdout)
HANDLER.setFormatter(logging.Formatter('%(asctime)s    %(module)s    %(levelname)s    %(message)s'))
HANDLER.setLevel(logging.DEBUG)
LOG.addHandler(HANDLER)
LOG.setLevel(logging.DEBUG)

cache = json.loads(open("dump.json").read())

COMMONS = pywikibot.Site('commons', 'commons')
FILE_NAMESPACE = 6
wikidata = pywikibot.Site("wikidata", "wikidata")
repo = wikidata.data_repository()

IMAGE_HEIGHT = 120

categories_tree = json.loads(open("categories1.json").read())

idMap = {}
result = {}
descrDict = {"fr":u"Peinture","en":u"Painting"}
allImages = []

def clean_image(image, title, removeList):
    t = image.text
    for r in removeList:
        pattern = re.compile("\[\["+r+"(\|(\w|>)+)?\]\]")
        s = re.search(pattern, t)
        if s is not None:
            t = t.replace(s.group(0),"")
    t = t+"\n[[Category:"+title+"]]"
    image.text = t
    image.save("#FileToCat Image in its own category")

def creator_of(category):
    try:
        creator = category.members(namespaces=CREATOR_NAMESPACE).next()
        if re.search(itemExpression, creator.text) is not None:
            return re.search(itemExpression, creator.text).group(0)
        else:
            return None
    except StopIteration:
        return None

def creators_of(category_name):
    category = pywikibot.Category(commons, category_name)
    for subcat in category.subcategories():
        item = creator_of(subcat)
        if item is not None:
            dict_creator[subcat.title()]={
            u"Properties":{"P170":{"Value":item.title()}},
            "Parents":[category_name]}
        else:
            missing.append(subcat.title())
    with open ("creators.json", "w") as data:
        json.dump(dict_creator, data, indent=2, ensure_ascii=False)
    with open ("missing.json", "w") as data:
        json.dump({"Missing":missing},data, indent=2, ensure_ascii=False)

def categories(p, height=0):
    if p not in categories_tree or "Parents" not in categories_tree[p]:
        categories_tree[p]={"Parents":[c.title() for c in page.Page(COMMONS, p).categories()]}
    cats = set(categories_tree[p]["Parents"])
    if height is 0:
        return cats
    else:
        temp = set(cats)
        for cat in cats:
            temp |= categories(cat,height-1)
        return temp

def gathering(category_name, height):
    category_set = set([])
    files = [f for f in page.Category(COMMONS, category_name).members(namespaces=FILE_NAMESPACE)]
    allImages = [f.title() for f in files]
    LOG.info(u"Examining %s", category_name)
    for file in files:
        LOG.info(u'gathering %s', file.title())
        if file.title() not in categories_tree:
            categories_tree[file.title()]=list(categories(file.title(), height))
        category_set |= set(categories_tree[file.title()])
    stringBuffer = []
    categories_tree["files"]={}
    categories_tree["categories"]={}
    for j,file in enumerate(page.Category(COMMONS, category_name).members(namespaces=FILE_NAMESPACE)):
        categories_tree["files"][j]=file.title()
        stringBuffer.append("\n")
        stringBuffer.append(str(j))
        for i,category in enumerate(category_set):
            categories_tree["categories"][i]=category.title()
            stringBuffer.append(" ")
            stringBuffer.append(str(i))
            stringBuffer.append(":")
            stringBuffer.append(str(int(category in categories_tree[file.title()])))
    LOG.info(u"Storing categories")
    with open("categories1.json", "w") as file:
        data = json.dumps(categories_tree, indent=2)
        file.write(data)
    LOG.info(u"Storing datapoints")
    file = io.open(category_name+"-"+str(height)+".txt", mode="w", encoding="utf-8")
    file.write(u"".join(stringBuffer))
    return allImages

def label(item):
    title=""
    if u"en" in item.labels:
        title = item.labels["en"]
    elif u"fr" in item.labels:
        title = item.labels["fr"]
    if catalog in item.claims:
        if item.claims[catalog][0].target is not None:
            title = title+" ("+item.claims[catalog][0].target+")"
        elif item.claims[catalog][1].target is not None:
            title = title+" ("+item.claims[catalog][1].target+")"
    elif inventory in item.claims:
        title = title+" ("+item.claims[inventory][0].target+")"
    elif creator in item.claims:
        itemAuthor = item.claims[creator][0].target
        itemAuthor.get()
        title = title+" ("+itemAuthor.labels["en"]+")"
    return title

def print_category(item, title, addList, objectCat=True):
    if title is not "":
        result = ""
        if item is not "" and objectCat:
            result = "{{Wikidata Infobox|qid="+item+"}}"
        category = pywikibot.Category(COMMONS, title)
        for add in addList:
            result = result+"\n[["+add+"]]"
        category.text = result
        category.save("#FileToCat Category creation")

def clustering(category_name, height):
    X, labels_true = load_svmlight_file(category_name+"-"+str(height)+".txt")
    af = AffinityPropagation(preference=-50,affinity="euclidean").fit(X)
    cluster_centers_indices = af.cluster_centers_indices_
    labels = af.labels_
    n_clusters_ = len(cluster_centers_indices)
    LOG.info('Estimated number of clusters: %d' % n_clusters_)
    LOG.info("Homogeneity: %0.3f" % metrics.homogeneity_score(labels_true, labels))
    LOG.info("Completeness: %0.3f" % metrics.completeness_score(labels_true, labels))
    LOG.info("V-measure: %0.3f" % metrics.v_measure_score(labels_true, labels))
    LOG.info("Adjusted Rand Index: %0.3f" % metrics.adjusted_rand_score(labels_true, labels))
    LOG.info("Adjusted Mutual Information: %0.3f" % metrics.adjusted_mutual_info_score(labels_true, labels))
    # Reversing
    temp={}
    for i,label in enumerate(labels):
        if label not in temp:
            temp[label]=[i]
        else:
            temp[label].append(i)
    clusters=[]
    for key in temp:
        if len(temp[key]) > 1: #Actual cluster
            try:
                clusters.append([categories_tree["files"][i] for i in temp[key]])
            except KeyError as e:
                LOG.error("unable to create cluster %s \n %s" % (key,temp[key]))
                if "files" in categories_tree:
                    for i in temp[key]:
                        if i not in categories_tree["files"]:
                            LOG.error("%d not found" % i)
    return clusters

def visualize(category_name, clusters):
    test_page=page.Page(COMMONS, "User:Donna Nobot/clusterArtworks")
    stringBuffer=[test_page.text]
    stringBuffer.append("\n\n== [[:Category:")
    stringBuffer.append(category_name)
    stringBuffer.append("|")
    stringBuffer.append(category_name)
    stringBuffer.append("]] ==\n")
    for cluster in clusters:
        stringBuffer.append("<gallery mode=\"packed\">\n")
        for file in cluster:
            stringBuffer.append(file)
            stringBuffer.append("\n")
        stringBuffer.append("</gallery>\n\n")
    test_page.put("".join(stringBuffer), "#clusterArworks")

def imageOf(fileName):
    file = pywikibot.FilePage(COMMONS, fileName)
    uid = str(uuid.uuid4())
    idMap[uid]=fileName
    idMap[fileName]=uid
    return {'url':file.get_file_url(url_height=IMAGE_HEIGHT),'id':uid}

def imagesOf(clusters, allImages):
    result = []
    for i,cluster in enumerate(clusters):
        uid = str(uuid.uuid4())
        idMap[uid]=i
        idMap[i]=uid
        result.append({'id':uid,'images':[imageOf(fileName) for fileName in cluster]})
        allImages = [img for img in allImages if img not in cluster]
    return result, allImages

def hidden(category):
    return "Category:Hidden categories" in [c.title() for c in category.categories()]

def fusion_cat(images,qitem="", cat_name="", label_dict={}, descr_dict=descrDict, objectCat=True, createCat=True):
    categories=set([])
    img = None
    item = None
    for image in images:
        img = image.title()[5:]
        for cat in image.categories():
            if createCat:
                if not hidden(cat):
                    categories.add(cat.title())
            elif not hidden(cat):
                for parent in cat.categories():
                        categories.add(parent.title())
    if qitem is not "":
        item = pywikibot.ItemPage(repo,qitem)
        item.get()
    else:
        item = pywikibot.ItemPage(wikidata)
        item.editLabels(label_dict, summary="#Commons2Data label")
        item.editDescriptions(descr_dict, summary="#Commons2Data description")
        item.get()
    for cat in categories:
        if cat in cache:
            for p in cache[cat][u"Properties"]:
                LOG.info("Examining property "+p)
                if p not in item.claims:
                    claim = pywikibot.Claim(repo, p)
                    if u"Value" in cache[cat][u"Properties"][p]:
                        LOG.info("Adding value "+cache[cat][u"Properties"][p]["Value"])
                        if "Q" in cache[cat][u"Properties"][p]["Value"]:
                            claim.setTarget(pywikibot.ItemPage(repo,cache[cat][u"Properties"][p]["Value"]))
                        else:
                            claim.setTarget(pywikibot.WbTime(year=cache[cat][u"Properties"][p]["Value"]["Year"]))
                        item.addClaim(claim, summary=u'#Commons2Data adding claim')
    title = cat_name
    if title is "":
        title = label(item)
    if title is "":
        title = re.split("\.|:",images[0].title())[1]
    if createCat:
        print_category(item.title(), title, [c for c in categories],objectCat)
        for image in images:
            clean_image(image, title, [c for c in categories])
    # Wikidata
    if imageProperty not in item.claims:
        claim = pywikibot.Claim(repo, imageProperty)
        claim.setTarget(pywikibot.FilePage(COMMONS,img))
        item.addClaim(claim, summary=u"Commons2Data image")
    category = pywikibot.Category(COMMONS, title)
    item.setSitelink(category, summary="#FileToCat Commons sitelink.")
    claim = pywikibot.Claim(repo, commonsCat)
    claim.setTarget(title)
    item.addClaim(claim, summary="#FileToCat Commons claim")

@app.route('/update')
def update():
    LOG.info("updating Wikimedia projects")
    data = request.args.get('data', 0, type=str)
    d = ast.literal_eval(data)
    for cluster in d:
        if cluster["id"] is not "unclustered" and len(cluster["images"]) > 0:
            cluster["images"] = [idMap[img] for img in cluster["images"]]
            fusion_cat([page.Page(COMMONS, img) for img in cluster["images"]])
    return render_template('result.html', **result)


@app.route('/load', methods=['GET', 'POST'])
def show():
    height=1
    LOG.info("Loading")
    categoryName = request.args['category']
    LOG.info(categoryName)
    if categoryName:
        allImages = gathering(categoryName, height)
        clusters = clustering(categoryName, height)
        images, remainings = imagesOf(clusters, allImages)
        result["clusters"]=images
        result["category"]=categoryName
        if categoryName in cache:
            result["common"]=categoryName
        result["remainings"]={'id':"unclustered",'images':[imageOf(fileName) for fileName in remainings]}
        LOG.info(result)
    LOG.info("Loaded")
    return render_template('dragdrop.html', **result)

@app.route('/', methods=['GET', 'POST'])
def basic():
    return render_template('load.html', **result)

def main():
    category_name = "Portrait paintings of women holding flower baskets"
    height=1
    if len(sys.argv) > 1:
        category_name = sys.argv[1]
    gathering(category_name, height)
    clusters = clustering(category_name, height)
    visualize(category_name, clusters)
