from PyQt6.QtCore import QObject, QPoint, Qt, QTimer, pyqtSignal, QStringListModel

from PyQt6.QtGui import QBrush, QColor, QIcon, QKeySequence, QPixmap, QShortcut, QAction
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QTableView,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QDial,
    QSpinBox,
    QPushButton,
    QFrame,
    QSizePolicy,
    QLayout,
    QTableWidget,
)
import logging

log = logging.getLogger(__name__)


class DropDownWithListView(QWidget):
    """Custom widget that includes a list view with custom context menu and dropdown.

    This class provides a context menu for a QListView.
    When the user right-clicks on an item in the list, a context menu is shown.
    """

    contextMenuRequested = pyqtSignal(object, object)  # (index, event)

    def __init__(self, title="", parent=None):
        super().__init__(parent)
        # Size Policy

        # Toggle Button (Initially Points Right ▶)
        self.closed_text = f"▶ {title!s}"
        self.opened_text = f"▼ {title!s}"
        self.toggle_button = QPushButton(self.opened_text)
        self.toggle_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.toggle_button.setStyleSheet("text-align: left;")
        self.toggle_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.list_view = QListView()

        # Create a frame to act as the dropdown container
        self.dropdown_frame = QFrame()
        self.dropdown_layout = QVBoxLayout(self.dropdown_frame)
        self.dropdown_layout.setContentsMargins(0, 0, 0, 0)  # Remove padding inside the dropdown
        self.dropdown_layout.addWidget(self.list_view)
        self.dropdown_frame.setVisible(True)

        # Connect button click to toggle dropdown
        self.toggle_button.clicked.connect(self.toggle_dropdown)

        # Layout
        layout = QVBoxLayout(self)
        layout.setSpacing(0)  # Remove space between widgets
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.dropdown_frame)
        self.list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_view.customContextMenuRequested.connect(self.request_context_menu)

    def request_context_menu(self, position):
        """Detect right-click and emit a signal with the selected region."""
        index = self.list_view.indexAt(position)
        if not index.isValid():
            log.debug("Context menu requested outside of list view.")
            return
        log.debug(f"Context menu requested at index: {index.row()}")
        # item = index.data(Qt.ItemDataRole.UserRole)  # Fetch item
        self.contextMenuRequested.emit(index, self.list_view.mapToGlobal(position))

    def toggle_dropdown(self):
        """Toggle dropdown visibility and update caret direction."""
        is_open = self.dropdown_frame.isVisible()
        self.dropdown_frame.setVisible(not is_open)  # Show/hide frame

        # Update button text with caret indicator
        self.toggle_button.setText(self.opened_text if not is_open else self.closed_text)

    def setModel(self, model):
        self.list_view.setModel(model)


class DialWidget(QWidget):
    """Custom widget to select an angle with a dial and a spin box."""

    def __init__(self):
        super().__init__()

        # Create layout
        main_layout = QVBoxLayout()
        control_layout = QHBoxLayout()

        # Circular Dial
        self.dial = QDial()
        self.dial.setRange(0, 360)  # Set range from 0° to 360°
        self.dial.setNotchesVisible(True)  # Show notches
        self.dial.setWrapping(False)  # Prevent full rotation
        self.dial.setFixedSize(40, 40)  # Match UI size

        # Angle Spin Box
        self.angle_spinbox = QSpinBox()
        self.angle_spinbox.setSuffix("°")  # Add degree symbol
        self.angle_spinbox.setRange(0, 360)  # Set range from 0° to 360°
        self.angle_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center align text

        # Connect dial and spin box
        self.dial.valueChanged.connect(self.angle_spinbox.setValue)
        self.angle_spinbox.valueChanged.connect(self.dial.setValue)

        # Label Below
        self.label = QLabel("Angle")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Add widgets to layouts
        control_layout.addWidget(self.dial)
        control_layout.addWidget(self.angle_spinbox)

        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.label)

        # Set final layout
        self.setLayout(main_layout)


