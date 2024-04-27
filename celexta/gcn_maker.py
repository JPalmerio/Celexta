"""Contains the GCN maker ui"""

import logging
from PyQt6 import uic, QtWidgets
from celexta.initialize import SRC_DIRS, USR_DIRS
from celexta.io_gui import select_file

log = logging.getLogger(__name__)

GCN_MAKER_DIR  = USR_DIRS['GCN_MAKER']

class GcnMakerWindow(QtWidgets.QDialog):
    def __init__(self, parent):
        super(GcnMakerWindow, self).__init__(parent)
        self.parent = parent
        uic.loadUi(SRC_DIRS["UI"] / "GCN_maker.ui", self)
        self.create_dir()
        self.connect_buttons()
        
    def connect_buttons(self):
        """Connect buttons with signals"""
        self.btn_author_table.clicked.connect(self.do_nothing)
        self.btn_update_author_table.clicked.connect(self.do_nothing)
        self.btn_load_template.clicked.connect(self.do_nothing)
        self.btn_save_template.clicked.connect(self.save_template)
        
    def do_nothing(self):
        log.debug("Doing nothing")
        return
    def save_template(self):
        """Save text in plainTextEdit_gcn as template"""
        
        log.debug(f"Saving current GCN text as template")
        
        fname = select_file(
            self,
            base_dir=GCN_MAKER_DIR / "templates",
            file_type="(*.txt)"
        )
        # If no file selected, do nothing
        if fname is None:
            return
        
        text = self.plainTextEdit_gcn.toPlainText()
        with open(fname, 'w', encoding='utf-8') as f:
            f.write(text)
        
        
    def create_dir(self):
        """Create directories if they don't exist"""
        # Make sure templates directory exists
        templates_dir = GCN_MAKER_DIR / "templates"
        templates_dir.mkdir(exist_ok=True, parents=True)
