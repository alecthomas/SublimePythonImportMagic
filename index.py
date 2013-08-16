import re
import json
import ast
import os
import logging
import sys
from contextlib import contextmanager


"""Build an index of top-level symbols from Python modules and packages."""


# TODO: Update scores based on import reference frequency.
# eg. if "sys.path" is referenced more than os.path, prefer it.


logger = logging.getLogger(__name__)


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, SymbolIndex):
            return o._tree
        return super(JSONEncoder, self).default(o)


BLACK_LIST_RE = re.compile(r'test', re.I)
BUILTIN_MODULES = [
    'array', 'audioop', 'binascii', 'bsddb185', 'bz2', 'cmath',
    'cPickle', 'crypt', 'cStringIO', 'datetime', 'dbm', 'fcntl',
    'gestalt', 'grp', 'icglue', 'imageop', 'itertools', 'math', 'mmap', 'nis',
    'operator', 'parser', 'readline', 'resource', 'select',
    'strop', 'sys', 'syslog', 'termios', 'time', 'unicodedata', 'zlib',
]


class SymbolIndex(object):
    PACKAGE_ALIASES = {
        # Give os.path a score boost over posixpath and ntpath.
        'os.path': (os.path.__name__, 1.0),
    }
    _PACKAGE_ALIASES = dict((v[0], (k, v[1])) for k, v in PACKAGE_ALIASES.items())

    def __init__(self, name=None, parent=None, score=1.0):
        self._name = name
        self._tree = {}
        self._exports = {}
        self._parent = parent
        self._score = score
        if parent is None:
            self._merge_aliases()

    def _merge_aliases(self):
        def create(node, alias, score):
            if not alias:
                return
            name = alias.pop(0)
            with node.enter(name, score=1.0 if alias else score) as index:
                create(index, alias, score)

        for alias, (package, score) in SymbolIndex._PACKAGE_ALIASES.items():
            create(self, package.split('.'), score)

    def _score_key(self, scope, key):
        if not key:
            return [], 0.0
        key_score = value = scope._tree.get(key[0], None)
        if value is None:
            return [], 0.0
        if type(value) is float:
            return [], key_score
        else:
            path, score = self._score_key(value, key[1:])
            return [key[0]] + path, score + value._score

    def symbol_scores(self, symbol):
        scores = []
        path = []

        def score_walk(scope, scale):
            sub_path, score = self._score_key(scope, full_key)
            if score > 0.1:
                scores.append((score * scale, '.'.join(path + sub_path)))

            for key, subscope in scope._tree.items():
                if type(subscope) is not float:
                    path.append(key)
                    score_walk(subscope, scale - 0.1)
                    path.pop()

        full_key = symbol.split('.')
        score_walk(self, 1.0)
        scores.sort(reverse=True)
        return scores

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

    def add_explicit_export(self, name, score):
        self._exports[name] = score

    def find(self, path):
        path = path.split('.')
        node = self
        while node._parent:
            node = node._parent
        for name in path:
            node = node._tree.get(name, None)
            if node is None or type(node) is float:
                return None
        return node

    def add(self, name, score):
        current_score = self._tree.get(name, 0.0)
        if score > current_score:
            self._tree[name] = score

    @contextmanager
    def enter(self, name, score=1.0):
        if name is None:
            tree = self
        else:
            tree = self._tree.get(name)
            if not isinstance(tree, SymbolIndex):
                tree = self._tree[name] = SymbolIndex(name, self, score=score)
                if tree.path() in SymbolIndex._PACKAGE_ALIASES:
                    alias_path, _ = SymbolIndex._PACKAGE_ALIASES[tree.path()]
                    alias = self.find(alias_path)
                    alias._tree = tree._tree
        yield tree
        if tree._exports:
            # Delete unexported variables
            for key in set(tree._tree) - set(tree._exports):
                del tree._tree[key]

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
        tree = SymbolIndex()
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
            self._tree.add(name.name, 0.25)

    def visit_Import(self, node):
        for name in node.names:
            if name.name.startswith('_'):
                continue
            self._tree.add(name.name, 0.25)

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
                    if isinstance(subnode, ast.Str):
                        self._tree.add_explicit_export(subnode.s, 1.0)
            elif not name.id.startswith('_'):
                self._tree.add(name.id, 1.0)

    def visit_If(self, node):
        # NOTE: In lieu of actually parsing if/else blocks at the top-level,
        # we'll just ignore them.
        pass


def index_source(tree, filename, source):
    try:
        st = ast.parse(source, filename)
    except Exception as e:
        print 'Failed to parse %s: %s' % (filename, e)
        return
    visitor = SymbolVisitor(tree)
    visitor.visit(st)


def index_file(module, tree, filename):
    if BLACK_LIST_RE.search(filename):
        return
    with tree.enter(module) as subtree:
        with open(filename) as fd:
            index_source(subtree, filename, fd.read())


def index_path(tree, root):
    """Index a path.

    :param root: Either a package directory or a .py module.
    """
    if os.path.basename(root).startswith('_'):
        return
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


def index_builtin(tree, name):
    try:
        module = __import__(name, fromlist=['.'])
    except ImportError:
        logger.debug('failed to index builtin module %s', name)
        return

    with tree.enter(name) as subtree:
        for key, value in vars(module).iteritems():
            if not key.startswith('_'):
                subtree.add(key, 1.0)


def build_index(tree, paths):
    for builtin in BUILTIN_MODULES:
        index_builtin(tree, builtin)
    for path in paths:
        if os.path.isdir(path):
            for filename in os.listdir(path):
                filename = os.path.join(path, filename)
                index_path(tree, filename)


if __name__ == '__main__':
    # print ast.dump(ast.parse(open('pyautoimp.py').read(), 'pyautoimp.py'))
    tree = SymbolIndex()
    build_index(tree, sys.path)
