import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton
from PyQt6.QtGui import QTransform


class ImageFlipper(QWidget):
    def __init__(self, image_data):
        """Initialize the widget with an image and buttons to flip."""
        super().__init__()
        self.image_data = image_data
        self.flipped_x = False  # Track flip state along X-axis
        self.flipped_y = False  # Track flip state along Y-axis

        # Create PyQtGraph ImageView
        self.image_view = pg.ImageView()
        self.image_view.setImage(self.image_data.T)  # PyQtGraph expects transposed images

        # Buttons to flip the image
        self.flip_x_button = QPushButton("Flip X")
        self.flip_y_button = QPushButton("Flip Y")

        # Connect buttons to their respective flip functions
        self.flip_x_button.clicked.connect(self.flip_x)
        self.flip_y_button.clicked.connect(self.flip_y)

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.image_view)
        layout.addWidget(self.flip_x_button)
        layout.addWidget(self.flip_y_button)

        # Get the ViewBox for transformations
        self.view = self.image_view.getView()

    def flip_x(self):
        """Flip the image along the X-axis."""
        self.flipped_x = not self.flipped_x  # Toggle flip state
        self.apply_transform()

    def flip_y(self):
        """Flip the image along the Y-axis."""
        self.flipped_y = not self.flipped_y  # Toggle flip state
        self.apply_transform()

    def apply_transform(self):
        """Apply the flipping transformations and re-center the view."""
        # Reset the transformation
        self.view.resetTransform()

        # Create a new QTransform
        transform = QTransform()

        # Apply scaling for flipping
        scale_x = -1 if self.flipped_x else 1
        scale_y = -1 if self.flipped_y else 1
        transform.scale(scale_x, scale_y)

        # Apply the transform to the ViewBox
        self.view.setTransform(transform)

        # Get the image dimensions
        height, width = self.image_data.shape

        # Adjust the ranges to keep the flipped image centered
        x_min, x_max = (0, width) if not self.flipped_x else (width, 0)
        y_min, y_max = (0, height) if not self.flipped_y else (height, 0)

        # Re-center the view
        self.view.setRange(xRange=(x_min, x_max), yRange=(y_min, y_max), padding=0)


# PyQt Application
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQtGraph Image Flipper")
        self.setGeometry(100, 100, 800, 600)

        # Example image data (random array)
        image_data = np.random.rand(100, 100)

        # Load and display the ImageFlipper widget
        self.viewer = ImageFlipper(image_data)
        self.setCentralWidget(self.viewer)


# Run Application
app = QApplication([])
window = MainWindow()
window.show()
app.exec()
