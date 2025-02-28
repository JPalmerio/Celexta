import logging
import sys
from pathlib import Path
from astropy.io import fits
from astropy.wcs import WCS
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction, QFont, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QLineEdit,
    QFileDialog,
)

from celexta import io_gui
from celexta.catalogs import CATALOGS, CatalogQueryDialog
from celexta.custom_tab import CustomTab
from celexta.decorators import requires_tab
from celexta.examples import (
    generate_example_image,
    generate_example_table,
    generate_example_candidate,
    generate_example_region,
    ExampleWidget,
)
from celexta.tables import CustomTable
import celexta.svom_fsc as svom_fsc
from celexta.error_handling import show_error_popup
import celexta.initialize as init

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window for Celexta."""

    def __init__(self):
        super().__init__()

        # Set up the main window
        self.setWindowTitle("Celexta")
        # self.resize(1200, 800)

        self.config = init.load_config()
        # Create the central widget
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)

        # Add control buttons
        self.create_button_layout()

        # Create a tab widget
        self.tab_widget = QTabWidget(self)
        self.tab_widget.setMovable(True)  # Enable drag-and-drop reordering
        self.tab_widget.tabBarDoubleClicked.connect(self.rename_tab)
        self.tab_widget.setTabsClosable(True)  # Enable closing tabs
        self.tab_widget.tabCloseRequested.connect(self.close_current_tab)
        main_layout.addWidget(self.tab_widget, 1)  # Expand in layout

        # Create example widget
        self.example_widget = None

        # Add menu bar
        self.create_menu_bar()
        # Set focus so keyboard events work
        self.tab_widget.setFocus()
        # Load any previous session
        self.load_state()

    def create_button_layout(self):
        """Create a layout with buttons for adding and deleting frames."""
        self.button_widget = QWidget()
        button_layout = QVBoxLayout(self.button_widget)

        # Button to query astronomical catalogs
        query_cat_button = QPushButton("Query Catalogs")
        query_cat_button.clicked.connect(self.open_catalog_query_dialog)
        button_layout.addWidget(query_cat_button)

        # Button to delete the focused frame
        query_fsc_button = QPushButton("Query SVOM/FSC")
        query_fsc_button.clicked.connect(self.open_fsc_query_dialog)
        button_layout.addWidget(query_fsc_button)

        # Button to hide scatter frame
        toggle_scatter_button = QPushButton("Toggle Scatter")
        toggle_scatter_button.clicked.connect(self.toggle_scatter)
        button_layout.addWidget(toggle_scatter_button)

        # Match to frame
        match_to_frame_button = QPushButton("Match to Frame")
        match_to_frame_button.clicked.connect(self.match_to_frame)
        button_layout.addWidget(match_to_frame_button)

        # Add GRB optical afterglow population
        toggle_grb_oa_pop_button = QPushButton("Toggle GRB Optical Afterglow Population")
        toggle_grb_oa_pop_button.clicked.connect(self.toggle_grb_oa_pop)
        button_layout.addWidget(toggle_grb_oa_pop_button)

        # Add candidate button
        add_candidate_button = QPushButton("Add Candidate")
        add_candidate_button.clicked.connect(self.add_candidate)
        button_layout.addWidget(add_candidate_button)

        # Load fsc_products button
        load_fsc_products_button = QPushButton("Load FSC products")
        load_fsc_products_button.clicked.connect(self.load_fsc_products)
        button_layout.addWidget(load_fsc_products_button)

    def load_fsc_products(self):
        """Load QPO VT data from a FITS file."""
        file, _ = QFileDialog.getOpenFileName(
            self,
            caption="Select file",
            directory=str(Path(self.config["files"].get("last_opened", ".")).expanduser().parent),
            filter="FITS files (*.fits *.fit)",
        )
        if file:
            init.update_last_opened(file)
            # Check contents of the file
            with fits.open(file) as hdul:
                acronym = hdul[0].header.get("CARD", "")
                if not acronym:
                    log.warning(f"No CARD keyword found in {file}")
                    return
                burst_id = hdul[0].header.get("BURST_ID", "")

            # Add a tab if necessary
            if self.tab_widget.count() == 0:
                self.add_new_tab(title=burst_id)
            custom_tab = self.tab_widget.currentWidget()

            # Add the data to the frame
            if acronym == "QPO_VT":
                svom_fsc.add_qpo_vt(custom_tab, burst_id, file)
            elif acronym == "QPO_MXT":
                svom_fsc.add_qpo_mxt(custom_tab, burst_id, file)
            elif acronym == "QCANDI_VT":
                svom_fsc.add_qcandi_vt(custom_tab, burst_id, file)
            elif acronym == "QIM1B_VT":
                svom_fsc.add_qim1b_vt(custom_tab, burst_id, file)
            elif acronym == "QPO_ECL":
                svom_fsc.add_qpo_ecl(custom_tab, burst_id, file)
            else:
                log.warning(f"Unknown acronym '{acronym}' in {file}")

    def match_to_frame(self):
        """Match all regions and tables to the current frame."""
        custom_tab = self.tab_widget.currentWidget()
        if custom_tab is not None:
            custom_tab.controller.match_to_current_frame()

    def toggle_scatter(self):
        """Toggle the visibility of the scatter frame."""
        custom_tab = self.tab_widget.currentWidget()
        if custom_tab is not None:
            custom_tab.controller.toggle_scatter()

    def toggle_grb_oa_pop(self):
        """Toggle the visibility of the GRB Optical Afterglow Population."""
        custom_tab = self.tab_widget.currentWidget()
        if custom_tab is not None:
            custom_tab.controller.toggle_grb_oa_pop()

    def add_candidate(self):
        """Add a candidate to the current frame."""
        custom_tab = self.tab_widget.currentWidget()
        if custom_tab is not None:
            custom_tab.controller.add_new_candidate()

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
        # add_frame_action = QAction("Add Frame", self)
        # add_frame_action.setShortcut(QKeySequence.StandardKey.New)
        # add_frame_action.triggered.connect(self.add_example)
        # file_menu.addAction(add_frame_action)

        # Open image action (Cmd+O / Ctrl+O)
        open_file_action = QAction("Open Image", self)
        open_file_action.setShortcut(QKeySequence.StandardKey.Open)
        open_file_action.triggered.connect(self.open_files)
        file_menu.addAction(open_file_action)

        # Delete Focused Frame action
        delete_frame_action = QAction("Delete Focused Frame", self)
        delete_frame_action.setShortcut(QKeySequence.StandardKey.Close)
        delete_frame_action.triggered.connect(self.delete_focused_frame)
        file_menu.addAction(delete_frame_action)

        # Show example widget
        example_action = QAction("Show Examples", self)
        example_action.triggered.connect(self.show_examples)
        file_menu.addAction(example_action)
        example_action.setShortcut(QKeySequence("Ctrl+E"))

        # Show button widget
        button_action = QAction("Show Buttons", self)
        button_action.triggered.connect(self.button_widget.show)
        file_menu.addAction(button_action)
        button_action.setShortcut(QKeySequence("Ctrl+B"))

        # Exit action
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def show_examples(self):
        """Show a dialog with buttons to add example frames."""
        if self.example_widget is None:
            if self.tab_widget.count() == 0:
                self.add_new_tab(title="Examples")
            self.example_widget = ExampleWidget(tab_widget=self.tab_widget)
        self.example_widget.show()

    def closeEvent(self, event):
        """Ensure all floating windows are closed when MainWindow closes."""
        if self.example_widget:
            self.example_widget.close()
        self.button_widget.close()
        self.save_state()
        event.accept()

    def save_state(self):
        """Save the current state of the application."""
        settings = QSettings("Celexta", "Celexta")
        settings.setValue("window/geometry", self.saveGeometry())
        settings.setValue("window/state", self.saveState())
        init.save_session(self)

    def load_state(self):
        """Load the saved state of the application."""
        settings = QSettings("Celexta", "Celexta")
        self.restoreGeometry(settings.value("window/geometry", self.saveGeometry()))
        self.restoreState(settings.value("window/state", self.saveState()))
        try:
            init.load_session(self)
        except Exception as e:
            log.exception(f"Failed to load session data: {e}")

    # Tabs management
    def add_new_tab(self, *args, title=None, style="pyqtgraph"):
        """Add a new tab with a frame."""
        log.info("Adding new tab")
        if title is None:
            title = f"Tab {self.tab_widget.count() + 1}"
        custom_tab = CustomTab(style=style, parent=self.tab_widget)
        self.tab_widget.addTab(custom_tab, title)
        self.tab_widget.setCurrentWidget(custom_tab)
        return custom_tab

    def close_current_tab(self):
        """Close the currently focused tab."""
        current_index = self.tab_widget.currentIndex()
        if current_index != -1:  # Ensure there's a tab to remove
            current_title = self.tab_widget.tabText(current_index)
            log.info(f"Removed tab: {current_title}")
            self.tab_widget.removeTab(current_index)

    def rename_tab(self, index):
        """Allow the user to rename a tab by double-clicking on it."""
        if index != -1:  # Ensure a valid tab is selected
            current_title = self.tab_widget.tabText(index)
            new_title, ok = QInputDialog.getText(self, "Rename Tab", "Enter new tab name:", text=current_title)
            if ok and new_title.strip():  # Ensure it's not empty
                # Check if the new title is unique
                existing_names = [self.tab_widget.tabText(i) for i in range(self.tab_widget.count())]
                if new_title in existing_names:
                    new_title = f"{new_title} (1)"
                    while new_title in existing_names:
                        new_title = f"{new_title[:-3]}({int(new_title[-2]) + 1})"
                self.tab_widget.setTabText(index, new_title)

    @requires_tab
    def delete_focused_frame(self, *args, **kwargs):
        """Delete the currently focused frame."""
        custom_tab = self.tab_widget.currentWidget()
        custom_tab.controller.delete_frame(custom_tab.controller.focused_frame)

    def open_files(self):
        """Open a FITS file and add it to the current frame."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            caption="Select Files",
            directory=str(Path(self.config["files"].get("last_opened", ".")).expanduser().parent),
            filter="FITS files (*.fits *.fit)",
        )
        if files:
            for fname in files:
                with fits.open(fname) as hdul:
                    _hdu = None
                    for _hdu in hdul:
                        if _hdu.data is not None:
                            hdu = _hdu
                            break
                    if _hdu is None:
                        log.warning(f"No HDU with data found in {fname}")
                        return
                    if self.tab_widget.count() == 0:
                        self.add_new_tab(title=Path(fname).name)
                    custom_tab = self.tab_widget.currentWidget()
                    custom_tab.controller.add_image_frame(
                        hdu.data,
                        WCS(hdu.header),
                        header=hdu.header,
                        name=Path(fname).name,
                    )
                init.update_last_opened(fname)

    def open_catalog_query_dialog(self):
        """Open the catalog query dialog and retrieve results."""
        dialog = CatalogQueryDialog(parent=self, catalogs=CATALOGS)

        # Get the current tab's plot widget
        custom_tab = self.tab_widget.currentWidget()
        if custom_tab is not None:
            # If there are frames, pre-fill the dialog with the current frame's center coordinates
            if custom_tab.controller.image_frames:
                if custom_tab.controller.focused_frame is None:
                    custom_tab.controller.set_focus(custom_tab.controller.image_frames[-1])
                frame = custom_tab.controller.focused_frame

                # Pre-fill the dialog with the current center coordinates
                sc = frame.get_world_center()
                # Get the current radius of the frame as the Field of view divided by 2
                radius = frame.get_world_fov() / 2
                dialog.ra_input.setText(f"{sc.ra.to(unit="deg").value:.5f}")
                dialog.dec_input.setText(f"{sc.dec.to(unit="deg").value:.5f}")
                dialog.radius_input.setText(f"{radius.to(unit="arcmin").value:.0f}")
                dialog.radius_unit_combo.setCurrentText("arcmin")
        if dialog.exec():  # If user clicks submit (i.e., dialog is accepted)
            query_type, data, meta = dialog.query_result  # Retrieve stored result

            if query_type == "image":
                img_data = data.data
                wcs = WCS(data)
                custom_tab.controller.add_image_frame(
                    img_data,
                    wcs,
                    header=data.header,
                    name=meta["catalog"] + f' {meta["filter"]} band',
                )

            elif query_type == "sources":
                # Turn into CustomTable
                table = CustomTable(data=data, name=meta["catalog"])
                custom_tab.controller.add(table)

    def open_fsc_query_dialog(self):
        """Open the FSC query dialog and retrieve results."""
        if hasattr(self.tab_widget.currentWidget(), "burst_id"):
            burst_id = self.tab_widget.currentWidget().burst_id
        else:
            burst_id = ""

        dialog = svom_fsc.SVOMQueryDialog(parent=self, burst_id=burst_id)
        if dialog.exec():
            # Get the burst id
            burst_id = dialog.burst_id_field.text()
            log.info(f"Querying SVOM/FSC for burst ID: {burst_id}")
            # Add a new tab if there are no tabs
            if self.tab_widget.count() == 0:
                self.add_new_tab(title=burst_id)
            # Store the burst ID in the tab widget
            self.tab_widget.currentWidget().burst_id = burst_id
            try:
                # Add QPO_MXT and QPO_VT data to the frame
                custom_tab = self.tab_widget.currentWidget()
                svom_fsc.add_qim1b_vt(custom_tab, burst_id)
                svom_fsc.add_qpo_mxt(custom_tab, burst_id)
                svom_fsc.add_qpo_vt(custom_tab, burst_id)
            except Exception as e:
                log.exception(f"Failed to display SVOM data for burst id: {burst_id}")
                show_error_popup(
                    title="Could not display SVOM data",
                    text="An error occurred while displaying:",
                    error_message=str(e),
                )


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
    default_font = QFont("CMU Serif", 12)  # Change to preferred font and size
    app.setFont(default_font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
