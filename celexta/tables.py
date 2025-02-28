import logging

from pathlib import Path
import astropy.units as u
import matplotlib.pyplot as plt
import numpy as np
import zhunter.catalogs as cat
from astropy.table import Table
from astropy.wcs import WCS
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import (
    QAbstractTableModel,
    QItemSelectionModel,
    QModelIndex,
    QObject,
    QPoint,
    Qt,
    pyqtSignal,
)
from PyQt6.QtCore import Qt, QTimer, QSettings, QObject, pyqtSignal, QAbstractListModel, QModelIndex
from PyQt6.QtGui import QBrush, QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QMainWindow,
    QMenu,
    QTableView,
    QVBoxLayout,
    QWidget,
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

from celexta.aesthetics import create_icon, ColorManager
from matplotlib.colors import to_hex
from celexta.abstract_models import CustomAbstractListModel
from celexta.widgets import DropDownWithListView

log = logging.getLogger(__name__)


class CustomTable:
    """Encapsulates an Astropy Table with some extra info."""

    def __init__(
        self,
        data: Table,
        name=None,
        color=None,
    ):
        self.name = name if name is not None else "Table"
        self.data = data  # Astropy Table
        self.color = to_hex(color) if color is not None else None

    def __str__(self):
        """Return a string representation of the CustomTable."""
        return f"CustomTable(name={self.name}, color={self.color}, len={len(self.data):d})"

    def to_serializable_dict(self, save_dir: Path | str):
        """Return a JSON-serializable dictionary of the CustomTable."""
        fname = Path(save_dir) / f"{str(self.name).replace(' ','_')}.fits"
        log.debug(f"Saving table data to: {fname!s}")
        self.data.write(fname, overwrite=True)
        return {
            "name": str(self.name),
            "color": str(to_hex(self.color)),
            "data": str(fname.expanduser().resolve()),
        }

    @classmethod
    def from_serializable_dict(cls, data: dict):
        """Update the CustomTable from a JSON-serializable dictionary."""
        table = cls(
            name=data["name"],
            color=data["color"],
            data=Table.read(data["data"]),
        )
        log.debug(f"Loaded table from JSON: {table!s}")
        return table


class TableModel(QAbstractTableModel):
    """A simple table model that wraps a `CustomTable` so it can be displayed in a QTableView."""

    def __init__(self, table: CustomTable, parent=None):
        """Initialize the model.

        Parameters
        ----------
        table : celexta.tables.AstropyTable
            The Astropy Table to be displayed.
        parent : QObject
            The parent object.
        """
        super().__init__(parent)
        self.table = table

    def rowCount(self, parent=QModelIndex()):
        """Return the number of rows in the Astropy table."""
        return len(self.table.data)

    def columnCount(self, parent=QModelIndex()):
        """Return the number of columns (i.e. the number of column names)."""
        return len(self.table.data.colnames)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """Return the data to be displayed at the given index.

        For the DisplayRole, we convert the value to a string.
        """
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            row = index.row()
            col = index.column()
            # Get the column name from the astropy Table
            colname = self.table.data.colnames[col]
            # Get the value at that row and column.
            value = self.table.data[colname][row]
            # If float, format it to 6 decimal places.
            if isinstance(value, float):
                # Use scientific notation if the value is too large or too small.
                if np.abs(value) > 1e3 or np.abs(value) < 1e-3:
                    return f"{value:.5e}"
                return f"{value:.6f}"
            return f"{value}"
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        """Return header data.

        For horizontal headers, we return the column names.
        For vertical headers, we simply return the row number.
        """
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == Qt.Orientation.Horizontal:
            # Return the column name.
            return self.table.data.colnames[section]
        # Return row numbers.
        return str(section)


