import logging
from datetime import datetime
from itertools import chain
from pathlib import Path
import astropy.units as u
import numpy as np
import pyqtgraph as pg
import astropy
from astropy.coordinates import SkyCoord
from astropy.table import Table
from astropy.time import Time
from astropy.units import Quantity
from astropy.visualization import ImageNormalize, MinMaxInterval, ZScaleInterval
from astropy.visualization.wcsaxes import Quadrangle, SphericalCircle, WCSAxes
from astropy.wcs.utils import proj_plane_pixel_scales
from astropy.io import fits
from astropy.io.fits import HDUList
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.patches import Rectangle
from PyQt6.QtCore import QObject, Qt, pyqtSignal, QAbstractListModel
from PyQt6.QtGui import QColor, QFocusEvent, QTransform
from PyQt6.QtWidgets import (
    QApplication,
    QDial,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QDialog,
    QLabel,
    QLineEdit,
)
from scipy.ndimage import rotate
from zhunter.photometry import PhotometricPoint
from astropy.wcs import WCS
from celexta.candidates import Candidate
from celexta.examples import (
    generate_example_candidate,
    generate_example_image,
    generate_example_region,
    generate_example_table,
)
from celexta.initialize import SRC_DIRS
from celexta.regions import CircleRegion, QuadrangleRegion, RegionModel
from celexta.error_handling import show_error_popup, show_warning_popup
from celexta.tables import CustomTable, GlobalTableModel
from zhunter.conversions import ergscm2AA
import json
import pandas as pd

log = logging.getLogger(__name__)


class CustomViewBox(pg.ViewBox):
    """Custom ViewBox that detects when it receives focus amd handles panning with the keyboard."""

    focused = pyqtSignal(bool)  # Signal emitted when the ViewBox gains/loses focus

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlag(self.GraphicsItemFlag.ItemIsFocusable)  # Enable focus events

    def focusInEvent(self, event: QFocusEvent):
        """Triggered when the ViewBox gains focus."""
        self.setBorder("red")
        log.debug("ViewBox has gained focus.")
        self.focused.emit(True)
        super().focusInEvent(event)  # Call parent method

    def keyPressEvent(self, event):
        """Handle keyboard events for panning and zooming."""
        xlim, ylim = self.viewRange()  # Get current view range

        pan_factor = 0.1 * (xlim[1] - xlim[0])  # Pan by 10% of the width
        zoom_factor = 1.2  # Zoom in/out factor

        # Check if Shift is being held
        is_shift_pressed = event.modifiers() & Qt.KeyboardModifier.ShiftModifier

        if is_shift_pressed:
            # Shift + W = zoom in
            if event.key() == Qt.Key.Key_W:
                self.setXRange(
                    (xlim[0] + xlim[1]) / 2 - (xlim[1] - xlim[0]) / (2 * zoom_factor),
                    (xlim[0] + xlim[1]) / 2 + (xlim[1] - xlim[0]) / (2 * zoom_factor),
                    padding=0,
                )
                self.setYRange(
                    (ylim[0] + ylim[1]) / 2 - (ylim[1] - ylim[0]) / (2 * zoom_factor),
                    (ylim[0] + ylim[1]) / 2 + (ylim[1] - ylim[0]) / (2 * zoom_factor),
                    padding=0,
                )
            # Shift + S = zoom out
            elif event.key() == Qt.Key.Key_S:
                self.setXRange(
                    (xlim[0] + xlim[1]) / 2 - (xlim[1] - xlim[0]) * (zoom_factor / 2),
                    (xlim[0] + xlim[1]) / 2 + (xlim[1] - xlim[0]) * (zoom_factor / 2),
                    padding=0,
                )
                self.setYRange(
                    (ylim[0] + ylim[1]) / 2 - (ylim[1] - ylim[0]) * (zoom_factor / 2),
                    (ylim[0] + ylim[1]) / 2 + (ylim[1] - ylim[0]) * (zoom_factor / 2),
                    padding=0,
                )

        # Panning controls (only executed if Shift is NOT pressed)
        elif event.key() == Qt.Key.Key_A:  # Pan Left
            self.setXRange(xlim[0] - pan_factor, xlim[1] - pan_factor, padding=0)
        elif event.key() == Qt.Key.Key_D:  # Pan Right
            self.setXRange(xlim[0] + pan_factor, xlim[1] + pan_factor, padding=0)
        elif event.key() == Qt.Key.Key_W:  # Pan Up
            self.setYRange(ylim[0] + pan_factor, ylim[1] + pan_factor, padding=0)
        elif event.key() == Qt.Key.Key_S:  # Pan Down
            self.setYRange(ylim[0] - pan_factor, ylim[1] - pan_factor, padding=0)


