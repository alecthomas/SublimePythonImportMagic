from textwrap import dedent

from importer import extract_unresolved_symbols


def test_importer_symbol_in_global_function():
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

        sys.path, os.path = [], []

        sys.path[0] = 10

        moo = lambda a: True

        comp = [p for p in sys.path]

        sys.path()[10] = 2

        posixpath.join(['a', 'b'])


        ''')
    symbols = extract_unresolved_symbols(src)
    assert symbols == set(['os', 'sys'])


def test_importer_class_methods_namespace_correctly():
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
