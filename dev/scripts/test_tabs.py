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
from PyQt6.QtCore import Qt, QTimer, QSettings
from PyQt6.QtGui import QAction, QFont, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
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

from celexta import io_gui
from celexta.decorators import requires_pan_mode

# Need to import pyqt6 before this to avoid problems
# This says qt5 but it works with pyqt6
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

log = logging.getLogger(__name__)


class MatplotlibWidget(QWidget):
    def __init__(self, parent=None, coordinate_table=None):
        super().__init__(parent)

        # Create a matplotlib figure and canvas
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        # Store the coordinate table reference
        self.coordinate_table = coordinate_table

        # Timer to differentiate single & double clicks
        self.click_timer = QTimer()
        self.click_timer.setSingleShot(True)

        self.mode = "default"

        # Create a layout and add the canvas
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        # Attributes to manage frames
        self.frames = []  # List of CustomFrame objects
        self.focused_frame = None  # Track the currently focused frame
        self.original_limits = {}  # Store original view limits for reset
        self.pan_start = None  # Store the starting position for panning
        self.circles = []  # Store circle objects
        self.selected_circle = None  # Track the selected circle

        # Connect Matplotlib events
        self.connect_mpl_events()
        # Enable keyboard focus
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def connect_mpl_events(self):
        """Connect Matplotlib events to their slots."""
        self.canvas.mpl_connect("scroll_event", self.on_scroll)  # Enable mouse zoom
        self.canvas.mpl_connect("button_press_event", self.on_mouse_click)
        self.canvas.mpl_connect("button_press_event", self.start_pan)
        self.canvas.mpl_connect("motion_notify_event", self.pan)
        self.canvas.mpl_connect("button_release_event", self.end_pan)
        # Connect Matplotlib hover events
        self.canvas.mpl_connect("motion_notify_event", self.on_hover)

    def set_focus(self, frame):
        """Set focus to a specific frame."""
        if frame is None or frame is self.focused_frame:
            return

        # Remove focus from the previously focused frame
        if self.focused_frame:
            self.focused_frame.set_focus(False)

        # Set focus to the new frame
        self.focused_frame = frame
        self.focused_frame.set_focus(True)

    def on_mouse_click(self, event):
        """Handle click events to switch focus between frames and select circles."""
        # Check if a circle was clicked
        if event.inaxes is not None:
            # Check if a circle was clicked
            for circle_data in self.circles:
                circle = circle_data["circle"]
                contains, _ = circle.contains(event)
                if contains:
                    if self.selected_circle != circle_data:
                        self.select_circle(circle_data)  # Select circle if not already selected
                    # If double click, open the circle editor
                    if self.click_timer.isActive():  # If another click happens before timeout
                        self.click_timer.stop()
                        self.open_circle_editor(circle_data)  # Process as double-click
                    else:
                        self.click_timer.start(300)  # Start single-click timer
                    return

        # Find the frame that was clicked
        frame = None
        for _frame in self.frames:
            if _frame.ax is event.inaxes:
                frame = _frame
                break
        if not frame:
            return  # Do nothing if no frame was clicked

        # If the frame was not focused, set focus to it
        if not frame.focused:
            self.set_focus(frame)
            return

    def on_scroll(self, event):
        """Handle mouse scroll event for zooming."""
        if self.focused_frame is None:
            return  # Do nothing if no frame is selected

        ax = self.focused_frame.ax
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        zoom_factor = 1.2  # Zoom in/out factor

        # Determine zoom direction (scroll up = zoom in, scroll down = zoom out)
        if event.step > 0:  # Scroll up → Zoom In
            scale = 1 / zoom_factor
        else:  # Scroll down → Zoom Out
            scale = zoom_factor

        # Zoom around the mouse cursor position
        x_cursor = event.xdata  # Get cursor x-coordinate
        y_cursor = event.ydata  # Get cursor y-coordinate

        if x_cursor is not None and y_cursor is not None:
            # Compute new x-limits centered at cursor
            xlim_new = [x_cursor + (x - x_cursor) * scale for x in xlim]
            ylim_new = [y_cursor + (y - y_cursor) * scale for y in ylim]

            ax.set_xlim(xlim_new)
            ax.set_ylim(ylim_new)
            self.canvas.draw()  # Refresh display

    # Pan mode functions
    @requires_pan_mode
    def start_pan(self, event):
        """Start panning when the mouse is pressed."""
        if self.focused_frame is None or event.button != 1:  # Left mouse button only
            return
        self.pan_start = (event.xdata, event.ydata)

    @requires_pan_mode
    def pan(self, event):
        """Pan the image when dragging the mouse."""
        if self.focused_frame is None or self.pan_start is None or event.xdata is None or event.ydata is None:
            return

        self.canvas.setCursor(Qt.CursorShape.ClosedHandCursor)

        ax = self.focused_frame.ax
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        # Compute shift
        dx = self.pan_start[0] - event.xdata
        dy = self.pan_start[1] - event.ydata

        # Apply shift to limits
        ax.set_xlim(xlim[0] + dx, xlim[1] + dx)
        ax.set_ylim(ylim[0] + dy, ylim[1] + dy)

        self.canvas.draw()  # Refresh view

    @requires_pan_mode
    def end_pan(self, event):
        """End panning when the mouse button is released."""
        self.pan_start = None  # Reset the panning state
        self.canvas.setCursor(Qt.CursorShape.OpenHandCursor)

    def on_hover(self, event):
        """Handle mouse hover events to update coordinates and pixel value."""
        # If no frames are present, do nothing
        if not self.frames:
            # log.debug("No frames present.")
            return

        # Find the frame that the mouse is hovering over
        for frame in self.frames:
            if frame.ax == event.inaxes:
                # log.debug("Event in ax: %s", frame.ax)
                break

        # If no data is present, do nothing
        if frame.img_data is None:
            # log.debug("No image data present.")
            return

        x, y = event.xdata, event.ydata  # Pixel coordinates
        if x is None or y is None:
            # log.debug("No pixel coordinates found.")
            return

        x_int, y_int = int(x), int(y)  # Integer pixel values
        img_shape = frame.img_data.shape
        pixel_value = frame.img_data[y_int, x_int] if 0 <= y_int < img_shape[0] and 0 <= x_int < img_shape[1] else None

        # World coordinates (RA, DEC) from WCS
        if hasattr(frame.ax, "wcs"):
            world = frame.ax.wcs.pixel_to_world(x, y)
            gal_coord = world.transform_to("galactic")
            icrs_coord = world.transform_to("icrs")
            gal_lon, gal_lat = gal_coord.l.deg, gal_coord.b.deg
            ra, dec = icrs_coord.ra.deg, icrs_coord.dec.deg
        else:
            gal_lon, gal_lat = None, None
            ra, dec = None, None

        # Update the table widget with real-time data
        self.update_coordinate_table(pixel_value, x, y, ra, dec, gal_lon, gal_lat)

    def reset_view(self):
        """Reset the view of the focused frame to its original limits."""
        if self.focused_frame is None:
            return  # Do nothing if no frame is selected

        if self.focused_frame in self.original_limits:
            ax = self.focused_frame.ax
            limits = self.original_limits[self.focused_frame]

            ax.set_xlim(limits["xlim"])
            ax.set_ylim(limits["ylim"])

            self.canvas.draw()  # Refresh display

    def keyPressEvent(self, event):
        """Handle keyboard events for panning and zooming."""
        if self.focused_frame is None:
            return  # Do nothing if no frame is selected

        ax = self.focused_frame.ax
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        pan_factor = 0.1 * (xlim[1] - xlim[0])  # Pan by 10% of the width
        zoom_factor = 1.2  # Zoom in/out factor

        # Check if Shift is being held
        is_shift_pressed = event.modifiers() & Qt.KeyboardModifier.ShiftModifier

        if is_shift_pressed:
            if event.key() == Qt.Key.Key_W:  # Zoom In
                ax.set_xlim(
                    (xlim[0] + xlim[1]) / 2 - (xlim[1] - xlim[0]) / (2 * zoom_factor),
                    (xlim[0] + xlim[1]) / 2 + (xlim[1] - xlim[0]) / (2 * zoom_factor),
                )
                ax.set_ylim(
                    (ylim[0] + ylim[1]) / 2 - (ylim[1] - ylim[0]) / (2 * zoom_factor),
                    (ylim[0] + ylim[1]) / 2 + (ylim[1] - ylim[0]) / (2 * zoom_factor),
                )

            elif event.key() == Qt.Key.Key_S:  # Zoom Out
                ax.set_xlim(
                    (xlim[0] + xlim[1]) / 2 - (xlim[1] - xlim[0]) * (zoom_factor / 2),
                    (xlim[0] + xlim[1]) / 2 + (xlim[1] - xlim[0]) * (zoom_factor / 2),
                )
                ax.set_ylim(
                    (ylim[0] + ylim[1]) / 2 - (ylim[1] - ylim[0]) * (zoom_factor / 2),
                    (ylim[0] + ylim[1]) / 2 + (ylim[1] - ylim[0]) * (zoom_factor / 2),
                )

        # Panning controls (only executed if Shift is NOT pressed)
        elif event.key() == Qt.Key.Key_A:  # Pan Left
            ax.set_xlim(xlim[0] - pan_factor, xlim[1] - pan_factor)
        elif event.key() == Qt.Key.Key_D:  # Pan Right
            ax.set_xlim(xlim[0] + pan_factor, xlim[1] + pan_factor)
        elif event.key() == Qt.Key.Key_W:  # Pan Up
            ax.set_ylim(ylim[0] + pan_factor, ylim[1] + pan_factor)
        elif event.key() == Qt.Key.Key_S:  # Pan Down
            ax.set_ylim(ylim[0] - pan_factor, ylim[1] - pan_factor)
        elif event.key() == Qt.Key.Key_R:  # Reset View
            self.reset_view()
        elif event.key() == Qt.Key.Key_P:  # Activate Pan Mode
            self.activate_pan_mode()
        elif event.key() == Qt.Key.Key_C:  # Add new circle
            dialog = CircleEditor(circle_data={}, parent=self)
            if dialog.exec():
                new_values = dialog.get_values()
                self.add_circle(**new_values)
        elif event.key() == Qt.Key.Key_Backspace:  # Press "Backspace" to delete selected circle
            self.delete_selected_circle()
        elif event.key() == Qt.Key.Key_Escape:
            self.escape_key_pressed()

        # Refresh the canvas
        self.canvas.draw()

    def escape_key_pressed(self):
        """Handle the Escape key press."""
        if self.selected_circle:
            self.deselect_circle()
        else:
            self.activate_default_mode()

    def activate_default_mode(self):
        """Activate the default mode."""
        if self.mode == "default":
            return
        self.mode = "default"
        self.canvas.setCursor(Qt.CursorShape.ArrowCursor)

    def activate_pan_mode(self):
        """Activate pan mode to allow panning with the mouse."""
        if self.mode == "pan":
            return  # Do nothing if already in pan mode
        self.mode = "pan"
        self.canvas.setCursor(Qt.CursorShape.OpenHandCursor)

    def add_image(self, image_data, wcs=None):
        """Add a new image to the widget."""
        # Create a new axis for the frame
        if wcs:
            ax = self.figure.add_subplot(111, projection=wcs)
        else:
            ax = self.figure.add_subplot(111)
        new_frame = CustomFrame(ax, image_data)
        self.frames.append(new_frame)
        # Store original limits for reset
        self.original_limits[new_frame] = {"xlim": ax.get_xlim(), "ylim": ax.get_ylim()}
        # Set focus to the newly added frame
        self.set_focus(new_frame)
        # Resize all frames to fit the new layout
        self.resize_frames()

    def add_sources(self, sources):
        """Add sources to the image as markers."""
        if self.focused_frame is None:
            return  # Do nothing if no frame is selected

        ax = self.focused_frame.ax
        ax.scatter(
            sources["ra"],
            sources["dec"],
            transform=ax.get_transform("world"),
            # s=5,
            color="red",
            marker="o",
            facecolors="none",
            linewidths=0.5,
        )

    def delete_frame(self, frame):
        """Delete a specific frame."""
        if frame in self.frames:
            # Remove the frame from the list
            self.frames.remove(frame)

            # Clear the axes and remove it from the figure
            frame.ax.clear()
            self.figure.delaxes(frame.ax)

            # If the deleted frame was focused, clear the focus
            if self.focused_frame == frame:
                self.focused_frame = None

            # Resize remaining frames
            self.resize_frames()

    def resize_frames(self):
        """Resize and reposition all frames."""
        num_frames = len(self.frames)
        if num_frames == 0:
            self.figure.clear()
            self.canvas.draw()
            return

        # Calculate grid layout (e.g., rows and columns)
        cols = int(np.ceil(np.sqrt(num_frames)))
        rows = int(np.ceil(num_frames / cols))

        # Update each frame's position
        for idx, frame in enumerate(self.frames):
            row, col = divmod(idx, cols)
            # Calculate position as [left, bottom, width, height]
            left = col / cols
            bottom = 1 - (row + 1) / rows
            width = 1 / cols
            height = 1 / rows
            frame.ax.set_position([left, bottom, width, height])

        # Redraw the canvas
        self.canvas.draw()

    def update_coordinate_table(self, pixel_value, x, y, ra, dec, gal_lon, gal_lat):
        """Update the real-time coordinate table with the latest values."""
        if self.coordinate_table:
            table = self.coordinate_table
            table.setItem(0, 2, QTableWidgetItem(f"{pixel_value:.6e}" if pixel_value is not None else "N/A"))
            table.setItem(1, 2, QTableWidgetItem(f"{ra:.6f}" if ra is not None else "N/A"))
            table.setItem(1, 4, QTableWidgetItem(f"{dec:.6f}" if dec is not None else "N/A"))
            table.setItem(2, 2, QTableWidgetItem(f"{gal_lon:.6f}" if gal_lon is not None else "N/A"))
            table.setItem(2, 4, QTableWidgetItem(f"{gal_lat:.6f}" if gal_lat is not None else "N/A"))

            table.setItem(3, 2, QTableWidgetItem(f"{x:.1f}"))
            table.setItem(3, 4, QTableWidgetItem(f"{y:.1f}"))

    def add_circle(self, ra, dec, radius, label="", color="red", linewidth=2):
        """Add a circle to the figure with a given RA/DEC, radius, and label."""
        ax = self.focused_frame.ax
        circle = SphericalCircle(
            (ra * u.deg, dec * u.deg),
            radius * u.deg,
            color=color,
            fill=False,
            linewidth=linewidth,
            picker=True,
            transform=ax.get_transform("world"),
        )
        ax.add_patch(circle)

        text_label = ax.text(
            ra,
            dec + radius,
            label,
            color=color,
            ha="center",
            va="bottom",
            picker=True,
            transform=ax.get_transform("world"),
        )

        # Store data
        circle_data = {
            "circle": circle,
            "text": text_label,
            "ra": ra,
            "dec": dec,
            "radius": radius,
            "label": label,
            "color": color,
            "linewidth": linewidth,
        }
        self.circles.append(circle_data)

        self.canvas.draw()

    def select_circle(self, circle_data):
        """Highlight the selected circle by changing its appearance."""
        # Deselect previously selected circle
        if self.selected_circle:
            self.deselect_circle()

        # Select new circle
        self.selected_circle = circle_data
        self.selected_circle["circle"].set_edgecolor("blue")  # Highlight color
        self.selected_circle["text"].set_color("blue")  # Highlight color
        self.selected_circle["circle"].set_linewidth(self.selected_circle["linewidth"] + 1)  # Make it thicker
        self.canvas.draw()

    def deselect_circle(self):
        """Deselect the currently selected circle."""
        if self.selected_circle:
            self.selected_circle["circle"].set_edgecolor(self.selected_circle["color"])  # Reset to default color
            self.selected_circle["text"].set_color(self.selected_circle["color"])  # Reset to default color
            self.selected_circle["circle"].set_linewidth(self.selected_circle["linewidth"])  # Reset to default width
            self.selected_circle = None
            self.canvas.draw()

    def open_circle_editor(self, circle_data):
        """Open a dialog to edit the circle's properties."""
        dialog = CircleEditor(circle_data, parent=self)
        if dialog.exec():
            new_values = dialog.get_values()

            # Need to create new circle since center isn't stored for SphereCircle
            self.delete_selected_circle()
            self.add_circle(**new_values)

    def delete_selected_circle(self):
        """Delete the currently selected circle."""
        if self.selected_circle:
            self.selected_circle["circle"].remove()
            self.selected_circle["text"].remove()
            self.circles.remove(self.selected_circle)
            self.selected_circle = None  # Reset selection
            self.canvas.draw()


