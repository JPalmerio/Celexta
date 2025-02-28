import logging

import astropy.units as u
import numpy as np
import zhunter.catalogs as cat
from astropy.coordinates import SkyCoord
from astropy.table import Table
from astropy.units import Quantity
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from celexta import __CELEXTA_DIR__ as ROOTDIR
from celexta.error_handling import show_error_popup
from celexta.utils import create_input_field

log = logging.getLogger(__name__)

CATALOGS = {
    "Legacy Survey DR10": {
        "filters": ["g", "r", "i", "z"],
    },
    "Pan-STARRS DR2": {
        "filters": ["g", "r", "i", "z", "y"],
    },
    "Gaia DR3": {
        "filters": [],
    },
}


class CatalogQueryDialog(QDialog):
    """Pop-up dialog to query astronomical catalogs with RA, Dec, Radius, and filters."""

    def __init__(self, catalogs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Query Catalogs")
        self.setFixedWidth(400)  # Ensure a clean layout

        self.catalogs = catalogs
        # Main vertical layout
        main_layout = QVBoxLayout(self)

        # Persistent storage for last input values
        # self.settings = QSettings("Celexta", "CatalogQuery")

        grid_layout = self.create_grid_layout()
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

    def create_grid_layout(self):
        """Create a grid layout for the input fields."""
        # Grid Layout for Fields
        grid_layout = QGridLayout()

        # --- Catalog Selection (Row 0) ---
        grid_layout.addWidget(QLabel("Catalog:"), 0, 0)
        self.catalog_combo = QComboBox()
        self.catalog_combo.addItems(self.catalogs.keys())
        self.catalog_combo.currentIndexChanged.connect(self.update_filters)
        grid_layout.addWidget(self.catalog_combo, 0, 1, 1, 2)  # Span across columns 1 & 2

        # --- R.A. Field (Row 1) ---
        self.ra_input, self.ra_unit_combo = create_input_field(["degree", "hourangle"])
        grid_layout.addWidget(QLabel("R.A.:"), 1, 0)
        grid_layout.addWidget(self.ra_input, 1, 1)
        grid_layout.addWidget(self.ra_unit_combo, 1, 2)

        # --- Declination Field (Row 2) ---
        self.dec_input, self.dec_unit_combo = create_input_field(["degree"])
        grid_layout.addWidget(QLabel("Declination:"), 2, 0)
        grid_layout.addWidget(self.dec_input, 2, 1)
        grid_layout.addWidget(self.dec_unit_combo, 2, 2)

        # --- Radius Field (Row 3) ---
        self.radius_input, self.radius_unit_combo = create_input_field(["arcmin", "arcsec", "degree"])
        grid_layout.addWidget(QLabel("Radius:"), 3, 0)
        grid_layout.addWidget(self.radius_input, 3, 1)
        grid_layout.addWidget(self.radius_unit_combo, 3, 2)

        # --- Filter Selection (Row 4) ---
        grid_layout.addWidget(QLabel("Filter:"), 4, 0)
        self.filter_combo = QComboBox()
        grid_layout.addWidget(self.filter_combo, 4, 1)
        return grid_layout

    def update_filters(self):
        """Update the available filters based on the selected catalog."""
        selected_catalog = self.catalog_combo.currentText()
        self.filter_combo.clear()
        self.filter_combo.addItems(self.catalogs.get(selected_catalog, {}).get("filters", []))

    def get_ra_dec(self) -> tuple[Quantity[u.deg], Quantity[u.deg]]:
        """Retrieve the RA and Dec values from the input fields."""
        ra = self.ra_input.text()
        dec = self.dec_input.text()
        ra_unit = self.ra_unit_combo.currentText()
        dec_unit = self.dec_unit_combo.currentText()
        # Use SkyCoord to validate the input
        sc = SkyCoord(ra=ra, dec=dec, unit=(ra_unit, dec_unit), frame="icrs")
        return sc.ra.to("deg"), sc.dec.to("deg")

    def get_radius(self) -> Quantity[u.deg]:
        """Retrieve the radius value from the input fields."""
        radius = self.radius_input.text()
        radius_unit = self.radius_unit_combo.currentText()
        if not radius:
            raise ValueError("Radius cannot be empty")

        return u.Quantity(radius, unit=radius_unit).to("deg")

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

    def query_image(self):
        """Handle querying an image from the selected catalog."""
        try:
            ra, dec = self.get_ra_dec()
            radius = self.get_radius()
            query_data = self.get_query_data()
            band = query_data["filter"]
            log.info(
                f"Querying {band} band image from catalog {query_data['catalog']} "
                f"at RA={ra:5f} Dec={dec:5f}, Radius={radius.to(u.arcmin):3f}"
            )

            if query_data["catalog"] == "Legacy Survey DR10":
                im_size = cat.get_img_size(np.sqrt(2) * radius, arcsec_per_pixel=0.262)
                im_hdu = cat.get_ls_image(ra=ra.value, dec=dec.value, size=im_size, bands=band)
                self.query_result = ("image", im_hdu, query_data)

            elif query_data["catalog"] == "Pan-STARRS DR2":
                im_size = cat.get_img_size(radius, arcsec_per_pixel=0.25)
                im_hdu = cat.get_ps1_image(ra=ra.value, dec=dec.value, size=im_size, bands=band)
                self.query_result = ("image", im_hdu, query_data)

            elif query_data["catalog"] == "Gaia DR3":
                raise ValueError("Gaia does not produce images")

            self.accept()
        except Exception as e:
            log.exception("Error querying image")
            show_error_popup(
                title="Query Error",
                text="An error occurred while querying:",
                error_message=str(e),
            )

    def query_sources(self):
        """Handle querying sources from the selected catalog."""
        try:
            ra, dec = self.get_ra_dec()
            radius = self.get_radius()
            query_data = self.get_query_data()
            log.info(
                f"Querying sources for catalog {query_data['catalog']} at RA={ra:5f} Dec={dec:5f}, Radius={radius.to(u.arcmin):3f}"
            )

            if query_data["catalog"] == "Legacy Survey DR10":
                sources = query_lsdr10_photoz(ra=ra, dec=dec, radius=radius)
                self.query_result = ("sources", sources, query_data)

            elif query_data["catalog"] == "Pan-STARRS DR2":
                raise NotImplementedError("Source query not implemented for Pan-STARRS DR2")

            elif query_data["catalog"] == "Gaia DR3":
                raise NotImplementedError("Source query not implemented for Gaia DR3")

            self.accept()
        except Exception as e:
            log.exception("Error querying sources")
            show_error_popup(
                title="Query Error",
                text="An error occurred while querying:",
                error_message=str(e),
            )


def query_lsdr10_photoz(
    ra: Quantity[u.deg],
    dec: Quantity[u.deg],
    radius: Quantity[u.deg],
    n_src_max=10000,
    cache=True,
    format_table=True,
):
    """Query the Legacy Survey DR10 for photometric redshifts of sources

    Parameters
    ----------
    ra : Quantity
        Right ascension in degrees.
    dec : Quantity
        Declination in degrees.
    radius : Quantity
        Radius in degrees.
    n_src_max : int, optional
        Maximum number of sources to return.
    cache : bool, optional
        If ``True``, cache the query results.
    format_table : bool, optional
        If ``True``, format the table to a more user-friendly format.

    Returns
    -------
    astropy.table.Table
        Table with the results of the query.
    """
    tractor_cols = (
        "ls_id",
        "ra",
        "dec",
        "type",
        "flux_g",
        "flux_r",
        "flux_i",
        "flux_z",
        "flux_ivar_g",
        "flux_ivar_r",
        "flux_ivar_i",
        "flux_ivar_z",
    )
    photoz_cols = (
        "ls_id",
        "z_spec",
        "z_phot_median_i",
        "z_phot_l68_i",
        "z_phot_u68_i",
        "z_phot_median",
        "z_phot_l68",
        "z_phot_u68",
    )
    cache_dir = ROOTDIR / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    fname = cache_dir / (
        f"lsdr10_photoz_query_results_ra{ra.to(u.deg).value:.2f}_dec{dec.to(u.deg).value:.2f}_rad{radius.to(u.deg).value:2f}_nmax{n_src_max:d}.csv"
    )

    if fname.exists():
        log.debug(f"Reading cached query results from {fname!s}")
    else:
        log.debug("Querying LS DR10 catalog")
        from dl import queryClient as qc

        result = qc.query(
            sql=f"""
        SELECT
            {','.join([f't.{col}' for col in tractor_cols])},
            {','.join([f'p.{col}' for col in photoz_cols])}
        FROM 
            ls_dr10.tractor AS t
        JOIN 
            ls_dr10.photo_z AS p
        ON 
            t.ls_id = p.ls_id
        WHERE 
            't' = Q3C_RADIAL_QUERY(t.ra, t.dec, {ra.to(u.deg).value}, {dec.to(u.deg).value}, {radius.to(u.deg).value})
        LIMIT {n_src_max:d}
        """
        )

        with open(fname, "w") as f:
            f.write(result)
    tab = Table.read(fname, format="ascii.csv")
    if not cache:
        fname.unlink()
    if format_table:
        tab = format_lsdr10_query_results(tab)
    return tab


def format_lsdr10_query_results(tab: Table) -> Table:
    """
    Format the results of a query to the Legacy Survey DR10 to a more user-friendly format.

    Parameters
    ----------
    tab : astropy.table.Table
        Table with the results of the query to the Legacy Survey DR10.

    Returns
    -------
    astropy.table.Table
        Formatted table with the results.
    """
    # Copy the table to avoid modifying the original
    tab = tab.copy()
    if len(tab) == 0:
        return tab
    # Get the bands from the column names (e.g. 'flux_g')
    bands = [col[-1] for col in tab.columns if "flux_" in col]
    # For each band, calculate the magnitude and propagate the error
    for b in bands:
        # Use the inverse variance column for the error
        log10_flux, log10_flux_uncp, log10_flux_uncm = propagate_uncertainty_lin_to_log(
            tab[f"flux_{b}"], 1 / np.sqrt(tab[f"flux_ivar_{b}"])
        )
        # Convert log10(flux) to mag (formula comes from the conversion from linear fluxes in nanomaggies to AB magnitudes)
        tab[f"mag_{b}"] = 22.5 - 2.5 * log10_flux
        # Scale uncertainty as well
        tab[f"mag_{b}_uncp"], tab[f"mag_{b}_uncm"] = (
            2.5 * log10_flux_uncp,
            2.5 * log10_flux_uncm,
        )

    # Format redshift columns
    tab["z"] = tab["z_spec"].astype(float)
    # Set uncertainties to 0 for spectroscopic redshift (even though that's not strictly true)
    tab["z_uncp"], tab["z_uncm"] = np.zeros(len(tab)), np.zeros(len(tab))
    tab["z_origin"] = "spectro"

    # -99 is the value returned by Legacy Survey for invalid or missing data
    mask = np.where(tab["z"] == -99)[0]
    # Where no spectroscopic redshift, use photometric redshift with i-band
    tab["z"][mask] = tab["z_phot_median_i"][mask]
    tab["z_origin"][mask] = "photo_i"
    # Convert uncertainty from a bound value to plus/minus value
    tab["z_uncp"][mask] = tab["z_phot_u68_i"][mask] - tab["z_phot_median_i"][mask]
    tab["z_uncm"][mask] = tab["z_phot_median_i"][mask] - tab["z_phot_l68_i"][mask]

    mask = np.where(tab["z"] == -99)[0]
    # Where no photometric redshift with i-band, use regular photometric redshift (without i-band)
    tab["z"][mask] = tab["z_phot_median"][mask]
    tab["z_origin"][mask] = "photo"
    # Convert uncertainty from a bound value to plus/minus value
    tab["z_uncp"][mask] = tab["z_phot_u68"][mask] - tab["z_phot_median"][mask]
    tab["z_uncm"][mask] = tab["z_phot_median"][mask] - tab["z_phot_l68"][mask]

    # Remove columns no longer useful
    tab.remove_columns(
        [f"flux_{b}" for b in bands]
        + [f"flux_ivar_{b}" for b in bands]
        + [
            "z_spec",
            "z_phot_median_i",
            "z_phot_l68_i",
            "z_phot_u68_i",
            "z_phot_median",
            "z_phot_l68",
            "z_phot_u68",
            "ls_id_1",  # Drop ls_id_1 duplicate column
        ]
    )
    tab.rename_columns(names=["ra", "dec"], new_names=["RA", "DEC"])
    return tab


def propagate_uncertainty_log_to_lin(
    log_x: float,
    log_x_uncp: float,
    log_x_uncm: float | None = None,
) -> tuple[float, float, float]:
    """
    Takes logscale data with uncertainties and converts to linear scale with correct uncertainty propagation.

    If `log_x_uncm` is not provided, uncertainties are assumed symmetric.

    Parameters
    ----------
    log_x : int, float, array-like
        The logarithmic value or array to convert to linear.
    log_x_uncp : float, array-like
        The positive uncertainty in logscale.
    log_x_uncm : float, array-like, optional
        The negative uncertainty in logscale. If not provided, uncertainties are assumed symmetric.

    Returns
    -------
    tuple
        x, x_uncp, x_uncm
    """
    if log_x_uncm is None:
        log_x_uncm = log_x_uncp
    x = 10**log_x
    x_uncp = x * (10**log_x_uncp - 1.0)
    x_uncm = x * (1.0 - 10 ** (-log_x_uncm))

    return x, x_uncp, x_uncm


def propagate_uncertainty_lin_to_log(
    x: float,
    x_uncp: float,
    x_uncm: float | None = None,
) -> tuple[float, float, float]:
    """
    Takes linear scale data with uncertainties and converts to logscale with correct uncertainty propagation.

    If `x_uncm` is not provided, uncertainties are assumed symmetric.

    Parameters
    ----------
    x : float, array-like
        The linear value or array to convert to logarithmic.
    x_uncp : float, array-like
        The positive uncertainty in linear scale.
    x_uncm : float, array-like, optional
        The negative uncertainty in linear scale. If not provided, uncertainties are assumed symmetric.

    Returns
    -------
    tuple
        log_x, log_x_uncp, log_x_uncm
    """
    if x_uncm is None:
        x_uncm = x_uncp
    log_x = np.log10(x)
    log_x_uncp = np.log10((x + x_uncp) / x)
    log_x_uncm = np.log10(x / (x - x_uncm))

    return log_x, log_x_uncp, log_x_uncm
