"""Contains the Finding Chart Generator ui"""

import logging
from pathlib import Path

import pandas as pd
from PyQt6 import QtCore, QtWidgets

from celexta.decorators import check_active
from celexta.windows import Ui_FindingChartGeneratorWindow

log = logging.getLogger(__name__)

Shape = str
Shapes = list[Shape]


class FindingChartGeneratorWindow(QtWidgets.QDialog, Ui_FindingChartGeneratorWindow):
    """Finding Chart Generator Window"""

    def __init__(self, parent):
        super().__init__(parent)
        log.info("Initializing Finding Chart Generator")
        self.parent = parent
        self.setupUi(self)
        self.active = False
        # Models
        self.shape_model = ShapeModel()
        self.listView_shapes.setModel(self.shape_model)
        # self.survey_model = SurveyModel()
        # Items
        self.ruler = None
        self.compass = None
        # Signals and slots
        self.connect_buttons()

    def connect_buttons(self):
        """Connect buttons with signals"""
        # Buttons
        self.btn_generate.clicked.connect(self.generate_fc_from_survey)
        self.btn_upload_usr_img.clicked.connect(self.generate_fc_from_usr_img)
        self.btn_add_circle.clicked.connect(self.add_circle)
        self.btn_add_slit.clicked.connect(self.add_slit)
        # Checkboxes
        self.checkBox_show_compass.stateChanged.connect(self.show_compass)
        self.checkBox_show_ruler.stateChanged.connect(self.show_ruler)

    def generate_fc_from_survey(self):
        """Generate finding chart from survey"""
        log.debug("Generating finding chart from survey")

    def generate_fc_from_usr_img(self):
        """Generate finding chart from user image"""
        log.debug("Generating finding chart from user image")

    @check_active
    def add_circle(self):
        """Add circle to finding chart"""
        log.debug("Adding circle to finding chart")

    @check_active
    def add_slit(self):
        """Add slit to finding chart"""
        log.debug("Adding slit to finding chart")

    @check_active
    def show_compass(self):
        """Show compass in finding chart"""
        if not self.compass:
            log.debug("No compass defined yet, ignoring call.")
            return

        if self.checkBox_show_compass.isChecked():
            log.debug("Showing compass in finding chart")
            self.compass.show()
        else:
            log.debug("Hiding compass in finding chart")
            self.compass.hide()

    @check_active
    def show_ruler(self):
        """Show ruler in finding chart"""
        if not self.ruler:
            log.debug("No ruler defined yet, ignoring call")
            return

        if self.checkBox_show_ruler.isChecked():
            log.debug("Showing ruler in finding chart")
            self.ruler.show()
        else:
            log.debug("Hiding ruler in finding chart")
            self.ruler.hide()


class ShapeModel(QtCore.QAbstractListModel):
    def __init__(self, shapes: Shapes | None = None):
        super().__init__()
        self.shapes = shapes or []

    def update_shapes(self, shapes: Shapes):
        """Update shapes in model"""
        self.shapes += shapes

    def data(self, index, role):
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            shape = self.shapes[index.row()]
            return shape
        if role == QtCore.Qt.ItemDataRole.EditRole:
            shape = self.shapes[index.row()]
            return shape
        return None

    def rowCount(self, index):

        return len(self.shapes)
