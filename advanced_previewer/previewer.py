from PyQt6.QtCore import Qt
# -*- coding: utf-8 -*-

"""
This file is part of the Advanced Previewer add-on for Anki

General previewer user interface

Copyright: Glutanimate 2016-2017
License: GNU AGPL, version 3 or later; https://www.gnu.org/licenses/agpl-3.0.en.html
"""

import re
import time
from typing import Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QDialogButtonBox, QPushButton, QLabel
)
from PyQt6.QtGui import QKeySequence, QAction, QShortcut
from aqt.browser import Browser
from aqt.webview import AnkiWebView
from aqt.utils import (mungeQA, openLink,
                       saveGeom, restoreGeom, tooltip, askUser)

from aqt.operations import CollectionOp

from anki.lang import _
from anki.consts import *

from anki.hooks import wrap, runFilter
from anki.sound import clearAudioQueue, playFromText, play
# from anki.js import browserSel  # Removed: not available in Anki 25.x
from anki.utils import json

from .html import *
from .config import loadConfig
from .utils import trySetAttribute, transl

# Shortcuts for each ease button
PRIMARY_KEYS = (Qt.Key_1, Qt.Key_2, Qt.Key_3, Qt.Key_4)  # 1,2,3,4
SECONDARY_KEYS = (Qt.Key_J, Qt.Key_K, Qt.Key_L, Qt.Key_Odiaeresis)  # J,K,L,Ö


# support for JS Booster add-on
try:
    from jsbooster.location_hack import getBaseUrlText, stdHtmlWithBaseUrl
    preview_jsbooster = True
except ImportError:
    preview_jsbooster = False



