import ast
import os
import sys

from index import build_index, SymbolIndex
from symbols import extract_unresolved_symbols
from importer import update_imports


if __name__ == '__main__':
    if os.path.exists('index.json'):
        with open('index.json') as fd:
            index = SymbolIndex.deserialize(fd)
    else:
        index = SymbolIndex()
        build_index(index, sys.path)
        with open('index.json', 'w') as fd:
            fd.write(index.serialize())

    for filename in sys.argv[1:]:
        print filename
        with open(filename) as fd:
            src = fd.read()
            st = ast.parse(src)
            symbols = extract_unresolved_symbols(st)
            if symbols:
                print update_imports(src, st, symbols, index)
