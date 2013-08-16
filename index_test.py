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
        def walk(dir): pass
        ''')
    tree = SymbolIndex()
    with tree.enter('os') as os_tree:
        with os_tree.enter('path') as path_tree:
            index_source(path_tree, 'os.py', src)
    assert tree.symbol_scores('walk') == [(0.8, 'os.path')]
    assert tree.symbol_scores('os') == [(1.0, 'os')]
    assert tree.symbol_scores('os.path.walk') == [(3.0, 'os.path')]


def test_index_score_deep_reference(index):
    assert index.symbol_scores('os.path.basename')[0] == (3.0, 'os.path')


def test_index_score_simulated_sys(index):
    index.symbol_scores('sys.path')[0] == (2.0, 'sys.path')


def test_encoding_score(index):
    assert index.symbol_scores('iso8859_6.Codec')[0] == (1.8, 'encodings.iso8859_6')
