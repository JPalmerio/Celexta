"""Contains the GCN maker ui"""

from PyQt6 import uic, QtWidgets
from celexta.initialize import DIRS


class GcnMakerWindow(QtWidgets.QDialog):
    def __init__(self, parent):
        super(GcnMakerWindow, self).__init__(parent)
        self.parent = parent
        uic.loadUi(DIRS["UI"] / "GCN_maker.ui", self)
        
        