class Previewer(QDialog):
    """Advanced Previewer window"""

    def updateButtons(self):
        """Toggle next/previous buttons and update preview state"""
        self.b._previewState = self.state
        if hasattr(self, 'multi') and self.multi:
            self.btnPrev.setEnabled(False)
            self.btnNext.setEnabled(False)
            return
        # Navigation buttons logic disabled for compatibility

    def onSidesToggle(self):
        """Switches between preview modes ('front' vs 'back and front')"""
        self.both = self.btnSides.isChecked()
        if self.both:
            self.state = "answer"
        else:
            self.state = "question"
        self.renderPreview(cardChanged=True)

    def __init__(self, browser):
        super(Previewer, self).__init__(parent=browser)
        self.b = browser
        self.mw = self.b.mw
        # list of currently previewed card ids
        self.cards = []
        self.card = self.b.card
        # indicates whether user clicked on card in preview
        self.linkClicked = False
        self.setWindowTitle(_("Preview"))
        self.setObjectName("Previewer")
        self.setupConfig()
        self.initUI()
        self.renderPreview(cardChanged=True)  # Ensure initial render shows question side
        # self.finished.connect(self.b._onPreviewFinished)  # Disabled: not available in Anki 25.x

    def setupConfig(self):
        # Initialize a number of variables used by the add-on:
        self.config = loadConfig()
        self.multi = False
        self.state = "question"
        self.revAhead = False
        self.revAnswers = []
        self._revTimer = 0
        self.both = False  # Always start with front side only
        self.b._previewState = self.state

    def initUI(self):
        self.web = self.initWeb()
        self.b._previewWeb = self.web
        layout = self.setupMainLayout()
        self.setLayout(layout)
        self.setupHotkeys()
        restoreGeom(self, "preview")

    def setupMainLayout(self):
        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)

        # Set up buttons:
        bottom = QWidget()
        bottom_l = QHBoxLayout()
        bottom_l.setContentsMargins(0, 0, 0, 5)
        bottom.setLayout(bottom_l)
        bottom.setMaximumHeight(80)
        left = QHBoxLayout()
        right = QHBoxLayout()
        left.setAlignment(Qt.AlignBottom)
        right.setAlignment(Qt.AlignBottom)
        left.setContentsMargins(0, 0, 0, 0)
        right.setContentsMargins(0, 0, 0, 0)

        # 1: answer buttons
        if self.config["rev"][0]:  # reviewing enabled?
            self.revArea = self.setupReviewArea()
            left.addWidget(self.revArea)
            self.revArea.show()

        # 2: other buttons
        bbox = QDialogButtonBox()
        self.btnSides = bbox.addButton(
            transl("Both sides"), QDialogButtonBox.ActionRole)
        self.btnSides.setAutoDefault(False)
        self.btnSides.setShortcut(QKeySequence("B"))
        self.btnSides.setToolTip(_("Shortcut key: %s" % "B"))
        self.btnSides.setCheckable(True)
        self.btnSides.setChecked(self.both)

        # Add Show Answer button
        self.btnShowAnswer = bbox.addButton(
            transl("Show Answer"), QDialogButtonBox.ActionRole)
        self.btnShowAnswer.setAutoDefault(False)
        self.btnShowAnswer.setShortcut(QKeySequence("Space"))
        self.btnShowAnswer.setToolTip(_("Shortcut key: Space"))
        self.btnShowAnswer.clicked.connect(self.onShowAnswer)
        btnReplay = bbox.addButton(
            _("Replay Audio"), QDialogButtonBox.ActionRole)
        btnReplay.setAutoDefault(False)
        btnReplay.setShortcut(QKeySequence("R"))
        btnReplay.setToolTip(_("Shortcut key: %s" % "R"))
        self.btnPrev = bbox.addButton("<", QDialogButtonBox.ActionRole)
        self.btnPrev.setAutoDefault(False)
        self.btnPrev.setShortcut(QKeySequence("Left"))
        self.btnPrev.setToolTip(_("Shortcut key: Right arrow"))
        self.btnNext = bbox.addButton(">", QDialogButtonBox.ActionRole)
        self.btnNext.setToolTip(_("Shortcut key: Right arrow or Enter"))
        self.btnNext.setAutoDefault(True)
        self.btnNext.setShortcut(QKeySequence("Right"))

        self.btnSides.clicked.connect(self.onSidesToggle)
        self.btnPrev.clicked.connect(self.onPrev)
        self.btnNext.clicked.connect(self.onNext)
        # btnReplay.clicked.connect(self.b._onReplayAudio)  # Disabled: not available in Anki 25.x

        right.addWidget(bbox)
        bottom_l.addLayout(left)
        bottom_l.addLayout(right)

        vbox.addWidget(self.web, 10)
        # Set up window and launch preview
        vbox.addWidget(bottom, 0)

        return vbox

    def setupHotkeys(self):
        QShortcut(QKeySequence(_("Ctrl+Z")),
                  self, activated=self.mw.onUndo)
        # QShortcut(QKeySequence(_("Ctrl+J")),
        #           self, activated=self.b.onSuspend)  # Disabled: not available in Anki 25.x
        # QShortcut(QKeySequence(_("Ctrl+K")),
        #           self, activated=self.b.onMark)  # Disabled: not available in Anki 25.x
        QShortcut(QKeySequence(_("Alt+Delete")),
                  self, activated=self.b.deleteNotes)
        QShortcut(QKeySequence(_("Alt+Home")),
                  self, activated=lambda: self.onMove("s"))
        QShortcut(QKeySequence(_("Alt+End")),
                  self, activated=lambda: self.onMove("e"))
        QShortcut(QKeySequence(_("Alt+PgDown")),
                  self, activated=lambda: self.onMove("n"))
        QShortcut(QKeySequence(_("Alt+PgUp")),
                  self, activated=lambda: self.onMove("p"))

    def initWeb(self):
        web = AnkiWebView()
        # set up custom link handler (removed for Anki 25.x)
        # web.setLinkHandler(self.linkHandler)
        return web

    ############ REVIEWS ############

    def setupReviewArea(self):
        """Sets up review area of the preview window"""
        revArea = QWidget()
        review_layout = QVBoxLayout()
        review_layout.setContentsMargins(0, 0, 0, 0)
        revArea.setLayout(review_layout)

        self.revAns = QWidget()
        answer_layout = QHBoxLayout()
        answer_layout.setContentsMargins(0, 0, 0, 0)
        self.revAns.setLayout(answer_layout)

        self.revAnsBtns = []
        labels = ["Again", "Hard", "Good", "Easy"]
        for idx in range(1, 5):
            btn = QPushButton(labels[idx - 1], self)
            btn.setObjectName(labels[idx - 1].lower())
            # Use default argument to fix lambda late binding
            btn.clicked.connect(lambda _, o=idx: self.onPreviewAnswer(o))
            btn.setToolTip(_("Shortcut key: %s" % str(idx)))
            act1 = QAction(self, triggered=btn.animateClick)
            act1.setShortcut(QKeySequence(PRIMARY_KEYS[idx - 1]))
            act2 = QAction(self, triggered=btn.animateClick)
            act2.setShortcut(QKeySequence(SECONDARY_KEYS[idx - 1]))
            btn.addActions([act1, act2])
            btn.setAutoDefault(False)
            btn.setAutoRepeat(False)
            answer_layout.addWidget(btn)
            self.revAnsBtns.append(btn)

        self.revAnsInfo = QLabel()
        self.revAnsInfo.setAlignment(Qt.AlignCenter)
        review_layout.addWidget(self.revAnsInfo)
        review_layout.addWidget(self.revAns)

        return revArea

        self.revAnsInfo = QLabel()
        self.revAnsInfo.setAlignment(Qt.AlignCenter)

        review_layout.addWidget(self.revAnsInfo)
        review_layout.addWidget(self.revAns)

        return revArea


    def onPreviewAnswer(self, ease: int) -> None:
        """Answer card with given ease"""
        c: Any = self.b.card
        import types
        import time
        now: float = time.time() - 1.0

        # Use Anki's day-based attributes for scheduler compatibility
        # from anki.cards import Card  # Disabled: not available in Anki 25.x
        today: int = self.mw.col.sched.today

        # Ensure all interval/count attributes are integers before calling scheduler
        int_attrs = ["due", "ivl", "queue", "reps", "lapses", "factor", "odid", "odue", "left"]
        for attr in int_attrs:
            val = getattr(c, attr, None)
            if val is not None and not isinstance(val, int):
                try:
                    setattr(c, attr, int(val))
                except Exception:
                    setattr(c, attr, 0)

        # Set review timing attributes to match Anki's expectations
        for attr in ["_lastReviewed", "_reviewStart", "_startTimer"]:
            setattr(c, attr, today)

        # Use Anki's built-in timer logic
        c.start_timer()
        # timeTaken must be a float, not a method
        if getattr(c, "timeTaken", None) is None or callable(getattr(c, "timeTaken", None)):
            # Use browser batch grading API for safety (like learn-now-button)
            # from aqt.operations import CollectionOp  # Disabled: not available in Anki 25.x
            selected_cid = self.b.selectedCards()[0] if self.b.selectedCards() else None
            if not selected_cid:
                tooltip("No card selected in browser.", period=3000)
                return
            ease_val = ease
            def grade_card_op(col):
                card = col.get_card(selected_cid)
                card.start_timer()
                col.sched.answerCard(card, ease_val)
                return col.update_cards([card])
            CollectionOp(
                parent=self.b,
                op=grade_card_op,
            ).success(
                lambda out: tooltip(self.revAnswers[ease - 1], period=2000)
            ).run_in_background()
            if self.config["rev"][2]:
                self.b.onNextCard()
        if self.config["rev"][2]:
            self.b.onNextCard()

    ############ REVIEWS END ############

    def renderPreview(self, cardChanged=False):
        """
        Generates the preview window content
        """

        oldfocus = None
        cids = self.b.selectedCards()
        nr = len(cids)
        multiple_selected = nr > 1

        if not cids:
            txt = "Please select one or more cards"
            self.web.stdHtml(txt)
            self.updateButtons()
            return

        # Always start with front side on initial preview
        if not hasattr(self, '_initialPreviewed'):
            self.state = "question"
            self._initialPreviewed = True
        elif cardChanged and not self.both:
            self.state = "question"

        if self.config["rev"][0]:
            answers = [_("Again"), _("Hard"), _("Good"), _("Easy")]
            self.revArea.show()
            self.revAnswers = answers
            self._revTimer = time.time()
            if cids:
                c = self.mw.col.getCard(cids[0])
                # Set timerStarted on card when review area is shown
                c.timerStarted = self._revTimer
            for btn in self.revAnsBtns:
                btn.setEnabled(True)
                btn.setToolTip("Rate this card.")

        # Always render the currently selected card in the browser
        cids = self.b.selectedCards()
        if cids:
            c = self.mw.col.getCard(cids[0])
            if self.state == "answer":
                html = c.a()
            else:
                html = c.q()
            self.web.stdHtml(html)

        self.btnPrev.setEnabled(True)
        self.btnNext.setEnabled(True)

        if oldfocus and self.multi:
            self.scrollToCard(oldfocus)

        self.cards = cids

        self.updateButtons()

        clearAudioQueue()

        if not self.multi and self.mw.reviewer.autoplay(self.b.card):
            playFromText(html)

    def renderCards(self, cids):
        page = ""
        css = [preview_css]
        html = u"""<div id="{0}" class="card card{1}">{2}</div>"""

        # RegEx to remove multiple imports of external JS/CSS (JS-Booster-specific)
        jspattern = r"""(<script type=".*" src|<style>@import).*(</script>|</style>)"""
        scriptre = re.compile(jspattern)
        js = ""  # browserSel removed

        if self.multi:
            # only apply custom CSS and JS when previewing multiple cards
            html = u"""<div id="{0}" onclick="py.link('focus {0}');toggleActive(this);" \
                   class="card card{1}">{2}</div>"""
            css += [multi_preview_css]
            js += multi_preview_js

        for idx, cid in enumerate(cids):
            # add contents of each card to preview
            c = self.mw.col.getCard(cid)
            if self.state == "answer":
                ctxt = c.a()
            else:
                ctxt = c.q()
            # Remove subsequent imports of external JS/CSS
            if idx >= 1:
                ctxt = scriptre.sub("", ctxt)
            page += html.format(cid, c.ord + 1, ctxt)

        page = re.sub("\[\[type:[^]]+\]\]", "", page)
        page = runFilter("previewerMungeQA", page)

        return page, css, js
        jspattern = r"""(<script type=".*" src|<style>@import).*(</script>|</style>)"""
        scriptre = re.compile(jspattern)
        js = ""  # browserSel removed

        if self.multi:
            # only apply custom CSS and JS when previewing multiple cards
            html = u"""<div id="{0}" onclick="py.link('focus {0}');toggleActive(this);" \
                   class="card card{1}">{2}</div>"""
            css += [multi_preview_css]
            js += multi_preview_js

        for idx, cid in enumerate(cids):
            # add contents of each card to preview
            c = self.mw.col.getCard(cid)
            if self.state == "answer":
                ctxt = c.a()
            else:
                ctxt = c.q()
            # Remove subsequent imports of external JS/CSS
            if idx >= 1:
                ctxt = scriptre.sub("", ctxt)
            page += html.format(cid, c.ord + 1, ctxt)

        page = re.sub("\[\[type:[^]]+\]\]", "", page)
        page = runFilter("previewerMungeQA", page)

        return page, css, js

    def updatePreview(self, note):
        replacements = self.renderNote(note)
        if not replacements:
            return False
        cid = None
        for cid, html in replacements.items():
            self.web.eval(u"""
                const elm = document.getElementById('{}');
                elm.innerHTML = {}
                """.format(str(cid), json.dumps(html)))
        if cid:
            self.scrollToCard(cid)

    def renderNote(self, note):
        cards = note.cards()
        replacements = {}
        for card in cards:
            cid = card.id
            if self.state == "answer":
                inner_html = card.a()
            else:
                inner_html = card.q()
            replacements[cid] = inner_html
        return replacements

    def linkHandler(self, url):
        """Executed when clicking on a card"""
        if url.startswith("focus"):
            # bring card into focus
            cid = int(url.split()[1])
            self.linkClicked = True
            self.b.focusCid(cid)
        elif url.startswith("ankiplay"):
            # support for 'Replay Buttons on Card' add-on
            clearAudioQueue()  # stop current playback
            play(url[8:])
        else:
            # handle regular links with the default link handler
            openLink(url)

    def onPrev(self):
        from PyQt6.QtCore import QTimer
        if self.state == "answer" and not self.both:
            self.state = "question"
            self.renderPreview()
        else:
            self.b.onPreviousCard()
            QTimer.singleShot(50, lambda: self.renderPreview(cardChanged=True))
        self.updateButtons()

    def onNext(self):
        from PyQt6.QtCore import QTimer
        self.b.onNextCard()  # Move browser selection first
        self.state = "question"
        QTimer.singleShot(50, lambda: self.renderPreview(cardChanged=True))
        self.updateButtons()

    def onShowAnswer(self):
        if self.state != "answer":
            self.state = "answer"
            oldfocus = None
            cids = self.b.selectedCards()  # Always fetch latest selection
            nr = len(cids)
            multiple_selected = nr > 1

            if not cids:
                txt = "Please select one or more cards"
                self.web.stdHtml(txt)
                self.updateButtons()
                return

            # Always start with front side on initial preview
            if not hasattr(self, '_initialPreviewed'):
                self.state = "question"
                self._initialPreviewed = True
            # elif cardChanged and not self.both:
            #     self.state = "question"  # Disabled: cardChanged not defined in this context

            if self.config["rev"][0]:
                answers = [_("Again"), _("Hard"), _("Good"), _("Easy")]
                self.revArea.show()
                self.revAnswers = answers
                self._revTimer = time.time()
                if cids:
                    c = self.mw.col.getCard(cids[0])
                    # Set timerStarted on card when review area is shown
                    c.timerStarted = self._revTimer
                for btn in self.revAnsBtns:
                    btn.setEnabled(True)
                    btn.setToolTip("Rate this card.")

            # Always render the currently selected card in the browser
            cids = self.b.selectedCards()  # Always fetch latest selection
            if cids:
                c = self.mw.col.getCard(cids[0])
                if self.state == "answer":
                    html = c.a()
                else:
                    html = c.q()
                self.web.stdHtml(html)

            self.btnPrev.setEnabled(True)
            self.btnNext.setEnabled(True)

            if oldfocus and self.multi:
                self.scrollToCard(oldfocus)

            self.cards = cids

            self.updateButtons()

            clearAudioQueue()


            # Always use the latest selected card for autoplay
            if not self.multi and cids:
                c = self.mw.col.getCard(cids[0])
                if self.mw.reviewer.autoplay(c):
                    playFromText(html)

# The following functions should be outside the class, not indented under renderPreview
def _openPreview(self):
    """Creates and launches the preview window"""
    pvw = Previewer(self)
    ret = pvw.renderPreview(True)
    if ret is False:
        self.form.previewButton.setChecked(False)
        return
    pvw.show()
    self._previewWindow = pvw


def _onClosePreview(self):
    self._previewWindow = self._previewPrev = self._previewNext = None


def onTogglePreview(self):
    """only used to set the link handler after loading the preview window
    (required in order to be compatible with "Replay Buttons on Card")"""
    if self._previewWindow:
        self._previewWindow.web.setLinkHandler(
            self._previewWindow.linkHandler)


def _refreshCurrentCard(self, note):
    self.model.refreshNote(note)
    if not self._previewWindow:
        return
    # multiple cards selected?:
    if self._previewWindow.multi:
        self._previewWindow.updatePreview(note)
    else:
        self._previewWindow.renderPreview(False)



# For Anki 2.1+, use gui_hooks to patch browser methods
