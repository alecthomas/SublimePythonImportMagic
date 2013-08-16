from __future__ import absolute_import
import ast
from textwrap import dedent

from importer import ImportFinder, Imports


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
