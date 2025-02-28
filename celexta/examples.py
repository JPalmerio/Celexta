import logging
import warnings

import astropy.units as u
import matplotlib.pyplot as plt
import numpy as np
from astropy.io import fits
from astropy.table import Table
from astropy.utils.data import get_pkg_data_filename
from astropy.wcs import WCS

from celexta.regions import CircleRegion, QuadrangleRegion
from celexta.tables import CustomTable
from celexta.candidates import Candidate, PhotometricPoint
from astropy.time import Time
from datetime import datetime
from itertools import product
from astropy.coordinates import SkyCoord
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QComboBox

log = logging.getLogger(__name__)


class ExampleWidget(QWidget):
    """A Simple widget containing buttons to trigger examples"""

    def __init__(self, tab_widget, parent=None):
        super().__init__(parent)
        self.tab_widget = tab_widget
        tab_widget.currentChanged.connect(self.update_controller)
        self.controller = self.tab_widget.currentWidget().controller
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        add_frame_button = QPushButton("Add frame")
        add_region_button = QPushButton("Add region")
        add_table_button = QPushButton("Add table")
        add_candidate_button = QPushButton("Add candidate")
        add_full_example_button = QPushButton("Add full example")

        add_frame_button.clicked.connect(lambda x: self.controller.add_image_frame())
        add_region_button.clicked.connect(self.add_example_region)
        add_table_button.clicked.connect(self.add_example_table)
        add_candidate_button.clicked.connect(self.add_example_candidate)
        add_full_example_button.clicked.connect(self.add_full_example)

        self.example_name_cbbox = QComboBox()
        self.example_name_cbbox.addItems(["vt", "ps1", "galactic", "horse"])

        hlayout = QHBoxLayout()
        hlayout.addWidget(self.example_name_cbbox)
        hlayout.addWidget(add_full_example_button)

        self.layout.addWidget(add_frame_button)
        self.layout.addWidget(add_region_button)
        self.layout.addWidget(add_table_button)
        self.layout.addWidget(add_candidate_button)
        self.layout.addLayout(hlayout)

    def update_controller(self, index):
        self.controller = self.tab_widget.widget(index).controller

    def add_example_region(self):
        if self.controller.focused_frame is None:
            return

        region = generate_example_region(
            data=self.controller.focused_frame.img_data,
            wcs=self.controller.focused_frame.wcs,
        )
        self.controller.add(region)

    def add_example_table(self):
        if self.controller.focused_frame is None:
            return

        table = generate_example_table(
            data=self.controller.focused_frame.img_data,
            wcs=self.controller.focused_frame.wcs,
        )
        self.controller.add(table)

    def add_example_candidate(self):
        if self.controller.focused_frame is None:
            return

        candidate = generate_example_candidate(
            data=self.controller.focused_frame.img_data,
            wcs=self.controller.focused_frame.wcs,
        )
        self.controller.add(candidate)

    def add_full_example(self):

        example_name = self.example_name_cbbox.currentText()
        hdu = generate_example_image(example_name=example_name)
        im, wcs = hdu.data, WCS(hdu.header)
        self.controller.add_image_frame(im, wcs, name=example_name)
        region = generate_example_region(data=im, wcs=wcs)
        table = generate_example_table(data=im, wcs=wcs)
        candidate = generate_example_candidate(data=im, wcs=wcs)
        self.controller.add(region)
        self.controller.add(table)
        self.controller.add(candidate)


def generate_example_candidate(
    data,
    wcs,
    positional_uncertainty=None,
    nobs=5,
):
    num = np.random.uniform()  # random number between 0 and 1

    center = get_img_center(data=data, wcs=wcs)
    fov = get_img_fov(data=data, wcs=wcs)
    ra, dec = center.ra, center.dec
    # Add some random noise
    ra = ra + num * fov / 10
    dec = dec + num * fov / 10
    if positional_uncertainty is None:
        rad = num * fov / 4 + fov / 20
    else:
        rad = positional_uncertainty

    offset = {
        "LSST_u": 2.6 * 0.1 * np.random.uniform(),
        "LSST_g": 0.8 * 0.1 * np.random.uniform(),
        "LSST_r": 0.1 * 0.1 * np.random.uniform(),
        "LSST_i": 1.2 * 0.1 * np.random.uniform(),
        "LSST_z": 2.0 * 0.1 * np.random.uniform(),
        "LSST_y": 1.8 * 0.1 * np.random.uniform(),
    }
    # Add a candidate
    candidate = Candidate(
        position=SkyCoord(ra, dec),
        positional_uncertainty=rad,
        name="Test Candidate",
        t0=Time(datetime.now()),
        meta={"PROB_GRB": 0.99},
        observations=[
            PhotometricPoint(
                mag=(16 + i + offset[phot_filter] + 0.2 * np.random.uniform()) * u.ABmag,
                unc=0.2 * u.mag,
                phot_filter=phot_filter,
                obs_time=Time(datetime.now()) + 300 * u.s + i * 3600 * u.s,
                obs_duration=300 * u.s,
            )
            for i, phot_filter in product(
                range(nobs),
                (
                    "LSST_u",
                    "LSST_g",
                    "LSST_r",
                    "LSST_i",
                    "LSST_y",
                    "LSST_z",
                ),
            )
        ]
        + [
            PhotometricPoint(
                mag=(20.5) * u.ABmag,
                unc=0.0 * u.mag,
                limit=True,
                phot_filter="VT_R",
                obs_time=Time(datetime.now()) + (nobs + 1) * 3600 * u.s,
                obs_duration=300 * u.s,
            )
        ]
        + [
            PhotometricPoint(
                mag=(20.5) * u.ABmag,
                unc=0.0 * u.mag,
                limit=True,
                phot_filter="VT_B",
                obs_time=Time(datetime.now()) + (nobs + 1) * 3600 * u.s,
                obs_duration=300 * u.s,
            )
        ],
        color=(0, 1, 0),
    )
    return candidate


