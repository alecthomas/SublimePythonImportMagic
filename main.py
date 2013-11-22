import ast
import os
import sys

from importmagic.index import SymbolIndex
from importmagic.symbols import extract_unresolved_symbols
from importmagic.importer import update_imports


if __name__ == '__main__':
    if os.path.exists('index.json'):
        with open('index.json') as fd:
            index = SymbolIndex.deserialize(fd)
    else:
        index = SymbolIndex()
        index.build_index(sys.path)
        with open('index.json', 'w') as fd:
            fd.write(index.serialize())

    for filename in sys.argv[1:]:
        with open(filename) as fd:
            src = fd.read()
            st = ast.parse(src)
            symbols = extract_unresolved_symbols(st)
            print update_imports(src, st, symbols, index)