class CoordinatesTable(QTableWidget):
    """Create a table widget to display real-time coordinate data."""

    def __init__(self):
        super().__init__(5, 5)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setVisible(False)

        # # Set the font to Computer Modern or equivalent
        # cm_font = QFont("CMU Serif")  # Try "STIXGeneral" or "CMU Serif" if unavailable
        # # cm_font.setPointSize(12)  # Adjust the font size
        # table.setFont(cm_font)

        # Populate the table with initial values
        self.setItem(0, 0, QTableWidgetItem("Name"))
        self.setItem(1, 0, QTableWidgetItem("Value"))
        self.setItem(2, 0, QTableWidgetItem("ICRS"))
        self.setItem(3, 0, QTableWidgetItem("Galactic"))
        self.setItem(4, 0, QTableWidgetItem("Image"))
        name = QTableWidgetItem("")
        self.setItem(0, 1, name)
        self.setSpan(0, 1, 1, 4)

        self.setItem(2, 1, QTableWidgetItem("α"))
        self.setItem(2, 3, QTableWidgetItem("δ"))
        self.setItem(3, 1, QTableWidgetItem("l"))
        self.setItem(3, 3, QTableWidgetItem("b"))
        self.setItem(4, 1, QTableWidgetItem("x"))
        self.setItem(4, 3, QTableWidgetItem("y"))

        # Set alignment and make cells non-editable
        for row in range(4):
            for col in range(4):
                item = self.item(row, col)
                if not item:
                    self.setItem(row, col, QTableWidgetItem(""))
                self.item(row, col).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.item(row, col).setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        # Autoscale column widths to fit content
        self.resizeColumnToContents(0)
        self.resizeColumnToContents(1)
        self.resizeColumnToContents(3)
        self.resizeRowsToContents()

        # Set the height of the table to fit its content
        self.setFixedHeight(int(self.sizeHint().height() / 1.6))
        self.setFixedWidth(int(1.2 * self.sizeHint().width()))

    def update_coordinates(self, dict_values):
        """Update the table with new values."""
        pixel_value = dict_values.get("pixel_value", None)
        pixel_unit = dict_values.get("pixel_unit", None)
        ra = dict_values.get("ra", None)
        dec = dict_values.get("dec", None)
        gal_lon = dict_values.get("gal_lon", None)
        gal_lat = dict_values.get("gal_lat", None)
        x = dict_values.get("x", None)
        y = dict_values.get("y", None)
        self.setItem(0, 1, QTableWidgetItem(f"{dict_values.get('name', '')}"))
        self.setItem(1, 2, QTableWidgetItem(f"{pixel_value:.6e}" if pixel_value is not None else ""))
        self.setItem(1, 4, QTableWidgetItem(f"{pixel_unit}" if pixel_unit is not None else ""))
        self.setItem(2, 2, QTableWidgetItem(f"{ra:.6f}" if ra is not None else ""))
        self.setItem(2, 4, QTableWidgetItem(f"{dec:.6f}" if dec is not None else ""))
        self.setItem(3, 2, QTableWidgetItem(f"{gal_lon:.6f}" if gal_lon is not None else ""))
        self.setItem(3, 4, QTableWidgetItem(f"{gal_lat:.6f}" if gal_lat is not None else ""))
        self.setItem(4, 2, QTableWidgetItem(f"{x:.1f}" if x is not None else ""))
        self.setItem(4, 4, QTableWidgetItem(f"{y:.1f}" if y is not None else ""))


if __name__ == "__main__":
    app = QApplication([])
    # Create a simple example with a QMainWindow and a ListViewWithContextMenu
    window = QMainWindow()
    window.setWindowTitle("List Widget with Context Menu")
    # Create a simple model
    model = QStringListModel()
    model.setStringList(["Item 1", "Item 2", "Item 3"])

    def on_context_menu(item, event):
        menu = QMenu()
        open_action = menu.addAction("Open")
        delete_action = menu.addAction("Delete")

        action = menu.exec(event)
        if action == open_action:
            print("Open action")
        elif action == delete_action:
            print("Delete action")
        print("Received context menu click", item, event)

    # Create a list widget
    ddw = DropDownWithListView("Test")
    ddw.list_view.setModel(model)
    ddw.contextMenuRequested.connect(on_context_menu)
    ddw2 = DropDownWithListView("Test2")
    ddw2.list_view.setModel(model)
    ddw2.contextMenuRequested.connect(on_context_menu)
    qw = QWidget()
    qw.setLayout(QVBoxLayout())
    qw.layout().addWidget(ddw)

    qw.layout().addWidget(ddw2)

    # Dial
    dial_widget = DialWidget()
    qw.layout().addWidget(dial_widget)

    qw.layout().addStretch()
    qw.layout().setSpacing(0)
    window.setCentralWidget(qw)

    window.show()
    app.exec()