def generate_example_region(data, wcs):
    log.debug("Generating example region")
    num = np.random.uniform()  # random number between 0 and 1
    color = plt.cm.plasma(num)  # Generate unique color for region
    center = get_img_center(data=data, wcs=wcs)
    fov = get_img_fov(data=data, wcs=wcs)
    ra, dec = center.ra, center.dec
    # Add some random noise
    ra = ra + num * fov / 10
    dec = dec + num * fov / 10
    rad = num * fov / 4 + fov / 20

    # _reg = np.random.choice([CircleRegion, QuadrangleRegion])
    _reg = CircleRegion
    region_name = f"Region {10*num:.1f}"
    region = _reg(SkyCoord(ra, dec), rad, name=region_name, color=color)
    return region


def generate_example_table(data, wcs):
    log.debug("Generating example table")
    num = np.random.uniform()
    color = plt.cm.viridis(num)  # Generate unique colors for tables

    center = get_img_center(data=data, wcs=wcs)
    fov = get_img_fov(data=data, wcs=wcs)
    ra, dec = center.ra, center.dec
    # Add some random noise
    ra = ra + num * fov / 4
    dec = dec + num * fov / 4
    table_name = f"Tab {10*num:.1f}"
    data = Table(
        {
            "RA": np.random.normal(ra.to("deg").value, fov.to("deg").value / 10, 10),
            "DEC": np.random.normal(dec.to("deg").value, fov.to("deg").value / 10, 10),
            "Magnitude": np.random.normal(20, 1, 10),
        }
    )

    table = CustomTable(data, name=table_name, color=color)
    return table


def generate_example_image(example_name="vt"):
    """Generate an astronomical image for demonstration."""
    # Galactic center from astropy
    if example_name == "galactic":
        hdu = get_galactic_img()
    elif example_name == "vt":
        hdu = get_vt_img()
    elif example_name == "ps1":
        hdu = get_ps1_img()
    elif example_name == "horse":
        hdu = get_horse_img()
    return hdu


def get_img_center(data, wcs) -> SkyCoord:
    """Get the center of an image."""
    sc = wcs.pixel_to_world(int(data.shape[0]) / 2, int(data.shape[1] / 2))
    sc = sc.transform_to("icrs")
    return sc


def get_img_fov(data, wcs) -> u.Quantity:
    """Get the field of view of an image."""
    corner1 = wcs.pixel_to_world(data.shape[0], data.shape[1])
    corner2 = wcs.pixel_to_world(0, 0)
    return corner1.separation(corner2)


def get_horse_img():
    log.debug("Getting Horsehead image")
    filename = get_pkg_data_filename("tutorials/FITS-images/HorseHead.fits")

    hdu = fits.open(filename)[0]
    return hdu


def get_galactic_img():
    log.debug("Getting galactic image")
    filename = get_pkg_data_filename("galactic_center/gc_msx_e.fits")

    hdu = fits.open(filename)[0]
    return hdu


def get_vt_img():
    log.debug("Getting VT image")
    filename = "~/Downloads/1storb_R_com.fits"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hdu = fits.open(filename)[0]
    return hdu


def get_ps1_img():
    from astropy.utils.data import download_file

    log.debug("Getting PS1 image")

    url = "https://ps1images.stsci.edu/cgi-bin/fitscut.cgi?ra=0.0&dec=0.0&size=264&format=fits&red=/rings.v3.skycell/1232/094/rings.v3.skycell.1232.094.stk.g.unconv.fits"
    url = download_file(url, cache=True, pkgname="zhunter")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hdu = fits.open(url)[0]
    return hdu
