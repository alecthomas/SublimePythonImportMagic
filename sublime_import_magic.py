import os
import os.path
import sys
from threading import RLock, Thread

import sublime_plugin
import sublime

from importmagic.importer import get_update
from importmagic.index import SymbolIndex
from importmagic.symbols import Scope


settings = sublime.load_settings('Python Import Magic.sublime-settings')


def index_filename():
    return settings.get('index_filename', '.importmagic.idx')


def log(fmt, *args, **kwargs):
    text = fmt.format(*args, **kwargs)
    text = 'ImportMagic: {0}'.format(text)
    if kwargs.get('status', False):
        sublime.status_message(text)
    print text


class Indexer(object):
    def __init__(self):
        self._lock = RLock()
        self._indexes = {}
        self._threads = {}

    def rebuild(self, root):
        log('Rebuilding index for {0}', root)
        with self._lock:
            index_file = os.path.join(root, index_filename())
            try:
                os.unlink(index_file)
            except OSError:
                pass
            try:
                del self._indexes[root]
            except KeyError:
                pass
            log('Rebuilt index for {0}', root, status=True)
        return self.index(root)

    def index(self, root):
        with self._lock:
            if root in self._indexes:
                return self._indexes[root]
            if root in self._threads:
                log('WARNING: Still loading index from {0}', root, status=True)
                return None
            index_file = os.path.join(root, index_filename())
            thread = self._threads[root] = Thread(target=self._indexer, args=(root, index_file))
            self._threads[root].start()
            self._lock.release()
            thread.join(2.0)
            self._lock.acquire()
            if not thread.is_alive():
                return self._indexes[root]
            log('WARNING: Still loading index from {0}', root, status=True)

    def _indexer(self, root, index_file):
        # Delay indexing briefly so we don't hammer the system.
        sublime.status_message('Loading index {0}'.format(root))
        if os.path.exists(index_file):
            log('Loading index for {0}', root)
            with open(index_file) as fd:
                index = SymbolIndex.deserialize(fd)
        else:
            log('Indexing {0}', root)
            index = SymbolIndex()
            paths = sys.path[:]
            if root not in paths:
                paths.insert(0, root)
            index.build_index(paths)
            with open(index_file, 'w') as fd:
                fd.write(index.serialize())
        with self._lock:
            self._indexes[root] = index
            del self._threads[root]
        log('Ready for {0}', root, status=True)


class PythonImportMagic(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        if not settings.get('update_imports_on_save', False):
            return

        index = index_for_view(view)
        if not index:
            return

        update_imports_for_view(view, index)


class UpdatePythonImports(sublime_plugin.TextCommand):
    def run(self, edit):
        index = index_for_view(self.view)
        if not index:
            return

        update_imports_for_view(self.view, index)


class RebuildPythonImportIndex(sublime_plugin.TextCommand):
    def run(self, edit):
        indexer.rebuild(get_project_root(self.view))


indexer = Indexer()


def index_for_view(view):
    if not view.match_selector(0, 'source.python'):
        return

    return indexer.index(get_project_root(view))


def get_project_root(view):
    # NOTE: It would be nice if this wasn't so difficult :\
    try:  # handle case with no open folder
        return view.window().folders()[0]
    except IndexError:
        dir = get_working_dir(view)
        last_package = None
        while not os.path.exists(os.path.join(dir, index_filename())):
            if os.path.exists(os.path.join(dir, '__init__.py')):
                last_package = dir
            dir = os.path.dirname(dir)
        if os.path.dirname(dir) == dir:
            return last_package
        return dir


def get_working_dir(view):
    file_name = active_file_name(view)
    if file_name:
        return os.path.realpath(os.path.dirname(file_name))
    else:
        try:  # handle case with no open folder
            return view.window().folders()[0]
        except IndexError:
            return ''


def active_file_name(view):
    if view and view.file_name() and len(view.file_name()) > 0:
        return view.file_name()


def update_imports_for_view(view, index):
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