class GlobalTableModel(QAbstractListModel):
    """Model to manage the various tables in a given tab.

    Each table is actually an CustomTable object, which wraps
    an Astropy Table.
    """

    selectionChanged = pyqtSignal(object)  # (CustomTable)
    visibilityChanged = pyqtSignal(list)  # (bool, CustomTable)
    itemRemoved = pyqtSignal(object)  # (CustomTable)
    itemUpdated = pyqtSignal(object)  # (CustomTable)

    def __init__(self, parent=None, tables=None):
        super().__init__(parent)
        self.tables = tables if tables is not None else []
        self.visibility = {table: True for table in self.tables}  # Track visibility
        self.selected_table = None  # Track selected table

    def rowCount(self, parent=None):
        """Return the number of tables."""
        return len(self.tables)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """Return the data for each table in the list."""
        if not index.isValid():
            return None
        table = self.tables[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:  # Display name
            return table.name
        if role == Qt.ItemDataRole.DecorationRole:  # Display color
            return QColor(table.color)
        if role == Qt.ItemDataRole.CheckStateRole:  # Checkbox for visibility
            state = Qt.CheckState.Checked if self.visibility[table] else Qt.CheckState.Unchecked
            return state
        if role == Qt.ItemDataRole.UserRole:
            return table
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
            table = self.tables[index.row()]
            new_state = value == Qt.CheckState.Checked.value
            # Check if the state is changing
            if self.visibility.get(table, True) != new_state:
                self.visibility[table] = new_state
                self.visibilityChanged.emit([new_state, table])
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
                return True
        return False

    def add_table(self, table):
        """Add a new table to the model."""
        if table in self.tables:
            return
        row = len(self.tables)
        self.insertRow(row, table=table)

    def insertRow(self, row, table, parent=QModelIndex()):
        """Insert a new row into the model."""
        if isinstance(row, QModelIndex):  # Ensure row is an integer
            row = row.row()

        if row < 0 or row > len(self.tables):  # Ensure valid index
            return False
        # Finer grained that layoutChanged.emit()
        # Use QModelIndex() to indicate the parent is the root
        # i.e. no hierarchy for list models
        self.beginInsertRows(parent, row, row)
        self.tables.insert(row, table)
        self.visibility[table] = True
        log.debug(f"Added table: {table!s}")
        if table.color is None:
            table.color = "red"
            log.warning("Table color not set. Defaulting to red.")

        # Notify views that the row insertion is complete.
        self.endInsertRows()
        return True

    def delete_table(self, table):
        """Delete a table from the model."""
        if table not in self.tables:
            return
        row = self.get_index(table)
        self.removeRow(row)

    def removeRow(self, row, parent=QModelIndex()):
        """Remove a row from the model."""
        if isinstance(row, QModelIndex):  # Ensure row is an integer
            row = row.row()
        if row < 0 or row >= len(self.tables):
            return False
        table = self.tables[row]
        self.beginRemoveRows(parent, row, row)
        self.visibility.pop(table, None)
        del self.tables[row]
        log.info(f"Deleted table: {table!s}")
        self.endRemoveRows()
        self.itemRemoved.emit(table)
        return True

    def select_table(self, table):
        """Select a table and emit signal."""
        if table is not self.selected_table:
            log.debug(f"Selecting table: {table!s}")
            self.selected_table = table
            self.selectionChanged.emit(table)

    def get_index(self, table):
        """Return the QModelIndex of the given table, or an invalid index if not found."""
        try:
            row = self.tables.index(table)
            return self.createIndex(row, 0)
        except ValueError:
            return QModelIndex()

    def update_table(self, table, name=None, color=None):
        """Update the properties of a table."""
        log.debug(f"Updated table: {table!s}")
        if name is not None:
            table.name = name
        if color is not None:
            table.color = color

        # Emit dataChanged signal to update the views
        index = self.get_index(table)
        self.dataChanged.emit(index, index)
        self.itemUpdated.emit(table)


class TableEditor(QDialog):
    """Popup to edit table properties (name, color)."""

    def __init__(self, table=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Table Properties")

        defaults = {
            "name": "",
            "color": "red",
        }
        # Update defaults with table data
        if table:
            defaults.update(
                {
                    "name": table.name,
                    "color": table.color,
                }
            )

        main_layout = QVBoxLayout(self)
        grid_layout = self.create_grid_layout(defaults)
        main_layout.addLayout(grid_layout)
        # Save/Cancel Buttons
        button_layout = QHBoxLayout()
        save_button = QPushButton("Ok")
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

        # Color Input
        self.color_input = QLineEdit(defaults["color"])
        grid_layout.addWidget(QLabel("Color:"), 1, 0)
        grid_layout.addWidget(self.color_input, 1, 1)

        return grid_layout

    def get_values(self):
        """Retrieve user-input values."""
        return {
            "color": to_hex(self.color_input.text()),
            "name": self.name_input.text(),
        }


class TableViewDialog(QDialog):
    """Pop-up table view for a selected CustomTable."""

    def __init__(self, table: CustomTable, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Table View - {table.name}")
        self.setGeometry(200, 200, 600, 400)
        self.table = table

        layout = QVBoxLayout(self)

        # Create a table view with the table data
        self.table_view = QTableView(parent=self)
        self.model = TableModel(self.table, parent=self)
        self.table_view.setModel(self.model)
        layout.addWidget(self.table_view)

        # Change selection mode to allow multiple rows to be selected
        self.table_view.setSelectionMode(QTableView.SelectionMode.MultiSelection)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        # self.table.selection_changed.connect(self.update_selection)

    def update_selection(self, selected_idx):
        """Update the table view selection to match the CustomTable selection."""
        selection_model = self.table_view.selectionModel()
        if selection_model:
            selection_model.clearSelection()  # Clear previous selection
            for row_idx in selected_idx:
                index = self.model.index(row_idx, 0)  # Get index for first column
                selection_model.select(
                    index, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
                )

    def closeEvent(self, event):
        """Reset reference when the dialog is closed so it can be reopened."""
        self.table.dialog = None  # Allow reopening
        event.accept()


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
    # Main Widow
    window = QMainWindow()
    window.setWindowTitle("Table Model Example")

    # Model
    # model = GlobalTableModel()
    model = CustomAbstractListModel()
    # Views
    view = DropDownWithListView("List 1")
    view2 = DropDownWithListView("List 2")
    view.setModel(model)
    view2.setModel(model)

    # Add a table
    table = CustomTable(data=Table({"x": [1, 2, 3], "y": [4, 5, 6]}), name="Tab1")
    model.add_item(table)
    # Add the 2 views to the window
    layout = QVBoxLayout()
    layout.addWidget(
        QPushButton(
            "Add Table",
            clicked=lambda: model.add_item(CustomTable(data=Table({"x": [1, 2, 3], "y": [4, 5, 6]}), name="Tab2")),
        )
    )

    layout.addWidget(view)
    layout.addWidget(view2)
    layout.addStretch()

    # Set the layout
    widget = QWidget()
    widget.setLayout(layout)
    window.setCentralWidget(widget)
    window.show()
    sys.exit(app.exec())
