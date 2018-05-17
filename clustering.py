# -*- coding: utf-8 -*-
import io
import sys
import json
import logging
import pywikibot
from pywikibot import page
from sklearn import metrics
from sklearn.cluster import AffinityPropagation
from sklearn.datasets import load_svmlight_file
from sklearn.metrics import pairwise

LOG =  logging.getLogger(name=__name__)
HANDLER = logging.StreamHandler(stream=sys.stdout)
HANDLER.setFormatter(logging.Formatter('%(asctime)s    %(module)s    %(levelname)s    %(message)s'))
HANDLER.setLevel(logging.DEBUG)
LOG.addHandler(HANDLER)
LOG.setLevel(logging.DEBUG)

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

def gathering(category_name, height):
    category_set = set([])
    files = page.Category(COMMONS, category_name).members(namespaces=FILE_NAMESPACE)
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
                        print categories_tree["files"]
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


def main():
    category_name = "Paintings of interiors of art galleries"
    height=1
    if len(sys.argv) > 1:
        category_name = sys.argv[1]
    gathering(category_name, height)
    clusters = clustering(category_name, height)
    visualize(category_name,  clusters)


if __name__ == '__main__':
    main()