class ScatterFrame(pg.GraphicsLayout):
    """Custom frame class based on pyqtgraph used to scatter points."""

    def __init__(self, name=None, parent=None):
        super().__init__(parent)
        self.name = name
        self.candidates = []
        self.set_up_layout()
        self.units = {"wvlg": u.nm, "flux": u.ABmag, "time": u.s}

    def set_up_layout(self):
        """Set up the layout for the frame."""
        self.temporal_plot = self.addPlot(row=0, col=0)
        self.spectral_plot = self.addPlot(row=0, col=1)

        # Link the yaxis together
        self.temporal_plot.setYLink(self.spectral_plot)
        self.spectral_plot.setYLink(self.temporal_plot)

        # Invert axis
        self.temporal_plot.invertY()
        self.spectral_plot.invertY()

    def update_units(self, units):
        """Update the units of the frame."""
        self.units.update(units)
        self.temporal_plot.setLabel("left", f"Flux [{self.units['flux']}]")
        self.temporal_plot.setLabel("bottom", f"Time [{self.units['time']}]")
        self.spectral_plot.setLabel("right", f"Flux [{self.units['flux']}]")
        self.spectral_plot.setLabel("bottom", f"Wavelength [{self.units['wvlg']}]")

    def add_candidate(self, candidate: Candidate):
        """Add a photometric point to the frame."""
        for obs in candidate.observations:
            # Spectral plot
            obs.plot_pyqt(vb=self.spectral_plot, mode="spectral")
            # Make sure the points are on top
            for artist in obs.visreps[-1].artists:
                artist.setZValue(10)

            # Temporal plot
            if obs.obs_time is None:
                show_warning_popup(
                    title="Missing Observation Time",
                    text="Observation time is missing for one or more observations, they will be ignored",
                    warning_message=f"Observation: {obs}",
                )
                continue
            if candidate.t0 is not None and obs.obs_time is not None and candidate.t0 > obs.obs_time:
                show_warning_popup(
                    title="Invalid Observation Time",
                    text="Observation time is before the candidate's t0, it will be ignored",
                    warning_message=f"t0: {candidate.t0}, obs_time: {obs.obs_time}",
                )
                continue
            obs.plot_pyqt(vb=self.temporal_plot, mode="temporal", t0=candidate.t0, xlogscale=candidate.t0 is not None)
            # Change Z value to ensure the points are on top
            for artist in obs.visreps[-1].artists:
                artist.setZValue(10)

        self.temporal_plot.autoRange()
        self.candidates.append(candidate)

    def remove_candidate(self, candidate: Candidate):
        """Remove a Candidate from the frame."""
        if candidate in self.candidates:
            log.debug(f"Removing candidate {candidate!s} from scatter frame.")
            visreps = [obs.visreps for obs in candidate.observations]
            # Flatten the list
            for visrep in chain.from_iterable(visreps):
                for artist in visrep.artists:
                    if artist in self.temporal_plot.vb.addedItems:
                        self.temporal_plot.vb.removeItem(artist)
                    if artist in self.spectral_plot.vb.addedItems:
                        self.spectral_plot.vb.removeItem(artist)
            self.candidates.remove(candidate)

    def update_candidate(self, candidate: Candidate):
        """Update the candidate in the frame."""
        if candidate in self.candidates:
            self.remove_candidate(candidate)
            self.add_candidate(candidate)

    def isVisible(self):
        """Check if the frame is visible."""
        return super().isVisible() & (self.temporal_plot.isVisible() | self.spectral_plot.isVisible())

    def toggle_grb_oa_pop(self):
        """Toggle the visibility of the GRB OA population."""
        log.info("Toggling GRB Optical Afterglow population. Data is from the GRBase project, private comm. D. Turpin")
        if not hasattr(self, "grb_oa_pop"):
            self.grb_oa_pop_visible = True
            self.grb_oa_pop = {}
            with open(SRC_DIRS["DATA"] / "GRBase_Rlc_synth.json") as json_data:
                data = json.load(json_data)
            grb_lcs = pd.DataFrame.from_dict(data)
            for grb, group in grb_lcs.groupby("grb_name"):
                x = group["midtimes"].to_numpy()
                y = group["flux"].to_numpy()
                pdi = self.temporal_plot.plot(x, y, pen=pg.mkPen("gray", width=1), name=grb)
                pdi.setZValue(0)
                self.grb_oa_pop[grb] = pdi
            self.temporal_plot.setLogMode(x=True)
            self.temporal_plot.setVisible(True)
            self.temporal_plot.vb.autoRange()

        elif self.grb_oa_pop_visible:
            for grb in self.grb_oa_pop.values():
                grb.hide()
            self.grb_oa_pop_visible = False
        else:
            for grb in self.grb_oa_pop.values():
                grb.show()
            self.grb_oa_pop_visible = True

    def toggle_candidate(self, signal: list[bool, Candidate]):
        """Toggle the visibility of a Candidate."""
        visible, candidate = signal
        if candidate in self.candidates:
            visreps = [obs.visreps for obs in candidate.observations]
            # Flatten the list
            for visrep in chain.from_iterable(visreps):
                log.debug(f"Setting visibility of {visrep} to {visible}")
                for artist in visrep.artists:
                    artist.setVisible(visible)


