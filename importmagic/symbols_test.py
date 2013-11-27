import ast
from textwrap import dedent

from importmagic.symbols import Scope, UnknownSymbolVisitor, _symbol_series


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
    symbols, _ = Scope.from_source(src).find_unresolved_and_unreferenced_symbols()
    assert symbols == set(['sys.path', 'os.path.splitext', 'os.path.basename'])


def test_deep_package_reference_with_function_call():
    src = dedent('''
        print os.path.dirname('src/python')
        ''')
    symbols, _ = Scope.from_source(src).find_unresolved_and_unreferenced_symbols()
    assert symbols == set(['os.path.dirname'])


def test_deep_package_reference_with_subscript():
    src = dedent('''
        print sys.path[0]
        ''')
    symbols, _ = Scope.from_source(src).find_unresolved_and_unreferenced_symbols()
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
    symbols, _ = Scope.from_source(src).find_unresolved_and_unreferenced_symbols()
    assert symbols == set(['get_value'])


def test_path_from_node_function():
    src = dedent('''
        os.path.basename('foo/bar').tolower()
        ''')
    st = ast.parse(src)
    visitor = UnknownSymbolVisitor()
    assert visitor._paths_from_node(st.body[0].value) == ['os.path.basename']


def test_path_from_node_subscript():
    src = dedent('''
        sys.path[0].tolower()
        ''')
    st = ast.parse(src)
    visitor = UnknownSymbolVisitor()
    assert visitor._paths_from_node(st.body[0].value) == ['sys.path']


def test_symbol_series():
    assert _symbol_series('os.path.basename') == ['os', 'os.path', 'os.path.basename']


def test_symbol_from_nested_tuples():
    src = dedent("""
        a = (os, (os.path, sys))
        """)
    symbols, _ = Scope.from_source(src).find_unresolved_and_unreferenced_symbols()
    assert symbols == set(['os', 'os.path', 'sys'])


def test_symbol_from_decorator():
    src = dedent("""
        @foo.bar(a=waz)
        def bar(): pass
        """)
    symbols, _ = Scope.from_source(src).find_unresolved_and_unreferenced_symbols()
    assert symbols == set(['foo.bar', 'waz'])


def test_find_unresolved_and_unreferenced_symbols():
    src = dedent("""
        import os
        import sys
        import urllib2
        from os.path import basename

        def f(p):
            def b():
                f = 10
                print f
            return basename(p)

        class A(object):
            etc = os.walk('/etc')

            def __init__(self):
                print sys.path, urllib.urlquote('blah')

        """).strip()
    scope = Scope.from_source(src)
    unresolved, unreferenced = scope.find_unresolved_and_unreferenced_symbols()
    assert unresolved == set(['urllib.urlquote'])
    assert unreferenced == set(['A', 'urllib2', 'f'])

