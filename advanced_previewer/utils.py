# -*- coding: utf-8 -*-

"""
This file is part of the Advanced Previewer add-on for Anki

Reusable utilities

Copyright: Glutanimate 2016-2017
License: GNU AGPL, version 3 or later; https://www.gnu.org/licenses/agpl-3.0.en.html
"""

def transl(phrase):
    """Translate string (disabled for Anki 25.x)"""
    return phrase


def trySetAttribute(obj, attr, value):
    if not hasattr(obj, attr):
        setattr(obj, attr, value)
