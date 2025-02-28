import sys
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QListView,
    QWidget,
    QPushButton,
    QDialog,
    QFormLayout,
    QLineEdit,
    QSpinBox,
)
from PyQt6.QtCore import Qt, QAbstractListModel, QModelIndex, pyqtSignal


# ----------------- Model -----------------
class CircleRegion:
    """Represents a circular region with a name, position, and radius."""

    def __init__(self, name, x, y, radius, visible=True):
        self.name = name
        self.x = x
        self.y = y
        self.radius = radius
        self.visible = visible  # Determines if the circle is shown in frames


class CircleRegionModel(QAbstractListModel):
    """Model that manages CircleRegions and notifies views of changes."""

    def __init__(self, circles=None):
        super().__init__()
        self.circles = circles if circles else []

    def rowCount(self, parent=QModelIndex()):
        return len(self.circles)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        circle = self.circles[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return circle.name
        if role == Qt.ItemDataRole.CheckStateRole:
            return Qt.CheckState.Checked if circle.visible else Qt.CheckState.Unchecked
        return None

    def flags(self, index):
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable

    def setData(self, index, value, role=Qt.ItemDataRole.CheckStateRole):
        """Toggle visibility of a circle."""
        if index.isValid() and role == Qt.ItemDataRole.CheckStateRole:
            circle = self.circles[index.row()]
            circle.visible = value == Qt.CheckState.Checked
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            return True
        return False

    def add_circle(self, circle):
        """Add a new circle and notify views."""
        self.beginInsertRows(QModelIndex(), len(self.circles), len(self.circles))
        self.circles.append(circle)
        self.endInsertRows()

    def remove_circle(self, index):
        """Remove a circle from the model."""
        if 0 <= index < len(self.circles):
            self.beginRemoveRows(QModelIndex(), index, index)
            del self.circles[index]
            self.endRemoveRows()


# ----------------- Edit Dialog -----------------
class CircleEditDialog(QDialog):
    """Dialog to edit a CircleRegion's properties."""

    def __init__(self, circle, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Circle")

        self.circle = circle
        layout = QFormLayout(self)

        self.name_input = QLineEdit(circle.name)
        self.x_input = QSpinBox()
        self.x_input.setValue(circle.x)
        self.y_input = QSpinBox()
        self.y_input.setValue(circle.y)
        self.radius_input = QSpinBox()
        self.radius_input.setValue(circle.radius)

        layout.addRow("Name:", self.name_input)
        layout.addRow("X:", self.x_input)
        layout.addRow("Y:", self.y_input)
        layout.addRow("Radius:", self.radius_input)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        layout.addRow(save_btn)

    def get_data(self):
        """Return edited circle data."""
        return {
            "name": self.name_input.text(),
            "x": self.x_input.value(),
            "y": self.y_input.value(),
            "radius": self.radius_input.value(),
        }


# ----------------- ImageFrame -----------------
class ImageFrame(pg.GraphicsLayoutWidget):
    """An image frame that can display circles."""

    def __init__(self):
        super().__init__()
        self.view = self.addViewBox()
        self.view.setAspectLocked(True)
        self.image = pg.ImageItem(np.random.normal(size=(100, 100)))  # Example image
        self.view.addItem(self.image)
        self.circles = {}  # Map circles to plot items

    def add_circle(self, circle):
        """Add a circle to the image."""
        if circle in self.circles:
            return  # Prevent duplicate circles
        plot_circle = pg.ScatterPlotItem([circle.x], [circle.y], size=circle.radius, brush="r")
        self.view.addItem(plot_circle)
        self.circles[circle] = plot_circle

    def remove_circle(self, circle):
        """Remove a circle from the frame."""
        if circle in self.circles:
            self.view.removeItem(self.circles.pop(circle))

    def update_visibility(self, model):
        """Toggle visibility of circles based on the model."""
        for i, circle in enumerate(model.circles):
            if circle in self.circles:
                self.circles[circle].setVisible(circle.visible)


# ----------------- Main Window -----------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Circle Manager")
        self.setGeometry(100, 100, 800, 600)

        # Create model & list view
        self.circle_model = CircleRegionModel()
        self.circle_list = QListView()
        self.circle_list.setModel(self.circle_model)
        self.circle_list.clicked.connect(self.update_frames_visibility)

        # Create two ImageFrames
        self.frame1 = ImageFrame()
        self.frame2 = ImageFrame()

        # Buttons
        self.add_btn = QPushButton("Add Circle")
        self.del_btn = QPushButton("Delete Circle")
        self.edit_btn = QPushButton("Edit Circle")

        self.add_btn.clicked.connect(self.add_circle)
        self.del_btn.clicked.connect(self.delete_circle)
        self.edit_btn.clicked.connect(self.edit_circle)

        # Layout
        center_widget = QWidget()
        layout = QHBoxLayout(center_widget)

        frame_layout = QVBoxLayout()
        frame_layout.addWidget(self.frame1)
        frame_layout.addWidget(self.frame2)

        list_layout = QVBoxLayout()
        list_layout.addWidget(self.circle_list)
        list_layout.addWidget(self.add_btn)
        list_layout.addWidget(self.del_btn)
        list_layout.addWidget(self.edit_btn)

        layout.addLayout(frame_layout, 2)
        layout.addLayout(list_layout, 1)
        self.setCentralWidget(center_widget)

    def add_circle(self):
        """Add a new circle and update the UI."""
        circle = CircleRegion(f"Circle {len(self.circle_model.circles) + 1}", 50, 50, 10)
        self.circle_model.add_circle(circle)
        self.frame1.add_circle(circle)  # Add to the focused frame
        self.update_frames_visibility()

    def delete_circle(self):
        """Remove selected circle."""
        index = self.circle_list.currentIndex().row()
        if index >= 0:
            circle = self.circle_model.circles[index]
            self.circle_model.remove_circle(index)
            self.frame1.remove_circle(circle)
            self.frame2.remove_circle(circle)

    def edit_circle(self):
        """Edit selected circle."""
        index = self.circle_list.currentIndex().row()
        if index >= 0:
            circle = self.circle_model.circles[index]
            dialog = CircleEditDialog(circle)
            if dialog.exec():
                new_data = dialog.get_data()
                circle.name = new_data["name"]
                circle.x, circle.y, circle.radius = new_data["x"], new_data["y"], new_data["radius"]
                self.circle_model.dataChanged.emit(self.circle_model.index(index, 0), self.circle_model.index(index, 0))
                self.update_frames_visibility()

    def update_frames_visibility(self):
        """Sync circle visibility between frames and the model."""
        self.frame1.update_visibility(self.circle_model)
        self.frame2.update_visibility(self.circle_model)


# Run
app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec())
