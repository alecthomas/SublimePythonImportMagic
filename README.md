# Sublime Text 2 - Python Import Magic

This plugin attempts to automatically manage Python imports.

**WARNING: This is a relatively complex plugin and thus may contain bugs. It may remove imports that you need. It may add imports that you don't. Use at your own risk.**

It can:

- Detect and add imports for unknown symbols.
- Remove unused imports.
- Order imports according to PEP8.

It currently can **NOT** (but support is planned):

- Detect changes to files and update its index automatically. The current workaround is to use the command palette `Python Import Magic: Reset Index`.

## Example

![Example of Import Magic at work](Python%20Import%20Magic.gif)

## Usage

There are three ways of invoking the auto-importer:

- The hotkey: `⌘⇧I` on OSX and `^⇧I` on Windows and Linux.
- Via the command palette: `Python Import Magic: Update Imports`.
- Setting `update_imports_on_save` to `true` in the user settings for the package. *I would not encourage use of this setting at this stage, but if you're feeling particularly brave...*
