from __future__ import absolute_import
from textwrap import dedent

from index import index_source, SymbolIndex


def test_index_file_with_all():
    src = dedent('''
        __all__ = ['one']

        one = 1
        two = 2
        three = 3
        ''')
    tree = SymbolIndex()
    with tree.enter('test') as subtree:
        index_source(subtree, 'test.py', src)
    assert subtree.serialize() == '{\n  "one": 1.0\n}'


def test_index_if_name_main():
    src = dedent('''
        if __name__ == '__main__':
            one = 1
        else:
            two = 2
        ''')
    tree = SymbolIndex()
    with tree.enter('test') as subtree:
        index_source(subtree, 'test.py', src)
    assert subtree.serialize() == '{}'


def test_index_symbol_scores():
    src = dedent('''
        path = []

        def walk(dir): pass
        ''')
    tree = SymbolIndex()
    with tree.enter('os') as subtree:
        index_source(subtree, 'os.py', src)
    assert tree.symbol_scores('walk') == [(0.9, 'os')]
    assert tree.symbol_scores('os') == [(1.0, '')]
