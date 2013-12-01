import os
import os.path
import time
import sys
from threading import RLock, Thread

import sublime_plugin
import sublime

from importmagic.importer import get_update
from importmagic.index import SymbolIndex
from importmagic.symbols import Scope


def log(fmt, *args, **kwargs):
    text = fmt.format(*args, **kwargs)
    print 'ImportMagic: {0}'.format(text)


class Indexer(object):
    def __init__(self):
        self._lock = RLock()
        self._indexes = {}
        self._threads = {}

    def index(self, root):
        with self._lock:
            if root in self._indexes:
                return self._indexes[root]
            if root in self._threads:
                return None
            index_file = os.path.join(root, '.index.json')
            self._threads[root] = Thread(target=self._indexer, args=(root, index_file))
            self._threads[root].start()

    def _indexer(self, root, index_file):
        time.sleep(0.5)
        sublime.status_message('Loading index {0}'.format(root))
        if os.path.exists(index_file):
            log('Loading index for {0}', root)
            with open(index_file) as fd:
                index = SymbolIndex.deserialize(fd)
            self._indexes[root] = index
            log('Finished loading index for {0}', root)
            return index
        else:
            log('Indexing {0}', root)
            index = SymbolIndex()
            paths = sys.path[:]
            if root not in paths:
                paths.insert(0, root)
            index.build_index(paths)
            with open(index_file, 'w') as fd:
                fd.write(index.serialize())
            log('Finished generating index for {0}', root)
        with self._lock:
            self._indexes[root] = index
            del self._threads[root]


class PythonImportMagic(sublime_plugin.EventListener):
    def __init__(self):
        super(PythonImportMagic, self).__init__()
        self.indexer = Indexer()

    def _index_for_view(self, view):
        if not view.match_selector(0, 'source.python'):
            return

        return self.indexer.index(self._get_project_root(view))

    def on_pre_save(self, view):
        index = self._index_for_view(view)
        if not index:
            return

        # Extract symbols from source
        src = view.substr(sublime.Region(0, view.size())).encode('utf-8')
        scope = Scope.from_source(src)
        unresolved, unreferenced = scope.find_unresolved_and_unreferenced_symbols()

        # Get update region and replacement text.
        start_line, end_line, text = get_update(src, index, unresolved, unreferenced)

        # Get region that needs updating
        start = view.text_point(start_line, 0)
        end = view.text_point(end_line, 0)
        region = sublime.Region(start, end)

        # Replace existing imports!
        edit = view.begin_edit()
        try:
            view.replace(edit, region, text)
        finally:
            view.end_edit(edit)

    def _get_project_root(self, view):
        try:  # handle case with no open folder
            return view.window().folders()[0]
        except IndexError:
            dir = self._get_working_dir(view)
            last_package = None
            while not os.path.exists(os.path.join(dir, '.index.json')):
                if os.path.exists(os.path.join(dir, '__init__.py')):
                    last_package = dir
                dir = os.path.dirname(dir)
            if os.path.dirname(dir) == dir:
                return last_package
            return dir

    def _get_working_dir(self, view):
        file_name = self._active_file_name(view)
        if file_name:
            return os.path.realpath(os.path.dirname(file_name))
        else:
            try:  # handle case with no open folder
                return view.window().folders()[0]
            except IndexError:
                return ''

    def _active_file_name(self, view):
        if view and view.file_name() and len(view.file_name()) > 0:
            return view.file_name()
