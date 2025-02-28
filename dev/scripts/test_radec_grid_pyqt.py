import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from astropy.io import fits
from astropy.wcs import WCS


class WCSImageViewer(QWidget):
    def __init__(self, fits_file):
        """Initialize viewer with a FITS image and overlay RA/DEC grid."""
        super().__init__()
        self.fits_file = fits_file

        # Load FITS image and WCS
        self.hdu = fits.open(self.fits_file)[0]
        self.wcs = WCS(self.hdu.header)
        self.image_data = self.hdu.data

        # Create PyQtGraph ImageView
        self.image_view = pg.ImageView()
        self.image_view.setImage(self.image_data.T)  # PyQtGraph expects transposed images

        # Overlay RA/DEC Grid Lines
        self.add_ra_dec_grid()

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.image_view)

    def add_ra_dec_grid(self):
        """Add RA/DEC grid lines to the image."""
        ra_ticks = np.linspace(self.wcs.wcs.crval[0] - 0.5, self.wcs.wcs.crval[0] + 0.5, 5)  # Example RA grid
        dec_ticks = np.linspace(self.wcs.wcs.crval[1] - 0.5, self.wcs.wcs.crval[1] + 0.5, 5)  # Example DEC grid

        # Convert RA grid to pixel coordinates
        for ra in ra_ticks:
            pixel_x, pixel_y1 = self.wcs.all_world2pix([[ra, dec_ticks[0]]], 0)[0]
            _, pixel_y2 = self.wcs.all_world2pix([[ra, dec_ticks[-1]]], 0)[0]
            line = pg.InfiniteLine(pos=pixel_x, angle=90, pen="r")  # Vertical RA line
            self.image_view.addItem(line)

        # Convert DEC grid to pixel coordinates
        for dec in dec_ticks:
            pixel_x1, pixel_y = self.wcs.all_world2pix([[ra_ticks[0], dec]], 0)[0]
            pixel_x2, _ = self.wcs.all_world2pix([[ra_ticks[-1], dec]], 0)[0]
            line = pg.InfiniteLine(pos=pixel_y, angle=0, pen="b")  # Horizontal DEC line
            self.image_view.addItem(line)


# PyQt Application
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQtGraph WCS Image with RA/DEC Grid")
        self.setGeometry(100, 100, 800, 600)

        # Load and display the FITS image with RA/DEC grid
        self.viewer = WCSImageViewer("~/Downloads/1storb_R_com.fits")
        # self.viewer = WCSImageViewer("~/Desktop/ls_img.fits")
        self.setCentralWidget(self.viewer)


# Run Application
app = QApplication([])
window = MainWindow()
window.show()
app.exec()
