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
from celexta.aesthetics import ColorManager

log = logging.getLogger(__name__)


class CustomAbstractListModel(QAbstractListModel):
    """Model to manage lists of items"""

    visibilityChanged = pyqtSignal(list)  # [bool, item]
    itemRemoved = pyqtSignal(object)  # item
    itemUpdated = pyqtSignal(object)  # item

    def __init__(self, parent=None, items=None):
        super().__init__(parent)
        self.items = items if items is not None else []
        self.visibility = {item: True for item in self.items}  # Track visibility

    def rowCount(self, parent=None):
        """Return the number of items."""
        return len(self.items)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """Return the data for each item in the list."""
        if not index.isValid():
            return None
        item = self.items[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:  # Display name
            return item.name
        if role == Qt.ItemDataRole.DecorationRole:  # Display color
            if hasattr(item, "color"):
                return QColor(item.color)
            return None
        if role == Qt.ItemDataRole.CheckStateRole:  # Checkbox for visibility
            state = Qt.CheckState.Checked if self.visibility[item] else Qt.CheckState.Unchecked
            return state
        if role == Qt.ItemDataRole.UserRole:
            return item
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
            item = self.items[index.row()]
            new_state = value == Qt.CheckState.Checked.value
            # Check if the state is changing
            if self.visibility.get(item, True) != new_state:
                self.visibility[item] = new_state
                self.visibilityChanged.emit([new_state, item])
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
                return True
        return False

    def add_item(self, item):
        """Add a new item to the model."""
        log.debug(f"Trying to add item: {item!s}")
        if item in self.items:
            log.debug("Item already exists, ignoring")
            return
        row = len(self.items)
        self.insertRow(row, item)

    def insertRow(self, row, item):
        """Insert a row into the model."""
        if isinstance(row, QModelIndex):  # Ensure row is an integer
            row = row.row()
        if row < 0 or row > len(self.items):
            log.debug("Invalid row, ignoring")
            return False
        # Finer grained that layoutChanged.emit()
        # Use QModelIndex() to indicate the parent is the root
        # i.e. no hierarchy for list models
        self.beginInsertRows(QModelIndex(), row, row)
        self.items.append(item)
        self.visibility[item] = True
        log.debug(f"Added item: {item!s}")
        if hasattr(item, "color") and item.color is None:
            item.color = "red"
            log.warning("Item color not set. Defaulting to red.")
        # Notify views that the row insertion is complete.
        self.endInsertRows()
        return True

    def delete_item(self, item):
        """Delete a item from the model."""
        row = self.get_index(item)
        self.removeRow(row)

    def removeRow(self, row, parent=QModelIndex()):
        """Remove a row from the model."""
        if isinstance(row, QModelIndex):  # Ensure row is an integer
            row = row.row()
        if row < 0 or row > len(self.items):
            log.debug("Invalid row, ignoring")
            return False
        item = self.items[row]
        self.beginRemoveRows(parent, row, row)
        self.visibility.pop(item, None)
        del self.items[row]
        log.debug(f"Deleted item: {item!s}")
        self.endRemoveRows()
        self.itemRemoved.emit(item)
        return True

    def get_index(self, item):
        """Return the QModelIndex of the given item, or an invalid index if not found."""
        try:
            row = self.items.index(item)
            return self.createIndex(row, 0)
        except ValueError:
            return QModelIndex()

    def update_item(self, item, **args):
        """Update the properties of a item."""
        log.debug(f"Updated item: {item!s}")
        for key, value in args.items():
            if hasattr(item, key):
                setattr(item, key, value)
        # Emit dataChanged signal to update the views
        index = self.get_index(item)
        self.dataChanged.emit(index, index)
        self.itemUpdated.emit(item)