class QImageFrame(pg.GraphicsLayout):
    """Custom frame class based on pyqtgraph used to display an image."""

    hoverChanged = pyqtSignal(dict)  # Signal emitted when the hover event changes
    focused = pyqtSignal(object)  # Signal emitted when the frame gains/loses focus

    def __init__(
        self,
        projection=None,
        image_data=None,
        header=None,
        name=None,
        interval=None,
        parent=None,
    ):
        super().__init__(parent)
        self.name = name if name is not None else "Image Frame"
        self.regions = {}  # Dictionary mapping a region to its artist
        self.tables = {}  # Dictionary mapping a table to its artist
        self.candidates = {}  # Dictionary mapping a candidate to its artist
        self.set_up_layout()

        self.interval = interval if interval is not None else ZScaleInterval()
        self.rotation_angle = 0
        self.img_data = image_data
        self.wcs = projection

        if image_data is not None:
            self.display_image(
                image_data,
                projection=projection,
                header=header,
                interval=interval,
            )

    def set_up_layout(self):
        """Set up the layout of the frame.

        Layout consists of a ViewBox that contains and image item and a colorbar.
        """
        # Image Item
        self.img_itm = pg.ImageItem()  # Displayed image, placeholder for now
        self.img_itm.setZValue(0)  # Set Z value
        self.img_itm.hoverEvent = self.hoverEvent  # Connect hover event
        self.img_itm.setOpts(axisOrder="row-major")  # Set axis order

        self.main_vb = CustomViewBox(lockAspect=True, name=self.name)
        self.main_vb.focused.connect(self.send_focus_signal)
        self.main_vb.addItem(self.img_itm)
        # self.colorbar = pg.HistogramLUTItem(image=self.img_itm, orientation="horizontal", fillHistogram=False)
        # self.colorbar = pg.ColorBarItem(
        #     width=10,
        #     # values=(0, 30_000),
        #     # colorMap= pg.colormap.get("Grays", source="matplotlib"),
        #     # limits=(0, None),
        #     # rounding=1000,
        #     orientation="h",
        #     # pen="#8888FF",
        #     hoverPen="#EEEEFF",
        #     hoverBrush="#EEEEFF80",
        # )
        # self.colorbar.setImageItem(self.img_itm)
        self.addItem(self.main_vb, row=0, col=0)
        # self.addItem(self.colorbar, row=1, col=0)
        # By default hide the colorbar
        # self.colorbar.hide()

    def get_world_center(self) -> SkyCoord:
        """Return the center of the displayed image in world coordinates."""
        log.info("Computing center of the displayed image.")
        img_shape = self.img_data.shape if self.img_data is not None else None
        if img_shape is not None:
            x_cen, y_cen = img_shape[1] / 2, img_shape[0] / 2  # Get center pixel
            center = self.wcs.pixel_to_world(x_cen, y_cen)  # Convert to world coordinates
            return center
        return None

    def get_world_fov(self) -> Quantity:
        """Return the Field of View (FoV) of the displayed image in world coordinates."""
        log.info("Computing Field of View.")
        img_shape = self.img_data.shape if self.img_data is not None else None
        if img_shape:
            xmin, xmax = 0, img_shape[1]  # Pixel range in X
            ymin, ymax = 0, img_shape[0]  # Pixel range in Y
            bottom_left = self.wcs.pixel_to_world(xmin, ymin)
            top_right = self.wcs.pixel_to_world(xmax, ymax)
            fov = bottom_left.separation(top_right)
            return fov
        return None

    def match_to(self, frame):
        """Match the WCS projection of the frame to the current frame."""
        log.info("Matching WCS projection.")
        if not hasattr(frame, "wcs") or not hasattr(self, "wcs"):
            log.exception("Frames must have a WCS projection.")
            return

        # Get the current view limits in pixel coordinates of the frame to match
        x0, x1 = frame.img_itm.getViewBox().viewRange()[0]  # X limits in pixel coordinates
        y0, y1 = frame.img_itm.getViewBox().viewRange()[1]  # Y limits in pixel coordinates

        # Define the four corner pixel positions of the view
        corners_pixels = np.array([[x0, y0], [x0, y1], [x1, y0], [x1, y1]])

        # Convert these pixel coordinates to world coordinates using WCS
        world_coords = frame.wcs.pixel_to_world(corners_pixels[:, 0], corners_pixels[:, 1])

        # Convert world coordinates back to pixel coordinates in the target frame
        target_pixels = self.wcs.world_to_pixel(world_coords)

        # Determine new pixel limits
        new_xmin, new_xmax = target_pixels[0].min(), target_pixels[0].max()
        new_ymin, new_ymax = target_pixels[1].min(), target_pixels[1].max()

        # Set the new view limits in this frame
        self.img_itm.getViewBox().setXRange(new_xmin, new_xmax, padding=0)
        self.img_itm.getViewBox().setYRange(new_ymin, new_ymax, padding=0)

    def hoverEvent(self, event):
        """Handle hover events on the frame."""
        if event.isExit():
            self.hoverChanged.emit({})
            return

        pos = event.pos()

        if self.img_data is None:
            # log.debug("No image data found.")
            return  # No valid frame or image data

        x, y = pos.x(), pos.y()

        if x is None or y is None:
            log.debug("No pixel coordinates found.")
            return  # No valid pixel coordinates

        x_int, y_int = int(x), int(y)  # Integer pixel values
        img_data = self.img_data
        img_shape = img_data.shape
        pixel_value = img_data[y_int, x_int] if 0 <= y_int < img_shape[0] and 0 <= x_int < img_shape[1] else None

        # World coordinates (RA, DEC) from WCS
        if self.wcs:
            world = self.wcs.pixel_to_world(x, y)
            gal_coord = world.transform_to("galactic")
            icrs_coord = world.transform_to("icrs")
            gal_lon, gal_lat = gal_coord.l.deg, gal_coord.b.deg
            ra, dec = icrs_coord.ra.deg, icrs_coord.dec.deg
        else:
            gal_lon, gal_lat = None, None
            ra, dec = None, None

        # Check for units (can be None)
        pixel_unit = self.unit if hasattr(self, "unit") else None
        self.hoverChanged.emit(
            {
                "name": self.name,
                "pixel_value": pixel_value,
                "pixel_unit": pixel_unit,
                "x": x,
                "y": y,
                "ra": ra,
                "dec": dec,
                "gal_lon": gal_lon,
                "gal_lat": gal_lat,
            }
        )

    def send_focus_signal(self, focused):
        """Send a signal when the frame gains focus."""
        if focused:
            log.debug("Frame received focused signal from view box")
            self.focused.emit(self)

    def set_focus(self, focused):
        """Set the focus of the frame."""
        if not focused:
            log.debug("Frame has been told to lose focus.")
            self.main_vb.setBorder(None)
        # Focused case is handled by ViewBox directly

    # Images
    def display_image(self, img_data, projection=None, header=None, interval=None, cmap=None):
        """Display and normalize the image data on the canvas."""
        log.info("Displaying image.")
        if self.img_itm.image is not None:
            self.img_itm.clear()

        # Check if the projection (WCS) has changed
        if projection is not None:
            self.wcs = projection

        # Handle normalization
        if interval is None:
            interval = self.interval
        else:
            self.interval = interval

        if interval:
            vmin, vmax = interval.get_limits(img_data)

        # Display the image
        self.img_itm.setImage(img_data, levels=[vmin, vmax])
        self.img_itm.setLevels((vmin, vmax))
        # Set the colormap
        self.img_itm.setLookupTable(cmap)
        # self.colorbar.setHistogramRange(vmin, vmax)
        # self.colorbar.setLevels((vmin, vmax))
        if cmap is not None:
            self.img_itm.setLookupTable(cmap)
        # Save metadata
        self.header = header
        self.unit = u.Unit(header["BUNIT"]) if header and "BUNIT" in header else None
        self.img_data = img_data

    def update_rotation(self, angle):
        """Rotate the displayed image by the given angle."""
        if self.img_itm is None:
            return

        # log.debug(f"Rotating image by {angle}")
        # Compute the center of the view in scene coordinates
        # Reset the transformation before applying a new one
        self.img_itm.setTransform(QTransform())  # Reset to prevent cumulative drift

        # Find the bounding box of the entire scene
        bounding_rect = self.main_vb.sceneBoundingRect()
        center_x = bounding_rect.center().x()
        center_y = bounding_rect.center().y()

        # Create transformation matrix
        transform = QTransform()
        transform.translate(center_x, center_y)  # Move origin to center
        transform.rotate(-angle)  # Apply rotation
        transform.translate(-center_x, -center_y)  # Move origin back
        self.rotation_angle = angle
        # Apply transformation to the ImageView
        self.img_itm.setTransform(transform)
        for patch in self.regions.values():
            patch.setTransform(transform)
        for scatter in self.tables.values():
            scatter.setTransform(transform)
        for scatter in self.candidates.values():
            scatter.setTransform(transform)

    # Items
    def add_item(self, item: CircleRegion | QuadrangleRegion | CustomTable | Candidate):
        """Add a new item to the frame."""
        if self.wcs is None:
            log.error("No WCS projection found.")
            return
        if isinstance(item, CircleRegion):
            self.add_region(item)
        elif isinstance(item, CustomTable):
            self.add_table(item)
        elif isinstance(item, Candidate):
            self.add_candidate(item)

    def remove_item(self, item: CircleRegion | QuadrangleRegion | CustomTable | Candidate):
        """Remove an item from the frame."""
        if isinstance(item, CircleRegion):
            self.remove_region(item)
        elif isinstance(item, CustomTable):
            self.remove_table(item)
        elif isinstance(item, Candidate):
            self.remove_candidate(item)

    def update_item(self, item: CircleRegion | QuadrangleRegion | CustomTable | Candidate):
        """Update an item in the frame."""
        if isinstance(item, CircleRegion):
            self.update_region(item)
        elif isinstance(item, CustomTable):
            self.update_table(item)
        elif isinstance(item, Candidate):
            self.update_candidate(item)

    def toggle_item(self, signal: list[bool, CircleRegion | QuadrangleRegion | CustomTable | Candidate]):
        """Toggle the visibility of an item."""
        visible, item = signal
        if isinstance(item, CircleRegion):
            self.toggle_region([visible, item])
        elif isinstance(item, CustomTable):
            self.toggle_table([visible, item])
        elif isinstance(item, Candidate):
            self.toggle_candidate([visible, item])

    # Regions
    def add_region(self, region: CircleRegion):
        """Add a Region to the frame."""
        if region in self.regions:
            return  # Do nothing if the region is already present

        log.debug("Adding region to frame.")

        if isinstance(region, CircleRegion):
            # Use SphericalCircle because it handles odd shaped circles
            # when near the poles
            _patch = SphericalCircle(region.center, region.radius)

        elif isinstance(region, QuadrangleRegion):
            _patch = Quadrangle(region.anchor, region.width, region.height)
        # Get the vertices from the patch and add them to the plot
        vertices = _patch.get_path().vertices.T  # Convert from RA/DEC to pixels
        vertices = self.wcs.world_to_pixel(SkyCoord(ra=vertices[0], dec=vertices[1], unit="deg"))
        patch = pg.PlotDataItem(
            x=vertices[0],
            y=vertices[1],
            pen=pg.mkPen(region.color, width=2),
        )
        if hasattr(region, "zorder"):
            patch.setZValue(region.zorder)
        else:
            patch.setZValue(10)
        self.img_itm.getViewBox().addItem(patch)
        transform = self.img_itm.transform()
        patch.setTransform(transform)
        patch.region = region  # Store the reference to the Region in the patch
        self.regions[region] = patch

    def remove_region(self, region: CircleRegion):
        """Remove a Region from the frame."""
        if region in self.regions:
            log.debug("Removing region from frame.")
            patch = self.regions.pop(region)
            self.main_vb.removeItem(patch)

    def update_region(self, region: CircleRegion):
        """Update the properties of a Region (requiring to remove and re-add the patch)."""
        if region in self.regions:
            log.debug("Updating region.")
            self.remove_region(region)
            self.add_region(region)

    def toggle_region(self, signal: list[bool, CircleRegion]):
        """Toggle the visibility of a region."""
        visible, region = signal
        if region in self.regions:
            patch = self.regions[region]
            if visible:
                patch.show()
            else:
                patch.hide()

    # Tables
    def add_table(self, table: CustomTable):
        """Plot the table's data on the given axis and store the scatter plot."""
        if table in self.tables:
            return  # Do nothing if the table is already present
        log.debug("Adding table to frame.")
        # Extract coordinates
        ra_vals = table.data["RA"]
        dec_vals = table.data["DEC"]
        # Convert to pixel coordinates
        x, y = self.wcs.world_to_pixel(SkyCoord(ra=ra_vals, dec=dec_vals, unit="deg"))

        scatter = pg.ScatterPlotItem(
            x,
            y,
            pen=pg.mkPen(table.color, width=2),  # Border color
            brush=pg.mkBrush(None),  # No fill
            symbol="o",  # Circular markers
            size=table.size if hasattr(table, "size") else 10,  # Marker size
        )
        if hasattr(table, "zorder"):
            scatter.setZValue(table.zorder)
        self.main_vb.addItem(scatter)  # Add to ViewBox
        transform = self.img_itm.transform()
        scatter.setTransform(transform)
        self.tables[table] = scatter  # Store reference

    def remove_table(self, table: CustomTable):
        """Remove a CustomTable from the frame."""
        if table in self.tables:
            log.debug("Removing table from frame.")
            scatter = self.tables.pop(table)
            self.main_vb.removeItem(scatter)

    def update_table(self, table: CustomTable):
        """Update the aesthetics of a table."""
        if table in self.tables:
            log.debug("Updating table")
            scatter = self.tables[table]
            scatter.setPen(pg.mkPen(table.color))

    def toggle_table(self, signal: list[bool, CustomTable]):
        """Toggle the visibility of a Table."""
        visible, table = signal
        if table in self.tables:
            scatter = self.tables[table]
            if visible:
                scatter.show()
            else:
                scatter.hide()

    # Candidates
    def add_candidate(self, candidate: Candidate):
        """Add a Candidate to the frame."""
        if candidate in self.candidates:
            return
        log.debug("Adding candidate to frame.")
        x, y = self.wcs.world_to_pixel(candidate.pos)
        pix_scale = proj_plane_pixel_scales(self.wcs)
        sx = pix_scale[0]
        sy = pix_scale[1]
        degrees_per_pixel = np.sqrt(sx * sy)
        size = candidate.pos_unc.to(u.deg).value / degrees_per_pixel
        scatter = pg.ScatterPlotItem(
            [x],
            [y],
            pen=pg.mkPen(candidate.color, width=2),  # Border color
            brush=pg.mkBrush(None),  # No fill
            symbol="o",  # Circular markers
            size=size,  # Marker size
            pxMode=False,
        )
        if hasattr(candidate, "zorder"):
            scatter.setZValue(candidate.zorder)
        self.main_vb.addItem(scatter)  # Add to ViewBox
        transform = self.img_itm.transform()
        scatter.setTransform(transform)
        self.candidates[candidate] = scatter  # Store reference

    def remove_candidate(self, candidate: Candidate):
        """Remove a Candidate from the frame."""
        if candidate in self.candidates:
            log.debug(f"Removing candidate: {candidate!s} from image frame.")
            scatter = self.candidates.pop(candidate)
            if scatter in self.main_vb.addedItems:
                self.main_vb.removeItem(scatter)

    def update_candidate(self, candidate: Candidate):
        """Update the aesthetics of a candidate."""
        if candidate in self.candidates:
            log.debug(f"Updating candidate: {candidate!s}")
            self.remove_candidate(candidate)
            self.add_candidate(candidate)

    def toggle_candidate(self, signal: list[bool, Candidate]):
        """Toggle the visibility of a Table."""
        visible, candidate = signal
        if candidate in self.candidates:
            scatter = self.candidates[candidate]
            if visible:
                scatter.show()
            else:
                scatter.hide()

    # Save and load
    def to_serializable_dict(self, save_dir: str | Path):
        """Convert the frame to a serializable dictionary."""
        log.info("Converting frame to serializable dictionary.")
        fname = Path(save_dir) / f"{str(self.name).replace(' ','_')}_frame_img.fits"
        if hasattr(self, "header") and self.header is not None:
            header = self.header
        else:
            header = fits.Header()

        # Update header with WCS information
        header.update(self.wcs.to_header())
        fits_img = HDUList([fits.PrimaryHDU(data=self.img_data, header=header)])
        fits_img.writeto(fname, overwrite=True)
        data = {
            "name": str(self.name),
            "rotation_angle": float(self.rotation_angle),
            "image": str(fname.expanduser().resolve()),
            "levels": self.img_itm.levels.astype(float).tolist(),
            "interval": str(type(self.interval).__name__),
            "cmap": str(self.img_itm.getColorMap().name) if self.img_itm.getColorMap() is not None else None,
        }
        return data

    @classmethod
    def from_serializable_dict(cls, data: dict):
        """Load the frame from a serializable dictionary."""
        log.info("Loading frame from serializable dictionary.")

        # Create instance of the interval class
        interval = getattr(astropy.visualization, data["interval"])()
        # Load the image data
        hdu = fits.open(data["image"])
        frame = cls(name=data["name"])
        frame.display_image(
            hdu[0].data,
            projection=WCS(hdu[0].header),
            header=hdu[0].header,
            interval=interval,
            cmap=data["cmap"],
        )
        frame.img_itm.setLevels(data["levels"])
        frame.update_rotation(data["rotation_angle"])
        return frame


