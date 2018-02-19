# -*- coding: utf-8 -*-
import io
import json
import pywikibot
from pywikibot import page
from sklearn import metrics
from sklearn.cluster import AffinityPropagation
from sklearn.datasets import load_svmlight_file
from sklearn.metrics import pairwise

COMMONS = pywikibot.Site('commons', 'commons')
FILE_NAMESPACE = 6

categories_tree = json.loads(open("categories1.json").read())

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


def gathering(category_name, height=0):
    category_dictionnary={}
    category_set = set([])
    for file in page.Category(COMMONS, category_name).members(namespaces=FILE_NAMESPACE):
        print "gathering "+file.title()
        category_dictionnary[file.title()]=list(categories(file.title(), height))
        category_set |= set(category_dictionnary[file.title()])
    stringBuffer = []
    category_dictionnary["files"]={}
    category_dictionnary["categories"]={}
    for j,file in enumerate(page.Category(COMMONS, category_name).members(namespaces=FILE_NAMESPACE)):
        category_dictionnary["files"][j]=file.title()
        stringBuffer.append("\n")
        stringBuffer.append(str(j))
        for i,category in enumerate(category_set):
            category_dictionnary["categories"][i]=category.title()
            stringBuffer.append(" ")
            stringBuffer.append(str(i))
            stringBuffer.append(":")
            stringBuffer.append(str(int(category in category_dictionnary[file.title()])))
    print "Storing categories"
    print category_dictionnary
    with open("categories1.json", "w") as file:
        data = json.dumps(category_dictionnary, indent=2)
        file.write(data)
    print "Storing datapoints"
    file = io.open(category_name+"-"+str(height)+".txt", mode="w", encoding="utf-8")
    file.write(u"".join(stringBuffer))


def clustering(category_name):
    X, labels_true = load_svmlight_file("Desks in portrait paintings-1.txt")
    af = AffinityPropagation(preference=-50,affinity="euclidean").fit(X)
    cluster_centers_indices = af.cluster_centers_indices_
    labels = af.labels_
    n_clusters_ = len(cluster_centers_indices)
    print('Estimated number of clusters: %d' % n_clusters_)
    print("Homogeneity: %0.3f" % metrics.homogeneity_score(labels_true, labels))
    print("Completeness: %0.3f" % metrics.completeness_score(labels_true, labels))
    print("V-measure: %0.3f" % metrics.v_measure_score(labels_true, labels))
    print("Adjusted Rand Index: %0.3f" % metrics.adjusted_rand_score(labels_true, labels))
    print("Adjusted Mutual Information: %0.3f" % metrics.adjusted_mutual_info_score(labels_true, labels))
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
            clusters.append([categories_tree["files"][str(i)] for i in temp[key]])
    visualize(category_name, clusters)

def visualize(category_name, clusters):
    test_page=page.Page(COMMONS, "User:Donna Nobot/clusterArtworks")
    stringBuffer=["== [[:Category:"]
    stringBuffer.append(category_name)
    stringBuffer.append("|")
    stringBuffer.append(category_name)
    stringBuffer.append("]] ==\n")
    for cluster in clusters:
        stringBuffer.append("<gallery mode=\"packed\">")
        for file in cluster:
            stringBuffer.append(file)
            stringBuffer.append("\n")
        stringBuffer.append("</gallery>\n\n")
    test_page.put(test_page.text.join(stringBuffer), "#clusterArworks")

clustering("Desks in portrait paintings")
