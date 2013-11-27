import sublime
import sublime_plugin

from importmagic.importer import get_update
from importmagic.index import SymbolIndex
from importmagic.symbols import Scope


class PythonImportMagic(sublime_plugin.EventListener):
    with open('index.json') as fd:
        index = SymbolIndex.deserialize(fd)

    def on_pre_save(self, view):
        if not view.match_selector(0, 'source.python'):
            return

        # Extract symbols from source
        src = view.substr(sublime.Region(0, view.size())).encode('utf-8')
        scope = Scope.from_source(src)
        unresolved, unreferenced = scope.find_unresolved_and_unreferenced_symbols()

        # Get update region and replacement text.
        start_line, end_line, text = get_update(src, self.index, unresolved, unreferenced)

        # Get region that needs updating
        start = view.text_point(start_line, 0)
        end = view.text_point(end_line, 0)
        region = sublime.Region(start, end)

        # Replace existing imports!
        edit = view.begin_edit()
        view.replace(edit, region, text)
        view.end_edit(edit)
