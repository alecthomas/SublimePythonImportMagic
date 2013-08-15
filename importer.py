import __builtin__
import ast
import sys
from contextlib import contextmanager


class Scope(object):
    GLOBALS = ['__name__', '__file__', '__loader__', '__package__', '__path__']
    PYTHON3_BUILTINS = ['PermissionError']

    def __init__(self, parent=None, define_builtins=True, is_class=False):
        self._parent = parent
        self._definitions = set()
        self._references = set()
        self._children = []
        self._cursors = [self]
        self._cursor = self
        self._define_builtins = define_builtins
        self._is_class = is_class
        if define_builtins:
            self._define_builtin_symbols()

    def _define_builtin_symbols(self):
        self._cursor._definitions.update(dir(__builtin__))
        self._cursor._definitions.update(Scope.GLOBALS)
        self._cursor._definitions.update(Scope.PYTHON3_BUILTINS)

    def define(self, name):
        self._cursor._definitions.add(name)

    def reference(self, name):
        self._cursor._references.add(name)

    @contextmanager
    def enter(self, is_class=False):
        child = Scope(self._cursor, is_class=is_class, define_builtins=self._define_builtins)
        self._cursor._children.append(child)
        self._cursors.append(child)
        self._cursor = child
        try:
            yield child
        finally:
            self._cursors.pop()
            self._cursor = self._cursors[-1]

    def find_unresolved_references(self):
        def walk(scope, definitions):
            scope_definitions = definitions | scope._definitions
            # When we're in a class, don't export definitions to child function scopes
            if not scope._is_class:
                definitions = scope_definitions
            yield scope._references - scope_definitions
            for child in scope._children:
                for unresolved in walk(child, definitions):
                    yield unresolved

        all_unresolved = set()
        for unresolved in walk(self, set()):
            all_unresolved.update(unresolved)
        return all_unresolved

    def __repr__(self):
        return 'Scope(definitions=%r, references=%r, children=%r)' \
            % (self._definitions, self._references, self._children)


class UnknownSymbolVisitor(ast.NodeVisitor):
    def __init__(self, scope=None, trace=False):
        super(UnknownSymbolVisitor, self).__init__()
        self._scope = scope or Scope()
        self._trace = trace

    def visit(self, node):
        if self._trace:
            print node, vars(node)
        method = getattr(self, 'visit_%s' % node.__class__.__name__, None)
        if method is not None:
            try:
                method(node)
            except Exception:
                print >> sys.stderr, node, vars(node)
                raise
        else:
            self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._scope.define(node.name)
        self.visit_Lambda(node)

    def visit_Lambda(self, node):
        with self._scope.enter():
            args = node.args
            if args.kwarg:
                self._scope.define(args.kwarg)
            if args.vararg:
                self._scope.define(args.vararg)
            for arg in args.args:
                self._scope.define(arg.id)
            self.generic_visit(node)

    def visit_comprehension(self, node):
        self._apply_node(node.target)
        self.generic_visit(node)

    def _apply_node(self, target):
        if isinstance(target, ast.Tuple):
            for elt in target.elts:
                self._apply_node(elt)
        elif isinstance(target, (ast.Subscript, ast.Attribute)):
            while isinstance(target, (ast.Subscript, ast.Attribute, ast.Call)):
                try:
                    target = target.value
                except AttributeError:
                    target = target.func
            self._scope.reference(target.id)
        elif isinstance(target, ast.Call):
            self._apply_node(target.func)
        else:
            self._scope.define(target.id)

    def visit_Assign(self, node):
        for target in node.targets:
            self._apply_node(target)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self._scope.define(node.name)
        with self._scope.enter(is_class=True):
            self.generic_visit(node)

    def visit_Name(self, node):
        self._scope.reference(node.id)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        for name in node.names:
            if name.name == '*':
                # TODO: Do something.
                continue
            self._scope.define(name.asname or name.name.split('.')[0])
        self.generic_visit(node)

    def visit_Import(self, node):
        for name in node.names:
            self._scope.define(name.asname or name.name.split('.')[0])
        self.generic_visit(node)

    def visit_With(self, node):
        if node.optional_vars:
            self._scope.define(node.optional_vars.id)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        if node.name:
            self._scope.define(node.name.id)
        self.generic_visit(node)

    def visit_For(self, node):
        self._apply_node(node.target)
        self.generic_visit(node)


def extract_unresolved_symbols(src, trace=False, define_builtins=True):
    scope = Scope(define_builtins=define_builtins)
    visitor = UnknownSymbolVisitor(scope, trace=trace)
    visitor.visit(ast.parse(src))
    return scope.find_unresolved_references()
