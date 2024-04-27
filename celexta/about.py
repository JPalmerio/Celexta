"""Contains the "about" ui"""

from PyQt6 import uic, QtWidgets
from celexta import __version__
from celexta.initialize import DIRS

class aboutWindow(QtWidgets.QDialog):
    def __init__(self, parent):
        super(aboutWindow, self).__init__(parent)
        self.parent = parent
        uic.loadUi(DIRS["UI"] / "about.ui", self)
        self.label.setText(f"Celexta version: {__version__}")