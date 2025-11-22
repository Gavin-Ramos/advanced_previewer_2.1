# -*- coding: utf-8 -*-
"""
Temporary Anki add-on script to list all available hooks in aqt.gui_hooks.
Writes output to gui_hooks_list.txt in the add-on folder.
"""
import os
import aqt.gui_hooks

def list_gui_hooks():
    output = []
    output.append("aqt.gui_hooks available hooks:")
    output.extend(dir(aqt.gui_hooks))
    addon_dir = os.path.dirname(__file__)
    with open(os.path.join(addon_dir, "gui_hooks_list.txt"), "w") as f:
        for line in output:
            f.write(str(line) + "\n")

list_gui_hooks()
