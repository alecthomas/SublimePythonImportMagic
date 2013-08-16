from __future__ import absolute_import

import ast
from textwrap import dedent

from symbols import UnknownSymbolVisitor, extract_unresolved_symbols, _symbol_series


def test_parser_symbol_in_global_function():
    src = dedent('''
        import posixpath
        import os as thisos

        class Class(object):
            def foo(self):
                print self.bar

        def basename_no_ext(filename, default=1):
            def inner():
                print basename

            basename, _ = os.path.splitext(os.path.basename(filename))
            moo = 10
            inner()

            with open('foo') as fd:
                print fd.read()

            try:
                print 'foo'
            except Exception as e:
                print e

        basename_no_ext(sys.path)

        for path in sys.path:
            print path

        sys.path[0] = 10

        moo = lambda a: True

        comp = [p for p in sys.path]

        sys.path[10] = 2

        posixpath.join(['a', 'b'])


        ''')
    symbols = extract_unresolved_symbols(src)
    assert symbols == set(['sys.path', 'os.path.splitext'])


def test_deep_package_reference_with_function_call():
    src = dedent('''
        print os.path.dirname('src/python')
        ''')
    symbols = extract_unresolved_symbols(src)
    assert symbols == set(['os.path.dirname'])


def test_deep_package_reference_with_subscript():
    src = dedent('''
        print sys.path[0]
        ''')
    symbols = extract_unresolved_symbols(src)
    assert symbols == set(['sys.path'])


def test_parser_class_methods_namespace_correctly():
    src = dedent('''
        class Class(object):
            def __init__(self):
                self.value = 1
                get_value()  # Should be unresolved

            def get_value(self):
                return self.value

            def set_value(self, value):
                self.value = value

            setter = set_value  # Should be resolved
        ''')
    symbols = extract_unresolved_symbols(src)
    assert symbols == set(['get_value'])


def test_path_from_node_function():
    src = dedent('''
        os.path.basename('foo/bar').tolower()
        ''')
    st = ast.parse(src)
    visitor = UnknownSymbolVisitor()
    assert visitor._path_from_node(st.body[0].value) == 'os.path.basename'


def test_path_from_node_subscript():
    src = dedent('''
        sys.path[0].tolower()
        ''')
    st = ast.parse(src)
    print ast.dump(st)
    visitor = UnknownSymbolVisitor()
    assert visitor._path_from_node(st.body[0].value) == 'sys.path'


def test_symbol_series():
    assert _symbol_series('os.path.basename') == ['os', 'os.path', 'os.path.basename']
