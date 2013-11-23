from __future__ import absolute_import
import ast
from textwrap import dedent
from .importer import Imports, update_imports
from .symbols import extract_unresolved_symbols


def test_update_imports_inserts_initial_imports(index):
    src = dedent("""
        print os.path.basename("sys/foo")
        print sys.path[0]
        """).strip()
    st = ast.parse(src)
    symbols = extract_unresolved_symbols(st)
    assert symbols == set(['os.path.basename', 'sys.path'])
    new_src = update_imports(src, symbols, index)
    assert dedent("""
        import os.path
        import sys


        print os.path.basename("sys/foo")
        print sys.path[0]
        """).strip() == new_src


def test_update_imports_inserts_imports(index):
    src = dedent("""
        import sys

        print os.path.basename("sys/foo")
        print sys.path[0]
        """).strip()
    st = ast.parse(src)
    symbols = extract_unresolved_symbols(st)
    assert symbols == set(['os.path.basename'])
    new_src = update_imports(src, symbols, index)
    assert dedent("""
        import os.path
        import sys


        print os.path.basename("sys/foo")
        print sys.path[0]
        """).strip() == new_src


def test_update_imports_correctly_aliases(index):
    src = dedent('''
        print basename('src/foo')
        ''').strip()
    symbols = extract_unresolved_symbols(src)
    assert symbols == set(['basename'])
    new_src = update_imports(src, symbols, index)
    assert dedent('''
        from os.path import basename


        print basename('src/foo')
        ''').strip() == new_src


def test_parse_imports():
    src = dedent('''
        import os, sys as sys
        import sys as sys
        from os.path import basename

        from os import (
            path,
            posixpath
            )

        def main():
            pass
        ''').strip()
    imports = Imports(src)
    new_src = imports.update_source()
    assert dedent(r'''
        import os
        import sys
        from os import path, posixpath
        from os.path import basename


        def main():
            pass
        ''').strip() == new_src
