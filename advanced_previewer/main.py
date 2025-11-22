# Monkey patch: Add a button to the browser toolbar to open the advanced previewer
from PyQt6.QtGui import QAction
from aqt.gui_hooks import browser_will_show
from .config import AdvPrevOptions

def add_advanced_previewer_button(browser):
    from .previewer import Previewer
    def show_previewer():
        dlg = Previewer(browser)
        dlg.exec_()
    action = QAction("Advanced Previewer", browser)
    action.triggered.connect(show_previewer)
    # Add to Edit menu for visibility
    if hasattr(browser.form, "menuEdit"):
        browser.form.menuEdit.addAction(action)

browser_will_show.append(add_advanced_previewer_button)
# -*- coding: utf-8 -*-

"""
This file is part of the Advanced Previewer add-on for Anki

Main Module, hooks add-on methods into Anki

Copyright: Glutanimate 2016-2017
License: GNU AGPL, version 3 or later; https://www.gnu.org/licenses/agpl-3.0.en.html
"""


from PyQt6.QtGui import QAction
from aqt import mw
from aqt.gui_hooks import profile_did_open, previewer_did_init
# Inject advanced features into the built-in previewer using previewer_did_init

import os
def inject_advanced_features(previewer):
    from PyQt6.QtWidgets import QPushButton
    btn = QPushButton("Advanced Feature")
    btn.clicked.connect(lambda: print("Advanced feature activated!"))
    layout = previewer.layout()
    if layout:
        layout.addWidget(btn)
    else:
        print("No valid layout found on previewer")

previewer_did_init.append(inject_advanced_features)
# from .previewer import Previewer
# from aqt.browser import Browser

# Patch Browser's preview method to use Advanced Previewer
# def advanced_preview(self, *args, **kwargs):
#     pvw = Previewer(self)
#     pvw.exec_()
#     return True
# Browser.onTogglePreview = advanced_preview

from .config import loadConfig, AdvPrevOptions

# Menus


def onAdvPrevOptions(mw):
    """Invoke global config dialog"""
    dialog = AdvPrevOptions(mw)
    dialog.exec_()



def add_options_menu():
    options_action = QAction("A&dvanced Previewer Options...", mw)
    options_action.triggered.connect(lambda _, m=mw: onAdvPrevOptions(m))
    mw.form.menuTools.addAction(options_action)

profile_did_open.append(add_options_menu)

# Add-on setup


def setupAddon():
    loadConfig()

# Monkey patches and hooks into Anki's default methods


profile_did_open.append(setupAddon)
