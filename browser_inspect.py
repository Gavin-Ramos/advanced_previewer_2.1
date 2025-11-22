# -*- coding: utf-8 -*-
"""
Temporary Anki add-on script to inspect browser previewer internals.
Writes output to browser_inspect.txt in the add-on folder.
"""
import os
from aqt import mw
from aqt.browser import Browser
from aqt.gui_hooks import profile_did_open

def inspect_browser():
    output = []
    output.append("Browser class attributes and methods:")
    output.extend(dir(Browser))
    output.append("\nInstance attributes and methods:")
    try:
        browser = mw.form.browser
        output.extend(dir(browser))
    except Exception as e:
        output.append(f"Error accessing browser instance: {e}")
    # Write to file in add-on directory
    addon_dir = os.path.dirname(__file__)
    with open(os.path.join(addon_dir, "browser_inspect.txt"), "w") as f:
        for line in output:
            f.write(str(line) + "\n")

profile_did_open.append(inspect_browser)