class QImageFrameEditor(QDialog):
    """Custom dialog to edit the properties of a QImageFrame."""

    def __init__(self, frame: QImageFrame, parent=None):
        super().__init__(parent)
        self.frame = frame
        self.setWindowTitle("Image Frame Editor")
        self.setModal(False)

        main_layout = QVBoxLayout(self)
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel("Name:"))
        hlayout.addWidget(QLineEdit(self.frame.name))
        main_layout.addLayout(hlayout)
        # if hasattr(self.frame, "colorbar"):
        #     qw = pg.GraphicsLayoutWidget()
        #     vb = qw.addViewBox()
        #     vb.addItem(self.frame.colorbar)
        #     self.frame.colorbar.show()
        #     main_layout.addWidget(qw)
        if self.frame.img_data is not None:
            cb = pg.HistogramLUTWidget(
                image=self.frame.img_itm,
                orientation="horizontal",
                fillHistogram=False,
            )
            cb.item.setLevels(*self.frame.img_itm.levels)
            # cmap = self.frame.colorbar.colorMap()
            # if cmap is not None:
            #     cb.item.gradient.setColorMap(cmap)
            # for tick in cb.item.gradient.listTicks():
            #     tick[0].hide()
            main_layout.addWidget(cb)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        main_layout.addWidget(self.close_btn)


