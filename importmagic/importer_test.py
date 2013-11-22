from __future__ import absolute_import
import ast
from textwrap import dedent

from .importer import ImportFinder, Imports, update_imports
from .symbols import extract_unresolved_symbols


def test_import_finder():
    src = dedent('''
        # A comment

        from sys import path, moo
        from sys import path as syspath
        import os
        import sys as system

        def func():
            pass
        ''').strip()
    tree = ast.parse(src)
    imports = Imports()
    visitor = ImportFinder(imports)
    visitor.visit(tree)
    expected_imports = [
        'import os',
        'import sys as system',
        'from sys import path, moo, path as syspath',
        ]
    assert imports.imports_as_source() == expected_imports
    expected_src = dedent('''
        # A comment

        import os
        import sys as system
        from sys import path, moo, path as syspath

        def func():
            pass
        ''').strip()
    print imports.replace_imports(src)
    assert imports.replace_imports(src) == expected_src


def test_update_imports_inserts_initial_imports(index):
    src = dedent("""
        print os.path.basename("sys/foo")
        print sys.path[0]
        """).strip()
    st = ast.parse(src)
    symbols = extract_unresolved_symbols(st)
    assert symbols == set(['os.path.basename', 'sys.path'])
    assert update_imports(src, st, symbols, index) == dedent("""
        import os.path
        import sys


        print os.path.basename("sys/foo")
        print sys.path[0]
        """).strip()


def test_update_imports_inserts_imports(index):
    src = dedent("""
        import sys

        print os.path.basename("sys/foo")
        print sys.path[0]
        """).strip()
    st = ast.parse(src)
    symbols = extract_unresolved_symbols(st)
    assert symbols == set(['os.path.basename'])
    new_src = update_imports(src, st, symbols, index)
    assert new_src == dedent("""
        import os.path
        import sys

        print os.path.basename("sys/foo")
        print sys.path[0]
        """).strip()


def test_update_imports_correctly_aliases(index):
    src = dedent('''
        print basename('src/foo')
        ''').strip()
    st = ast.parse(src)
    symbols = extract_unresolved_symbols(src)
    assert symbols == set(['basename'])
    new_src = update_imports(src, st, symbols, index)
    assert new_src == dedent('''
        from os.path import basename


        print basename('src/foo')
        ''').strip()
