"""Celexta main GUI."""

from PyQt6 import uic, QtWidgets
from celexta.about import aboutWindow
from celexta.gcn_maker import GcnMakerWindow
from celexta.initialize import DIRS

class MainGUI(QtWidgets.QMainWindow):
    """Main high-level Graphical User Interface (GUI).

    This class defines the GUI elements/widgets, such as the menu,
    the various buttons and their associated actions.
    It connects the signals from buttons to actions to be performed,
    but the various actions are defined outside of this module.

    It is responsible for directly interacting with the user, handling
    errors and informing them of what is going on.

    """
    def __init__(self, *args, **kwargs):
        super(MainGUI, self).__init__(*args, **kwargs)
        uic.loadUi(DIRS["UI"] / "main_gui.ui", self)
        
        self.set_up_windows()
        
        self.actionAbout.triggered.connect(aboutWindow(self).show)
        self.actionQuit_Celexta.triggered.connect(self.close)
        self.actionGCN_Maker.triggered.connect(self.windows["gcn_maker"].show)
    
    def set_up_windows(self):
        self.windows = {
            "gcn_maker": GcnMakerWindow(self),
        }
