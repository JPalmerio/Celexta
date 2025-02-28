import logging
from datetime import datetime
from pathlib import Path
from pprint import pformat
import astropy.units as u
import matplotlib.pyplot as plt
import numpy as np
import pyqtgraph as pg
import zhunter.catalogs as cat
from astropy.coordinates import SkyCoord
from astropy.table import Table
from astropy.time import Time
from astropy.units import Quantity
from astropy.wcs import WCS
from astropy.io.ascii import InconsistentTableError
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.colors import to_hex
from matplotlib.figure import Figure
from PyQt6.QtCore import (
    QAbstractListModel,
    QAbstractTableModel,
    QItemSelectionModel,
    QModelIndex,
    QObject,
    QPoint,
    QSettings,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QBrush, QColor, QIcon, QPixmap, QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import (
    QColorDialog,
    QApplication,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QTextEdit,
    QFileDialog,
    QFrame,
)
from zhunter.photometry import PhotometricPoint

from celexta import __CELEXTA_DIR__ as ROOTDIR
from celexta.aesthetics import ColorManager, create_icon
from celexta.error_handling import show_error_popup
from celexta.utils import create_input_field
from celexta.tables import CustomTable, GlobalTableModel

log = logging.getLogger(__name__)


class Candidate(QObject):
    """Class to hold candidate information."""

    def __init__(
        self,
        position: SkyCoord,
        positional_uncertainty: Quantity | None = None,
        name: str | None = None,
        t0: Time | None = None,
        observations: list[PhotometricPoint] | None = None,
        color: str | None = None,
        meta: dict | None = None,
        files: list | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.pos = position
        self.pos_unc = positional_uncertainty if positional_uncertainty is not None else 1 * u.arcsec
        self.name = name if name is not None else "Candidate"
        self.t0 = t0
        self.color = to_hex(color) if color is not None else None
        self.meta = meta if meta is not None else {}
        self.observations = observations if observations is not None else []
        self.files = files if files is not None else []

    def __repr__(self):
        return f"Candidate: {self.name} (ra={self.pos.ra}, dec={self.pos.dec} +/- {self.pos_unc})"

    def __str__(self):
        return f"Candidate: {self.name} (ra={self.pos.ra}, dec={self.pos.dec} +/- {self.pos_unc})"

    def to_serializable_dict(self, save_dir: str | Path):
        """Return a JSON representation of the candidate.

        The observations are saved to a file in ECSV format.
        """
        fname = Path(save_dir) / f"{self.name}.ecsv"
        self.obs_to_file(fname)
        return {
            "name": self.name,
            "pos": {
                "ra": self.pos.ra.deg,
                "dec": self.pos.dec.deg,
                "unit": "deg",
                "frame": self.pos.frame.name,
            },
            "pos_unc": {"value": self.pos_unc.to("deg").value, "unit": "deg"},
            "color": self.color,
            "t0": self.t0.isot if self.t0 is not None else None,
            "meta": self.meta,
            "observations": str(fname.expanduser().resolve()),
        }

    def obs_to_file(self, fname: str | Path):
        """Save the observations to a file."""
        log.debug(f"Saving observations of candidate {self!s} to file: {fname!s}")
        tab = Table(
            units={"mag": u.ABmag, "unc": u.mag, "obs_duration": u.s},
            names=["mag", "unc", "phot_filter", "obs_time", "obs_duration", "limit"],
            dtype=[float, float, str, str, float, bool],
        )
        for obs in self.observations:
            tab.add_row(obs.to_dict())
        tab.write(fname, overwrite=True)

    @classmethod
    def obs_from_file(cls, fname: str | Path):
        """Load the observations from a file."""
        tab = Table.read(fname)
        log.debug(f"Loaded observations from file: {fname!s} {pformat(tab)}")
        # Check that the table has the required columns
        # and warn the user if not
        required_cols = ["mag", "unc", "phot_filter", "obs_time", "obs_duration"]
        if not all(col in tab.colnames for col in required_cols):
            log.warning(f"Table missing required columns: {required_cols}, ignoring")
            return []
        # Extract only the required columns and limit
        tab = tab[required_cols + ["limit"]]
        obs = []
        for row in tab:
            phot_pt = PhotometricPoint(
                mag=row["mag"] * tab["mag"].unit,
                unc=row["unc"] * tab["unc"].unit,
                phot_filter=row["phot_filter"],
                obs_time=Time(row["obs_time"]),
                obs_duration=row["obs_duration"] * tab["obs_duration"].unit,
                limit=row["limit"],
            )
            obs.append(phot_pt)

        return obs

    @classmethod
    def from_serializable_dict(cls, data: dict):
        """Load the candidate from a JSON representation."""
        name = data["name"]
        pos = SkyCoord(
            ra=data["pos"]["ra"],
            dec=data["pos"]["dec"],
            unit=data["pos"]["unit"],
            frame=data["pos"]["frame"],
        )
        pos_unc = data["pos_unc"]["value"] * u.deg
        color = data["color"]
        t0 = Time(data["t0"]) if data["t0"] is not None else None
        meta = data["meta"]
        observations = cls.obs_from_file(data["observations"])
        candidate = cls(
            position=pos,
            positional_uncertainty=pos_unc,
            name=name,
            t0=t0,
            color=color,
            meta=meta,
            observations=observations,
        )
        return candidate


class CandidateModel(QAbstractListModel):
    """Model to manage the various candidates in a given tab."""

    selectionChanged = pyqtSignal(object)  # (CustomTable)
    visibilityChanged = pyqtSignal(list)  # (bool, CustomTable)
    itemRemoved = pyqtSignal(object)  # (CustomTable)
    itemUpdated = pyqtSignal(object)  # (CustomTable)

    def __init__(self, parent=None, candidates=None):
        super().__init__(parent)
        self.candidates = candidates if candidates is not None else []
        self.visibility = {candidate: True for candidate in self.candidates}  # Track visibility
        self.selected_candidate = None  # Track selected candidate

    def rowCount(self, parent=None):
        """Return the number of candidates."""
        return len(self.candidates)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """Return the data for each candidate in the list."""
        if not index.isValid():
            return None
        candidate = self.candidates[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:  # Display name
            return candidate.name
        if role == Qt.ItemDataRole.DecorationRole:  # Display color
            return QColor(candidate.color)
        if role == Qt.ItemDataRole.CheckStateRole:  # Checkbox for visibility
            state = Qt.CheckState.Checked if self.visibility[candidate] else Qt.CheckState.Unchecked
            return state
        if role == Qt.ItemDataRole.UserRole:
            return candidate
        return None

    def flags(self, index):
        """Make items checkable."""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSeleccandidate | Qt.ItemFlag.ItemIsUserCheckable

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        """Handle checkbox toggles to update visibility."""
        if not index.isValid():
            return False
        if role == Qt.ItemDataRole.CheckStateRole:
            candidate = self.candidates[index.row()]
            new_state = value == Qt.CheckState.Checked.value
            # Check if the state is changing
            if self.visibility.get(candidate, True) != new_state:
                self.visibility[candidate] = new_state
                self.visibilityChanged.emit([new_state, candidate])
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
                return True
        return False

    def add_candidate(self, candidate):
        """Add a new candidate to the model."""
        if candidate in self.candidates:
            return
        row = len(self.candidates)
        self.insertRow(row, candidate=candidate)

    def insertRow(self, row, candidate, parent=QModelIndex()):
        """Insert a new row into the model."""
        if isinstance(row, QModelIndex):  # Ensure row is an integer
            row = row.row()

        if row < 0 or row > len(self.candidates):  # Ensure valid index
            return False
        # Finer grained that layoutChanged.emit()
        # Use QModelIndex() to indicate the parent is the root
        # i.e. no hierarchy for list models
        self.beginInsertRows(parent, row, row)
        self.candidates.insert(row, candidate)
        self.visibility[candidate] = True
        log.debug(f"Added candidate: {candidate!s}")
        if candidate.color is None:
            candidate.color = "red"
            log.warning("Table color not set. Defaulting to red.")

        # Notify views that the row insertion is complete.
        self.endInsertRows()
        return True

    def delete_candidate(self, candidate):
        """Delete a candidate from the model."""
        if candidate not in self.candidates:
            return
        row = self.get_index(candidate)
        self.removeRow(row)

    def removeRow(self, row, parent=QModelIndex()):
        """Remove a row from the model."""
        if isinstance(row, QModelIndex):  # Ensure row is an integer
            row = row.row()
        if row < 0 or row >= len(self.candidates):
            return False
        candidate = self.candidates[row]
        self.beginRemoveRows(parent, row, row)
        self.visibility.pop(candidate, None)
        del self.candidates[row]
        log.info(f"Deleted candidate: {candidate!s}")
        self.endRemoveRows()
        self.itemRemoved.emit(candidate)
        return True

    def select_candidate(self, candidate):
        """Select a candidate and emit signal."""
        if candidate is not self.selected_candidate:
            log.debug(f"Selecting candidate: {candidate!s}")
            self.selected_candidate = candidate
            self.selectionChanged.emit(candidate)

    def get_index(self, candidate):
        """Return the QModelIndex of the given candidate, or an invalid index if not found."""
        try:
            row = self.candidates.index(candidate)
            return self.createIndex(row, 0)
        except ValueError:
            return QModelIndex()

    def update_candidate(self, candidate, position=None, name=None, color=None):
        """Update the properties of a candidate."""
        log.debug(f"Updated candidate: {candidate!s}")
        if position is not None:
            candidate.pos = position
        if name is not None:
            candidate.name = name
        if color is not None:
            candidate.color = color

        # Emit dataChanged signal to update the views
        index = self.get_index(candidate)
        self.dataChanged.emit(index, index)
        self.itemUpdated.emit(candidate)


class CandidateEditor(QDialog):
    """Popup to edit candidate properties (RA, DEC, Radius, Name)."""

    def __init__(self, candidate=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Candidate")
        self.setModal(False)
        defaults = {
            "name": "",
            "trigger time": "",
            "t0": "",
            "ra": "",
            "dec": "",
            "radius": "",
            "color": "red",
            "files": [],
        }
        # Update defaults with candidate data
        if candidate is None:
            self.candidate = Candidate(SkyCoord(ra=0 * u.deg, dec=0 * u.deg))
        else:
            self.candidate = candidate
            defaults.update(
                {
                    "name": candidate.name,
                    "t0": f"{candidate.t0.isot}" if candidate.t0 is not None else "",
                    "ra": f"{candidate.pos.ra.to("deg").value:.6f}",
                    "dec": f"{candidate.pos.dec.to("deg").value:.6f}",
                    "radius": f"{candidate.pos_unc.to("deg").value:.6f}",
                    "color": candidate.color if candidate.color is not None else "red",
                    "files": candidate.files if candidate.files is not None else [],
                }
            )

        main_layout = QVBoxLayout(self)
        grid_layout = self.create_grid_layout(defaults)
        obs_layout = self.create_add_obs_layout()
        main_layout.addLayout(grid_layout)
        # add horizontal line
        line = QLabel()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)
        main_layout.addLayout(obs_layout)
        # Save/Cancel Buttons
        button_layout = QHBoxLayout()
        save_button = QPushButton("OK")
        save_button.clicked.connect(self.update_candidate)
        # Set focus to save button
        save_button.setFocus()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

    def create_grid_layout(self, defaults):
        """Create a grid layout for the input fields."""
        # Grid Layout for Fields
        grid_layout = QGridLayout()

        # --- Name Field (Row 0) ---
        self.name_input = QLineEdit(defaults["name"])
        grid_layout.addWidget(QLabel("Name:"), 0, 0)
        grid_layout.addWidget(self.name_input, 0, 1)

        # --- t0 Field (Row 1) ---
        self.t0_input = QLineEdit(defaults["t0"])
        grid_layout.addWidget(QLabel("t0:"), 1, 0)
        grid_layout.addWidget(self.t0_input, 1, 1)

        # --- R.A. Field (Row 2) ---
        self.ra_input, self.ra_unit_combo = create_input_field(
            unit_options=["degree", "hourangle"],
            text=str(defaults["ra"]),
        )
        grid_layout.addWidget(QLabel("R.A.:"), 2, 0)
        grid_layout.addWidget(self.ra_input, 2, 1)
        grid_layout.addWidget(self.ra_unit_combo, 2, 2)

        # --- Declination Field (Row 3) ---
        self.dec_input, self.dec_unit_combo = create_input_field(
            unit_options=["degree"],
            text=str(defaults["dec"]),
        )
        grid_layout.addWidget(QLabel("Declination:"), 3, 0)
        grid_layout.addWidget(self.dec_input, 3, 1)
        grid_layout.addWidget(self.dec_unit_combo, 3, 2)

        # --- Radius Field (Row 3) ---
        self.radius_input, self.radius_unit_combo = create_input_field(
            unit_options=["degree", "arcmin", "arcsec"],
            text=str(defaults["radius"]),
        )
        grid_layout.addWidget(QLabel("Radius:"), 4, 0)
        grid_layout.addWidget(self.radius_input, 4, 1)
        grid_layout.addWidget(self.radius_unit_combo, 4, 2)

        # Color Input
        self.color_input = QLineEdit(defaults["color"])
        self.color_btn = QPushButton("Choose color")
        # Dont let button get focus
        self.color_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.color_dialog = QColorDialog(parent=self)
        self.color_dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        self.color_dialog.setCurrentColor(QColor(defaults["color"]))
        self.color_btn.clicked.connect(self.color_dialog.open)
        self.color_dialog.accepted.connect(lambda: self.color_input.setText(self.color_dialog.selectedColor().name()))
        grid_layout.addWidget(QLabel("Color:"), 5, 0)
        grid_layout.addWidget(self.color_input, 5, 1)
        grid_layout.addWidget(self.color_btn, 5, 2)

        return grid_layout

    def create_add_obs_layout(self):
        """Create a layout for adding observations."""
        layout = QVBoxLayout()
        # Button to load files.
        self.loadButton = QPushButton("Load observations from files", self)
        self.loadButton.clicked.connect(self.load_files)
        self.loadButton.setToolTip("Load observations from one or multiple files.")
        self.loadButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.loadButton)

        # ListView to display the names of the loaded files.
        self.obs_list_view = QListView(self)
        self.obs_model = GlobalTableModel(self.obs_list_view)
        self.obs_list_view.setModel(self.obs_model)
        layout.addWidget(self.obs_list_view)

        # A multi-line text input widget.
        self.textEdit = QTextEdit(self)
        example_text = """# Recommended format (order of columns doesn't matter but name does)
# Assumed units: - s ABmag mag -
# Name = LCOGT
date-obs duration mag unc filter
2021-09-01T00:00:00 300 18.0 0.1 SDSS_r_prime
2021-09-01T00:01:00 300 18.1 0.1 SDSS_r_prime
2021-09-01T00:02:00 300 <18.2 0.0 SDSS_r_prime
"""
        self.textEdit.setPlainText(example_text)
        layout.addWidget(self.textEdit)

        # Button to save the text from the textEdit.
        self.saveButton = QPushButton("Load observations from text", self)
        self.saveButton.clicked.connect(self.load_obs_from_txt)
        self.saveButton.setToolTip("Load observations from the text box.")
        self.saveButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.saveButton)

        return layout

    def load_files(self):
        """
        Open a file dialog to select one or multiple files.

        The names of the selected files are added to the list view.
        """
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files")
        if files:
            for file_path in files:
                try:
                    # Extract the file name
                    file_name = file_path.split("/")[-1]
                    # Load the file
                    tab = Table.read(file_path, format="ascii")
                    log.debug(f"Loaded table from file :\n{tab}")
                    self.obs_model.add_table(CustomTable(tab))
                except InconsistentTableError as e:  # noqa: PERF203
                    log.exception("Error loading observations from file")
                    show_error_popup(
                        title="Could not load observations",
                        text="An error occurred while loading observations from file:",
                        error_message="Could not figure out format of the file.",
                    )
                except Exception as e:  # noqa: PERF203
                    log.exception(f"Error loading file: {file_path}")
                    show_error_popup(
                        title="Could not load file",
                        text=f"An error occurred while loading file {file_name}:",
                        error_message=str(e),
                    )

    def load_obs_from_txt(self):
        """Load observations from a text box."""
        text = self.textEdit.toPlainText()
        try:
            tab = Table.read(text.split("\n"), format="ascii")
            log.debug(f"Loaded table from text :\n{tab}")
            name = [n.split("=")[-1] for n in tab.meta["comments"] if "name" in n.lower()]
            self.obs_model.add_table(CustomTable(tab, name=name[-1] if name else "Table"))

        except InconsistentTableError as e:
            log.exception("Error loading observations from text")
            show_error_popup(
                title="Could not load observations",
                text="An error occurred while loading observations from text:",
                error_message="Could not figure out format of the text.",
            )
        except Exception as e:
            log.exception("Error loading observations from text")
            show_error_popup(
                title="Could not load observations",
                text="An error occurred while loading observations from text:",
                error_message=str(e),
            )

    def get_values(self):
        """Retrieve user-inputted values."""
        pos = self.get_position()
        radius = self.get_radius()
        try:
            new_values = {
                "pos": pos,
                "t0": Time(self.t0_input.text()) if self.t0_input.text() else None,
                "pos_unc": radius,
                "color": self.color_input.text(),
                "name": self.name_input.text(),
            }
        except Exception as e:
            log.exception("Error getting values")
            show_error_popup(
                title="Invalid input",
                text="An error occurred while parsing the input values:",
                error_message=str(e),
            )
        return new_values

    def get_position(self) -> SkyCoord:
        """Retrieve the RA and Dec values from the input fields."""
        ra = self.ra_input.text()
        dec = self.dec_input.text()
        ra_unit = self.ra_unit_combo.currentText()
        dec_unit = self.dec_unit_combo.currentText()
        # Use SkyCoord to validate the input
        try:
            sc = SkyCoord(ra=ra, dec=dec, unit=(ra_unit, dec_unit), frame="icrs")
        except Exception as e:
            log.exception("Error parsing RA/Dec")
            show_error_popup(
                title="Invalid RA/Dec",
                text="An error occurred while parsing the RA/Dec values:",
                error_message=str(e),
            )
        return sc

    def get_radius(self) -> Quantity[u.deg]:
        """Retrieve the radius value from the input fields."""
        radius = self.radius_input.text()
        radius_unit = self.radius_unit_combo.currentText()
        if not radius:
            raise ValueError("Radius cannot be empty")

        return u.Quantity(radius, unit=radius_unit).to("deg")

    def update_candidate(self):
        """Update the candidate with the new values."""
        values = self.get_values()
        for key, value in values.items():
            setattr(self.candidate, key, value)
        for tab in self.obs_model.tables:
            for row in tab.data:
                obs = PhotometricPoint(
                    mag=float(str(row["mag"]).strip("<")) * u.ABmag,
                    unc=row["unc"] * u.mag,
                    limit=str(row["mag"])[0] == "<",
                    phot_filter=row["filter"],
                    obs_time=Time(row["date-obs"]),
                    obs_duration=row["duration"] * u.s,
                )
                self.candidate.observations.append(obs)
        self.accept()


if __name__ == "__main__":
    import sys

    from PyQt6.QtGui import QFont

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

    # Main window
    window = QMainWindow()
    window.setGeometry(100, 100, 800, 600)
    window.setWindowTitle("Candidate Test")
    pw = pg.GraphicsLayoutWidget()
    window.setCentralWidget(pw)
    cand1 = Candidate(
        SkyCoord(ra=10 * u.deg, dec=20 * u.deg),
        name="Test Candidate",
        t0=Time(datetime.now()) - 200 * u.s,
        meta={"PROB_GRB": 0.99},
        observations=[
            PhotometricPoint(
                mag=(18 + i) * u.ABmag,
                unc=0.2 * u.mag,
                phot_filter="Gaia_RP",
                obs_time=Time(datetime.now()) + i * 3600 * u.s,
                obs_duration=300 * u.s,
            )
            for i in range(5)
        ]
        + [
            PhotometricPoint(
                mag=(18 + 6) * u.ABmag,
                unc=0.15 * u.mag,
                limit=True,
                phot_filter="Gaia_RP",
                obs_time=Time(datetime.now()) + 6 * 3600 * u.s,
                obs_duration=300 * u.s,
            )
        ],
    )
    cand2 = Candidate(
        position=SkyCoord(ra=10.0 * u.deg, dec=20.0001 * u.deg),
        t0=Time(datetime.now()) - 100 * u.s,
        positional_uncertainty=0.1 * u.arcsec,
        name="Test Candidate2",
        meta={"PROB_GRB": 0.69},
        observations=[
            PhotometricPoint(
                mag=(18 + i**2 / 10) * u.ABmag,
                unc=0.15 * u.mag,
                phot_filter="Gaia_BP",
                obs_time=Time(datetime.now()) + i * 3600 * u.s,
                obs_duration=300 * u.s,
            )
            for i in range(5)
        ]
        + [
            PhotometricPoint(
                mag=(18 + 6**2 / 10) * u.ABmag,
                unc=0.15 * u.mag,
                limit=True,
                phot_filter="Gaia_BP",
                obs_time=Time(datetime.now()) + 6 * 3600 * u.s,
                obs_duration=300 * u.s,
            )
        ],
    )
    # Create plots
    p_p = pw.addPlot(row=0, col=0, colspan=2)
    p_p.setAspectLocked()
    p_p.setLabel("left", "Declination", units="deg")
    p_p.setLabel("bottom", "Right Ascension", units="deg")
    pw.nextRow()
    p_t = pw.addPlot(row=1, col=0)
    p_t.setLabel("left", "Magnitude", units="ABmag")
    p_t.setLabel("bottom", "Time", units="MJD")
    p_s = pw.addPlot(row=1, col=1)
    p_s.setLabel("left", "Magnitude", units="ABmag")
    p_s.setLabel("bottom", "Wavelength", units="Angstrom", siPrefixEnableRange=((0, 0)))

    color_manager = ColorManager()
    for cand in (cand1, cand2):
        # Plot light curve
        for obs in cand.observations:
            log.info(f"{obs}")
            obs.plot_pyqt(vb=p_t.vb, mode="temporal", t0=cand.t0)
        # Plot spectra
        for obs in cand.observations[0::5]:
            obs.plot_pyqt(vb=p_s.vb, mode="spectral")
        # Plot position
        p_p.addItem(
            pg.ScatterPlotItem(
                [cand.pos.ra.to("deg").value],
                [cand.pos.dec.to("deg").value],
                pen=pg.mkPen(color_manager.get_color(), width=1),
                symbol="o",
                size=cand.pos_unc.to("deg").value,
                pxMode=False,
                brush=None,
                name=cand.name,
            )
        )
    # Invert the yaxis
    p_s.invertY()
    p_t.invertY()

    dialog = CandidateEditor()
    if dialog.exec():
        cand3 = dialog.candidate
        log.info(f"Updated candidate: {cand3}")
        for obs in cand3.observations:
            obs.plot_pyqt(vb=p_t.vb, mode="temporal", t0=cand3.t0)

    window.show()
    sys.exit(app.exec())
