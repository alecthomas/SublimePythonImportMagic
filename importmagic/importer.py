import ast
from collections import defaultdict
from StringIO import StringIO


"""Imports new symbols."""


class ImportFinder(ast.NodeVisitor):
    def __init__(self, imports):
        self._imports = imports

    def visit_Import(self, node):
        for imp in node.names:
            self._imports.add_import(imp.name, imp.asname, line_no=node.lineno)

    def visit_ImportFrom(self, node):
        for imp in node.names:
            self._imports.add_import_from(node.module, imp.name, imp.asname, line_no=node.lineno)


class Imports(object):
    def __init__(self):
        self.imports = []
        self.imports_from = defaultdict(list)
        self.first_line = 9999
        self.last_line = 0

    def add_import(self, name, alias=None, line_no=None):
        self.imports.append((name, alias))
        self._update_line_nos(line_no)

    def add_import_from(self, module, name, alias=None, line_no=None):
        self.imports_from[module].append((name, alias))
        self._update_line_nos(line_no)

    def _update_line_nos(self, line_no):
        if line_no is None:
            return
        self.first_line = min(self.first_line, line_no)
        self.last_line = max(self.last_line, line_no)

    def imports_as_source(self):
        self.imports.sort()
        out = StringIO()
        for name, alias in self.imports:
            out.write('import %s' % name)
            if alias:
                out.write(' as %s' % alias)
            out.write('\n')
        for module, imports in sorted(self.imports_from.iteritems()):
            args = []
            for name, alias in imports:
                if alias:
                    args.append('%s as %s' % (name, alias))
                else:
                    args.append(name)
            out.write('from %s import %s\n' % (module, ', '.join(args)))
        return out.getvalue().strip().splitlines()

    def replace_imports(self, source):
        imports = self.imports_as_source()
        first = self.first_line
        if first == 9999:
            first = 1
            imports.extend(['', ''])
        lines = source.splitlines()
        lines[first - 1:self.last_line] = imports
        return '\n'.join(lines)

    def __repr__(self):
        return 'Imports(imports=%r, imports_from=%r, first_line=%r, last_line=%r)' \
            % (self.imports, self.imports_from, self.first_line, self.last_line)


def update_imports(src, st, symbols, index):
    imports = Imports()
    finder = ImportFinder(imports)
    finder.visit(st)
    for symbol in symbols:
        scores = index.symbol_scores(symbol)
        if not scores:
            continue
        _, module, variable = scores[0]
        # Direct module import: eg. os.path
        if variable is None:
            imports.add_import(symbol)
        else:
            if '%s.%s' % (module, variable) == symbol:
                imports.add_import(module)
            else:
                imports.add_import_from(module, variable)
    return imports.replace_imports(src)
