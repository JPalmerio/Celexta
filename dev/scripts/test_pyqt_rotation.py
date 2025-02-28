import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QDial
from astropy.io import fits
from astropy.wcs import WCS
from scipy.ndimage import rotate
from astropy.visualization import ZScaleInterval
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QDial
from PyQt6.QtGui import QTransform


class WCSImageViewer(QWidget):
    def __init__(self, fits_file, ra_dec):
        """
        Initialize the viewer with a FITS image and an RA/DEC point.

        :param fits_file: Path to the FITS file.
        :param ra_dec: (RA, DEC) tuple of the point to overlay.
        """
        super().__init__()
        self.fits_file = fits_file
        self.ra_dec = ra_dec  # RA/DEC of the point to plot

        # Load FITS image and WCS
        self.hdu = fits.open(self.fits_file)[1]
        self.wcs = WCS(self.hdu.header)
        # Realign image
        if hasattr(self.wcs.wcs, "cd"):
            rot_matrix = self.wcs.wcs.cd
        elif hasattr(self.wcs.wcs, "pc"):
            rot_matrix = self.wcs.wcs.pc
        else:
            raise ValueError("Could not find rotation matrix in wcs")
        det = np.linalg.det(rot_matrix)
        # REverse the y axis
        if det > 0:
            print("Fixing CD matrix")
            self.wcs.wcs.cd[1, 1] = -self.wcs.wcs.cd[1, 1]
            self.hdu.data = self.hdu.data[:, ::-1]
        self.image_data = self.hdu.data
        self.rotated_data = self.image_data  # Holds rotated image
        self.rotation_angle = 0  # Initial rotation angle

        # Convert RA/DEC to pixel coordinates
        self.point_pixel = self.wcs.all_world2pix([self.ra_dec], 0)[0]  # (x, y) pixel position

        # Create PyQtGraph ImageView
        self.image_view = pg.ImageView()
        print(type(self.image_view))
        self.image_view.setImage(self.image_data.T)  # PyQtGraph expects transposed images
        # Get image dimensions
        self.img_width, self.img_height = self.image_data.shape
        self.vmin, self.vmax = ZScaleInterval().get_limits(self.image_data)
        self.image_view.setLevels(self.vmin, self.vmax)
        # Create scatter plot for the RA/DEC point
        self.scatter = pg.ScatterPlotItem(
            [self.point_pixel[0]],
            [self.point_pixel[1]],
            size=10,
            brush=pg.mkBrush("r"),
        )
        self.image_view.addItem(self.scatter)

        # Create rotation dial
        self.dial = QDial()
        self.dial.setRange(0, 360)
        self.dial.setValue(0)
        self.dial.setWrapping(True)
        self.dial.valueChanged.connect(self.update_rotation)

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.image_view)
        layout.addWidget(self.dial)

    def update_rotation(self, angle):
        """Rotate the entire ImageView widget."""
        self.rotation_angle = angle

        # Create transformation matrix
        view = self.image_view.getView()  # Compute the center of the view in scene coordinates
        # Reset the transformation before applying a new one
        view.setTransform(QTransform())  # Reset to prevent cumulative drift

        scene = view.scene()
        if scene is None:
            return  # Avoid errors if the scene isn't ready

        items = scene.items()
        if not items:
            return  # Ensure there are items in the scene

        # Find the bounding box of the entire scene
        bounding_rect = items[0].sceneBoundingRect()
        center_x = bounding_rect.center().x()
        center_y = bounding_rect.center().y()

        # Create transformation matrix
        transform = QTransform()
        transform.translate(center_x, center_y)  # Move origin to center
        transform.rotate(self.rotation_angle)  # Apply rotation
        transform.translate(-center_x, -center_y)  # Move origin back
        # Apply transformation to the ImageView
        self.image_view.getView().setTransform(transform)


# PyQt Application
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQtGraph WCS Image Rotation with RA/DEC Point")
        self.setGeometry(100, 100, 800, 600)

        # Example RA/DEC point (Replace with actual coordinates)
        ra_dec = (113.4812, 32.3908)  # Example (RA, DEC)
        # ra_dec = (84.20416667, -25.33888889)  # Example (RA, DEC)

        # Load and display the FITS image with the RA/DEC point
        self.viewer = WCSImageViewer(
            # "~/Downloads/1storb_R_com.fits",
            # "~/Desktop/ls_img.fits",
            "~/Desktop/qimb0.fits",
            ra_dec,
        )  # Replace with actual FITS file
        self.setCentralWidget(self.viewer)


# Run Application
app = QApplication([])
window = MainWindow()
window.show()
app.exec()
