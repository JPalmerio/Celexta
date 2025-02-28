import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from astropy.io import fits
from astropy.wcs import WCS


class WCSImageViewer(QWidget):
    def __init__(self, fits_file):
        """Initialize viewer with a FITS image and overlay directional arrows."""
        super().__init__()
        self.fits_file = fits_file

        # Load FITS image and WCS
        self.hdu = fits.open(self.fits_file)[1]
        self.wcs = WCS(self.hdu.header)
        self.image_data = self.hdu.data

        # Extract WCS CD matrix
        cd = self.wcs.wcs.cd if self.wcs.wcs.has_cd() else self.wcs.pixel_scale_matrix

        # Compute angles for directions
        self.angle_north = np.arctan2(cd[1, 1], cd[0, 1]) * 180 / np.pi  # North direction
        self.angle_east = np.arctan2(cd[1, 0], cd[0, 0]) * 180 / np.pi  # East direction

        # Create PyQtGraph ImageView
        self.image_view = pg.ImageView()
        self.image_view.setImage(self.image_data.T)  # PyQtGraph expects transposed images

        # Overlay directional arrows
        self.add_directional_arrows()

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.image_view)

    def add_directional_arrows(self):
        """Add arrows for North, East, +X, and +Y directions."""
        arrow_size = 20  # Arrow size in pixels

        # Add North arrow
        north_arrow = pg.ArrowItem(angle=-self.angle_north, pen="y", brush="y", headLen=10)
        north_arrow.setPos(self.image_data.shape[1] * 0.1, self.image_data.shape[0] * 0.1)
        self.image_view.addItem(north_arrow)
        self.add_text("N", north_arrow.pos() + pg.QtCore.QPointF(0, -arrow_size))

        # Add East arrow
        east_arrow = pg.ArrowItem(angle=-self.angle_east, pen="y", brush="y", headLen=10)
        east_arrow.setPos(self.image_data.shape[1] * 0.1, self.image_data.shape[0] * 0.1)
        self.image_view.addItem(east_arrow)
        self.add_text("E", east_arrow.pos() + pg.QtCore.QPointF(arrow_size, 0))

        # Add +X arrow (always horizontal)
        x_arrow = pg.ArrowItem(angle=0, pen="c", brush="c", headLen=10)
        x_arrow.setPos(self.image_data.shape[1] * 0.1, self.image_data.shape[0] * 0.1 + 20)
        self.image_view.addItem(x_arrow)
        self.add_text("+X", x_arrow.pos() + pg.QtCore.QPointF(arrow_size, 0))

        # Add +Y arrow (always vertical)
        y_arrow = pg.ArrowItem(angle=90, pen="c", brush="c", headLen=10)
        y_arrow.setPos(self.image_data.shape[1] * 0.1, self.image_data.shape[0] * 0.1 + 20)
        self.image_view.addItem(y_arrow)
        self.add_text("+Y", y_arrow.pos() + pg.QtCore.QPointF(0, -arrow_size))

    def add_text(self, text, position):
        """Add text to the image at a given position."""
        text_item = pg.TextItem(text, anchor=(0.5, 0.5), color="y")
        text_item.setPos(position.x(), position.y())
        self.image_view.addItem(text_item)


# PyQt Application
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQtGraph WCS Image with Directional Arrows")
        self.setGeometry(100, 100, 800, 600)

        # Load and display the FITS image with directional arrows
        self.viewer = WCSImageViewer("~/Desktop/qimb0.fits")  # Replace with your actual FITS file
        self.setCentralWidget(self.viewer)


# Run Application
app = QApplication([])
window = MainWindow()
window.show()
app.exec()
