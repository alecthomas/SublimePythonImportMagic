import re
import json
import ast
import os
import sys
from contextlib import contextmanager


__all__ = ['JSONEncoder', 'BLACK_LIST_RE', 'SymbolTree']


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, SymbolTree):
            return o._tree
        return super(JSONEncoder, self).default(o)


BLACK_LIST_RE = re.compile(r'test', re.I)


class SymbolTree(object):
    def __init__(self, name=None, parent=None):
        self._name = name
        self._tree = {}
        self._parent = parent

    def depth(self):
        depth = 0
        node = self
        while node._parent:
            depth += 1
            node = node._parent
        return depth

    def path(self):
        path = []
        node = self
        while node and node._name:
            path.append(node._name)
            node = node._parent
        return '.'.join(reversed(path))

    def add(self, name, score):
        current_score = self._tree.get(name, 0.0)
        if score > current_score:
            self._tree[name] = score

    @contextmanager
    def enter(self, name):
        if name is None:
            tree = self
        else:
            # print '%s%s' % ('  ' * self.depth(), name)
            tree = self._tree.get(name)
            if not isinstance(tree, SymbolTree):
                tree = self._tree[name] = SymbolTree(name, self)
        yield tree

    @classmethod
    def deserialize(self, file):
        def load(tree, data):
            for key, value in data.items():
                if isinstance(value, dict):
                    with tree.enter(key) as subtree:
                        load(subtree, value)
                else:
                    tree.add(key, value)

        data = json.load(file)
        tree = SymbolTree()
        load(tree, data)
        return tree

    def serialize(self):
        return json.dumps(self, indent=2, cls=JSONEncoder)

    def __repr__(self):
        return repr(self._tree)


class SymbolVisitor(ast.NodeVisitor):
    def __init__(self, tree):
        self._tree = tree

    def visit_ImportFrom(self, node):
        for name in node.names:
            if name.name == '*' or name.name.startswith('_'):
                continue
            self._tree.add(name.name, 0.5)

    def visit_Import(self, node):
        for name in node.names:
            if name.name.startswith('_'):
                continue
            self._tree.add(name.name, 0.5)

    def visit_ClassDef(self, node):
        if not node.name.startswith('_'):
            self._tree.add(node.name, 1.0)

    def visit_FunctionDef(self, node):
        if not node.name.startswith('_'):
            self._tree.add(node.name, 1.0)

    def visit_Assign(self, node):
        # TODO: Handle __all__
        is_name = lambda n: isinstance(n, ast.Name)
        for name in filter(is_name, node.targets):
            if name.id == '__all__' and isinstance(node.value, ast.List):
                for subnode in node.value.elts:
                    self._tree.add(subnode.s, 1.0)
            elif not name.id.startswith('_'):
                self._tree.add(name.id, 1.0)


def index_file(module, tree, filename):
    if BLACK_LIST_RE.search(filename):
        return
    with tree.enter(module) as subtree:
        with open(filename) as fd:
            try:
                st = ast.parse(fd.read(), filename)
            except Exception as e:
                print 'Failed to parse %s: %s' % (filename, e)
                return
            visitor = SymbolVisitor(subtree)
            visitor.visit(st)


def index_path(tree, root):
    """Index a path.

    :param root: Either a package directory or a .py module.
    """
    if os.path.isfile(root) and root.endswith('.py'):
        basename, ext = os.path.splitext(os.path.basename(root))
        if basename == '__init__':
            basename = None
        index_file(basename, tree, root)
    elif os.path.isdir(root) and os.path.exists(os.path.join(root, '__init__.py')):
        basename = os.path.basename(root)
        with tree.enter(basename) as subtree:
            for filename in os.listdir(root):
                index_path(subtree, os.path.join(root, filename))


def build_index(tree, paths):
    for path in paths:
        if os.path.isdir(path):
            for filename in os.listdir(path):
                filename = os.path.join(path, filename)
                index_path(tree, filename)


if __name__ == '__main__':
    # print ast.dump(ast.parse(open('pyautoimp.py').read(), 'pyautoimp.py'))
    tree = SymbolTree()
    build_index(tree, sys.path)
    print
