# Sublime Text 2 - Python Import Magic [![image](https://secure.travis-ci.org/alecthomas/SublimePythonImportMagic.png?branch=master)](https://travis-ci.org/alecthomas/SublimePythonImportMagic)

This plugin attempts to automatically manage Python imports.

**WARNING: This is a relatively complex plugin and thus may contain bugs. It may remove imports that you need. It may add imports that you don't. Use at your own risk.**

It can:

- Detect and add imports for unknown symbols.
- Remove unused imports.
- Order imports according to PEP8.

It currently does **NOT** (but support is planned):

- Detect changes to files and update its index automatically. The current workaround is to use the command palette `Python Import Magic: Reset Index`.
- Work on Sublime Text 3.

## Example

![Example of Import Magic at work](Python%20Import%20Magic.gif)

## Usage

There are three ways of invoking the auto-importer:

- The hotkey: `⌘⇧I` on OSX and `^⇧I` on Windows and Linux.
- Via the command palette: `Python Import Magic: Update Imports`.
- Setting `update_imports_on_save` to `true` in the user settings for the package. *I would not encourage use of this setting at this stage, but if you're feeling particularly brave...*


## Configuration

eg.

```json
{
    "update_imports_on_save": true,
    "python_path": {
        "/Library/Python/2.7/site-packages": "S",
        "/Users/alec/Projects/SublimePythonImportMagic/.venv/lib/python2.7/site-packages": "L"
    }
}
```

### `update_imports_on_save = false`

If true, update imports on each save. **WARNING: This might not be a good idea.**

### `index_filename = ".importmagic.idx"`

Name of file to store index in.

### `python_path = {<path>: <classification>}`

**NOTE: Not implemented yet**

Keys are the paths to search for Python modules. Values are how the path should be classified.

Paths will also be looked up in the default Sublime configuration under the key `python_import_magic_python_path`.

`<classification>` is from the following table:

Key | Classification
--- | -------
3 | Third party
S | System
L | Local
