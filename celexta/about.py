"""Contains the "about" ui"""

from PyQt6 import QtWidgets, uic

from celexta import __version__
from celexta.initialize import SRC_DIRS


class aboutWindow(QtWidgets.QDialog):
    def __init__(self, parent):
        super(aboutWindow, self).__init__(parent)
        self.parent = parent
        uic.loadUi(SRC_DIRS["UI"] / "about.ui", self)
        self.label.setText(f"Celexta version: {__version__}")
