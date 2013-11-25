from __future__ import absolute_import

from textwrap import dedent

from importmagic.importer import Imports, update_imports
from importmagic.symbols import extract_unresolved_symbols


def test_deep_import(index):
    src = dedent("""
        print os.walk('/')
         """)
    symbols = extract_unresolved_symbols(src)
    assert symbols == set(['os.walk'])
    new_src = update_imports(src, symbols, index)
    assert dedent("""
        import os

        print os.walk('/')
        """).strip() == new_src


def test_update_imports_inserts_initial_imports(index):
    src = dedent("""
        print os.path.basename('sys/foo')
        print sys.path[0]
        print basename('sys/foo')
        print path.basename('sys/foo')
        """).strip()
    symbols = extract_unresolved_symbols(src)
    assert symbols == set(['os.path.basename', 'sys.path', 'basename', 'path.basename'])
    new_src = update_imports(src, symbols, index)
    assert dedent("""
        import os.path
        import sys
        from os import path
        from os.path import basename


        print os.path.basename('sys/foo')
        print sys.path[0]
        print basename('sys/foo')
        print path.basename('sys/foo')
        """).strip() == new_src


def test_update_imports_inserts_imports(index):
    src = dedent("""
        import sys

        print os.path.basename("sys/foo")
        print sys.path[0]
        """).strip()
    symbols = extract_unresolved_symbols(src)
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


def test_parse_imports(index):
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
    imports = Imports(index, src)
    new_src = imports.update_source()
    assert dedent(r'''
        import os
        import sys
        from os import path, posixpath
        from os.path import basename


        def main():
            pass
        ''').strip() == new_src
