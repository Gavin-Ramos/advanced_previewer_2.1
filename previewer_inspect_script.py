# -*- coding: utf-8 -*-
"""
Script to inspect the previewer object and write its attributes to previewer_inspect.txt on Anki startup.
"""
import os
from aqt.gui_hooks import previewer_did_init

def inspect_previewer(previewer):
    output = []
    output.append("Previewer object attributes and methods:")
    output.extend(dir(previewer))
    output.append("\nPreviewer child widgets:")
    for child in previewer.children():
        output.append(f"{type(child)}: {getattr(child, 'objectName', lambda: None)()}")
    output.append("\nPreviewer findChildren results:")
    for found in previewer.findChildren(object):
        output.append(f"{type(found)}: {getattr(found, 'objectName', lambda: None)()}")
    # Try inspecting web_view or similar attribute
    for attr in ["web", "web_view", "_web", "_web_view"]:
        if hasattr(previewer, attr):
            webview = getattr(previewer, attr)
            output.append(f"\nFound webview attribute: {attr}")
            output.append(f"Type: {type(webview)}")
            output.append(f"Attributes: {dir(webview)}")
    addon_dir = os.path.dirname(__file__)
    with open(os.path.join(addon_dir, "previewer_inspect.txt"), "w") as f:
        for line in output:
            f.write(str(line) + "\n")

previewer_did_init.append(inspect_previewer)
