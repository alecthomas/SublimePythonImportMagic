import os
import sys

from importer import extract_unresolved_symbols
from indexer import build_index, SymbolTree


if __name__ == '__main__':
    if os.path.exists('index.json'):
        with open('index.json') as fd:
            tree = SymbolTree.deserialize(fd)
    else:
        tree = SymbolTree()
        build_index(tree, sys.path)
        with open('index.json', 'w') as fd:
            fd.write(tree.serialize())

    for filename in sys.argv:
        with open(filename) as fd:
            src = fd.read()
            print filename
            print extract_unresolved_symbols(src)