if __name__ == "__main__":
    import sys

    from PyQt6.QtGui import QFont
    from pyqtgraph.dockarea.Dock import Dock
    from pyqtgraph.dockarea.DockArea import DockArea

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

    # example image
    hdu = generate_example_image("horse")
    im, wcs = hdu.data, WCS(hdu.header)
    imf = QImageFrame(image_data=im, projection=wcs)
    imf2 = QImageFrame(image_data=im, projection=wcs)
    sf = ScatterFrame()
    # Add a region
    center = imf.get_world_center()
    circle = CircleRegion(center=center, radius=8 * u.arcsec, color="red")
    rectangle = QuadrangleRegion(anchor=center, width=16 * u.arcsec, height=1 * u.arcsec, color="blue")
    # Add a candidate
    candidate = generate_example_candidate(data=im, wcs=wcs, positional_uncertainty=1 * u.arcmin)
    # add a table
    ra = np.random.normal(center.ra.deg, 0.01, 10)
    dec = np.random.normal(center.dec.deg, 0.01, 10)
    table = CustomTable(data=Table({"RA": ra, "DEC": dec}), color="cyan")
    table2 = generate_example_table(data=im, wcs=wcs)

    imf.add_table(table)
    imf.add_table(table2)
    imf.add_region(circle)
    imf.add_region(rectangle)
    imf.add_candidate(candidate)
    sf.add_candidate(candidate)

    imf.update_rotation(45)

    # ----- button layout -----
    btn_layout = QVBoxLayout()
    #  add button to hide/show colorbar
    cb = QPushButton("Toggle Colorbar")
    cb.clicked.connect(lambda: imf.colorbar.setVisible(not imf.colorbar.isVisible()))
    # Add button to show/hide scatterplot
    spt_btn = QPushButton("Toggle Temporal plot")
    spt_btn.clicked.connect(lambda: sf.temporal_plot.setVisible(not sf.temporal_plot.isVisible()))
    sps_btn = QPushButton("Toggle Spectral plot")
    sps_btn.clicked.connect(lambda: sf.spectral_plot.setVisible(not sf.spectral_plot.isVisible()))
    # toggle GRB oa population
    grb_btn = QPushButton("Toggle GRB OA Population")
    grb_btn.clicked.connect(sf.toggle_grb_oa_pop)

    # add dial to rotate image
    dial = QDial()
    dial.setRange(0, 360)
    dial.setSingleStep(1)
    dial.valueChanged.connect(imf.update_rotation)
    # Add to layout
    btn_layout.layout().addWidget(cb)
    btn_layout.layout().addWidget(spt_btn)
    btn_layout.layout().addWidget(sps_btn)
    btn_layout.layout().addWidget(grb_btn)
    btn_layout.layout().addWidget(dial)
    btn_layout.addStretch(100)
    # Main window
    window = QMainWindow()
    window.setGeometry(100, 100, 800, 600)

    # Using docks
    # area = DockArea()
    # window.setCentralWidget(area)
    # dock = Dock("Image", size=(500, 500))
    # dock_s = Dock("Scatter", size=(500, 500), closable=True)
    # area.addDock(dock, "top")
    # area.addDock(dock_s, "bottom")
    # # Wrap the QImageFrame which is a graphics layout inside a widget
    # # glw1 = pg.GraphicsLayoutWidget()
    # # glw1.addItem(imf)
    # # glw2 = pg.GraphicsLayoutWidget()
    # # glw2.addItem(sf)
    # # dock.addWidget(glw1)
    # # dock_s.addWidget(glw2)
    # dock.addWidget(imf)
    # dock_s.addWidget(sf)

    # Using graphics layout widget
    glw = pg.GraphicsLayoutWidget()
    glw.addItem(imf, row=0, col=0)
    glw.addItem(imf2, row=0, col=1)
    glw.addItem(sf, row=1, col=0, colspan=2)
    qw = QWidget()
    qw.setLayout(QHBoxLayout())
    qw.layout().addWidget(glw)
    qw.layout().addLayout(btn_layout)
    dialog = QImageFrameEditor(imf)
    dialog.show()
    window.setCentralWidget(qw)

    window.show()
    sys.exit(app.exec())
