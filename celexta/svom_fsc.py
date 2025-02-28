import logging
from pathlib import Path
import astropy.units as u
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.table import Table
from astropy.visualization import MinMaxInterval
from astropy.wcs import WCS
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)
from svom.messaging import SdbIo

from celexta.aesthetics import get_blues, get_reds
from celexta.candidates import Candidate
from celexta.custom_tab import CustomTab
from celexta.error_handling import show_error_popup, show_warning_popup
from celexta.initialize import USR_DIRS
from celexta.regions import CircleRegion
from celexta.tables import CustomTable
from zhunter.photometry import PhotometricPoint

log = logging.getLogger(__name__)


class SVOMQueryDialog(QDialog):
    """Pop-up dialog to query SVOM Science DataBase."""

    def __init__(self, burst_id: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Query SVOM Science DataBase")

        # Main vertical layout
        main_layout = QVBoxLayout(self)

        burst_id_layout = QHBoxLayout()
        self.burst_id_field = QLineEdit()
        self.burst_id_field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.burst_id_field.setFixedWidth(120)
        self.burst_id_field.setText(burst_id)
        burst_id_layout.addWidget(QLabel("Burst ID:"))
        burst_id_layout.addWidget(self.burst_id_field)
        main_layout.addLayout(burst_id_layout)

        # Checkbox for refreshing data or not
        self.refresh_checkbox = QCheckBox("Refresh data")

        # --- Query Button ---
        bot_layout = QHBoxLayout()
        self.query_sdb_button = QPushButton("Query SDB")
        self.query_sdb_button.clicked.connect(self.query_sdb)
        bot_layout.addWidget(self.query_sdb_button)
        bot_layout.addWidget(self.refresh_checkbox)
        main_layout.addLayout(bot_layout)

        # Set main layout
        self.setLayout(main_layout)

    def query_sdb(self):
        """Query the SVOM Science DataBase."""
        burst_id = self.burst_id_field.text()
        # Get the refresh state from the checkbox
        refresh = self.refresh_checkbox.isChecked()
        try:
            fetch_data(burst_id, refresh=refresh)
            self.accept()
        except Exception as e:
            log.exception(f"Failed to fetch SVOM data for burst id: {burst_id}")
            show_error_popup(
                title="FSC Query Error",
                text="An error occurred while querying:",
                error_message=str(e),
            )


def fetch_data(burst_id: str, refresh: bool = False):
    """Fetch SVOM data from SDB and store in cache directory."""
    # Create a directory to store the data
    data_dir = USR_DIRS["CACHE"] / f"svom/{burst_id}"
    data_dir.mkdir(parents=True, exist_ok=True)

    sdb_client = SdbIo(fsc_url="https://fsc.svom.org")
    for acronym in ("QCANDI_VT", "QPO_VT", "QIM1B_VT", "QPO_MXT", "QPO_ECL"):
        fname = data_dir / f"{acronym.lower()}.fits"
        # Skip if file exists and not refreshing
        if fname.exists() and not refresh:
            continue
        sdb_client.save_latest_fits_file(
            acronym=acronym,
            burst_id=burst_id,
            filename=str(fname),
        )


def add_qpo_mxt(custom_tab: CustomTab, burst_id: str, fname: str = None):
    """Add QPO MXT data to the frame."""
    if fname is None:
        data_dir = USR_DIRS["CACHE"] / f"svom/{burst_id}"
        fname = data_dir / "qpo_mxt.fits"
    hdul = fits.open(fname)
    # Check if the file is QPO_VT and if so get the MXT information from the header
    if hdul[0].header.get("CARD", None) == "QPO_VT":
        ra = hdul[0].header["MXT_RA"] * u.deg
        dec = hdul[0].header["MXT_DEC"] * u.deg
        unc = hdul[0].header["MXT_ERR"] * u.deg
        if any(c is None for c in (ra, dec, unc)):
            log.warning("No QPO_MXT information in QPO_VT")
        return
    # Check if the file is QPO_MXT
    if hdul[0].header.get("CARD", None) == "QPO_MXT":
        qpo_mxt = hdul
        for i in range(1, 4):
            if f"QPO_MXT_S{i}" not in qpo_mxt:
                log.warning(f"No extension QPO_MXT_S{i} found, moving on.")
                continue

            tab = Table.read(qpo_mxt, hdu=f"QPO_MXT_S{i}")

            if len(tab) == 0:
                log.warning(f"Empty extension QPO_MXT_S{i}, moving on.")
                continue

            # Use the value with the lowest uncertainty (R90)
            ind_min_r90 = tab["R90"].argmin()
            known_src = tab[ind_min_r90]["KNOWN_SOURCE"]
            if known_src == 1:
                log.warning(f"Source {i} of QPO_MXT has flag KNOWN_SOURCE, moving on to next source")
                continue

            ra = tab[ind_min_r90]["RA"] * tab["RA"].unit
            dec = tab[ind_min_r90]["DEC"] * tab["DEC"].unit
            unc = tab[ind_min_r90]["R90"] * tab["R90"].unit

    mxt_pos = CircleRegion(
        SkyCoord(ra=ra, dec=dec, frame="icrs"),
        radius=unc,
        name="QPO_MXT",
        color="cyan",
    )
    custom_tab.controller.add(mxt_pos)


def add_qcandi_vt(custom_tab: CustomTab, burst_id: str, fname: str = None):
    """Add QCANDI VT data to the plot widget."""
    if fname is None:
        data_dir = USR_DIRS["CACHE"] / f"svom/{burst_id}"
        fname = data_dir / "qcandi_vt.fits"
    qcandi_vt = fits.open(fname)
    t0 = qcandi_vt[0].header["TT_ECL"]
    if len(qcandi_vt) == 1:
        log.warning("No candidates found in the FITS file")
        show_warning_popup(
            title="No candidates found",
            text="No candidates found in the FITS file",
            warning_message=f"No candidates found for burst ID {burst_id}",
        )

        return
    for hdu in qcandi_vt[1:]:
        _tab = Table.read(hdu)
        obs = []
        for _obs in _tab:
            for band in ("R", "B"):
                # Detection
                if np.isfinite(_obs[f"MAG_{band}"]):
                    vt_obs = PhotometricPoint(
                        mag=_obs[f"MAG_{band}"] * u.ABmag,
                        unc=(
                            _obs[f"MAG_{band}_ERR"] * u.mag if _obs[f"MAG_{band}_ERR"] > 0 else 0.01 * u.mag
                        ),  # 0.01 mag minimum uncertainty
                        phot_filter=f"VT_{band}",
                        # phot_filter=f"VT_{band}",
                        obs_time=_obs["DATE-OBS"],
                        obs_duration=300 * u.s,
                    )
                else:
                    # Upper limit
                    vt_obs = PhotometricPoint(
                        mag=_obs[f"MAG_{band}_LIM"] * u.ABmag,
                        unc=0.0 * u.mag,
                        limit=True,
                        phot_filter=f"VT_{band}",
                        # phot_filter=f"VT_{band}",
                        obs_time=_obs["DATE-OBS"],
                        obs_duration=300 * u.s,
                    )
                obs.append(vt_obs)

        cand = Candidate(
            ra=hdu.header["RA"],
            dec=hdu.header["DEC"],
            name=f"VT_ID {hdu.header["VT_ID"]}",
            size=10,
            t0=t0,
            observations=obs,
        )
        cand.zorder = 11
        custom_tab.controller.add(cand)


def add_qpo_vt(custom_tab: CustomTab, burst_id: str, fname: str = None):
    """Add QPO VT data to the plot widget."""
    if fname is None:
        data_dir = USR_DIRS["CACHE"] / f"svom/{burst_id}"
        fname = data_dir / "qpo_vt.fits"
    qpo_vt = fits.open(fname)

    # All sources
    vt_all = Table.read(qpo_vt["COMBINED"])
    srcs = CustomTable(
        data=vt_all,
        name=f"VT all (N={len(qpo_vt['COMBINED'].data)})",
        color="yellow",
    )
    srcs.zorder = 10
    # Individual sequences
    av_seq = qpo_vt[0].header["SEQ_USED"].split(",")
    blues = get_blues(4)
    reds = get_reds(4)
    colors = {
        "B0": blues[0],
        "B1": blues[1],
        "B2": blues[2],
        "B3": blues[3],
        "R0": reds[0],
        "R1": reds[1],
        "R2": reds[2],
        "R3": reds[3],
    }
    av_seq.sort()
    for seq in av_seq:
        _tab = vt_all[vt_all[f"OBJID_{seq}"].mask]
        tab = CustomTable(
            data=_tab,
            name=f"{seq} (N={len(_tab)})",
            color=colors[seq],
        )
        tab.size = 10 + 5 * int(seq[1])
        tab.zorder = int(seq[1])
        custom_tab.controller.add(tab)

    # Catalogs
    # cat_used = qpo_vt[0].header["CATALOGS"].split(",")
    # for cat in cat_used:
    #     _tab = Table.read(qpo_vt[f"CAT_{cat}"])
    #     tab = CustomTable(
    #         data=_tab,
    #         name=f"{cat} (N={len(_tab)})",
    #         color="lightgrey",
    #     )
    #     custom_tab.controller.add(tab)

    # Add candidates
    cand = CustomTable(
        data=Table.read(qpo_vt["CANDIDATES"]),
        name=f"VT best candidates (N={len(qpo_vt['CANDIDATES'].data)})",
        color=(0, 1, 0),
    )
    cand.zorder = 11

    bcand = CustomTable(
        data=Table.read(qpo_vt["BEST_CANDIDATES"]),
        name=f"VT best candidates (N={len(qpo_vt['BEST_CANDIDATES'].data)})",
        color=(0, 1, 0),
    )
    bcand.zorder = 12
    custom_tab.controller.add(srcs)
    custom_tab.controller.add(cand)
    custom_tab.controller.add(bcand)


def add_qim1b_vt(custom_tab: CustomTab, burst_id: str, fname: str = None):
    """Add QIM1B VT data to the plot widget."""
    if fname is None:
        data_dir = USR_DIRS["CACHE"] / f"svom/{burst_id}"
        fname = data_dir / "qim1b_vt.fits"
    if not Path(fname).exists():
        log.warning(f"QIM1B VT data not found at {fname}")
        return
    qim1b_vt = fits.open(fname)
    # Skip PrimaryHDU
    for hdu in qim1b_vt[1:]:
        seq = hdu.name.split("_")[1]

        if seq[0] == "R":
            log.warning("Transposing data for 'R' band because there is a bug at the moment")
            hdu.data = hdu.data.T
            # hdu.data = hdu.data[::-1, :]

        name = f"VT {seq}"
        wcs = WCS(hdu)
        custom_tab.controller.add_image_frame(image_data=hdu.data, projection=wcs, name=name, interval=MinMaxInterval())


def add_qpo_ecl(custom_tab: CustomTab, burst_id: str, fname: str = None):
    """Add QPO ECL data to the plot widget."""
    if fname is None:
        data_dir = USR_DIRS["CACHE"] / f"svom/{burst_id}"
        fname = data_dir / "qpo_ecl.fits"
    if not fname.exists():
        log.warning(f"QPO ECL data not found at {fname}")
        return
    qpo_ecl = fits.open(fname)
    raise NotImplementedError("QPO_ECL not implemented yet")


if __name__ == "__main__":
    app = QApplication([])
    dialog = SVOMQueryDialog()
    dialog.exec()
