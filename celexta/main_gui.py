from typing import Dict
from .about_window import AboutWindow
"""Celexta main GUI."""

from PyQt6 import QtWidgets

from celexta.about import aboutWindow
from celexta.gcn_maker import GcnMakerWindow
from celexta.finding_chart_generator import FindingChartGeneratorWindow
from celexta.initialize import USR_DIRS
from celexta.windows import Ui_MainWindow


class MainGUI(QtWidgets.QMainWindow, Ui_MainWindow):
    """Main high-level Graphical User Interface (GUI).

    This class defines the GUI elements/widgets, such as the menu,
    the various buttons and their associated actions.
    It connects the signals from buttons to actions to be performed,
    but the various actions are defined outside of this module.

    It is responsible for directly interacting with the user, handling
    errors and informing them of what is going on.

    """

    def __init__(self, config: dict, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        # uic.loadUi(SRC_DIRS["UI"] / "main_gui.ui", self)
        self.setupUi(self)
        self.config = config
        self.set_up_windows()

        self.actionAbout.triggered.connect(self.show_about_window)
        self.actionQuit_Celexta.triggered.connect(self.quit_application)
        self.actionGCN_Maker.triggered.connect(self.show_gcn_maker)
        self.actionFinding_Chart_Generator.triggered.connect(self.show_finding_chart_generator)

    def create_windows(self) -> Dict[str, QtWidgets.QWidget]:
        return {
            "gcn_maker": GcnMakerWindow(self, authors_fname=USR_DIRS["GCN_MAKER"]/self.config["files"]["default_gcn_authors"]),
            "finding_chart_generator": FindingChartGeneratorWindow(self),
        }

    def set_up_windows(self):
        self.windows = self.create_windows()

    def show_about_window(self):
        about_window = AboutWindow(self)
        about_window.show()

    def quit_application(self):
        self.close()

    def show_gcn_maker(self):
        self.windows["gcn_maker"].show()

    def show_finding_chart_generator(self):
        self.windows["finding_chart_generator"].show()

