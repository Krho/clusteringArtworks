# clusteringArtworks

Finds different files of the same artwork in Wikimedia Commons on stores them in the same category

# Algorithm

Uses sklearn library with affinity propagation.

The coordinates in the space are the categories of the files in the category (1 if the file is in the category, 0 if it is not) and also of the parents' categories.

For instance, if file1 is in Category A, of parents Category B and Category D, and file2 is in Category B of parents Category C, the coordinates are:
file1: {1, 1, 0, 1}
file2: {0, 1, 1, 0}

We use parent categories to catch the incertitude and incompleteness of the Wikimedia Commons category system.
