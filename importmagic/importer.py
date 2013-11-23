import tokenize
from collections import defaultdict, namedtuple
from cStringIO import StringIO


"""Imports new symbols."""


class Iterator(object):
    def __init__(self, tokens):
        self._tokens = tokens
        self._cursor = 0

    def rewind(self):
        self._cursor -= 1

    def next(self):
        if not self:
            return None, None
        token = self._tokens[self._cursor]
        index = self._cursor
        self._cursor += 1
        return index, token

    def until(self, type):
        tokens = []
        while self:
            index, token = self.next()
            tokens.append((index, token))
            if type == token[0]:
                break
        return tokens

    def __nonzero__(self):
        return self._cursor < len(self._tokens)


Import = namedtuple('Import', 'name alias')


class Imports(object):
    def __init__(self, source):
        self._imports = set()
        self._imports_from = defaultdict(set)
        self._import_begin = self._imports_end = None
        self._source = source
        reader = StringIO(source)
        self._tokens = list(tokenize.generate_tokens(reader.readline))
        self._parse()

    def add_import(self, name, alias=None):
        self._imports.add(Import(name, alias))

    def add_import_from(self, module, name, alias=None):
        self._imports_from[module].add(Import(name, alias))

    def update_source(self):
        out = StringIO()
        for imp in sorted(self._imports):
            out.write('import {module}{alias}\n'.format(
                module=imp.name,
                alias='as {alias}'.format(alias=imp.alias) if imp.alias else '',
            ))
        for module, imports in sorted(self._imports_from.iteritems()):
            out.write('from {module} import {imports}\n'.format(
                module=module,
                imports=', '.join(
                    '{name}{alias}'.format(
                        name=name, alias=' as {alias}'.format(alias=alias) if alias else ''
                    ) for name, alias in imports)
            ))
        out.write('\n')

        lines = self._source.splitlines()
        start = self._tokens[self._import_begin][2][0] - 1
        end = self._tokens[self._imports_end][2][0] - 1
        lines[start:end] = [out.getvalue()]
        return '\n'.join(lines)

    def _parse(self):
        it = Iterator(self._tokens)
        self._seek_imports(it)
        self._parse_imports(it)

    def _parse_imports(self, it):
        while it:
            index, token = it.next()

            if token[0] == tokenize.INDENT or token[0] == tokenize.NAME and token[1] not in ('import', 'from'):
                break

            type = token[1]
            if type in ('import', 'from'):
                if self._import_begin is None:
                    self._import_begin = index
                tokens = it.until(tokenize.NEWLINE)
                self._imports_end = tokens[-1][0] + 1
                tokens = [t[1] for i, t in tokens
                          if t[0] == tokenize.NAME or t[1] in ',.']
                tokens.reverse()
                self._parse_import(type, tokens)
            else:
                self._imports_end = index + 1

        if self._import_begin is None:
            self._import_begin = self._imports_end = 0

    def _seek_imports(self, it):
        indentation = 0
        while it:
            index, token = it.next()

            if token[0] == tokenize.INDENT:
                indentation += 1
                continue
            elif token[0] == tokenize.DEDENT:
                indentation += 1
                continue

            # Don't process imports unless they're at module level. Safety first people!
            if indentation:
                continue

            if token[1] in ('import', 'from'):
                it.rewind()
                break

    def _parse_import(self, type, tokens):
        module = None
        if type == 'from':
            module = ''
            while tokens and tokens[-1] != 'import':
                module += tokens.pop()
            assert tokens.pop() == 'import'
        while tokens:
            name = tokens.pop()
            alias = None
            next = tokens.pop() if tokens else None
            if next == 'as':
                alias = tokens.pop()
                if alias == name:
                    alias = None
            elif next == ',':
                pass
            if type == 'import':
                self.add_import(name, alias=alias)
            else:
                self.add_import_from(module, name, alias=alias)

    def __repr__(self):
        return 'Imports(imports=%r, imports_from=%r)' % (self.imports, self.imports_from)


def update_imports(src, symbols, index):
    imports = Imports(src)
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
    return imports.update_source()
