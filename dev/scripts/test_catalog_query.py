from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox
import logging
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QPushButton

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QSizePolicy,
    QWidget,
)

catalogs = {
    "Legacy Survey DR10": {
        "filters": ["g", "r", "i", "z"],
    },
    "Pan-STARRS DR2": {
        "filters": ["g", "r", "i", "z", "y"],
    },
}


class CatalogQueryDialog(QDialog):
    """Pop-up dialog to query astronomical catalogs with RA, Dec, Radius, and filters."""

    def __init__(self, catalogs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Query Catalog")
        self.setFixedWidth(400)  # Ensure a clean layout

        self.catalogs = catalogs
        # Main vertical layout
        main_layout = QVBoxLayout(self)

        # Grid Layout for Fields
        grid_layout = QGridLayout()

        # --- Catalog Selection (Row 0) ---
        grid_layout.addWidget(QLabel("Catalog:"), 0, 0)
        self.catalog_combo = QComboBox()
        self.catalog_combo.addItems(self.catalogs.keys())
        self.catalog_combo.currentIndexChanged.connect(self.update_filters)
        grid_layout.addWidget(self.catalog_combo, 0, 1, 1, 2)  # Span across columns 1 & 2

        # --- R.A. Field (Row 1) ---
        self.ra_input, self.ra_unit_combo = self.create_input_field(["degrees", "hours"])
        grid_layout.addWidget(QLabel("R.A.:"), 1, 0)
        grid_layout.addWidget(self.ra_input, 1, 1)
        grid_layout.addWidget(self.ra_unit_combo, 1, 2)

        # --- Declination Field (Row 2) ---
        self.dec_input, self.dec_unit_combo = self.create_input_field(["degrees"])
        grid_layout.addWidget(QLabel("Declination:"), 2, 0)
        grid_layout.addWidget(self.dec_input, 2, 1)
        grid_layout.addWidget(self.dec_unit_combo, 2, 2)

        # --- Radius Field (Row 3) ---
        self.radius_input, self.radius_unit_combo = self.create_input_field(["arcmin", "arcsec", "degrees"])
        grid_layout.addWidget(QLabel("Radius:"), 3, 0)
        grid_layout.addWidget(self.radius_input, 3, 1)
        grid_layout.addWidget(self.radius_unit_combo, 3, 2)

        # --- Filter Selection (Row 4) ---
        grid_layout.addWidget(QLabel("Filter:"), 4, 0)
        self.filter_combo = QComboBox()
        grid_layout.addWidget(
            self.filter_combo,
            4,
            1,
        )

        # Add Grid Layout to the Main Layout
        main_layout.addLayout(grid_layout)

        # --- Query Buttons (Below Grid) ---
        button_layout = QHBoxLayout()
        self.query_image_button = QPushButton("Query Image")
        self.query_sources_button = QPushButton("Query Sources")

        self.query_image_button.clicked.connect(self.query_image)
        self.query_sources_button.clicked.connect(self.query_sources)

        button_layout.addWidget(self.query_image_button)
        button_layout.addWidget(self.query_sources_button)
        main_layout.addLayout(button_layout)

        # Initialize filters based on selected catalog
        self.update_filters()

        # Set main layout
        self.setLayout(main_layout)

    def create_input_field(self, unit_options):
        """Create an input field and unit dropdown, ensuring proper alignment."""
        input_field = QLineEdit()
        input_field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        input_field.setFixedWidth(120)

        unit_combo = QComboBox()
        unit_combo.addItems(unit_options)
        unit_combo.setFixedWidth(80)

        return input_field, unit_combo

    def update_filters(self):
        """Update the available filters based on the selected catalog."""
        selected_catalog = self.catalog_combo.currentText()
        self.filter_combo.clear()
        self.filter_combo.addItems(self.catalogs.get(selected_catalog, {}).get("filters", []))

    def query_image(self):
        """Handle querying an image from the selected catalog."""
        query_data = self.get_query_data()
        log.info(f"Querying Image for catalog {query_data['catalog']} at RA={query_data['ra']} Dec={query_data['dec']}")
        self.accept()

    def query_sources(self):
        """Handle querying sources from the selected catalog."""
        query_data = self.get_query_data()
        log.info(
            f"Querying sources for catalog {query_data['catalog']} at RA={query_data['ra']} Dec={query_data['dec']}"
        )
        self.accept()

    def get_query_data(self):
        """Retrieve all input values for the query."""
        return {
            "catalog": self.catalog_combo.currentText(),
            "ra": self.ra_input.text(),
            "ra_unit": self.ra_unit_combo.currentText(),
            "dec": self.dec_input.text(),
            "dec_unit": self.dec_unit_combo.currentText(),
            "radius": self.radius_input.text(),
            "radius_unit": self.radius_unit_combo.currentText(),
            "filter": self.filter_combo.currentText(),
        }


class MainWindow(QMainWindow):
    """Main application window with tabs for frames."""

    def __init__(self):
        super().__init__()

        self.resize(1000, 800)
        # self.setCentralWidget()
        CatalogQueryDialog(parent=self, catalogs=catalogs).exec()


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
