import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from celexta.examples import generate_example_image, generate_example_region, generate_example_table

from celexta.regions import RegionModel, CircleRegion
from celexta.controller import Controller
from celexta.tables import CustomTable, TableModel, GlobalTableModel
from celexta.toolbar import create_mpl_toolbar
from celexta.widgets import DropDownWithListView
from celexta.abstract_models import CustomAbstractListModel

log = logging.getLogger(__name__)


class CustomTab(QWidget):
    """Widget containing a central plot widget and some list views on the side.

    Contains the models and controllers for tables, regions, and candidates.
    """

    def __init__(
        self,
        style="pyqtgraph",
        parent=None,
    ):
        super().__init__(parent)

        self.style = style
        # Create a horizontal layout for the plot and list widgets
        main_layout = QHBoxLayout(self)

        # Create list views
        self.controller = Controller(parent=self)
        # btn_layout = self.create_buttons()
        btn_layout = QVBoxLayout()
        for view in self.controller.item_views.values():
            btn_layout.addWidget(view)
        btn_layout.addStretch(100)
        btn_layout.setSpacing(0)
        btn_layout.addWidget(self.controller.coordinates_table)
        # Make main plot occupy 5/6 of the width
        main_layout.addWidget(self.controller.plot_widget, 5)
        # Make btn views occupy 1/6 of the width
        main_layout.addLayout(btn_layout, 1)

    def create_buttons(self):
        """Create the btn widgets for tables, regions, and candidates."""
        # Create a vertical layout for the btn widgets
        btn_layout = QVBoxLayout()

        # Dummy buttons for now
        # add_table_button = QPushButton("Add table")
        # add_table_button.clicked.connect(self.add_example_table)
        # btn_layout.addWidget(add_table_button)
        add_region_button = QPushButton("Add region")
        add_region_button.clicked.connect(self.controller.add_new_region)
        btn_layout.addWidget(add_region_button)
        add_frame_button = QPushButton("Add frame")
        add_frame_button.clicked.connect(lambda x: self.controller.add_image_frame())
        btn_layout.addWidget(add_frame_button)
        match_to_current_frame_button = QPushButton("Match all to frame")
        match_to_current_frame_button.clicked.connect(self.controller.match_to_current_frame)
        btn_layout.addWidget(match_to_current_frame_button)

        return btn_layout


if __name__ == "__main__":
    import sys

    from PyQt6.QtGui import QFont

    logging.getLogger("PyQt6").setLevel(logging.INFO)
    logging.getLogger("matplotlib").setLevel(logging.INFO)
    log = logging.getLogger(__name__)
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.DEBUG,
        format="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(funcName)s - %(filename)s:%(lineno)d : %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    app = QApplication(sys.argv)
    default_font = QFont("CMU Serif", 12)  # Change to preferred font and size
    app.setFont(default_font)
    window = QMainWindow()
    window.setWindowTitle("CustomTab Test")
    mtw = CustomTab(parent=window)
    window.setCentralWidget(mtw)
    window.show()
    sys.exit(app.exec())