class FrameTab(QWidget):
    """A single tab containing a Matplotlib figure and a record of queried tables."""

    def __init__(self, title, data=None, wcs=None):
        super().__init__()
        self.title = title
        self.circles = []  # Store circle objects
        self.queried_tables = {}  # Dictionary to store query results (name -> Table)

        # Layout
        layout = QVBoxLayout(self)

        # Create Matplotlib figure and canvas
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        # List widget to store queried tables
        self.table_list_widget = QListWidget()
        self.table_list_widget.itemClicked.connect(self.load_selected_table)  # Action when clicking a table
        layout.addWidget(self.table_list_widget)

        self.setLayout(layout)

    def add_table(self, table, table_name):
        """Store a new queried table and add it to the list widget."""
        if table_name in self.queried_tables:
            table_name += f" ({len(self.queried_tables)})"  # Avoid duplicate names

        self.queried_tables[table_name] = table
        item = QListWidgetItem(table_name)
        self.table_list_widget.addItem(item)

    def load_selected_table(self, item):
        """Retrieve the selected table when clicked."""
        table_name = item.text()
        selected_table = self.queried_tables.get(table_name)
        if selected_table:
            print(f"Selected Table: {table_name}")
            print(selected_table)  # Here you can add logic to display/use the table


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Set up the main window
        self.setWindowTitle("Celexta")
        self.resize(1000, 800)

        # Create the central widget
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)

        # Add control buttons
        button_layout = self.create_button_layout()
        main_layout.addLayout(button_layout)

        # Create a tab widget
        self.tab_widget = QTabWidget(self)
        self.tab_widget.setMovable(True)  # Enable drag-and-drop reordering
        self.tab_widget.tabBarDoubleClicked.connect(self.rename_tab)
        main_layout.addWidget(self.tab_widget, 1)  # Expand in layout

        # Add sliders for contrast and brightness
        slider_layout = self.create_sliders()
        # Create the coordinate table
        self.coordinate_table = self.create_coordinate_table()
        # Bottom layout
        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.coordinate_table)
        bottom_layout.addLayout(slider_layout)

        main_layout.addLayout(bottom_layout)

        # Add menu bar
        self.create_menu_bar()
        # Set focus so keyboard events work
        self.tab_widget.setFocus()

    def create_button_layout(self):
        """Create a layout with buttons for adding and deleting frames."""
        button_layout = QHBoxLayout()

        # Button to query astronomical catalogs
        query_cat_button = QPushButton("Query Catalogs")
        query_cat_button.clicked.connect(self.open_catalog_query_dialog)
        button_layout.addWidget(query_cat_button)

        # Button to delete the focused frame
        query_fsc_button = QPushButton("Query SVOM/FSC")
        query_fsc_button.clicked.connect(self.open_fsc_query_dialog)
        button_layout.addWidget(query_fsc_button)
        return button_layout

    def create_sliders(self):
        """Create sliders for adjusting contrast and brightness."""
        slider_layout = QVBoxLayout()

        self.sliders = {}
        for label, _range, default in [("Contrast", (1, 500), 100), ("Brightness", (-100, 100), 0)]:
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(*_range)
            slider.setValue(default)
            slider.valueChanged.connect(self.update_image_display)
            self.sliders[label] = slider
            reset_button = QPushButton("Reset")
            # Need to explicitly pass the label to the lambda function
            if label == "Contrast":
                reset_button.clicked.connect(lambda: self.sliders["Contrast"].setValue(100))
            elif label == "Brightness":
                reset_button.clicked.connect(lambda: self.sliders["Brightness"].setValue(0))
            # Add the slider and reset button to the layout
            layout = QHBoxLayout()
            layout.addWidget(QLabel(label))
            layout.addWidget(slider)
            layout.addWidget(reset_button)
            slider_layout.addLayout(layout)

        return slider_layout

    def create_coordinate_table(self):
        """Create a table widget to display real-time coordinate data."""
        table = QTableWidget(4, 5)  # 4 rows, 5 columns
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setVisible(False)

        # Set the font to Computer Modern or equivalent
        cm_font = QFont("CMU Serif")  # Try "STIXGeneral" or "CMU Serif" if unavailable
        # cm_font.setPointSize(12)  # Adjust the font size
        table.setFont(cm_font)

        # Populate the table with initial values
        table.setItem(0, 0, QTableWidgetItem("Value"))
        table.setItem(1, 0, QTableWidgetItem("ICRS"))
        table.setItem(2, 0, QTableWidgetItem("Galactic"))
        table.setItem(3, 0, QTableWidgetItem("Image"))
        table.setItem(1, 1, QTableWidgetItem("α"))
        table.setItem(1, 3, QTableWidgetItem("δ"))
        table.setItem(2, 1, QTableWidgetItem("l"))
        table.setItem(2, 3, QTableWidgetItem("b"))
        table.setItem(3, 1, QTableWidgetItem("x"))
        table.setItem(3, 3, QTableWidgetItem("y"))

        # Set alignment and make cells non-editable
        for row in range(4):
            for col in range(4):
                item = table.item(row, col)
                if not item:
                    table.setItem(row, col, QTableWidgetItem(""))
                table.item(row, col).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.item(row, col).setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        # Autoscale column widths to fit content
        table.resizeColumnToContents(0)
        table.resizeColumnToContents(1)
        table.resizeColumnToContents(3)
        table.resizeRowsToContents()

        # Set size policy to prevent unnecessary expansion
        # table.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        # Set the height of the table to fit its content
        table.setFixedHeight(int(table.sizeHint().height() / 1.9))
        table.setFixedWidth(int(1.2 * table.sizeHint().width()))
        return table

    def create_menu_bar(self):
        """Create a menu bar with File operations."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")

        # Add Tab action (Cmd+T / Ctrl+T)
        add_tab_action = QAction("Add Tab", self)
        add_tab_action.setShortcut(QKeySequence.StandardKey.AddTab)
        add_tab_action.triggered.connect(self.add_new_tab)
        file_menu.addAction(add_tab_action)

        # Close Tab action (Cmd+Shift+W / Ctrl+Shift+W)
        close_tab_action = QAction("Close Tab", self)
        close_tab_action.setShortcut(QKeySequence("Ctrl+Shift+W"))
        close_tab_action.triggered.connect(self.close_current_tab)
        file_menu.addAction(close_tab_action)

        # Add Frame action (Cmd+N / Ctrl+N)
        add_frame_action = QAction("Add Frame", self)
        add_frame_action.setShortcut(QKeySequence.StandardKey.New)
        add_frame_action.triggered.connect(self.add_example_frame)
        file_menu.addAction(add_frame_action)

        # Open image action (Cmd+O / Ctrl+O)
        open_file_action = QAction("Open Image", self)
        open_file_action.setShortcut(QKeySequence.StandardKey.Open)
        open_file_action.triggered.connect(self.open_file)
        file_menu.addAction(open_file_action)

        # Delete Focused Frame action
        delete_frame_action = QAction("Delete Focused Frame", self)
        delete_frame_action.setShortcut(QKeySequence.StandardKey.Close)
        delete_frame_action.triggered.connect(self.delete_focused_frame)
        file_menu.addAction(delete_frame_action)

        # Exit action
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    # Tabs management
    def add_new_tab(self):
        """Add a new tab with a frame."""
        title = f"Tab {self.tab_widget.count() + 1}"
        mpl_tab = MatplotlibWidget(self, coordinate_table=self.coordinate_table)
        self.tab_widget.addTab(mpl_tab, title)

    def close_current_tab(self):
        """Close the currently focused tab."""
        current_index = self.tab_widget.currentIndex()
        if current_index != -1:  # Ensure there's a tab to remove
            self.tab_widget.removeTab(current_index)

    def rename_tab(self, index):
        """Allow the user to rename a tab by double-clicking on it."""
        if index != -1:  # Ensure a valid tab is selected
            current_title = self.tab_widget.tabText(index)
            new_title, ok = QInputDialog.getText(self, "Rename Tab", "Enter new tab name:", text=current_title)
            if ok and new_title.strip():  # Ensure it's not empty
                self.tab_widget.setTabText(index, new_title)

    def add_example_frame(self):
        """Add a new frame with a random image."""
        # Generate a random image for demonstration
        image_data, wcs = generate_example_image()
        self.display_img(image_data, wcs)

    def display_img(self, img_data, wcs):
        """Display the given image data with the provided WCS."""
        if self.tab_widget.count() == 0:
            self.add_new_tab()
        mpl_widget = self.tab_widget.currentWidget()
        mpl_widget.add_image(img_data, wcs)

    def display_sources(self, sources):
        """Display the given sources on the current frame."""
        if self.tab_widget.count() == 0:
            self.add_new_tab()
        mpl_widget = self.tab_widget.currentWidget()
        mpl_widget.add_sources(sources)

    def delete_focused_frame(self, *args, **kwargs):
        """Delete the currently focused frame."""
        mpl_widget = self.tab_widget.currentWidget()
        mpl_widget.delete_frame(mpl_widget.focused_frame)

    def update_image_display(self, *args, **kwargs):
        """Update the displayed image normalization based on slider values."""
        contrast = self.sliders["Contrast"].value() / 100.0  # Map to 0.1 - 3.0
        brightness = self.sliders["Brightness"].value() / 100.0  # Map to -1.0 - 1.0
        mpl_widget = self.tab_widget.currentWidget()
        mpl_widget.focused_frame.update_contrast_and_brightness(contrast, brightness)

    def open_file(self):
        """Open a FITS file and add it to the current frame."""
        fname = io_gui.open_file(self, file_type="FITS files (*.fits *.fit *.fts)")
        if fname:
            with fits.open(fname) as hdul:
                if self.tab_widget.count() == 0:
                    self.add_new_tab()
                hdu = hdul[0]
                mpl_widget = self.tab_widget.currentWidget()
                mpl_widget.add_image(hdu.data, WCS(hdu.header))

    def open_catalog_query_dialog(self):
        """Open the catalog query dialog and retrieve results."""
        dialog = CatalogQueryDialog(parent=self, catalogs=CATALOGS)

        if dialog.exec():  # If user clicks submit (i.e., dialog is accepted)
            query_type, query_data = dialog.query_result  # Retrieve stored result

            if query_type == "image":
                img_data = query_data.data
                wcs = WCS(query_data)
                self.display_img(img_data, wcs)
            elif query_type == "sources":
                sources = query_data
                self.display_sources(sources)

    def open_fsc_query_dialog(self):
        """Open the FSC query dialog and retrieve results."""
        raise NotImplementedError("Querying SVOM/FSC is not yet implemented.")


if __name__ == "__main__":
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
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
