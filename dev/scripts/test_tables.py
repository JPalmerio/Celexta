import sys

import astropy.units as u
import matplotlib.pyplot as plt
import numpy as np
import zhunter.catalogs as cat
from astropy.table import Table
from astropy.wcs import WCS
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
from PyQt6.QtGui import QBrush, QColor, QPixmap, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QMenu,
    QTableView,
    QVBoxLayout,
    QWidget,
    QListWidgetItem,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas


def mpl_rbga_to_pyqt_color(color: list[float, float, float, float]) -> QColor:
    """Convert a matplotlib RGBA color to a PyQt QColor."""
    return QColor(*[int(255 * c) for c in color[:4]])


from PyQt6.QtWidgets import QGroupBox, QVBoxLayout


class ScatterPlotWidget(QWidget):
    """Widget containing a Matplotlib scatter plot and list widget inside a titled group box."""

    def __init__(self):
        super().__init__()

        self.tables = {}  # Dictionary of InteractiveTables

        # Main Layout
        main_layout = QVBoxLayout(self)

        # Create a group box to contain the list
        self.table_group_box = QGroupBox("Available Tables")
        group_layout = QVBoxLayout(self.table_group_box)

        # List Widget for Tables
        self.table_list_widget = QListWidget()
        group_layout.addWidget(self.table_list_widget)

        self.table_group_box.setLayout(group_layout)
        main_layout.addWidget(self.table_group_box)

        self.setLayout(main_layout)


from PyQt6.QtWidgets import QLabel, QVBoxLayout


class ScatterPlotWidget2(QWidget):
    """Widget containing a Matplotlib scatter plot and list widget with a title."""

    def __init__(self):
        super().__init__()

        self.tables = {}  # Dictionary of InteractiveTables

        # Main Layout
        main_layout = QVBoxLayout(self)

        # Create a title label
        self.table_list_title = QLabel("Available Tables")
        self.table_list_title.setStyleSheet("font-weight: bold; font-size: 14px;")  # Optional styling
        main_layout.addWidget(self.table_list_title)

        # List Widget for Tables
        self.table_list_widget = QListWidget()
        main_layout.addWidget(self.table_list_widget)

        self.setLayout(main_layout)


class MainWindow(QMainWindow):
    """Main application window containing the scatter plot and table list."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Interactive Astropy Table & Scatter Plot")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = ScatterPlotWidget2()
        self.setCentralWidget(self.central_widget)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
