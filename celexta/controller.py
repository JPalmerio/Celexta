import logging
from pathlib import Path
from pprint import pformat
import sys

import astropy.units as u
import matplotlib.pyplot as plt
import numpy as np
import pyqtgraph as pg
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.units import Quantity
from astropy.utils.data import get_pkg_data_filename
from astropy.visualization import ImageNormalize, MinMaxInterval, ZScaleInterval
from astropy.visualization.wcsaxes import SphericalCircle
from astropy.wcs import WCS
from matplotlib.colors import to_hex
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from PyQt6.QtCore import QAbstractListModel, QModelIndex, QObject, QSettings, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from zhunter import catalogs as cat

from celexta import io_gui
from celexta.abstract_models import CustomAbstractListModel
from celexta.aesthetics import ColorManager
from celexta.candidates import Candidate, CandidateEditor
from celexta.frames import QImageFrame, ScatterFrame, QImageFrameEditor
from celexta.regions import CircleEditor, CircleRegion, RegionModel, QuadrangleRegion
from celexta.tables import CustomTable, GlobalTableModel, TableEditor, TableModel, TableViewDialog
from celexta.examples import (
    generate_example_table,
    generate_example_candidate,
    generate_example_image,
    generate_example_region,
)
from celexta.widgets import DropDownWithListView, CoordinatesTable

log = logging.getLogger(__name__)


