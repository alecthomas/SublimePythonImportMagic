import re
import json
import ast
import os
import logging
import sys
from contextlib import contextmanager
from distutils import sysconfig

STD_LIBS = set([sysconfig.get_python_lib(standard_lib=True),
                sysconfig.get_python_lib(plat_specific=True),
                sysconfig.get_python_lib(plat_specific=False)])


"""Build an index of top-level symbols from Python modules and packages."""

BLACKLIST_RE = re.compile(r'test', re.I)
BUILTIN_MODULES = sys.builtin_module_names


# TODO: Update scores based on import reference frequency.
# eg. if "sys.path" is referenced more than os.path, prefer it.


logger = logging.getLogger(__name__)


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, SymbolIndex):
            d = o._tree.copy()
            d['.score'] = o._score
            d['.stdlib'] = o._stdlib
            return d
        return super(JSONEncoder, self).default(o)


class SymbolIndex(object):
    PACKAGE_ALIASES = {
        # Give os.path a score boost over posixpath and ntpath.
        'os.path': (os.path.__name__, 1.2),
    }
    _PACKAGE_ALIASES = dict((v[0], (k, v[1])) for k, v in PACKAGE_ALIASES.items())

    def __init__(self, name=None, parent=None, score=1.0, stdlib=False):
        self._name = name
        self._tree = {}
        self._exports = {}
        self._parent = parent
        self._score = score
        self._stdlib = stdlib
        if parent is None:
            self._merge_aliases()

    @classmethod
    def deserialize(self, file):
        def load(tree, data):
            for key, value in data.items():
                if isinstance(value, dict):
                    score = value.pop('.score', 1.0)
                    stdlib = value.pop('.stdlib', False)
                    with tree.enter(key, score=score, stdlib=stdlib) as subtree:
                        load(subtree, value)
                else:
                    tree.add(key, value)

        data = json.load(file)
        tree = SymbolIndex()
        load(tree, data)
        return tree

    def index_source(self, filename, source):
        try:
            st = ast.parse(source, filename)
        except Exception as e:
            print 'Failed to parse %s: %s' % (filename, e)
            return
        visitor = SymbolVisitor(self)
        visitor.visit(st)

    def index_file(self, module, filename):
        if BLACKLIST_RE.search(filename):
            return
        with self.enter(module, stdlib=is_stdlib(filename)) as subtree:
            with open(filename) as fd:
                subtree.index_source(filename, fd.read())

    def index_path(self, root):
        """Index a path.

        :param root: Either a package directory, a .so or a .py module.
        """
        if os.path.basename(root).startswith('_'):
            return
        stdlib = is_stdlib(root)
        if os.path.isfile(root):
            basename, ext = os.path.splitext(os.path.basename(root))
            ext = ext.lower()
            if ext == '.py':
                if basename == '__init__':
                    basename = None
                self.index_file(basename, root)
            elif ext in ('.dll', '.so'):
                self.index_builtin('.'.join(filter(None, [self.path(), basename])), stdlib=stdlib)
        elif os.path.isdir(root) and os.path.exists(os.path.join(root, '__init__.py')):
            basename = os.path.basename(root)
            with self.enter(basename, stdlib=stdlib) as subtree:
                for filename in os.listdir(root):
                    subtree.index_path(os.path.join(root, filename))

    def index_builtin(self, name, stdlib=False):
        if name.startswith('_'):
            return
        try:
            module = __import__(name, fromlist=['.'])
        except ImportError:
            logger.debug('failed to index builtin module %s', name)
            return

        with self.enter(name, stdlib=stdlib) as subtree:
            for key, value in vars(module).iteritems():
                if not key.startswith('_'):
                    subtree.add(key, 1.0)

    def build_index(self, paths):
        for builtin in BUILTIN_MODULES:
            self.index_builtin(builtin, stdlib=True)
        for path in paths:
            if os.path.isdir(path):
                for filename in os.listdir(path):
                    filename = os.path.join(path, filename)
                    self.index_path(filename)

    def symbol_scores(self, symbol):
        """Find matches for symbol.

        :param symbol: A . separated symbol. eg. 'os.path.basename'
        :returns: A list of tuples of (score, package, reference|None),
            ordered by score from highest to lowest.
        """
        scores = []
        path = []

        def score_walk(scope, scale):
            sub_path, score = self._score_key(scope, full_key)
            if score > 0.1:
                try:
                    i = sub_path.index(None)
                    sub_path, from_symbol = sub_path[:i], '.'.join(sub_path[i + 1:])
                except ValueError:
                    from_symbol = None
                package_path = '.'.join(path + sub_path)
                scores.append((score * scale, package_path, from_symbol))

            for key, subscope in scope._tree.items():
                if type(subscope) is not float:
                    path.append(key)
                    score_walk(subscope, subscope._score * scale - 0.1)
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
    def enter(self, name, score=1.0, stdlib=False):
        if name is None:
            tree = self
        else:
            tree = self._tree.get(name)
            if not isinstance(tree, SymbolIndex):
                tree = self._tree[name] = SymbolIndex(name, self, score=score, stdlib=stdlib)
                if tree.path() in SymbolIndex._PACKAGE_ALIASES:
                    alias_path, _ = SymbolIndex._PACKAGE_ALIASES[tree.path()]
                    alias = self.find(alias_path)
                    alias._tree = tree._tree
        yield tree
        if tree._exports:
            # Delete unexported variables
            for key in set(tree._tree) - set(tree._exports):
                del tree._tree[key]

    def serialize(self):
        return json.dumps(self, cls=JSONEncoder)

    def __repr__(self):
        return repr(self._tree)

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
            return [None, key[0]], key_score
        else:
            path, score = self._score_key(value, key[1:])
            return [key[0]] + path, score + value._score


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


def is_stdlib(path):
    for stdpath in STD_LIBS:
        if path.startswith(stdpath):
            return True
    return False

if __name__ == '__main__':
    # print ast.dump(ast.parse(open('pyautoimp.py').read(), 'pyautoimp.py'))
    tree = SymbolIndex()
    tree.build_index(sys.path)
    sys.stdout.write(tree.serialize())
