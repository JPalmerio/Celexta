import logging
import sys

import astropy.units as u
import matplotlib.pyplot as plt
import numpy as np
from astropy.io import fits
from astropy.utils.data import get_pkg_data_filename
from astropy.visualization import ImageNormalize, MinMaxInterval, ZScaleInterval
from astropy.visualization.wcsaxes import SphericalCircle
from astropy.wcs import WCS


from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.colors import to_hex
from PyQt6.QtCore import Qt, QTimer, QSettings, QObject, pyqtSignal, QAbstractListModel, QModelIndex
from PyQt6.QtGui import QAction, QFont, QKeySequence, QColor
from PyQt6.QtWidgets import (
    QMenu,
    QApplication,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QListView,
    QLabel,
    QLineEdit,
    QMainWindow,
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
from astropy.coordinates import SkyCoord

from astropy.units import Quantity
from celexta import io_gui
from celexta.utils import create_input_field
from celexta.widgets import DropDownWithListView
from celexta.aesthetics import ColorManager
from celexta.abstract_models import CustomAbstractListModel

log = logging.getLogger(__name__)


class QuadrangleRegion:
    """A rectangular region on the sky defined by two corners."""

    # TODO: change this so it can be initialized with the center of the slit, a position angle, and the width and height of the slit
    # TODO: Or from four corners
    def __init__(
        self,
        anchor: SkyCoord,
        width: Quantity,
        height: Quantity = None,
        name=None,
        color=None,
    ):
        """Initialize a QuadrangleRegion.

        Parameters
        ----------
        anchor : SkyCoord
            The anchor point of the quadrangle.
        width : Quantity
            The width of the quadrangle.
        height : Quantity, optional
            The height of the quadrangle. If ``None``, defaults to `width`.
        name : str, optional
            The name of the quadrangle. If ``None``, defaults to "Quadrangle".
        color : str, optional
            The color of the quadrangle. Default is "C0".
        """
        self.name = name if name is not None else "Quadrangle"
        self.anchor = (anchor.ra, anchor.dec)
        self.width = width
        self.height = height if height is not None else width
        self.color = to_hex(color) if color is not None else to_hex("C0")

    def __str__(self):
        """Return a string representation of the QuadrangleRegion."""
        return f"QuadrangleRegion(name={self.name}, anchor={self.anchor}, width={self.width:.6f}, height={self.height:.6f})"

    def to_json(self):
        """Return a JSON-serializable dictionary of the QuadrangleRegion."""
        return {
            "type": "quadrangle",
            "name": self.name,
            "anchor": {
                "ra": self.anchor[0].deg,
                "dec": self.anchor[1].deg,
                "unit": "deg",
                "frame": "icrs",
            },
            "width": {"value": self.width.deg, "unit": "deg"},
            "height": {"value": self.height.deg, "unit": "deg"},
            "color": self.color,
        }

    def from_json(self, data):
        """Initialize a QuadrangleRegion from a JSON-serializable dictionary."""
        self.name = data["name"]
        self.anchor = SkyCoord(ra=data["anchor"]["ra"], dec=data["anchor"]["dec"], unit="deg")
        self.width = u.Quantity(data["width"]["value"], unit=data["width"]["unit"])
        self.height = u.Quantity(data["height"]["value"], unit=data["height"]["unit"])
        self.color = data["color"]
        log.debug(f"QuadrangleRegion from JSON: {self!s}")
        return self


class CircleRegion:
    """A circular region on the sky defined by a center and radius."""

    def __init__(
        self,
        center: SkyCoord,
        radius: Quantity,
        name=None,
        color=None,
    ):
        """Initialize a CircleRegion.

        Parameters
        ----------
        center : SkyCoord
            The center of the circle.
        radius : Quantity
            The radius of the circle.
        name : str, optional
            The name of the circle. If ``None``, defaults to "Circle".
        color : str, optional
            The color of the circle. Default is "C0".
        """
        self.name = name if name is not None else "Circle"
        self.center = center
        self.radius = radius
        # Convert color to hex so Qt can use it
        self.color = to_hex(color) if color is not None else None

    def __str__(self):
        """Return a string representation of the CircleRegion."""
        return f"CircleRegion(name={self.name}, center={self.center}, radius={self.radius:.4f})"

    def to_serializable_dict(self, *args, **kwargs):
        """Return a JSON-serializable dictionary of the CircleRegion."""
        return {
            "type": "circle",
            "name": str(self.name),
            "center": {
                "ra": float(self.center.ra.deg),
                "dec": float(self.center.dec.deg),
                "unit": "deg",
                "frame": str(self.center.frame.name),
            },
            "radius": {"value": float(self.radius.to("deg").value), "unit": "deg"},
            "color": str(to_hex(self.color)),
        }

    @classmethod
    def from_serializable_dict(cls, data):
        """Initialize a CircleRegion from a JSON-serializable dictionary."""
        name = data["name"]
        center = SkyCoord(
            ra=data["center"]["ra"],
            dec=data["center"]["dec"],
            unit="deg",
            frame=data["center"]["frame"],
        )
        radius = u.Quantity(data["radius"]["value"], unit=data["radius"]["unit"])
        color = data["color"]
        circle = cls(center=center, radius=radius, name=name, color=color)
        log.debug(f"CircleRegion from JSON: {circle!s}")
        return circle


class RegionModel(QAbstractListModel):
    """Model to manage region objects"""

    visibilityChanged = pyqtSignal(list)  # [bool, region]
    itemRemoved = pyqtSignal(object)  # region
    itemUpdated = pyqtSignal(object)  # region

    def __init__(self, parent=None, regions=None):
        super().__init__(parent)
        self.regions = regions if regions is not None else []
        self.visibility = {region: True for region in self.regions}  # Track visibility

    def rowCount(self, parent=None):
        """Return the number of circles."""
        return len(self.regions)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """Return the data for each circle in the list."""
        if not index.isValid():
            return None
        region = self.regions[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:  # Display name
            return region.name
        if role == Qt.ItemDataRole.DecorationRole:  # Display color
            return QColor(region.color)
        if role == Qt.ItemDataRole.CheckStateRole:  # Checkbox for visibility
            state = Qt.CheckState.Checked if self.visibility[region] else Qt.CheckState.Unchecked
            return state
        if role == Qt.ItemDataRole.UserRole:
            return region
        return None

    def flags(self, index):
        """Make items checkable."""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        """Handle checkbox toggles to update visibility."""
        if not index.isValid():
            return False
        if role == Qt.ItemDataRole.CheckStateRole:
            region = self.regions[index.row()]
            new_state = value == Qt.CheckState.Checked.value
            # Check if the state is changing
            if self.visibility.get(region, True) != new_state:
                self.visibility[region] = new_state
                self.visibilityChanged.emit([new_state, region])
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
                return True
        return False

    def add_region(self, region):
        """Add a new region to the model."""
        log.debug(f"Trying to add region: {region!s}")
        if region in self.regions:
            log.debug("Region already exists, ignoring")
            return
        row = len(self.regions)
        self.insertRow(row, region)

    def insertRow(self, row, region):
        """Insert a row into the model."""
        if isinstance(row, QModelIndex):  # Ensure row is an integer
            row = row.row()
        if row < 0 or row > len(self.regions):
            log.debug("Invalid row, ignoring")
            return False
        # Finer grained that layoutChanged.emit()
        # Use QModelIndex() to indicate the parent is the root
        # i.e. no hierarchy for list models
        self.beginInsertRows(QModelIndex(), row, row)
        self.regions.append(region)
        self.visibility[region] = True
        log.debug(f"Added region: {region!s}")

        # Notify views that the row insertion is complete.
        self.endInsertRows()
        return True

    def delete_region(self, region):
        """Delete a region from the model."""
        row = self.get_index(region)
        self.removeRow(row)

    def removeRow(self, row, parent=QModelIndex()):
        """Remove a row from the model."""
        if isinstance(row, QModelIndex):  # Ensure row is an integer
            row = row.row()
        if row < 0 or row > len(self.regions):
            log.debug("Invalid row, ignoring")
            return False
        region = self.regions[row]
        self.beginRemoveRows(parent, row, row)
        self.visibility.pop(region, None)
        del self.regions[row]
        log.debug(f"Deleted region: {region!s}")
        self.endRemoveRows()
        self.itemRemoved.emit(region)
        return True

    def get_index(self, region):
        """Return the QModelIndex of the given region, or an invalid index if not found."""
        try:
            row = self.regions.index(region)
            return self.createIndex(row, 0)
        except ValueError:
            return QModelIndex()

    def update_region(self, region, center=None, radius=None, name=None, color=None):
        """Update the properties of a region."""
        log.debug(f"Updated region: {region!s}")
        if center is not None:
            region.center = center
        if radius is not None:
            region.radius = radius
        if name is not None:
            region.name = name
        if color is not None:
            region.color = color

        # Emit dataChanged signal to update the views
        index = self.get_index(region)
        self.dataChanged.emit(index, index)
        self.itemUpdated.emit(region)


class CircleEditor(QDialog):
    """Popup to edit circle properties (RA, DEC, Radius, Name)."""

    def __init__(self, circle=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Circle Properties")

        defaults = {
            "name": "",
            "ra": "",
            "dec": "",
            "radius": "",
            "color": "red",
        }
        # Update defaults with circle data
        if circle:
            defaults.update(
                {
                    "name": circle.name,
                    "ra": circle.center.ra.to("deg").value,
                    "dec": circle.center.dec.to("deg").value,
                    "radius": circle.radius.to("deg").value,
                    "color": circle.color,
                }
            )

        main_layout = QVBoxLayout(self)
        grid_layout = self.create_grid_layout(defaults)
        main_layout.addLayout(grid_layout)
        # Save/Cancel Buttons
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

    def create_grid_layout(self, defaults):
        """Create a grid layout for the input fields."""
        # Grid Layout for Fields
        grid_layout = QGridLayout()

        # --- Name Field (Row 0) ---
        self.name_input = QLineEdit(defaults["name"])
        grid_layout.addWidget(QLabel("Name:"), 0, 0)
        grid_layout.addWidget(self.name_input, 0, 1)

        # --- R.A. Field (Row 1) ---
        self.ra_input, self.ra_unit_combo = create_input_field(
            unit_options=["degree", "hourangle"],
            text=str(defaults["ra"]),
        )
        grid_layout.addWidget(QLabel("R.A.:"), 1, 0)
        grid_layout.addWidget(self.ra_input, 1, 1)
        grid_layout.addWidget(self.ra_unit_combo, 1, 2)

        # --- Declination Field (Row 2) ---
        self.dec_input, self.dec_unit_combo = create_input_field(
            unit_options=["degree"],
            text=str(defaults["dec"]),
        )
        grid_layout.addWidget(QLabel("Declination:"), 2, 0)
        grid_layout.addWidget(self.dec_input, 2, 1)
        grid_layout.addWidget(self.dec_unit_combo, 2, 2)

        # --- Radius Field (Row 3) ---
        self.radius_input, self.radius_unit_combo = create_input_field(
            unit_options=["degree", "arcmin", "arcsec"],
            text=str(defaults["radius"]),
        )
        grid_layout.addWidget(QLabel("Radius:"), 3, 0)
        grid_layout.addWidget(self.radius_input, 3, 1)
        grid_layout.addWidget(self.radius_unit_combo, 3, 2)

        # Color Input
        self.color_input = QLineEdit(defaults["color"])
        grid_layout.addWidget(QLabel("Color:"), 4, 0)
        grid_layout.addWidget(self.color_input, 4, 1)

        return grid_layout

    def get_values(self):
        """Retrieve user-inputted values."""
        center = self.get_ra_dec()
        radius = self.get_radius()

        return {
            "center": center,
            "radius": radius,
            "color": self.color_input.text(),
            "name": self.name_input.text(),
        }

    def get_ra_dec(self) -> tuple[Quantity[u.deg], Quantity[u.deg]]:
        """Retrieve the RA and Dec values from the input fields."""
        ra = self.ra_input.text()
        dec = self.dec_input.text()
        ra_unit = self.ra_unit_combo.currentText()
        dec_unit = self.dec_unit_combo.currentText()
        # Use SkyCoord to validate the input
        sc = SkyCoord(ra=ra, dec=dec, unit=(ra_unit, dec_unit), frame="icrs")
        return sc

    def get_radius(self) -> Quantity[u.deg]:
        """Retrieve the radius value from the input fields."""
        radius = self.radius_input.text()
        radius_unit = self.radius_unit_combo.currentText()
        if not radius:
            raise ValueError("Radius cannot be empty")

        return u.Quantity(radius, unit=radius_unit).to("deg")


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
    window.setWindowTitle("Region Model Example")
    model = CustomAbstractListModel()
    view = DropDownWithListView("List 1")
    view2 = DropDownWithListView("List 2")
    view.setModel(model)
    view2.setModel(model)
    # Add a circle
    circle = CircleRegion(SkyCoord(ra=0, dec=0, unit="deg"), 1 * u.deg)
    model.add_item(circle)
    # Add the 2 views to the window
    # layout = QVBoxLayout()
    # layout.addWidget(view)
    # layout.addWidget(view2)
    # widget = QWidget()
    # widget.setLayout(layout)
    # window.setCentralWidget(widget)
    qw = QWidget()
    qw.setLayout(QVBoxLayout())
    qw.layout().addWidget(view)
    qw.layout().addWidget(view2)
    # Add a spacer to fill vertical space when collapsed
    qw.layout().addStretch()
    window.setCentralWidget(qw)

    window.show()
    sys.exit(app.exec())