class Controller(QObject):
    """Controller to manage logic inside the Custom Tab.

    This class connects the model to the views and handles user interactions.
    It holds all the logic for the various actions that can be performed on items in the CustomTab.
    """

    def __init__(
        self,
        color_manager=None,
        parent=None,
    ):
        """Initialize the controller with a model and views."""
        super().__init__(parent)
        self.parent = parent
        self.image_frames = []
        self.models = {
            "frame": CustomAbstractListModel(),
            "region": CustomAbstractListModel(),
            "table": CustomAbstractListModel(),
            "candidate": CustomAbstractListModel(),
        }
        self.item_views = {
            "frame": DropDownWithListView("Frames"),
            "region": DropDownWithListView("Regions"),
            "table": DropDownWithListView("Tables"),
            "candidate": DropDownWithListView("Candidates"),
        }
        self.plot_widget = pg.GraphicsLayoutWidget()
        # Disable touch events to suppress warnings
        self.plot_widget.viewport().setAttribute(
            Qt.WidgetAttribute.WA_AcceptTouchEvents,
            False,
        )
        self.scatter_frame = ScatterFrame()
        self.coordinates_table = CoordinatesTable()
        self.focused_frame = None
        self.color_manager = color_manager if color_manager is not None else ColorManager()

        # Check that all required models and views are present
        # and set the models for the list views
        for key in ("frame", "region", "table", "candidate"):
            if key not in self.models or key not in self.item_views:
                raise ValueError(f"Missing model or view for key: {key}")
            self.item_views[key].setModel(self.models[key])
            # Connect the signals and slots
            if self.plot_widget is not None and self.models[key] is not None:
                # Connect visibility toggle signals
                self.models[key].visibilityChanged.connect(self.toggle_item)
                self.models[key].itemUpdated.connect(self.update_item)
                self.models[key].itemRemoved.connect(self.remove_from_all)

        for frame in self.image_frames:
            self.connect_frame(frame)  # Connect the frame's signals and slots

        # Connect context menu request signal
        self.connect_context_menu()

    def set_focused_frame(self, frame):
        """Set the focused frame."""
        self.focused_frame = frame
        for _frame in self.image_frames:
            if _frame is not frame:
                _frame.set_focus(False)

    def connect_context_menu(self):
        """Connect context menu signals for all views and frames."""
        for view in self.item_views.values():
            view.contextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, index, event):
        """Display the context menu on right-click."""
        log.debug("Context menu requested")
        # Easier to create menu every time than to update actions
        # that way we have access to the item
        menu = QMenu()
        item = index.data(Qt.ItemDataRole.UserRole)
        if isinstance(item, CustomTable):
            show_table = menu.addAction("Show Table")
            # show_table = menu.addAction("Show details")
        else:
            show_table = None
        if isinstance(item, CircleRegion | CustomTable | Candidate):
            add_to_frame = menu.addAction("Add to focused frame")
            add_to_all = menu.addAction("Add to all frames")
            menu.addSeparator()
            remove_from_frame = menu.addAction("Remove from focused frame")
        edit = menu.addAction("Edit")
        delete = menu.addAction("Delete")

        if self.focused_frame is None:
            add_to_frame.setDisabled(True)
            remove_from_frame.setDisabled(True)

        action = menu.exec(event)  # Show menu at mouse position
        if action is None:
            return
        if action == edit:
            self.edit(index)
        elif action == delete:
            self.delete(index)
        elif action == add_to_frame:
            self.add_to_frame(index)
        elif action == add_to_all:
            self.add_to_all(index)
        elif action == remove_from_frame:
            self.remove_from_frame(index)
        elif action == show_table:
            self.show_table(index)

    def edit(self, index):
        """Open a dialog to edit the selected item."""
        item = index.data(Qt.ItemDataRole.UserRole)
        log.debug(f"Edit action triggered on item: {item!s}")

        if isinstance(item, CircleRegion):
            item_type = "region"
            dialog = CircleEditor(item, parent=self.parent)
        elif isinstance(item, CustomTable):
            item_type = "table"
            dialog = TableEditor(item, parent=self.parent)
        elif isinstance(item, Candidate):
            item_type = "candidate"
            dialog = CandidateEditor(item, parent=self.parent)
        elif isinstance(item, QImageFrame):
            dialog = QImageFrameEditor(item, parent=self.parent)
            dialog.exec()
            return
        else:
            log.error(f"Unknown item type: {type(item)}, ignoring")
            return
        if dialog.exec():
            updated_data = dialog.get_values()
            self.models[item_type].update_item(item, **updated_data)

    def add(self, item: CircleRegion | CustomTable | Candidate):
        """Add an item to the model."""
        if item.color is None:
            item.color = self.color_manager.get_color()
        if isinstance(item, CircleRegion):
            model = self.models["region"]
        elif isinstance(item, CustomTable):
            model = self.models["table"]
        elif isinstance(item, Candidate):
            model = self.models["candidate"]
        else:
            log.error(f"Unknown item type: {type(item)}")
            return
        model.add_item(item)

        # If focused frame, add the item to the frame
        if self.focused_frame is not None:
            self.add_to_frame(model.get_index(item))
        if isinstance(item, Candidate):
            self.scatter_frame.add_candidate(item)

    def delete(self, index):
        """Delete the selected item."""
        item = index.data(Qt.ItemDataRole.UserRole)
        log.debug(f"Delete action triggered on item: {item!s}")
        if isinstance(item, CircleRegion):
            model = self.models["region"]
        elif isinstance(item, CustomTable):
            model = self.models["table"]
        elif isinstance(item, Candidate):
            model = self.models["candidate"]
        elif isinstance(item, QImageFrame):
            model = self.models["frame"]
            self.delete_frame(item)
        else:
            log.error(f"Unknown item type: {type(item)}")
            return
        model.delete_item(item)
        # Return the color to the pool of available colors
        if hasattr(item, "color") and item.color in self.color_manager.COLORS:
            self.color_manager.add_color_to_available_pool(item.color)

    def add_to_frame(self, index):
        """Add the selected item to the focused frame."""
        item = index.data(Qt.ItemDataRole.UserRole)
        log.debug(f"Add to frame action triggered on item: {item!s}")

        if self.focused_frame is None:
            log.debug("No focused frame, ignoring call.")
            return

        self.focused_frame.add_item(item)

    def add_to_all(self, index):
        """Add the selected item to all frames."""
        item = index.data(Qt.ItemDataRole.UserRole)
        log.debug(f"Add to all frames action triggered on item: {item!s}")
        for frame in self.image_frames:
            frame.add_item(item)

    def remove_from_frame(self, index):
        """Remove the selected item from the focused frame."""
        item = index.data(Qt.ItemDataRole.UserRole)
        log.debug(f"Remove from frame action triggered on item: {item!s}")
        if self.focused_frame is None:
            log.debug("No focused frame, ignoring call.")
            return
        self.focused_frame.remove_item(item)

    def remove_from_all(self, item):
        """Remove and item from all frames."""
        log.debug(f"Deleting item: {item!s}")
        for frame in self.image_frames:
            frame.remove_item(item)
        if isinstance(item, Candidate) and self.scatter_frame.isVisible():
            self.scatter_frame.remove_candidate(item)

    def toggle_item(self, signal: list[bool, CircleRegion | CustomTable | Candidate | QImageFrame]):
        """Toggle the visibility of an item."""
        visible, item = signal
        if isinstance(item, QImageFrame):
            if visible:
                item.main_vb.show()
            else:
                item.main_vb.hide()
            return

        for frame in self.image_frames:
            frame.toggle_item(signal)

        if isinstance(item, Candidate) and self.scatter_frame.isVisible():
            self.scatter_frame.toggle_candidate(signal)

    def update_item(self, item: CircleRegion | CustomTable | Candidate):
        """Update the properties of an item."""
        for frame in self.image_frames:
            frame.update_item(item)
        if isinstance(item, Candidate) and self.scatter_frame.isVisible():
            self.scatter_frame.update_candidate(item)

    def add_new_region(self):
        """Add a circle region to the widget."""
        dialog = CircleEditor(parent=self.parent)
        if dialog.exec():  # If user clicks "Ok"
            circle_data = dialog.get_values()
            circle = CircleRegion(**circle_data)
            self.add(circle)
            idx = self.models["region"].get_index(circle)
            self.add_to_frame(idx)

    def add_new_candidate(self):
        """Add a candidate to the widget."""
        dialog = CandidateEditor(parent=self.parent)
        if dialog.exec():
            candidate = dialog.candidate
            self.add(candidate)

    # Frames
    def resize_frames(self):
        """Resize and reposition all frames."""
        num_frames = len(self.image_frames)
        self.plot_widget.clear()  # Clear the layout before updating

        if num_frames == 0:
            return

        # Calculate grid layout (e.g., rows and columns)
        cols = int(np.ceil(np.sqrt(num_frames)))

        for idx, frame in enumerate(self.image_frames):
            row, col = divmod(idx, cols)
            self.plot_widget.addItem(frame, row, col)

        self.plot_widget.ci.layout.setSpacing(0)
        self.plot_widget.addItem(self.scatter_frame, row + 1, 0, 1, cols)
        self.plot_widget.update()

    def add_image_frame(
        self,
        image_data=None,
        projection=None,
        name=None,
        interval=None,
        frame=None,
    ):
        """Add a new frame to the plot widget."""
        if frame is None:
            frame = QImageFrame(
                projection=projection,
                image_data=image_data,
                name=name,
                interval=interval,
            )
        self.image_frames.append(frame)
        self.models["frame"].add_item(frame)
        self.connect_frame(frame)  # Connect the frame's signals and slots'
        # Change focus to the frame
        self.set_focused_frame(frame)
        self.resize_frames()  # Resize the frames takes care of adding it to the graphics layout
        return frame

    def connect_frame(self, frame):
        """Connect a frame to the controller."""
        frame.focused.connect(self.set_focused_frame)
        frame.hoverChanged.connect(self.coordinates_table.update_coordinates)

    def delete_frame(self, frame):
        """Delete a frame from the plot widget."""
        if frame in self.image_frames:
            # Remove the frame from the list
            self.image_frames.remove(frame)
            self.models["frame"].delete_item(frame)
            # If the deleted frame was focused, clear the focus
            if self.focused_frame == frame:
                self.focused_frame = None

            # Resize remaining frames
            self.resize_frames()

    def match_to_current_frame(self):
        """Match all tables and regions to the current frame."""
        if self.focused_frame is None:
            log.warning("No focused frame, ignoring.")
            return
        for frame in self.image_frames:
            frame.match_to(self.focused_frame)

    def show_table(self, index):
        """Show the table in a new window."""
        table = index.data(Qt.ItemDataRole.UserRole)
        log.debug(f"Show action triggered on table: {table!s}")
        if hasattr(table, "dialog") and table.dialog is not None:
            table.dialog.activateWindow()
        else:
            dialog = TableViewDialog(table, parent=self.parent)
            dialog.show()
            table.dialog = dialog

    def update_rotation(self, angle: float):
        """Update the rotation of the image."""
        if self.focused_frame is None:
            log.debug("No focused frame, ignoring call.")
            return
        self.focused_frame.update_rotation(angle)

    def toggle_scatter(self):
        """Toggle the scatter frame visibility."""
        self.scatter_frame.setVisible(not self.scatter_frame.isVisible())
        # Auto range so the data is visible when reshowing after hiding
        self.scatter_frame.spectral_plot.vb.autoRange()
        self.scatter_frame.temporal_plot.vb.autoRange()

    def toggle_grb_oa_pop(self):
        """Toggle the GRB OA population visibility."""
        self.scatter_frame.toggle_grb_oa_pop()

    # General save/load actions
    def to_serializable_dict(self, save_dir: str | Path):
        """Save the current state of the controller."""
        log.debug(f"Saving controller state to {save_dir!s}")
        # Make sure the directory exists
        Path(save_dir).mkdir(parents=True, exist_ok=True)

        data = {}
        # Iterate through items and convert them to serialized data to store as JSON
        for key in ("frame", "region", "table", "candidate"):
            if key in self.models:
                log.debug(f"Serializing {key} data")
                data[key] = []
                for item in self.models[key].items:
                    serialized_data = item.to_serializable_dict(save_dir)
                    log.debug(f"Serialized data for {key}: {pformat(serialized_data)}")
                    data[key].append(serialized_data)

        return data

    def from_serializable_dict(self, data: dict):
        """Load the controller state from a dictionary."""
        log.debug("Loading controller state")
        for key in ("frame", "region", "table", "candidate"):
            if key in data:
                log.debug(f"Loading {key} data")
                for item_data in data[key]:
                    if key == "frame":
                        frame = QImageFrame.from_serializable_dict(item_data)
                        self.add_image_frame(frame=frame)
                    elif key == "region":
                        if item_data["type"] == "circle":
                            self.add(CircleRegion.from_serializable_dict(item_data))
                        elif item_data["type"] == "quadrangle":
                            log.warning("Quadrangle regions not yet supported, ignoring")
                            # self.add(QuadrangleRegion.from_serializable_dict(item_data))
                    elif key == "table":
                        self.add(CustomTable.from_serializable_dict(item_data))
                    elif key == "candidate":
                        self.add(Candidate.from_serializable_dict(item_data))
        self.resize_frames()


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
    window.setWindowTitle("Controller Example")
    controller = Controller(parent=window)

    # Add the views to the window
    main_layout = QHBoxLayout()
    main_layout.addWidget(controller.plot_widget)
    layout = QVBoxLayout()
    main_layout.addLayout(layout)
    for view in controller.item_views.values():
        layout.addWidget(view)
    layout.addStretch()
    layout.addWidget(controller.coordinates_table)
    # Add a new frame
    controller.add_image_frame()
    hdu = generate_example_image("horse")
    im, wcs = hdu.data, WCS(hdu.header)
    controller.add_image_frame(image_data=im, projection=wcs)
    # Add a circle
    circle = generate_example_region(data=im, wcs=wcs)
    controller.add(circle)
    # Add a table
    table = generate_example_table(data=im, wcs=wcs)
    controller.add(table)
    # Add candidate
    candidate = generate_example_candidate(data=im, wcs=wcs)
    controller.add(candidate)

    widget = QWidget()
    widget.setLayout(main_layout)
    window.setCentralWidget(widget)
    window.show()
    sys.exit(app.exec())
